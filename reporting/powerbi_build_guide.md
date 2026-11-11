# Power BI dashboard: how it is built

The dashboard is generated, not hand-built. `python src/build_powerbi.py` writes a Power BI project (PBIP) to
`reporting/PPK_Dashboard/`. The project holds a TMDL semantic model and a report definition, both text, so they can be diffed in git. `reporting/PPK_Dashboard.pbix` is the same project saved from Power BI Desktop with its data.

## Open or refresh

1. Open `reporting/PPK_Dashboard/PPK_Dashboard.pbip` (or the `.pbix`) in Power BI Desktop.
2. If the repo is not at the original path, go to *Transform data → Edit parameters* and set `DataFolder` to
   `<repo>\reporting\powerbi_model\` (keep the trailing backslash).
3. Click **Refresh**. To produce a `.pbix` from the project, use *File → Save as → Power BI file (.pbix)*.

## Model

Star schema built from `reporting/powerbi_model/*.csv`:

| Table | Role |
|---|---|
| `fact_proposals` | One row per proposal. Holds all measures |
| `dim_office` | Office, country, ISO codes, region |
| `dim_practice` | 11 practices |
| `dim_date` | Marked as the date table. Holds `quarter_of_year` and `month_name` (sorted by `month_num`) for slicing |
| `ref_data_issues`, `ref_holiday_fetch` | Data quality page |

The fact table joins to all three dimensions, each one-to-many and single-direction. Auto date/time is off.

## Measures (in `fact_proposals`)

- **Base:** Proposals, Value USD, Won, Decided, Win Rate, Won Value USD, Median / P90 Days to Decision, Median Days to Review, Median Review to Decision, Share Over 30 Days, Open Pipeline USD, Share Still Open.
- **Like-for-like:** Proposals 2026 YTD / 2025 YTD, Volume Growth %, Volume Growth % Gap-adjusted, Value Growth % (and gap-adjusted), Win Rate 2026 / 2025, Win Rate Change pp, Won Value Growth %, Median Days 2026 / 2025.
  - Each one anchors the year inside the DAX: `CALCULATE(..., dim_date[year] = 2026, dim_date[is_ytd_window] = TRUE())`.
  - Region, office, practice and quarter slicers still apply, but no year filter can break the comparison.
  - `Win Rate Change pp` returns blank when either year is missing.
- **Data quality:** Rescaled Values, Share Without Holiday Data.

## Pages

| Page | Visuals |
|---|---|
| 1 Growth | Six cards: proposals, volume growth, gap-adjusted growth, value growth, won value growth, win rate. Region growth bars (gap-adjusted). Practice growth bars. Proposals per month, 2026 vs 2025 |
| 2 Win rate & speed | Win rate by office. Stacked stage bars by office (submitted to review, review to decision). Median and P90 days by quarter. Share still open by quarter |
| 3 Office scorecard | Table by office: proposals, volume and value growth (reported and gap-adjusted), win rate and change, median days, share over 30 days |
| 4 Data quality | Data issues log, holiday API coverage, and cards for rescaled values, proposals without holiday data and clean proposals |

Every page except Data quality has slicers for region, office, practice and period (quarter of year). Colours come from `reporting/ppk_theme.json`.
