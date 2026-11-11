"""Generate a Power BI project (PBIP) for the proposal dashboard: TMDL semantic model + report.

Run:  python src/build_powerbi.py   ->  reporting/PPK_Dashboard/PPK_Dashboard.pbip
Open the .pbip in Power BI Desktop, click Refresh, then File > Save as > .pbix.
The data folder is a model parameter (DataFolder); change it under Transform data >
Edit parameters if the repo lives somewhere else.

Pages: 1 Growth | 2 Win rate & speed | 3 Office scorecard | 4 Data quality.
Slicers on every page: region, office, practice and period (quarter of year). Growth measures
anchor the year (2026 vs 2025) inside DAX, so they stay like-for-like whatever is sliced.
"""
from __future__ import annotations

import json
import shutil
import uuid

from config import REPORTING

NAME = "PPK_Dashboard"
ROOT = REPORTING / NAME
MODEL_DIR = REPORTING / "powerbi_model"
NS = uuid.UUID("6f1c2a52-8a43-4c1e-9d0e-0b6f1a2c3d4e")


def tag(*parts: str) -> str:
    """Deterministic lineage tags so re-running the build produces an identical project."""
    return str(uuid.uuid5(NS, "/".join(parts)))


# ----------------------------------------------------------------------------- model
T, B, I, D, S = "double", "boolean", "int64", "dateTime", "string"
TABLES = {
    "fact_proposals": [
        ("proposal_id", S), ("submitted_date", D), ("office", S), ("practice", S), ("client_name", S),
        ("proposal_value_usd", T), ("value_flag", S), ("current_status", S), ("close_status", S),
        ("close_date", D), ("is_open", B), ("is_stale", B), ("is_decided", B), ("is_won", B),
        ("business_days_to_close", T), ("bd_to_review", T), ("bd_review_to_close", T),
        ("calendar_days_to_close", T), ("holiday_data_missing", B), ("in_ytd_window", B),
        ("in_mature_window", B), ("in_submission_gap", B)],
    "dim_office": [("office", S), ("country", S), ("country_code", S), ("subdivision_code", S), ("region", S)],
    "dim_practice": [("practice", S)],
    "dim_date": [("date", D), ("year", I), ("quarter", S), ("month", S), ("quarter_of_year", S),
                 ("month_num", I), ("month_name", S), ("month_day", S), ("is_ytd_window", B),
                 ("is_mature_window", B)],
    "ref_data_issues": [("issue_no", I), ("short", S), ("issue", S), ("rows_affected", I), ("impact", S),
                        ("treatment", S)],
    "ref_holiday_fetch": [("country_code", S), ("year", I), ("status", S), ("holidays_returned", I),
                          ("detail", S)],
}
M_TYPE = {T: "type number", B: "type logical", I: "Int64.Type", D: "type date", S: "type text"}
FORMATS = {D: "yyyy-mm-dd", T: "0", I: "0"}

F = "fact_proposals"
DEC = f"{F}[is_decided] = TRUE()"
MEASURES = [
    # name, DAX, format
    ("Proposals", f"COUNTROWS({F})", "#,0"),
    ("Value USD", f"SUM({F}[proposal_value_usd])", "$#,0"),
    ("Won", f'CALCULATE([Proposals], {F}[close_status] = "Won")', "#,0"),
    ("Decided", f"CALCULATE([Proposals], {DEC})", "#,0"),
    ("Win Rate", "DIVIDE([Won], [Decided])", "0.0%"),
    ("Won Value USD", f'CALCULATE([Value USD], {F}[close_status] = "Won")', "$#,0"),
    ("Median Days to Decision", f"CALCULATE(MEDIAN({F}[business_days_to_close]), {DEC})", "0"),
    ("P90 Days to Decision", f"CALCULATE(PERCENTILE.INC({F}[business_days_to_close], 0.9), {DEC})", "0"),
    ("Median Days to Review", f"CALCULATE(MEDIAN({F}[bd_to_review]), {DEC})", "0"),
    ("Median Review to Decision", f"CALCULATE(MEDIAN({F}[bd_review_to_close]), {DEC})", "0"),
    ("Share Over 30 Days", f"DIVIDE(CALCULATE([Proposals], {DEC}, {F}[business_days_to_close] > 30), [Decided])", "0%"),
    ("Open Pipeline USD", f"CALCULATE([Value USD], {F}[is_open] = TRUE())", "$#,0"),
    ("Share Still Open", f"DIVIDE(CALCULATE([Proposals], {F}[is_open] = TRUE()), [Proposals])", "0%"),
    # like-for-like: year anchored here, so slicers on quarter_of_year / region / office / practice still apply
    ("Proposals 2026 YTD", "CALCULATE([Proposals], dim_date[year] = 2026, dim_date[is_ytd_window] = TRUE())", "#,0"),
    ("Proposals 2025 YTD", "CALCULATE([Proposals], dim_date[year] = 2025, dim_date[is_ytd_window] = TRUE())", "#,0"),
    ("Volume Growth %", "DIVIDE([Proposals 2026 YTD] - [Proposals 2025 YTD], [Proposals 2025 YTD])", "+0.0%;-0.0%;0.0%"),
    ("Volume Growth % Gap-adjusted",
     f"VAR c = CALCULATE([Proposals 2026 YTD], {F}[in_submission_gap] = FALSE()) "
     f"VAR p = CALCULATE([Proposals 2025 YTD], {F}[in_submission_gap] = FALSE()) RETURN DIVIDE(c - p, p)",
     "+0.0%;-0.0%;0.0%"),
    ("Value 2026 YTD", "CALCULATE([Value USD], dim_date[year] = 2026, dim_date[is_ytd_window] = TRUE())", "$#,0"),
    ("Value 2025 YTD", "CALCULATE([Value USD], dim_date[year] = 2025, dim_date[is_ytd_window] = TRUE())", "$#,0"),
    ("Value Growth %", "DIVIDE([Value 2026 YTD] - [Value 2025 YTD], [Value 2025 YTD])", "+0.0%;-0.0%;0.0%"),
    ("Value Growth % Gap-adjusted",
     f"VAR c = CALCULATE([Value 2026 YTD], {F}[in_submission_gap] = FALSE()) "
     f"VAR p = CALCULATE([Value 2025 YTD], {F}[in_submission_gap] = FALSE()) RETURN DIVIDE(c - p, p)",
     "+0.0%;-0.0%;0.0%"),
    ("Proposals Complete Months", 'IF(MAX(dim_date[month]) = "2026-10", BLANK(), [Proposals])', "#,0"),
    ("Win Rate 2026", "CALCULATE([Win Rate], dim_date[year] = 2026, dim_date[is_mature_window] = TRUE())", "0.0%"),
    ("Win Rate 2025", "CALCULATE([Win Rate], dim_date[year] = 2025, dim_date[is_mature_window] = TRUE())", "0.0%"),
    ("Win Rate Change pp",
     "IF(ISBLANK([Win Rate 2025]) || ISBLANK([Win Rate 2026]), BLANK(), ([Win Rate 2026] - [Win Rate 2025]) * 100)",
     "+0.0;-0.0;0.0"),
    ("Won Value 2026", "CALCULATE([Won Value USD], dim_date[year] = 2026, dim_date[is_mature_window] = TRUE())", "$#,0"),
    ("Won Value 2025", "CALCULATE([Won Value USD], dim_date[year] = 2025, dim_date[is_mature_window] = TRUE())", "$#,0"),
    ("Won Value Growth %", "DIVIDE([Won Value 2026] - [Won Value 2025], [Won Value 2025])", "+0.0%;-0.0%;0.0%"),
    ("Median Days 2026", "CALCULATE([Median Days to Decision], dim_date[year] = 2026, dim_date[is_mature_window] = TRUE())", "0"),
    ("Median Days 2025", "CALCULATE([Median Days to Decision], dim_date[year] = 2025, dim_date[is_mature_window] = TRUE())", "0"),
    ("Rescaled Values", f'CALCULATE([Proposals], {F}[value_flag] <> "ok")', "#,0"),
    ("Share Without Holiday Data", f"DIVIDE(CALCULATE([Proposals], {F}[holiday_data_missing] = TRUE()), [Proposals])", "0.0%"),
]
RELATIONSHIPS = [("fact_proposals", "submitted_date", "dim_date", "date"),
                 ("fact_proposals", "office", "dim_office", "office"),
                 ("fact_proposals", "practice", "dim_practice", "practice")]


def q(name: str) -> str:
    """Quote a TMDL object name when it has spaces or symbols."""
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


def table_tmdl(name: str, cols: list[tuple[str, str]]) -> str:
    out = [f"table {name}", f"\tlineageTag: {tag(name)}", ""]
    if name == "dim_date":
        out.insert(1, "\tdataCategory: Time")
    if name == F:
        for m, dax, fmt in MEASURES:
            out += [f"\tmeasure {q(m)} = {dax}", f"\t\tformatString: {fmt}", f"\t\tlineageTag: {tag(name, m)}", ""]
    for c, dt in cols:
        out += [f"\tcolumn {c}", f"\t\tdataType: {dt}"]
        if name == "dim_date" and c == "date":
            out.append("\t\tisKey")
        if dt in FORMATS:
            out.append(f"\t\tformatString: {FORMATS[dt]}")
        out += [f"\t\tlineageTag: {tag(name, c)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {c}"]
        if name == "dim_date" and c == "month_name":
            out.append("\t\tsortByColumn: month_num")
        out += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
    types = ", ".join(f'{{"{c}", {M_TYPE[dt]}}}' for c, dt in cols)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{name}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"    Kept = Table.SelectColumns(Headers, {{{', '.join(chr(34) + c + chr(34) for c, _ in cols)}}}),",
        '    Blanks = Table.ReplaceValue(Kept, "", null, Replacer.ReplaceValue, Table.ColumnNames(Kept)),',
        f'    Typed = Table.TransformColumnTypes(Blanks, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    out += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource ="] + [f"\t\t\t\t{line}" for line in m]
    out += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def write_model() -> None:
    sm = ROOT / f"{NAME}.SemanticModel"
    d = sm / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    (sm / "definition.pbism").write_text(json.dumps({"version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    (sm / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": tag("semanticmodel")}}, indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n\n", encoding="utf-8")
    order = json.dumps(["DataFolder", *TABLES])
    refs = "\n".join(f"ref table {t}" for t in TABLES)
    (d / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"annotation __PBI_TimeIntelligenceEnabled = 0\n\nannotation PBI_QueryOrder = {order}\n\n{refs}\n\n",
        encoding="utf-8")
    folder = str(MODEL_DIR.resolve()) + "\\"
    (d / "expressions.tmdl").write_text(
        f'expression DataFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {tag('DataFolder')}\n\n\tannotation PBI_ResultType = Text\n\n", encoding="utf-8")
    rels = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rels += [f"relationship {tag('rel', ft, fc)}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}"]
        if fc == "submitted_date":
            rels.append("\tjoinOnDateBehavior: datePartOnly")
        rels.append("")
    (d / "relationships.tmdl").write_text("\n".join(rels) + "\n", encoding="utf-8")
    for t, cols in TABLES.items():
        (d / "tables" / f"{t}.tmdl").write_text(table_tmdl(t, cols), encoding="utf-8")


# ----------------------------------------------------------------------------- report
ALIAS = {"fact_proposals": "f", "dim_office": "o", "dim_practice": "p", "dim_date": "d",
         "ref_data_issues": "i", "ref_holiday_fetch": "h"}
MEASURE_NAMES = {m for m, _, _ in MEASURES}


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def field(entity: str, prop: str) -> dict:
    kind = "Measure" if entity == F and prop in MEASURE_NAMES else "Column"
    return {kind: {"Expression": {"SourceRef": {"Source": ALIAS[entity]}}, "Property": prop},
            "Name": f"{entity}.{prop}"}


class Page:
    def __init__(self, display: str, ordinal: int):
        self.display, self.ordinal, self.visuals = display, ordinal, []

    def add(self, vtype: str, x, y, w, h, roles: dict | None = None, title: str | None = None,
            objects: dict | None = None, order_by: tuple | None = None, extra: dict | None = None):
        roles = roles or {}
        fields = [(e, p) for refs in roles.values() for e, p in refs]
        entities = sorted({e for e, _ in fields}, key=list(ALIAS).index)
        sv = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if fields:
            sv["projections"] = {role: [{"queryRef": f"{e}.{p}", **({"active": True} if role in ("Category", "Values") and vtype == "slicer" else {})}
                                        for e, p in refs] for role, refs in roles.items()}
            query = {"Version": 2, "From": [{"Name": ALIAS[e], "Entity": e, "Type": 0} for e in entities],
                     "Select": [field(e, p) for e, p in dict.fromkeys(fields)]}
            if order_by:
                e, p, direction = order_by
                key = field(e, p)
                key.pop("Name")
                query["OrderBy"] = [{"Direction": direction, "Expression": key}]
            sv["prototypeQuery"] = query
        if objects:
            sv["objects"] = objects
        vc = {}
        if title:
            vc["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]
        if vc:
            sv["vcObjects"] = vc
        if extra:
            sv.update(extra)
        name = tag("visual", self.display, str(len(self.visuals))).replace("-", "")[:20]
        z = len(self.visuals) * 1000
        cfg = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h,
                                                                 "tabOrder": z}}], "singleVisual": sv}
        self.visuals.append({"x": x, "y": y, "z": z, "width": w, "height": h, "config": json.dumps(cfg),
                             "filters": "[]", "tabOrder": z})

    def textbox(self, text: str, x, y, w, h, size="18pt", bold=True, color="#1b1b1b"):
        para = [{"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold" if bold else "normal",
                                                             "fontSize": size, "color": color}}]}]
        self.add("textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": para}}]})

    def slicers(self, y=58):
        for i, (e, p, label, w) in enumerate([("dim_office", "region", "Region", 230), ("dim_office", "office", "Office", 230),
                                              ("dim_practice", "practice", "Practice", 300),
                                              ("dim_date", "quarter_of_year", "Period (quarter)", 200)]):
            x = 20 + sum([230, 230, 300, 200][:i]) + 10 * i
            self.add("slicer", x, y, w, 62, {"Values": [(e, p)]}, title=label,
                     objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                              "header": [{"properties": {"show": lit("false")}}]})

    def json(self) -> dict:
        return {"name": tag("page", self.display).replace("-", "")[:20], "displayName": self.display,
                "displayOption": 1, "filters": "[]", "ordinal": self.ordinal, "width": 1280, "height": 720,
                "config": "{}", "visualContainers": self.visuals}


LABELS = {"labels": [{"properties": {"show": lit("true")}}]}


def measure_color(measure: str, color: str) -> dict:
    return {"properties": {"fill": {"solid": {"color": lit(f"'{color}'")}}}, "selector": {"metadata": f"{F}.{measure}"}}


def series_colors() -> dict:
    """2026 in accent red, 2025 in grey, keyed on the year series."""
    def pick(year: int, color: str) -> dict:
        cond = {"Comparison": {"ComparisonKind": 0,
                               "Left": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_date"}}, "Property": "year"}},
                               "Right": {"Literal": {"Value": f"{year}L"}}}}
        return {"properties": {"fill": {"solid": {"color": lit(f"'{color}'")}}},
                "selector": {"data": [{"scopeId": cond}]}}
    return {"dataPoint": [pick(2026, "#CC0000"), pick(2025, "#A9A8A2")]}


def card(page: Page, measure: str, title: str, x, y, w=200, h=86):
    page.add("card", x, y, w, h, {"Values": [(F, measure)]}, title=title,
             objects={"labels": [{"properties": {"fontSize": lit("20D"), "labelDisplayUnits": lit("1D")}}],
                      "categoryLabels": [{"properties": {"show": lit("false")}}]})


def build_pages() -> list[dict]:
    p1 = Page("1 Growth", 0)
    p1.textbox("Proposal growth: 1 Jan-15 Oct 2026 vs same window 2025", 20, 8, 1240, 44)
    p1.slicers()
    for i, (m, t) in enumerate([("Proposals 2026 YTD", "Proposals, 2026 YTD"), ("Volume Growth %", "Volume growth"),
                                ("Volume Growth % Gap-adjusted", "Volume growth, gap-adjusted"),
                                ("Value Growth %", "Value growth"), ("Won Value Growth %", "Won value growth"),
                                ("Win Rate 2026", "Win rate 2026 (Jan-Jul cohorts)")]):
        card(p1, m, t, 20 + i * 207, 124)
    p1.add("clusteredBarChart", 20, 222, 400, 480,
           {"Category": [("dim_office", "region")], "Y": [(F, "Volume Growth % Gap-adjusted"), (F, "Value Growth % Gap-adjusted")]},
           title="Growth by region, gap-adjusted", objects=LABELS, order_by=(F, "Volume Growth % Gap-adjusted", 2))
    p1.add("clusteredBarChart", 430, 222, 400, 480,
           {"Category": [("dim_practice", "practice")], "Y": [(F, "Volume Growth %")]},
           title="Volume growth by practice", objects=LABELS, order_by=(F, "Volume Growth %", 2))
    p1.add("lineChart", 840, 222, 420, 480,
           {"Category": [("dim_date", "month_name")], "Series": [("dim_date", "year")], "Y": [(F, "Proposals Complete Months")]},
           title="Proposals per month, 2026 vs 2025 (Oct 2026 partial, not shown)", objects=series_colors())

    p2 = Page("2 Win rate & speed", 1)
    p2.textbox("Win rate is steady; Paris is slow to decide; recent quarters are not yet mature", 20, 8, 1240, 44)
    p2.slicers()
    p2.add("clusteredBarChart", 20, 124, 300, 578, {"Category": [("dim_office", "office")], "Y": [(F, "Win Rate 2026")]},
           title="Win rate by office, 2026", objects=LABELS, order_by=(F, "Win Rate 2026", 2))
    p2.add("barChart", 330, 124, 450, 578,
           {"Category": [("dim_office", "office")], "Y": [(F, "Median Days to Review"), (F, "Median Review to Decision")]},
           title="Median business days to decision, by stage", order_by=(F, "Median Review to Decision", 2),
           objects={**LABELS, "dataPoint": [measure_color("Median Days to Review", "#BFBFBF"),
                                            measure_color("Median Review to Decision", "#6F6E69")]})
    p2.add("lineChart", 790, 124, 470, 284,
           {"Category": [("dim_date", "quarter")], "Y": [(F, "Median Days to Decision"), (F, "P90 Days to Decision")]},
           title="Business days to decision by submission quarter")
    p2.add("clusteredColumnChart", 790, 418, 470, 284,
           {"Category": [("dim_date", "quarter")], "Y": [(F, "Share Still Open")]},
           title="Share still open at extract (why 2026 Q3-Q4 look faster)", objects=LABELS)

    p3 = Page("3 Office scorecard", 2)
    p3.textbox("Office scorecard: growth, win rate and speed", 20, 8, 1240, 44)
    p3.slicers()
    p3.add("tableEx", 20, 124, 1240, 578,
           {"Values": [("dim_office", "office"), ("dim_office", "region"), (F, "Proposals 2025 YTD"), (F, "Proposals 2026 YTD"),
                       (F, "Volume Growth %"), (F, "Volume Growth % Gap-adjusted"), (F, "Value Growth %"),
                       (F, "Win Rate 2026"), (F, "Win Rate Change pp"), (F, "Median Days 2026"), (F, "Share Over 30 Days")]},
           title="By office (volume: 1 Jan-15 Oct; win rate and days: cohorts to 15 Jul)",
           order_by=(F, "Volume Growth %", 2))

    p4 = Page("4 Data quality", 3)
    p4.textbox("Data quality: issues found, why they matter and how each was handled", 20, 8, 1240, 44)
    p4.add("tableEx", 20, 60, 900, 642,
           {"Values": [("ref_data_issues", "issue_no"), ("ref_data_issues", "short"), ("ref_data_issues", "rows_affected"),
                       ("ref_data_issues", "impact"), ("ref_data_issues", "treatment")]},
           title="Data issues log", order_by=("ref_data_issues", "issue_no", 1))
    p4.add("tableEx", 930, 60, 330, 420,
           {"Values": [("ref_holiday_fetch", "country_code"), ("ref_holiday_fetch", "year"), ("ref_holiday_fetch", "status"),
                       ("ref_holiday_fetch", "holidays_returned")]},
           title="Holiday API coverage (Task 1)")
    card(p4, "Rescaled Values", "Values rescaled (units)", 930, 492, 160, 100)
    card(p4, "Share Without Holiday Data", "Proposals without holiday data", 1100, 492, 160, 100)
    card(p4, "Proposals", "Clean proposals", 930, 602, 330, 100)
    return [p.json() for p in (p1, p2, p3, p4)]


def write_report() -> None:
    rp = ROOT / f"{NAME}.Report"
    res = rp / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPORTING / "ppk_theme.json", res / "PPK_Ops_theme.json")
    (rp / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2),
        encoding="utf-8")
    (rp / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": tag("report")}}, indent=2), encoding="utf-8")
    config = {"version": "5.43", "themeCollection": {"customTheme": {"name": "PPK_Ops_theme.json", "version": "5.43", "type": 1}},
              "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
              "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                           "useStylableVisualContainerHeader": True, "exportDataMode": 1}}
    report = {"config": json.dumps(config), "layoutOptimization": 0,
              "resourcePackages": [{"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                                                        "items": [{"name": "PPK_Ops_theme.json", "path": "PPK_Ops_theme.json", "type": 202}]}}],
              "sections": build_pages()}
    (rp / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / f"{NAME}.pbip").write_text(json.dumps(
        {"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}},
        indent=2), encoding="utf-8")
    (ROOT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT / f"{NAME}.Report", ignore_errors=True)
        shutil.rmtree(ROOT / f"{NAME}.SemanticModel" / "definition", ignore_errors=True)
    write_model()
    write_report()
    print(f"Saved Power BI project -> {(ROOT / f'{NAME}.pbip').relative_to(REPORTING.parent)}")


if __name__ == "__main__":
    main()
