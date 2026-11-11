"""Task 2 fact base: growth, speed and win-rate tables, plus the Power BI star schema.

Run:  python src/analysis.py   (needs data/clean/proposals_enriched.csv from public_holidays.py)

Metric definitions (also in README):
  Volume       count of proposals submitted
  Value        sum of proposal_value_usd (cleaned)
  Win rate     Won / (Won + Lost); Withdrawn and open proposals excluded
  Won value    sum of value of Won proposals; value win rate = won value / decided value
  Turnaround   business days from submission to first Won/Lost event
  Growth       2026 vs 2025 over the same window: volume/value use 1 Jan - 15 Oct (YTD);
               win rate/turnaround/won value use mature cohorts, submitted 1 Jan - 15 Jul, so
               slow proposals from recent cohorts have had time to close (right-censoring)
  Significance two-proportion z-test on win-rate changes (p < 0.05 = significant)
  Gap-adjusted growth excludes office-months with missing submissions (outputs/submission_gaps.csv)
               in both years, so the comparison stays like-for-like
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from config import CLEAN, OUTPUTS, REPORTING

YTD_END = "10-15"      # extract date: like-for-like volume/value window
MATURE_END = "07-15"   # 90 days before extract: like-for-like win rate/turnaround window


def load() -> pd.DataFrame:
    p = pd.read_csv(CLEAN / "proposals_enriched.csv", dtype={"proposal_id": str},
                    parse_dates=["submitted_date", "close_date", "under_review_date"])
    p["year"] = p["submitted_date"].dt.year
    p["quarter"] = p["submitted_date"].dt.to_period("Q").astype(str)
    p["month"] = p["submitted_date"].dt.to_period("M").astype(str)
    md = p["submitted_date"].dt.strftime("%m-%d")
    p["in_ytd_window"] = md <= YTD_END
    p["in_mature_window"] = md <= MATURE_END
    p["is_decided"] = p["close_status"].isin(["Won", "Lost"])
    p["is_won"] = p["close_status"] == "Won"
    p["bd_to_review"] = p["business_days_to_review"]
    p["bd_review_to_close"] = p["business_days_to_close"] - p["bd_to_review"]
    p["in_submission_gap"] = gap_mask(p)
    return p


def gap_mask(p: pd.DataFrame) -> pd.Series:
    """True for proposals in an office's gap calendar month, in either year (like-for-like)."""
    path = OUTPUTS / "submission_gaps.csv"
    gaps = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["office", "month"])
    mask = pd.Series(False, index=p.index)
    for g in gaps.itertuples():
        mask |= (p["office"] == g.office) & (p["submitted_date"].dt.month == int(str(g.month)[-2:]))
    return mask


def p_value_two_prop(w1: float, n1: float, w2: float, n2: float) -> float:
    """Two-sided p-value of a two-proportion z-test (pooled)."""
    if min(n1, n2) == 0:
        return float("nan")
    pooled = (w1 + w2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("nan")
    z = (w2 / n2 - w1 / n1) / se
    return math.erfc(abs(z) / math.sqrt(2))


def growth_table(p: pd.DataFrame, dim: str | None) -> pd.DataFrame:
    p = p.assign(scope="All PPK")
    key = dim or "scope"
    ytd = p[p["in_ytd_window"]]
    mat = p[p["in_mature_window"] & p["is_decided"]]
    vol = ytd.groupby([key, "year"]).agg(proposals=("proposal_id", "size"),
                                        value_usd=("proposal_value_usd", "sum"))
    mat = mat.assign(won_value=mat["proposal_value_usd"].where(mat["is_won"], 0))
    out = mat.groupby([key, "year"]).agg(decided=("proposal_id", "size"), won=("is_won", "sum"),
                                        won_value_usd=("won_value", "sum"),
                                        decided_value_usd=("proposal_value_usd", "sum"),
                                        median_bd_to_close=("business_days_to_close", "median"),
                                        mean_bd_to_close=("business_days_to_close", "mean"))
    t = vol.join(out).unstack("year")
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    for y in (2025, 2026):
        t[f"win_rate_{y}"] = t[f"won_{y}"] / t[f"decided_{y}"] * 100
        t[f"value_win_rate_{y}"] = t[f"won_value_usd_{y}"] / t[f"decided_value_usd_{y}"] * 100
    t["volume_growth_pct"] = (t["proposals_2026"] / t["proposals_2025"] - 1) * 100
    t["value_growth_pct"] = (t["value_usd_2026"] / t["value_usd_2025"] - 1) * 100
    t["won_value_growth_pct"] = (t["won_value_usd_2026"] / t["won_value_usd_2025"] - 1) * 100
    t["win_rate_change_pp"] = t["win_rate_2026"] - t["win_rate_2025"]
    t["win_rate_p_value"] = [p_value_two_prop(r.won_2025, r.decided_2025, r.won_2026, r.decided_2026)
                             for r in t.itertuples()]
    t["win_rate_change_significant"] = t["win_rate_p_value"] < 0.05
    t["median_bd_change"] = t["median_bd_to_close_2026"] - t["median_bd_to_close_2025"]
    t.index.name = key
    p_col = t.pop("win_rate_p_value").round(3)
    t = t.round(1)
    t["win_rate_p_value"] = p_col
    return t.sort_values("volume_growth_pct", ascending=False)


def win_rate_gap_by_region(p: pd.DataFrame) -> pd.DataFrame:
    """Each region's 2026 mature-cohort win rate vs the rest of PPK, with a z-test."""
    d = p[p["in_mature_window"] & p["is_decided"] & (p["year"] == 2026)]
    rows = []
    for r, g in d.groupby("region"):
        rest = d[d["region"] != r]
        rows.append({"region": r, "decided": len(g), "win_rate": g["is_won"].mean() * 100,
                     "rest_win_rate": rest["is_won"].mean() * 100,
                     "gap_pp": (g["is_won"].mean() - rest["is_won"].mean()) * 100,
                     "p_value": p_value_two_prop(rest["is_won"].sum(), len(rest), g["is_won"].sum(), len(g))})
    return pd.DataFrame(rows).set_index("region").round(4)


def quarterly_trend(p: pd.DataFrame) -> pd.DataFrame:
    d = p[p["is_decided"]]
    q = d.groupby("quarter").agg(decided=("proposal_id", "size"), win_rate=("is_won", "mean"),
                                 median_bd=("business_days_to_close", "median"),
                                 mean_bd=("business_days_to_close", "mean"),
                                 p90_bd=("business_days_to_close", lambda s: s.quantile(0.9)))
    q = q.join(p.groupby("quarter").agg(submitted=("proposal_id", "size"), still_open=("is_open", "sum")))
    q["share_still_open_pct"] = q["still_open"] / q["submitted"] * 100
    q["win_rate"] *= 100
    return q.round(1)


def quarterly_yoy(p: pd.DataFrame) -> pd.DataFrame:
    """Year-on-year volume growth per complete quarter, as reported and gap-adjusted."""
    out = []
    for q in (1, 2, 3):
        sel = p[p["submitted_date"].dt.quarter == q]
        adj = sel[~sel["in_submission_gap"]]
        n = sel.groupby("year").size()
        na = adj.groupby("year").size()
        out.append({"quarter": f"Q{q}", "proposals_2025": n.get(2025), "proposals_2026": n.get(2026),
                    "yoy_pct": (n.get(2026) / n.get(2025) - 1) * 100,
                    "yoy_gap_adjusted_pct": (na.get(2026) / na.get(2025) - 1) * 100})
    return pd.DataFrame(out).set_index("quarter").round(1)


def stage_by_office(p: pd.DataFrame) -> pd.DataFrame:
    d = p[p["is_decided"]]
    t = d.groupby("office")[["bd_to_review", "bd_review_to_close", "business_days_to_close"]].median()
    t["median_bd_no_review"] = d[d["bd_to_review"].isna()].groupby("office")["business_days_to_close"].median()
    t["share_over_30_bd_pct"] = d.groupby("office")["business_days_to_close"].apply(lambda s: (s > 30).mean() * 100)
    t["decided"] = d.groupby("office").size()
    return t.round(1).sort_values("business_days_to_close", ascending=False)


def pipeline_at_extract(p: pd.DataFrame) -> pd.DataFrame:
    """Open proposals at extract and expected won value (region value win rate x (1 - withdrawal rate))."""
    closed = p[p["close_status"].notna()]
    withdraw = (closed["close_status"] == "Withdrawn").groupby(closed["region"]).mean()
    d = p[p["is_decided"]]
    vwr = (d["proposal_value_usd"].where(d["is_won"], 0).groupby(d["region"]).sum()
           / d.groupby("region")["proposal_value_usd"].sum())
    o = p[p["is_open"]]
    t = o.groupby("region").agg(open_proposals=("proposal_id", "size"), open_value_usd=("proposal_value_usd", "sum"),
                                stale=("is_stale", "sum"))
    t["expected_won_value_usd"] = t["open_value_usd"] * vwr * (1 - withdraw)
    t.loc["All PPK"] = t.sum()
    return t.round(0)


def office_quarter_volume(p: pd.DataFrame) -> pd.DataFrame:
    return p.pivot_table(index="office", columns="quarter", values="proposal_id", aggfunc="size")


def office_month_volume(p: pd.DataFrame) -> pd.DataFrame:
    return p.pivot_table(index="office", columns="month", values="proposal_id", aggfunc="size", fill_value=0)


def write_powerbi_model(p: pd.DataFrame) -> None:
    """Star schema for Power BI: one fact, three dimensions, holidays for reference."""
    out = REPORTING / "powerbi_model"
    out.mkdir(parents=True, exist_ok=True)
    fact_cols = ["proposal_id", "submitted_date", "office", "practice", "client_name",
                 "proposal_value_usd", "value_flag", "current_status", "close_status", "close_date",
                 "is_open", "is_stale", "is_decided", "is_won", "business_days_to_close",
                 "bd_to_review", "bd_review_to_close", "calendar_days_to_close",
                 "holiday_data_missing", "in_ytd_window", "in_mature_window", "in_submission_gap"]
    p[fact_cols].to_csv(out / "fact_proposals.csv", index=False, date_format="%Y-%m-%d")
    pd.read_csv(CLEAN / "status_events_clean.csv", dtype={"proposal_id": str}).to_csv(
        out / "fact_status_events.csv", index=False)
    pd.read_csv(CLEAN / "offices.csv").to_csv(out / "dim_office.csv", index=False)
    pd.DataFrame({"practice": sorted(p["practice"].unique())}).to_csv(out / "dim_practice.csv", index=False)
    dates = pd.date_range("2025-01-01", "2026-12-31", freq="D")
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "year": dates.year,
                  "quarter": dates.to_period("Q").astype(str), "month": dates.strftime("%Y-%m"),
                  "quarter_of_year": "Q" + dates.quarter.astype(str),
                  "month_num": dates.month, "month_name": dates.strftime("%b"),
                  "month_day": dates.strftime("%m-%d"),
                  "is_ytd_window": dates.strftime("%m-%d") <= YTD_END,
                  "is_mature_window": dates.strftime("%m-%d") <= MATURE_END}
                 ).to_csv(out / "dim_date.csv", index=False)
    pd.read_csv(CLEAN / "public_holidays.csv").to_csv(out / "ref_public_holidays.csv", index=False)
    issues = pd.read_csv(OUTPUTS / "data_issues_log.csv")
    issues.insert(0, "issue_no", range(1, len(issues) + 1))
    issues.to_csv(out / "ref_data_issues.csv", index=False)
    pd.read_csv(OUTPUTS / "holiday_fetch_log.csv").to_csv(out / "ref_holiday_fetch.csv", index=False)


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    p = load()
    adj = p[~p["in_submission_gap"]]
    tables = {
        "growth_total": growth_table(p, None),
        "growth_by_region": growth_table(p, "region"),
        "growth_by_practice": growth_table(p, "practice"),
        "growth_by_office": growth_table(p, "office"),
        "growth_total_gap_adjusted": growth_table(adj, None),
        "growth_by_region_gap_adjusted": growth_table(adj, "region"),
        "growth_by_office_gap_adjusted": growth_table(adj, "office"),
        "growth_by_practice_gap_adjusted": growth_table(adj, "practice"),
        "win_rate_gap_by_region": win_rate_gap_by_region(p),
        "trend_by_quarter": quarterly_trend(p),
        "quarterly_yoy": quarterly_yoy(p),
        "turnaround_stage_by_office": stage_by_office(p),
        "pipeline_at_extract": pipeline_at_extract(p),
        "volume_by_office_quarter": office_quarter_volume(p),
        "volume_by_office_month": office_month_volume(p),
    }
    for name, t in tables.items():
        t.to_csv(OUTPUTS / f"{name}.csv")
    write_powerbi_model(p)

    g, ga = tables["growth_total"].iloc[0], tables["growth_total_gap_adjusted"].iloc[0]
    print(f"YTD volume {g.proposals_2025:,.0f} -> {g.proposals_2026:,.0f} ({g.volume_growth_pct:+.1f}%, "
          f"gap-adjusted {ga.volume_growth_pct:+.1f}%), value {g.value_growth_pct:+.1f}%, won value "
          f"{g.won_value_growth_pct:+.1f}%, win rate {g.win_rate_2025:.1f}% -> {g.win_rate_2026:.1f}% "
          f"(p={g.win_rate_p_value:.2f}), median turnaround {g.median_bd_to_close_2025:.0f} -> "
          f"{g.median_bd_to_close_2026:.0f} bd")
    print(tables["growth_by_region"][["volume_growth_pct", "value_growth_pct", "win_rate_2026",
                                       "win_rate_change_pp", "win_rate_p_value"]].to_string())
    print(f"Wrote {len(tables)} tables to outputs/ and Power BI model to reporting/powerbi_model/")


if __name__ == "__main__":
    main()
