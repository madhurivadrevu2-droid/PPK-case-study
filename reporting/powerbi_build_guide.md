# Power BI build guide (about 60-75 min)

All inputs are in `reporting/powerbi_model/`, produced by `python run_pipeline.py`.

## 1. Load and model (15 min)

1. **Get data -> Text/CSV**: load `fact_proposals`, `fact_status_events`, `dim_office`, `dim_practice`,
   `dim_date`, plus `outputs/data_issues_log.csv` and `outputs/holiday_fetch_log.csv`.
2. **Power Query types**: `proposal_id` = Text (keeps leading zeros); all `*_date` / `date` = Date;
   `is_*`, `holiday_data_missing`, `in_*_window` = True/False; `*_usd`, `*bd*`, `*days*` = Decimal.
3. **Model view relationships** (single direction, many-to-one):
   - `fact_proposals[submitted_date]` -> `dim_date[date]`
   - `fact_proposals[office]` -> `dim_office[office]`
   - `fact_proposals[practice]` -> `dim_practice[practice]`
   - `fact_status_events[proposal_id]` -> `fact_proposals[proposal_id]`
4. `dim_date` -> **Mark as date table** on `date`. Sort `quarter` / `month` by `date`.
5. **View -> Themes -> Browse**: `reporting/ppk_theme.json`.
6. Create a `_Measures` table and paste the measures from `reporting/powerbi_measures.dax`.
   Format `Win Rate*`, `*Growth %`, `Share*` as %, `Value*` as $ (millions, 1 dp).

## 2. Slicers on every page (sync via View -> Sync slicers)

`dim_office[region]`, `dim_office[office]`, `dim_practice[practice]`, `dim_date[year]`, `dim_date[quarter]`.

## 3. Page 1 - Growth: "Where is proposal activity growing?"

Page filter: `dim_date[is_ytd_window] = True` (like-for-like 1 Jan - 15 Oct).
Filter `dim_date[year] = 2026` on the cards so PY measures compare to 2025.

| Visual | Fields |
|---|---|
| 4 KPI cards | `Proposals` + `Volume Growth %`; `Value USD` + `Value Growth %`; `Win Rate (mature)` + `Win Rate Change (pp)`; `Median Turnaround (mature)` |
| Clustered bar | Axis `region`; values `Volume Growth %`, `Value Growth %` |
| Clustered bar | Axis `practice`; value `Volume Growth %`; tooltip `Value Growth %`, `Win Rate Change (pp)` (sort descending) |
| Line chart | Axis `dim_date[month]`; value `Proposals`; legend `region` (remove page YTD filter on this visual) |
| Matrix | Rows `region` > `office`; values `Proposals`, `Volume Growth %`, `Value Growth %`, `Win Rate (mature)`, `Win Rate Change (pp)`; conditional formatting on growth columns |

## 4. Page 2 - Speed: "Where do proposals take longest, and is it improving?"

| Visual | Fields |
|---|---|
| Stacked bar | Axis `office`; values `Median Submit to Review (bd)`, `Median Review to Decision (bd)` (Paris stands out) |
| Line chart | Axis `dim_date[quarter]`; values `Median Turnaround (bd)`, `P90 Turnaround (bd)`; add text box: "2026 Q3-Q4 not yet mature: slow proposals still open" |
| Column chart | Axis `quarter`; value `Open Pipeline` (shows why recent quarters look faster) |
| Matrix | Rows `practice`; columns `region`; value `Median Turnaround (bd)`, heat-map formatting |
| Card | `Median Turnaround (mature)` vs `Median Turnaround PY (mature)` |

## 5. Page 3 - Data quality and definitions

| Visual | Fields |
|---|---|
| Table | `data_issues_log`: issue, rows_affected, impact, treatment |
| Table | `holiday_fetch_log`: country_code, year, status, holidays_returned |
| Cards | `Rescaled Values`, `Share Without Holiday Data` |
| Text box | Metric definitions (copy from README "Definitions") |

## 6. Save

Save as `reporting/PPK_Proposal_Performance.pbix` and commit.
