"""Run the full pipeline: clean -> holidays + business days (Task 1) -> analysis (Task 2).

Usage:  python run_pipeline.py            (calls the Nager.Date API)
        python run_pipeline.py --offline  (reuses saved holidays)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import analysis  # noqa: E402
import build_slides  # noqa: E402
import clean  # noqa: E402
import public_holidays  # noqa: E402

if __name__ == "__main__":
    print("== 1/4 Cleaning raw extract"); clean.main()
    print("\n== 2/4 Public holidays and business days"); public_holidays.main()
    print("\n== 3/4 Analysis tables and Power BI model"); analysis.main()
    print("\n== 4/4 Executive summary deck"); build_slides.main()
