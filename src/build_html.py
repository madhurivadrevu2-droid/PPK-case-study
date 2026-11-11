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

from analysis import gap_mask as gap_flags
from config import CLEAN, OUTPUTS, REPORTING
from story import NOTES, qa, story_numbers

TEMPLATE = Path(__file__).with_name("presentation_template.html")
STATUS_CODE = {"Won": 1, "Lost": 2, "Withdrawn": 3}


def payload() -> dict:
    p = pd.read_csv(CLEAN / "proposals_enriched.csv", dtype={"proposal_id": str},
                    parse_dates=["submitted_date", "under_review_date", "close_date"])
    offices = pd.read_csv(CLEAN / "offices.csv").fillna("")
    office_list = offices["office"].tolist()
    practice_list = sorted(p["practice"].unique())
    sd = p["submitted_date"]
    bd_review = p["business_days_to_review"].fillna(-1)
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
        "g": gap_flags(p).astype(int).tolist(),
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
    script = REPORTING / "presenter_script.md"
    script.write_text(presenter_script(data["story"]), encoding="utf-8")
    print(f"Saved {script}")
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        for src in (out, script):
            copy = downloads / ("PPK_" + src.name if not src.name.startswith("PPK") else src.name)
            copy.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Copied to {copy}")


PAGES = [("title", "Title"), ("summary", "Executive summary"), ("growth", "Growth"), ("offices", "Office scorecard"),
         ("winrate", "Win rate"), ("speed", "Speed"), ("quality", "Data quality"), ("actions", "Actions"),
         ("appendix", "Appendix: definitions and method")]


def presenter_script(s: dict) -> str:
    lines = ["# Presenter script: PPK proposal performance", "",
             "Open `PPK_Proposal_Performance.html` in Edge or Chrome. Use the arrow keys to move, N for these notes on "
             "screen, F for full screen, and Ctrl+P to save a PDF. About 20 minutes plus questions.", "",
             f"**Headline:** {s['headline']}.", "", "## Talk track", ""]
    for i, (key, title) in enumerate(PAGES, 1):
        lines += [f"### {i}. {title}", "", NOTES[key], ""]
    lines += ["## Live demo moves", "",
              "- Growth page: set Region to India & Middle East, then untick Gap-adjusted to show how the August gap "
              "changes the answer.",
              "- Office scorecard: set Practice to one practice and show that the Paris and India & ME patterns hold.",
              "- Win rate page: point at the overlapping 2025 and 2026 ranges (noise) vs the gap between regions (real).",
              "- Speed page: set Office to Paris, then Period to a single quarter.", "",
              "## Likely questions", ""]
    for q, a in qa():
        lines += [f"**{q}**", "", a, ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
