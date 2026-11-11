"""Task 1: pull public holidays from Nager.Date and compute business days to close.

Run:  python src/public_holidays.py            (calls the API)
      python src/public_holidays.py --offline  (reuses data/clean/public_holidays.csv)

Steps
  1. Call https://date.nager.at/api/v3/PublicHolidays/{year}/{country} for every office
     country, for 2025 and 2026.
  2. Save the holidays to data/clean/public_holidays.csv, plus outputs/holiday_fetch_log.csv.
  3. Add business_days_to_close to each proposal -> data/clean/proposals_enriched.csv

Business days exclude Saturdays, Sundays and public holidays. A holiday applies to an office
if its type includes "Public" (a day off; observances and optional days are ignored) and it is
national (global=true) or listed for the office's ISO 3166-2 subdivision (e.g. GB-ENG for
London's bank holidays). Countries with no API data are flagged, not fatal: their offices are
counted on weekends only and marked holiday_data_missing=True. If the API fails mid-run, the
saved copy of that country-year is reused (status 'cached') so good data is never overwritten.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from config import CLEAN, OUTPUTS, RAW, YEARS

API = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
HOLIDAYS_CSV = CLEAN / "public_holidays.csv"
FETCH_LOG_CSV = OUTPUTS / "holiday_fetch_log.csv"


def fetch_holidays(country: str, year: int, retries: int = 2, timeout: int = 10) -> tuple[list, str, str]:
    """Return (holidays, status, detail). Never raises: failures come back as a status."""
    url = API.format(year=year, country=country)
    req = urllib.request.Request(url, headers={"User-Agent": "ppk-ops-analytics-case/1.0"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.status == 204 or not body.strip():
                    return [], "no_data", f"HTTP {resp.status}: API has no holidays for {country}"
                data = json.loads(body)
                if not data:
                    return [], "no_data", "HTTP 200 with empty list"
                return data, "ok", f"HTTP {resp.status}"
        except urllib.error.HTTPError as err:
            if err.code == 404:  # unknown country: retrying will not help
                return [], "error", "HTTP 404: country not supported"
            detail = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            detail = f"{type(err).__name__}: {err}"
        if attempt < retries:
            time.sleep(2 ** attempt)
    return [], "error", f"failed after {retries} attempts ({detail})"


def download_all(countries: list[str], cached: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch every country-year. On a network/API error, fall back to the saved copy of that
    country-year (status 'cached') so a bad run never wipes good data; after 3 errors in a row
    the API is treated as unreachable and the remaining calls use the cache straight away."""
    rows, log, kept, errors_in_row = [], [], [], 0
    for country in countries:
        for year in YEARS:
            if errors_in_row >= 3:
                data, status, detail = [], "error", "skipped: API unreachable (3 errors in a row)"
            else:
                data, status, detail = fetch_holidays(country, year)
                errors_in_row = errors_in_row + 1 if status == "error" else 0
            if status == "error" and cached is not None:
                prior = cached[(cached["country_code"] == country) & (cached["year"] == year)]
                if len(prior):
                    kept.append(prior)
                    status, detail = "cached", f"{detail}; using saved copy"
            n = len(data) if status != "cached" else len(kept[-1])
            log.append({"country_code": country, "year": year, "status": status,
                        "holidays_returned": n, "detail": detail})
            print(f"  {country} {year}: {status:<8} {n:>3} holidays  {detail}")
            for h in data:
                rows.append({
                    "country_code": country, "year": year, "date": h["date"], "name": h["name"],
                    "local_name": h.get("localName"), "is_national": bool(h.get("global")),
                    "subdivisions": ";".join(h.get("counties") or []),
                    "types": ";".join(h.get("types") or []),
                })
    holidays = pd.DataFrame(rows, columns=["country_code", "year", "date", "name", "local_name",
                                           "is_national", "subdivisions", "types"])
    if kept:
        holidays = pd.concat([holidays, *kept], ignore_index=True)
    return holidays, pd.DataFrame(log)


def office_holiday_calendar(offices: pd.DataFrame, holidays: pd.DataFrame) -> dict[str, np.ndarray]:
    """Map each office to the holiday dates that apply to it (national + its subdivision)."""
    calendars = {}
    for _, o in offices.iterrows():
        h = holidays[(holidays["country_code"] == o["country_code"])
                     & holidays["types"].fillna("").str.contains("Public")]   # days off only
        sub = o["subdivision_code"]
        applies = h["is_national"] | (h["subdivisions"].fillna("").str.split(";")
                                      .map(lambda subs: bool(sub) and sub in subs))
        calendars[o["office"]] = np.array(sorted(set(h.loc[applies, "date"])), dtype="datetime64[D]")
    return calendars


def _busdays(p: pd.DataFrame, end_col: str, out_col: str, calendars: dict) -> None:
    """Business days in [submitted_date, end_col), i.e. elapsed days, per office calendar."""
    p[out_col] = np.nan
    has_end = p[end_col].notna()
    for office, idx in p[has_end].groupby("office").groups.items():
        start = p.loc[idx, "submitted_date"].values.astype("datetime64[D]")
        end = p.loc[idx, end_col].values.astype("datetime64[D]")
        p.loc[idx, out_col] = np.busday_count(start, end, holidays=calendars[office])


def add_business_days(proposals: pd.DataFrame, calendars: dict, missing: set[str]) -> pd.DataFrame:
    """Add business_days_to_close (the Task 1 column) and business_days_to_review (for the stage
    split), both on the same office holiday calendar so the stages add up."""
    p = proposals.copy()
    _busdays(p, "close_date", "business_days_to_close", calendars)
    _busdays(p, "under_review_date", "business_days_to_review", calendars)
    p["holiday_data_missing"] = p["country_code"].isin(missing)
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="reuse saved holidays CSV")
    args = parser.parse_args()

    if not (CLEAN / "proposals_clean.csv").exists():
        import clean
        clean.main()

    offices = pd.read_csv(RAW / "offices.csv", dtype=str).fillna("")
    countries = sorted(offices["country_code"].unique())

    if args.offline and HOLIDAYS_CSV.exists():
        print(f"Offline: reading {HOLIDAYS_CSV.name}")
        holidays = pd.read_csv(HOLIDAYS_CSV, dtype={"subdivisions": str})
        log = pd.read_csv(FETCH_LOG_CSV)
    else:
        print(f"Fetching holidays for {len(countries)} countries x {len(YEARS)} years")
        cached = pd.read_csv(HOLIDAYS_CSV, dtype={"subdivisions": str}) if HOLIDAYS_CSV.exists() else None
        holidays, log = download_all(countries, cached)
        holidays.to_csv(HOLIDAYS_CSV, index=False)
        log.to_csv(FETCH_LOG_CSV, index=False)

    missing = set(log.loc[~log["status"].isin(["ok", "cached"]), "country_code"])
    if missing:
        print(f"WARNING: no holiday data for {sorted(missing)}; those offices count weekends only "
              "(flagged holiday_data_missing=True)")

    proposals = pd.read_csv(CLEAN / "proposals_clean.csv", dtype={"proposal_id": str},
                            parse_dates=["submitted_date", "close_date", "under_review_date"])
    calendars = office_holiday_calendar(offices, holidays)
    enriched = add_business_days(proposals, calendars, missing)
    enriched.to_csv(CLEAN / "proposals_enriched.csv", index=False, date_format="%Y-%m-%d")

    closed = enriched["business_days_to_close"].notna()
    print(f"Saved {len(holidays)} holidays -> {HOLIDAYS_CSV.relative_to(CLEAN.parents[1])}")
    print(f"Business days added to {closed.sum():,} closed proposals "
          f"(median {enriched.loc[closed, 'business_days_to_close'].median():.0f}) -> "
          "data/clean/proposals_enriched.csv")


if __name__ == "__main__":
    main()
