# PPK Operations analytics case: proposal performance fact base

A fact base on proposal performance across 14 offices and 11 practices, using proposals submitted
from 1 Jan 2025 to the 15 Oct 2026 extract. It contains:
- **Task 1:** a Python script that pulls public holidays from the Nager.Date API and adds business days to decision
- **Task 2:** clean data, a Power BI model, an executive summary and a log of data issues

## Headline findings

1. **Growth.** Volume is up **+10.6%** and value **+10.4%**, comparing the same 1 Jan to 15 Oct window each year. Win rate rose from **40.3% to 41.6%**.
   - **By region:** the Americas (+14.5%) and APAC (+14.2%) lead. India & Middle East is flat (−1.2%), because Dubai volume fell 42% in Q3 2026.
   - **By practice:** Performance Improvement, TMT and Strategy lead (+15–16%). Energy & Natural Resources and M&A have flat volume but higher win rates (+8pp and +4pp).
2. **Speed.** The median is **17 business days**, the same as 2025. Paris is the outlier at **23 days**, and the whole gap sits in the review-to-decision stage (20 days against 13 elsewhere), in every practice and quarter.
   - The apparent Q3 2026 speed-up comes from unclosed slow proposals, not from a real improvement. See issue 12 below.
3. **Data quality.** I found 12 issues in the source data, plus 1 gap in the holiday API, and treated each one (log below). The key traps:
   - IDs lost their leading zeros, so a naive join matches nothing.
   - The "Customer Strategy & Marketing" practice was renamed "Customer" in 2026.
   - Some values were entered in thousands.
   - One value is a 1000× typo of $1.5B.
4. **Actions.**
   1. Put FY27 proposal capacity where growth is.
   2. Fix the Paris review stage and the Dubai pipeline.
   3. Fix data at source and automate this fact base.

## How to run

```bash
pip install -r requirements.txt
python run_pipeline.py            # clean -> holidays + business days -> analysis -> deck
python run_pipeline.py --offline  # same, reusing saved holidays (no API call)
```

You can also run each step on its own:

| Step | Command | Outputs |
|---|---|---|
| Clean | `python src/clean.py` | `data/clean/proposals_clean.csv`, `status_events_clean.csv`, `outputs/data_issues_log.csv` |
| **Task 1** | `python src/public_holidays.py` | `data/clean/public_holidays.csv`, `outputs/holiday_fetch_log.csv`, `data/clean/proposals_enriched.csv` |
| Analysis | `python src/analysis.py` | `outputs/*.csv`, `reporting/powerbi_model/*.csv` |
| Deck | `python src/build_slides.py` | `reporting/PPK_Executive_Summary.pptx` |

`public_holidays.py` runs the cleaning step itself if the clean file is missing, so Task 1 is also a single command. You need Python 3.10+; I tested with 3.12, pandas 3.0 and numpy 2.5.

## Repository structure

```
run_pipeline.py          one command for the whole pipeline
src/                     config, clean, public_holidays (Task 1), analysis, build_slides
data/raw/                extract as received (unchanged)
data/clean/              cleaned proposals, events, holidays, proposals with business days
outputs/                 data issues log, holiday fetch log, analysis tables
reporting/               executive summary .pptx, Power BI model CSVs, DAX measures, theme, build guide
```

## Task 1: holidays and business days

- **API.** The script calls `GET https://date.nager.at/api/v3/PublicHolidays/{year}/{countryCode}` for each of the 12 office countries, for 2025 and 2026. It uses Python's standard `urllib`, a 15-second timeout, and 3 retries with exponential backoff.
- **No data is not an error.** India (IN), the UAE (AE) and Saudi Arabia (SA) return **HTTP 204 (no content)**. These are logged as `no_data` in `outputs/holiday_fetch_log.csv`, and the script prints a warning and carries on.
  - Proposals from those offices are counted on weekends only and flagged `holiday_data_missing = True`. That's 3,504 proposals, 14.4%.
- **Regional holidays.** A holiday applies to an office if it is national (`global = true`) or if its `counties` list includes the office's ISO 3166-2 code from `offices.csv`. For example, New York gets Lincoln's Birthday (`US-NY`) and London gets England's bank holidays (`GB-ENG`).
  - Using national holidays only would give London almost no holidays, because Nager tags UK bank holidays by nation.
- **Business days** are `numpy.busday_count(submitted_date, close_date, holidays)`. That counts business days in `[submitted, close)`, so a proposal submitted Monday and closed Tuesday scores 1.
  - Saturdays, Sundays and the office's holidays are excluded. Open proposals get no value.
- **Checks:**
  - business days never exceed calendar days
  - spot checks match a manual `busday_count`
  - 23,220 closed proposals get a value

## Definitions

| Metric | Definition |
|---|---|
| Volume | Count of proposals submitted (after removing duplicates and test records) |
| Value | Sum of `proposal_value_usd` after unit corrections |
| Win rate | Won / (Won + Lost). Withdrawn proposals (4.6% of closed) and open proposals are excluded |
| Turnaround | Business days from `submitted_date` to the first Won or Lost event |
| Stage split | Submitted to Under Review, and Under Review to decision. About 30% of proposals skip Under Review |
| Growth (volume, value) | 2026 vs 2025 over the same window, **1 Jan to 15 Oct**, because 2026 is a partial year |
| Win rate and turnaround trends | Cohorts submitted **1 Jan to 15 Jul** in each year. These are at least 90 days old at extract, so nearly all have closed (the slowest observed decision took 161 days) |
| Open / stale | No Won, Lost or Withdrawn event by the extract. Stale means open for more than 90 days |

## Data issues log

| # | Issue | Rows | Impact | Treatment |
|---|---|---:|---|---|
| 1 | Exact duplicate proposal rows | 300 | Inflates volume and value | Dropped duplicates, kept first |
| 2 | Test / dummy records (ZZ IDs, clients like 'TEST CLIENT', 'Dummy Co') | 50 | Fake round values (USD 1-5M) inflate value | Excluded from clean data |
| 3 | Mixed date formats in submitted_date (5,670 dd/mm/yyyy, 2,884 'dd Mon yyyy') | 8,554 | Naive parsing misreads or drops ~35% of dates | Parsed each format explicitly; slash dates are day-first (first part >12 in 3,400+ rows, second part never >12) |
| 4 | Office names with inconsistent case / stray whitespace | 744 | Splits one office into up to 5 labels | Trimmed and case-matched to offices.csv |
| 5 | Practice names with inconsistent case / stray whitespace | 681 | Splits one practice into several labels | Trimmed and case-matched |
| 6 | Practice renamed: 'Customer Strategy & Marketing' (2025) -> 'Customer' (from Jan 2026) | 952 | Without merging, one practice looks like it vanished and a new one appeared | Merged under 'Customer Strategy & Marketing' to keep 11 practices comparable |
| 7 | Values entered in USD thousands (USD 30 - 2,000 vs median ~USD 244K; empty gap between 2K and 30K) | 618 | Understates value and distorts averages | Multiplied by 1,000; flagged in value_flag |
| 8 | Extreme value outlier (USD 1.5B, ~3,700x median; 1000x keying error) | 1 | Single row would be ~25% of total 2025 value | Divided by 1,000 (USD 1.5M); flagged in value_flag |
| 9 | proposal_id lost leading zeros in status_events (e.g. '10131' vs '0010131') | 64,391 | A string join matches ~0% of events to proposals | Zero-padded to 7 characters before joining |
| 10 | Status events with no matching clean proposal (test records) | 100 | Would add phantom outcomes | Excluded |
| 11 | Open proposals with no status change for >90 days (likely stale, never closed) | 4 | Pipeline overstated; true win/loss unknown | Kept as open; excluded from win rate and turnaround; flagged is_stale |
| 12 | Right-censoring: recent proposals still open at extract (Jul-Oct 2026 cohorts) | 1,148 | Recent cohorts only contain fast decisions, so turnaround looks better than it is | Trends use mature cohorts only (submitted on/before 15 Jul, >=90 days before extract) |
| 13 | Holiday API returns no data for IN, AE, SA (HTTP 204); Task 1, see `outputs/holiday_fetch_log.csv` | 3,504 | Business days for those offices slightly overstated | Weekends only; flagged holiday_data_missing |

I also checked these and found no issue:
- no missing values
- no dates outside the coverage window
- no event dated before its proposal's submission
- no proposal with more than one Won/Lost/Withdrawn event
- every Submitted event date equals the proposal's `submitted_date`

## Assumptions

- Slash dates are `dd/mm/yyyy`. The first part exceeds 12 in 3,400+ rows and the second part never does.
- Values below USD 10,000 were keyed in thousands. There's a clean gap between about USD 2K and USD 30K, and once rescaled these values match the overall distribution. The USD 1.5B value is a 1000× keying error. All of these are flagged, so they can be reversed.
- "Customer" (2026) and "Customer Strategy & Marketing" (2025) are the same practice. The labels switch cleanly on 1 Jan 2026, and this matches the 11 practices in the brief.
- Records with `ZZ` IDs or placeholder client names are test data.
- Weekends are Saturday and Sunday everywhere, as the brief says. Saudi Arabia actually has a Friday–Saturday weekend (listed under next steps).
- Withdrawn proposals are neither a win nor a loss.

## Dashboard

Power BI Desktop builds the `.pbix` by hand. I've prepared everything it needs in `reporting/`:
- `powerbi_model/`: a star schema of `fact_proposals`, `fact_status_events`, `dim_office`, `dim_practice` and `dim_date`
- `powerbi_measures.dax`: all measures, including like-for-like YoY that still responds to slicers
- `ppk_theme.json`
- `powerbi_build_guide.md`: a page-by-page spec covering growth, speed, and data quality with definitions

There are slicers for region, office, practice, year and quarter.

## AI use

I built this repository with Claude Code (Anthropic) as a pair-programmer. It did the following:
- profiled the raw data and found the issues listed above
- drafted the cleaning, holiday API, analysis and deck-generation code
- drafted the DAX measures, the Power BI build guide and this README

I validated the AI output by running every script end to end and reconciling counts at each step:
- 24,722 raw rows, minus 300 duplicates and 50 test records, leaves 24,372
- all 64,391 events join after ID padding
- business days are never more than calendar days, and spot checks match manual `busday_count`

I checked one finding before using it: Consumer Products' +29% value growth is broad-based. Proposals above USD 2M went from 2 to 11, so a single bad record isn't driving it.

I checked the deck by rendering every slide. All numbers on the slides are generated from `outputs/`, not typed by hand.

## Next steps

1. Add local holidays for India, the UAE and Saudi Arabia from a manual calendar or a second API, and a Friday–Saturday weekend for Riyadh.
2. Map the Paris review workflow, then test whether its review-to-decision time falls toward the 13-day network median.
3. Fix data at source in the proposal system:
   - picklists for office and practice
   - ISO dates
   - a USD range check
   - text IDs
   - a test-record flag
   - auto-closing proposals that have gone stale
4. Schedule `run_pipeline.py` with Power Automate or a scheduled task, so the dashboard refreshes monthly without manual work.
5. Add win-rate drivers beyond office and practice, such as client repeat rate and value band, once more fields are available.
