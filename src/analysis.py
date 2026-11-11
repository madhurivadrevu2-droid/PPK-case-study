"""Task 2 fact base: growth, speed and win-rate tables, plus the Power BI star schema.

Run:  python src/analysis.py   (needs data/clean/proposals_enriched.csv from public_holidays.py)

Metric definitions (also in README):
  Volume       count of proposals submitted
  Value        sum of proposal_value_usd (cleaned)
  Win rate     Won / (Won + Lost); Withdrawn and open proposals excluded
  Turnaround   business days from submission to first Won/Lost event
  Growth       2026 vs 2025 over the same window: volume/value use 1 Jan - 15 Oct (YTD);
               win rate/turnaround use mature cohorts, submitted 1 Jan - 15 Jul, so slow
               proposals from recent cohorts have had time to close (right-censoring)
"""
from __future__ import annotations

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
    md = p["submitted_date"].dt.strftime("%m-%d")
    p["in_ytd_window"] = md <= YTD_END
    p["in_mature_window"] = md <= MATURE_END
    p["is_decided"] = p["close_status"].isin(["Won", "Lost"])
    p["is_won"] = p["close_status"] == "Won"
    review = p["under_review_date"].notna()
    p["bd_to_review"] = np.nan
    p.loc[review, "bd_to_review"] = np.busday_count(
        p.loc[review, "submitted_date"].values.astype("datetime64[D]"),
        p.loc[review, "under_review_date"].values.astype("datetime64[D]"))
    p["bd_review_to_close"] = p["business_days_to_close"] - p["bd_to_review"]
    return p


def growth_table(p: pd.DataFrame, dim: str | None) -> pd.DataFrame:
    keys = [dim] if dim else []
    ytd = p[p["in_ytd_window"]]
    mat = p[p["in_mature_window"] & p["is_decided"]]
    vol = ytd.groupby(keys + ["year"]).agg(proposals=("proposal_id", "size"),
                                          value_usd=("proposal_value_usd", "sum"))
    out = mat.groupby(keys + ["year"]).agg(win_rate=("is_won", "mean"),
                                          median_bd_to_close=("business_days_to_close", "median"),
                                          mean_bd_to_close=("business_days_to_close", "mean"))
    t = vol.join(out).unstack("year") if dim else vol.join(out).T
    if not dim:
        t = t.T.unstack().to_frame().T
        t.index = ["All PPK"]
    t.columns = [f"{m}_{y}" for m, y in t.columns]
    t["volume_growth_pct"] = (t["proposals_2026"] / t["proposals_2025"] - 1) * 100
    t["value_growth_pct"] = (t["value_usd_2026"] / t["value_usd_2025"] - 1) * 100
    t["win_rate_change_pp"] = (t["win_rate_2026"] - t["win_rate_2025"]) * 100
    t["median_bd_change"] = t["median_bd_to_close_2026"] - t["median_bd_to_close_2025"]
    for c in ("win_rate_2025", "win_rate_2026"):
        t[c] = t[c] * 100
    t.index.name = dim or "scope"
    return t.round(1).sort_values("volume_growth_pct", ascending=False)


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


def stage_by_office(p: pd.DataFrame) -> pd.DataFrame:
    d = p[p["is_decided"]]
    return (d.groupby("office")[["bd_to_review", "bd_review_to_close", "business_days_to_close"]]
            .median().sort_values("business_days_to_close", ascending=False))


def office_quarter_volume(p: pd.DataFrame) -> pd.DataFrame:
    return p.pivot_table(index="office", columns="quarter", values="proposal_id", aggfunc="size")


def write_powerbi_model(p: pd.DataFrame) -> None:
    """Star schema for Power BI: one fact, three dimensions, holidays for reference."""
    out = REPORTING / "powerbi_model"
    out.mkdir(parents=True, exist_ok=True)
    fact_cols = ["proposal_id", "submitted_date", "office", "practice", "client_name",
                 "proposal_value_usd", "value_flag", "current_status", "close_status", "close_date",
                 "is_open", "is_stale", "is_decided", "is_won", "business_days_to_close",
                 "bd_to_review", "bd_review_to_close", "calendar_days_to_close",
                 "holiday_data_missing", "in_ytd_window", "in_mature_window"]
    p[fact_cols].to_csv(out / "fact_proposals.csv", index=False, date_format="%Y-%m-%d")
    pd.read_csv(CLEAN / "status_events_clean.csv", dtype={"proposal_id": str}).to_csv(
        out / "fact_status_events.csv", index=False)
    pd.read_csv(CLEAN / "offices.csv").to_csv(out / "dim_office.csv", index=False)
    pd.DataFrame({"practice": sorted(p["practice"].unique())}).to_csv(out / "dim_practice.csv", index=False)
    dates = pd.date_range("2025-01-01", "2026-12-31", freq="D")
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "year": dates.year,
                  "quarter": dates.to_period("Q").astype(str), "month": dates.strftime("%Y-%m"),
                  "month_day": dates.strftime("%m-%d"),
                  "is_ytd_window": dates.strftime("%m-%d") <= YTD_END,
                  "is_mature_window": dates.strftime("%m-%d") <= MATURE_END}
                 ).to_csv(out / "dim_date.csv", index=False)
    pd.read_csv(CLEAN / "public_holidays.csv").to_csv(out / "ref_public_holidays.csv", index=False)


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    p = load()
    tables = {
        "growth_total": growth_table(p, None),
        "growth_by_region": growth_table(p, "region"),
        "growth_by_practice": growth_table(p, "practice"),
        "growth_by_office": growth_table(p, "office"),
        "trend_by_quarter": quarterly_trend(p),
        "turnaround_stage_by_office": stage_by_office(p),
        "volume_by_office_quarter": office_quarter_volume(p),
    }
    for name, t in tables.items():
        t.to_csv(OUTPUTS / f"{name}.csv")
    write_powerbi_model(p)

    g = tables["growth_total"].iloc[0]
    print(f"YTD volume {g.proposals_2025:,.0f} -> {g.proposals_2026:,.0f} ({g.volume_growth_pct:+.1f}%), "
          f"value {g.value_growth_pct:+.1f}%, win rate {g.win_rate_2025:.1f}% -> {g.win_rate_2026:.1f}%, "
          f"median turnaround {g.median_bd_to_close_2025:.0f} -> {g.median_bd_to_close_2026:.0f} bd")
    print(tables["growth_by_region"][["volume_growth_pct", "value_growth_pct", "win_rate_2026",
                                       "win_rate_change_pp"]].to_string())
    print(f"Wrote {len(tables)} tables to outputs/ and Power BI model to reporting/powerbi_model/")


if __name__ == "__main__":
    main()
