"""Clean the raw proposal-system extract and log every data issue found.

Run:  python src/clean.py
Writes:
  data/clean/proposals_clean.csv      one row per real proposal, with status/decision fields
  data/clean/status_events_clean.csv  one row per status change, joined-safe IDs
  data/clean/offices.csv              office dimension
  outputs/data_issues_log.csv         issue, rows affected, impact, treatment
"""
from __future__ import annotations

import pandas as pd

from config import (CLEAN, CLOSED_STATUSES, DATE_FORMATS, EXTRACT_DATE, OUTPUTS,
                    PRACTICE_ALIASES, PRACTICES, RAW, TEST_CLIENT_PATTERN, VALUE_THOUSANDS_BELOW,
                    VALUE_TYPO_ABOVE)

ISSUES: list[dict] = []


def log_issue(issue: str, rows: int, impact: str, treatment: str, short: str = "") -> None:
    ISSUES.append({"short": short or issue, "issue": issue, "rows_affected": int(rows), "impact": impact,
                   "treatment": treatment})
    print(f"  [{rows:>6}] {issue}")


def parse_date(value: str) -> pd.Timestamp:
    """Parse a date in any of the known formats; NaT if none match."""
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(value, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def normalise_label(series: pd.Series, canonical: list[str], aliases: dict | None = None) -> pd.Series:
    """Map messy labels (case, whitespace) onto a canonical list."""
    lookup = {c.lower(): c for c in canonical}
    lookup.update(aliases or {})
    return series.str.strip().str.lower().map(lookup)


def clean_proposals(offices: pd.DataFrame) -> pd.DataFrame:
    p = pd.read_csv(RAW / "proposals.csv", dtype=str)
    print(f"proposals.csv: {len(p):,} rows")

    dupes = p.duplicated()
    log_issue("Exact duplicate proposal rows", dupes.sum(),
              "Inflates volume and value", "Dropped duplicates, kept first", short="Duplicate rows")
    p = p[~dupes].copy()

    test = p["proposal_id"].str.startswith("ZZ") | p["client_name"].str.contains(TEST_CLIENT_PATTERN)
    log_issue("Test / dummy records (ZZ IDs, clients like 'TEST CLIENT', 'Dummy Co')", test.sum(),
              "Fake round values (USD 1-5M) inflate value", "Excluded from clean data",
              short="Test / dummy records")
    p = p[~test].copy()

    # Dates
    fmt_counts = {
        "dd/mm/yyyy": p["submitted_date"].str.fullmatch(r"\d{2}/\d{2}/\d{4}").sum(),
        "dd Mon yyyy": p["submitted_date"].str.fullmatch(r"\d{2} [A-Za-z]{3} \d{4}").sum(),
    }
    p["submitted_date"] = p["submitted_date"].map(parse_date)
    log_issue(f"Mixed date formats in submitted_date ({fmt_counts['dd/mm/yyyy']} dd/mm/yyyy, "
              f"{fmt_counts['dd Mon yyyy']} 'dd Mon yyyy')", sum(fmt_counts.values()),
              "Naive parsing misreads or drops ~35% of dates",
              "Parsed each format explicitly; slash dates are day-first (first part >12 in 3,400+ rows, "
              "second part never >12)", short="Mixed date formats")
    bad_dates = p["submitted_date"].isna().sum()
    if bad_dates:
        log_issue("Unparseable submitted_date", bad_dates, "Cannot place in period", "Excluded")
        p = p[p["submitted_date"].notna()]

    # Office
    canon_offices = offices["office"].tolist()
    messy = ~p["office"].isin(canon_offices)
    p["office"] = normalise_label(p["office"], canon_offices)
    log_issue("Office names with inconsistent case / stray whitespace", messy.sum(),
              "Splits one office into up to 5 labels", "Trimmed and case-matched to offices.csv", short="Office name variants")
    assert p["office"].notna().all(), "Unmapped office found"

    # Practice
    renamed = p["practice"].str.strip().str.lower().isin(PRACTICE_ALIASES)
    messy = ~p["practice"].isin(PRACTICES) & ~renamed
    p["practice"] = normalise_label(p["practice"], PRACTICES, PRACTICE_ALIASES)
    log_issue("Practice names with inconsistent case / stray whitespace", messy.sum(),
              "Splits one practice into several labels", "Trimmed and case-matched",
              short="Practice name variants")
    log_issue("Practice renamed: 'Customer Strategy & Marketing' (2025) -> 'Customer' (from Jan 2026)",
              renamed.sum(),
              "Without merging, one practice looks like it vanished and a new one appeared",
              "Merged under 'Customer Strategy & Marketing' to keep 11 practices comparable",
              short="Practice renamed in 2026")
    assert p["practice"].notna().all(), "Unmapped practice found"

    # Value
    v = p["proposal_value_usd"].astype(float)
    in_thousands = v < VALUE_THOUSANDS_BELOW
    typo = v > VALUE_TYPO_ABOVE
    p["value_flag"] = "ok"
    p.loc[in_thousands, "value_flag"] = "rescaled_x1000"
    p.loc[typo, "value_flag"] = "rescaled_div1000"
    p["proposal_value_usd_raw"] = v
    p["proposal_value_usd"] = v.where(~in_thousands, v * 1000).where(~typo, v / 1000)
    log_issue("Values entered in USD thousands (USD 30 - 2,000 vs median ~USD 244K; empty gap "
              "between 2K and 30K)", in_thousands.sum(),
              "Understates value and distorts averages", "Multiplied by 1,000; flagged in value_flag",
              short="Values keyed in thousands")
    log_issue("Extreme value outlier (USD 1.5B, ~3,700x median; 1000x keying error)", typo.sum(),
              "Single row would be ~25% of total 2025 value", "Divided by 1,000 (USD 1.5M); flagged in value_flag",
              short="USD 1.5B keying error")

    p["client_name"] = p["client_name"].str.strip()
    return p


def clean_events(valid_ids: pd.Index) -> pd.DataFrame:
    e = pd.read_csv(RAW / "status_events.csv", dtype=str)
    print(f"status_events.csv: {len(e):,} rows")

    unpadded = e["proposal_id"].str.len() < 7
    log_issue("proposal_id lost leading zeros in status_events (e.g. '10131' vs '0010131')",
              unpadded.sum(), "A string join matches ~0% of events to proposals",
              "Zero-padded to 7 characters before joining", short="IDs lost leading zeros")
    e["proposal_id"] = e["proposal_id"].str.zfill(7)
    e["status"] = e["status"].str.strip()
    e["event_date"] = pd.to_datetime(e["event_date"], format="%Y-%m-%d")

    orphan = ~e["proposal_id"].isin(valid_ids)
    log_issue("Status events with no matching clean proposal (test records)", orphan.sum(),
              "Would add phantom outcomes", "Excluded", short="Orphan status events")
    e = e[~orphan].copy()
    return e.sort_values(["proposal_id", "event_date"])


def add_outcomes(p: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Attach current status, closing status and closing date to each proposal."""
    closed = (e[e["status"].isin(CLOSED_STATUSES)]
              .groupby("proposal_id").first()
              .rename(columns={"status": "close_status", "event_date": "close_date"}))
    latest = e.groupby("proposal_id")["status"].last().rename("current_status")
    review = (e[e["status"] == "Under Review"].groupby("proposal_id")["event_date"].first()
              .rename("under_review_date"))
    p = (p.set_index("proposal_id").join([latest, review, closed[["close_status", "close_date"]]])
         .reset_index())

    p["is_open"] = p["close_status"].isna()
    p["days_open_at_extract"] = (pd.Timestamp(EXTRACT_DATE) - p["submitted_date"]).dt.days.where(p["is_open"])
    p["calendar_days_to_close"] = (p["close_date"] - p["submitted_date"]).dt.days
    stale = p["is_open"] & (p["days_open_at_extract"] > 90)
    log_issue("Open proposals with no status change for >90 days (likely stale, never closed)",
              stale.sum(), "Pipeline overstated; true win/loss unknown",
              "Kept as open; excluded from win rate and turnaround; flagged is_stale",
              short="Stale open proposals")
    p["is_stale"] = stale

    recent_open = p["is_open"] & (p["submitted_date"] >= pd.Timestamp(EXTRACT_DATE) - pd.Timedelta(days=90))
    log_issue("Right-censoring: recent proposals still open at extract (Jul-Oct 2026 cohorts)",
              recent_open.sum(),
              "Recent cohorts only contain fast decisions, so turnaround looks better than it is",
              "Turnaround trends use mature cohorts only (submitted on/before 2026-07-15, "
              ">=90 days before extract; slowest decision observed is 161 days)",
              short="Recent cohorts not yet closed")
    return p


def detect_submission_gaps(p: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Find office-months with zero submissions while the office's other proposals kept
    changing status: the system was live, so missing submissions point to an extract gap."""
    months = pd.period_range("2025-01", pd.Timestamp(EXTRACT_DATE).to_period("M") - 1, freq="M")
    counts = (p.assign(m=p["submitted_date"].dt.to_period("M"))
              .pivot_table(index="office", columns="m", values="proposal_id", aggfunc="size", fill_value=0)
              .reindex(columns=months, fill_value=0))
    office_of = p.set_index("proposal_id")["office"]
    ev = e.assign(office=e["proposal_id"].map(office_of), m=e["event_date"].dt.to_period("M"))
    rows = []
    is_zero = (counts == 0).stack()
    for office, m in is_zero[is_zero].index:
        same_month_py = counts.loc[office, m - 12] if (m - 12) in counts.columns else None
        other = counts.loc[office].drop(m)
        rows.append({"office": office, "month": str(m), "submissions": 0,
                     "submissions_same_month_prior_year": same_month_py,
                     "office_median_month": float(other.median()),
                     "status_events_that_month": int(((ev["office"] == office) & (ev["m"] == m)).sum())})
    gaps = pd.DataFrame(rows, columns=["office", "month", "submissions", "submissions_same_month_prior_year",
                                       "office_median_month", "status_events_that_month"])
    if len(gaps):
        desc = ", ".join(f"{r.office} {r.month}" for r in gaps.itertuples())
        log_issue(f"Missing submissions: zero proposals in {desc} while the system kept logging "
                  f"status changes ({int(gaps.status_events_that_month.sum())} events)",
                  int(gaps["office_median_month"].sum()),
                  "Understates those offices' volume (Dubai Q3 looks -42%; India & ME looks flat)",
                  "Kept as received (cannot impute rows); growth also reported gap-adjusted, excluding "
                  "that month in both years for those offices; confirm with the offices",
                  short="Missing Gulf submissions, Aug 2026")
    gaps.to_csv(OUTPUTS / "submission_gaps.csv", index=False)
    return gaps


def main() -> None:
    ISSUES.clear()
    CLEAN.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    offices = pd.read_csv(RAW / "offices.csv", dtype=str).fillna("")

    proposals = clean_proposals(offices)
    events = clean_events(pd.Index(proposals["proposal_id"]))
    proposals = add_outcomes(proposals, events)
    detect_submission_gaps(proposals, events)

    proposals = proposals.merge(offices[["office", "country", "country_code", "region"]], on="office")
    cols = ["proposal_id", "submitted_date", "office", "country", "country_code", "region",
            "practice", "client_name", "proposal_value_usd", "proposal_value_usd_raw", "value_flag",
            "current_status", "under_review_date", "close_status", "close_date", "is_open",
            "is_stale", "days_open_at_extract", "calendar_days_to_close"]
    proposals[cols].to_csv(CLEAN / "proposals_clean.csv", index=False, date_format="%Y-%m-%d")
    events.to_csv(CLEAN / "status_events_clean.csv", index=False, date_format="%Y-%m-%d")
    offices.to_csv(CLEAN / "offices.csv", index=False)
    pd.DataFrame(ISSUES).to_csv(OUTPUTS / "data_issues_log.csv", index=False)
    print(f"Clean proposals: {len(proposals):,} | events: {len(events):,} | issues logged: {len(ISSUES)}")


if __name__ == "__main__":
    main()
