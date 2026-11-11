"""Run the full pipeline: clean -> holidays + business days (Task 1) -> analysis -> deck -> HTML.

Usage:  python run_pipeline.py            (calls the Nager.Date API)
        python run_pipeline.py --offline  (reuses saved holidays)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import analysis  # noqa: E402
import build_html  # noqa: E402
import build_powerbi  # noqa: E402
import build_slides  # noqa: E402
import clean  # noqa: E402
import public_holidays  # noqa: E402

if __name__ == "__main__":
    print("== 1/6 Cleaning raw extract"); clean.main()
    print("\n== 2/6 Public holidays and business days"); public_holidays.main()
    print("\n== 3/6 Analysis tables and Power BI model data"); analysis.main()
    print("\n== 4/6 Executive summary deck"); build_slides.main()
    print("\n== 5/6 HTML presentation"); build_html.main()
    print("\n== 6/6 Power BI project"); build_powerbi.main()
