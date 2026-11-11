"""Build a self-contained HTML presentation + interactive dashboard from the clean data.

Run:  python src/build_html.py   ->  reporting/PPK_Proposal_Performance.html
Open in any browser (no internet needed). Arrow keys / buttons move between pages,
N toggles the speaker notes, F toggles full screen. Dashboard pages filter live by
region, office, practice and period; every number is computed from the embedded data.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import CLEAN, OUTPUTS, REPORTING
from story import NOTES, story_numbers

TEMPLATE = Path(__file__).with_name("presentation_template.html")
STATUS_CODE = {"Won": 1, "Lost": 2, "Withdrawn": 3}


def payload() -> dict:
    p = pd.read_csv(CLEAN / "proposals_enriched.csv", dtype={"proposal_id": str},
                    parse_dates=["submitted_date", "under_review_date", "close_date"])
    offices = pd.read_csv(CLEAN / "offices.csv").fillna("")
    office_list = offices["office"].tolist()
    practice_list = sorted(p["practice"].unique())
    sd = p["submitted_date"]
    review = p["under_review_date"]
    bd_review = pd.Series(-1, index=p.index)
    has = review.notna()
    import numpy as np
    bd_review[has] = np.busday_count(sd[has].values.astype("datetime64[D]"),
                                     review[has].values.astype("datetime64[D]"))
    cols = {
        "y": (sd.dt.year - 2025).tolist(),
        "md": (sd.dt.month * 100 + sd.dt.day).tolist(),
        "m": ((sd.dt.year - 2025) * 12 + sd.dt.month - 1).tolist(),
        "o": p["office"].map({o: i for i, o in enumerate(office_list)}).tolist(),
        "p": p["practice"].map({x: i for i, x in enumerate(practice_list)}).tolist(),
        "v": p["proposal_value_usd"].round().astype(int).tolist(),
        "s": p["close_status"].map(STATUS_CODE).fillna(0).astype(int).tolist(),
        "b": p["business_days_to_close"].fillna(-1).astype(int).tolist(),
        "r": bd_review.astype(int).tolist(),
    }
    issues = pd.read_csv(OUTPUTS / "data_issues_log.csv").to_dict("records")
    fetch = pd.read_csv(OUTPUTS / "holiday_fetch_log.csv")
    holidays = (fetch.groupby("country_code")
                .agg(status=("status", "first"), holidays=("holidays_returned", "sum")).reset_index())
    holidays = holidays.merge(offices.groupby("country_code")["office"].apply(", ".join).reset_index(),
                              on="country_code").to_dict("records")
    return {
        "offices": [{"name": r.office, "region": r.region, "country": r.country}
                    for r in offices.itertuples()],
        "practices": practice_list,
        "regions": sorted(offices["region"].unique()),
        "cols": cols,
        "issues": issues,
        "holidays": holidays,
    }


def main() -> None:
    REPORTING.mkdir(parents=True, exist_ok=True)
    data = payload()
    data["story"] = story_numbers()
    data["notes"] = NOTES
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(data, separators=(",", ":"), default=str))
    out = REPORTING / "PPK_Proposal_Performance.html"
    out.write_text(html, encoding="utf-8")
    print(f"Saved {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
