"""Build the executive summary deck from the analysis outputs (numbers are never hard-coded).

Run:  python src/build_slides.py   (after analysis.py)  ->  reporting/PPK_Executive_Summary.pptx
"""
from __future__ import annotations

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION,
                             XL_TICK_LABEL_POSITION)
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from config import OUTPUTS, REPORTING
from story import NOTES, story_numbers

RED, DARK_RED = RGBColor(0xCC, 0x00, 0x00), RGBColor(0x99, 0x00, 0x00)
INK, GREY, LIGHT, TINT = (RGBColor(0x33, 0x33, 0x33), RGBColor(0x7A, 0x7A, 0x7A),
                          RGBColor(0xBF, 0xBF, 0xBF), RGBColor(0xF4, 0xF4, 0xF4))
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"
SHORT = {"Technology, Media & Telecom": "TMT", "Customer Strategy & Marketing": "Customer Strategy & Mktg",
         "Energy & Natural Resources": "Energy & Nat. Resources", "India & Middle East": "India & ME"}
SOURCE = ("Source: PPK proposal system extract, 15 Oct 2026 (fictitious data); 24,372 proposals. "
          "Volume and value: 1 Jan-15 Oct 2026 vs same window 2025. Win rate, won value and turnaround: "
          "cohorts submitted 1 Jan-15 Jul. Gap-adjusted excludes Aug for Dubai and Riyadh in both years.")


def text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None):
    """Add a text box. `runs` is a string or a list of paragraphs, each a list of (text, opts)."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    paragraphs = [[(runs, {})]] if isinstance(runs, str) else runs
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        for t, opts in para:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold)
            f.color.rgb = opts.get("color", color)
    return box


def rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    if name:
        s.name = name
    return s


def title(slide, words: str, subtitle: str | None = None) -> None:
    text(slide, 0.5, 0.35, 12.3, 0.85, words, size=24, bold=True, anchor=MSO_ANCHOR.BOTTOM, name="Title")
    if subtitle:
        text(slide, 0.5, 1.25, 12.3, 0.35, subtitle, size=14, color=GREY, name="Subtitle")


def footer(slide, page: int) -> None:
    text(slide, 0.5, 6.95, 11.6, 0.4, SOURCE, size=10, color=GREY, name="Source")
    text(slide, 12.3, 6.95, 0.5, 0.3, str(page), size=10, color=GREY, align=PP_ALIGN.RIGHT, name="Page")


def style_chart(chart, number_format='0"%"', legend=False):
    chart.font.name = FONT
    chart.font.size = Pt(11)
    chart.font.color.rgb = INK
    chart.has_title = False
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(11)
    va = chart.value_axis
    va.visible = False
    va.has_major_gridlines = False
    ca = chart.category_axis
    ca.format.line.color.rgb = LIGHT
    ca.has_major_gridlines = False
    ca.tick_labels.font.size = Pt(11)
    ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW  # keep labels clear of negative bars
    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = number_format
    dl.number_format_is_linked = False
    dl.font.size = Pt(11)
    return plot


def bar_chart(slide, x, y, w, h, categories, series: dict, colors, number_format='0"%"',
              chart_type=XL_CHART_TYPE.BAR_CLUSTERED, legend=False, highlight=None, name=None,
              label_colors=None):
    data = CategoryChartData()
    data.categories = categories
    for label, values in series.items():
        data.add_series(label, values)
    gf = slide.shapes.add_chart(chart_type, Inches(x), Inches(y), Inches(w), Inches(h), data)
    if name:
        gf.name = name
    chart = gf.chart
    plot = style_chart(chart, number_format, legend)
    plot.gap_width = 60
    chart.category_axis.reverse_order = True  # first category on top for horizontal bars
    if chart_type == XL_CHART_TYPE.BAR_CLUSTERED:
        plot.overlap = -10
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    else:
        plot.overlap = 100
        plot.data_labels.position = XL_LABEL_POSITION.CENTER
    for s, c in zip(plot.series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = c
        s.invert_if_negative = False
    for s, c in zip(plot.series, label_colors or []):
        s.data_labels.show_value = True
        s.data_labels.font.size = Pt(11)
        s.data_labels.font.color.rgb = c
        s.data_labels.number_format = number_format
        s.data_labels.number_format_is_linked = False
        s.data_labels.position = XL_LABEL_POSITION.CENTER
    if highlight:  # {series_index: {point_index: color}}
        for si, points in highlight.items():
            for pi, c in points.items():
                pt = plot.series[si].points[pi]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = c
    return chart


def kpi(slide, x, y, w, value, label, delta, name, h=1.25):
    rect(slide, x, y, w, h, TINT, name=f"{name} tile")
    text(slide, x + 0.15, y + 0.1, w - 0.3, 0.3, label, size=11, bold=True, name=f"{name} label")
    text(slide, x + 0.15, y + 0.38, w - 0.3, 0.45, value, size=22, bold=True, color=RED, name=f"{name} value")
    text(slide, x + 0.15, y + 0.83, w - 0.3, 0.4, delta, size=10, color=GREY, name=f"{name} delta")


def slide_growth(prs, d, st):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, st["headline"])
    w = (12.3 - 5 * 0.15) / 6
    for i, k in enumerate(st["kpis"]):
        kpi(s, 0.5 + i * (w + 0.15), 1.4, w, k["value"], k["label"], k["delta"], name=f"KPI {i + 1}")

    reg = d["region_adj"]
    text(s, 0.5, 2.9, 3.9, 0.35, "Growth by region, % YTD (gap-adjusted)", size=14, bold=True,
         name="Region chart title")
    bar_chart(s, 0.4, 3.25, 4.0, 3.5, [SHORT.get(r, r) for r in reg.index],
              {"Volume": reg.volume_growth_pct.tolist(), "Value": reg.value_growth_pct.tolist()},
              [RED, LIGHT], number_format='0.0"%"', legend=True, name="Region growth chart")

    pr = d["practice"]
    text(s, 4.7, 2.9, 4.2, 0.35, "Volume growth by practice, % YTD", size=14, bold=True,
         name="Practice chart title")
    bar_chart(s, 4.6, 3.25, 4.3, 3.5, [SHORT.get(p, p) for p in pr.index],
              {"Volume": pr.volume_growth_pct.tolist()},
              [LIGHT], number_format='0.0"%"', highlight={0: {i: RED for i in range(3)}},
              name="Practice growth chart")

    rect(s, 9.2, 2.9, 3.6, 3.85, TINT, name="Findings panel")
    paras = [[("What stands out", {"bold": True})]]
    for head, body in st["findings"]:
        paras.append([(head + ": ", {"bold": True, "size": 11}), (body, {"size": 11})])
    dub = st["dubai"]
    paras.append([("Data gap: ", {"bold": True, "size": 11}),
                  (f"Dubai and Riyadh have no submissions in Aug 2026; India & ME is "
                   f"{dub['ime_reported']:+.1f}% as reported, {dub['ime_adj']:+.1f}% gap-adjusted.", {"size": 11})])
    text(s, 9.4, 3.02, 3.25, 3.7, paras, size=13, name="Findings text")
    footer(s, 1)
    s.notes_slide.notes_text_frame.text = st["notes"]["summary"] + " " + st["notes"]["growth"]


def action_card(s, x, y, w, h, n, head, body, meta, name):
    rect(s, x, y, w, h, TINT, name=f"{name} card")
    c = rect(s, x + 0.2, y + 0.2, 0.5, 0.5, RED, shape=MSO_SHAPE.OVAL, name=f"{name} number")
    tf = c.text_frame
    tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(16), True, WHITE
    text(s, x + 0.9, y + 0.15, w - 1.1, h - 0.25,
         [[(head, {"bold": True, "size": 13})], [(body, {"size": 11})], [(meta, {"size": 11, "bold": True})]],
         name=f"{name} text")


def slide_speed_actions(prs, d, st):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    pa = st["paris"]
    g = st["total"]
    title(s, f"Time to decision is flat at {g['median_bd_to_close_2026']:.0f} business days and Paris takes "
             f"{pa['total']:.0f}; three actions for FY27 planning")
    stage = d["stage"]
    text(s, 0.5, 1.4, 6.2, 0.35, "Median business days to decision, by office and stage", size=14,
         bold=True, name="Stage chart title")
    order = stage.sort_values("business_days_to_close", ascending=False)
    pi = order.index.get_loc("Paris")
    bar_chart(s, 0.4, 1.75, 6.3, 3.85, order.index.tolist(),
              {"Submitted to under review": order.bd_to_review.tolist(),
               "Under review to decision": order.bd_review_to_close.tolist()},
              [LIGHT, GREY], number_format="0", chart_type=XL_CHART_TYPE.BAR_STACKED, legend=True,
              highlight={1: {pi: RED}}, name="Stage turnaround chart", label_colors=[INK, WHITE])
    cz = st["censoring"]
    rect(s, 0.5, 5.7, 6.2, 1.05, TINT, name="Callout")
    text(s, 0.7, 5.78, 5.8, 0.95, [
        [("Paris is slow at the decision step: ", {"bold": True, "size": 11}),
         (f"{pa['no_review']:.0f} days even without formal review; {pa['over30']:.0f}% of decisions take over "
          f"30 days vs {pa['network_over30']:.0f}% elsewhere.", {"size": 11})],
        [("Not a real speed-up: ", {"bold": True, "size": 11}),
         (f"Q3 2026 looks faster (90th percentile {cz['p90_26']:.0f} vs {cz['p90_25']:.0f} days) only because "
          f"{cz['open_pct']:.0f}% of that cohort is still open.", {"size": 11})]], name="Callout text")
    for i, (head, body, meta) in enumerate(st["actions"]):
        action_card(s, 7.0, 1.4 + i * 1.68, 5.8, 1.55, i + 1, head, body, meta, name=f"Action {i + 1}")
    text(s, 7.0, 6.48, 5.8, 0.35, st["enabler"], size=10, color=GREY, name="Enabler")
    footer(s, 2)
    s.notes_slide.notes_text_frame.text = st["notes"]["speed"] + " " + st["notes"]["actions"]


KEY_ISSUES = {"Practice renamed in 2026", "Values keyed in thousands", "USD 1.5B keying error",
              "IDs lost leading zeros", "Missing Gulf submissions, Aug 2026"}


def slide_quality(prs, issues: pd.DataFrame, st):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, f"{len(issues)} data issues were found and treated before analysis; five would have changed the answer")
    steps = [("1. Detect", "Profile every field first"), ("2. Quantify", "Rows affected and impact"),
             ("3. Treat", "Fix, merge or exclude by a stated rule"), ("4. Flag", "Keep a flag so it is reversible")]
    for i, (h, b) in enumerate(steps):
        x = 0.5 + i * 3.1
        rect(s, x, 1.38, 2.95, 0.55, TINT, name=f"Step {i + 1}")
        text(s, x + 0.12, 1.5, 2.75, 0.4, [[(h + "  ", {"bold": True, "size": 11}), (b, {"size": 11})]],
             name=f"Step {i + 1} text")
    rows, cols = len(issues) + 1, 5
    tbl = s.shapes.add_table(rows, cols, Inches(0.5), Inches(2.05), Inches(12.3), Inches(4.75)).table
    for i, w in enumerate([0.35, 2.35, 0.8, 3.9, 4.9]):
        tbl.columns[i].width = Inches(w)
    heads = ["#", "Issue", "Rows", "Why it matters", "How it was handled"]
    for r in range(rows):
        key = r > 0 and issues.iloc[r - 1]["short"] in KEY_ISSUES
        for c in range(cols):
            cell = tbl.cell(r, c)
            if r == 0:
                val = heads[c]
            else:
                row = issues.iloc[r - 1]
                val = [str(r), row["short"], f"{row.rows_affected:,}", row.impact, row.treatment][c]
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = val
            run.font.name, run.font.size = FONT, Pt(9)
            run.font.bold = r == 0 or (key and c == 1)
            run.font.color.rgb = WHITE if r == 0 else INK
            if c == 2:
                p.alignment = PP_ALIGN.RIGHT
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.fill.solid()
            cell.fill.fore_color.rgb = INK if r == 0 else (RGBColor(0xFB, 0xEA, 0xEA) if key else
                                                          (TINT if r % 2 else WHITE))
    text(s, 0.5, 6.95, 11.6, 0.4, "Shaded rows would have changed the answer. Full log: outputs/data_issues_log.csv "
         "and README.", size=10, color=GREY, name="Source")
    text(s, 12.3, 6.95, 0.5, 0.3, "3", size=10, color=GREY, align=PP_ALIGN.RIGHT, name="Page")
    s.notes_slide.notes_text_frame.text = st["notes"]["quality"]


def load() -> dict:
    return {
        "region_adj": pd.read_csv(OUTPUTS / "growth_by_region_gap_adjusted.csv", index_col=0),
        "practice": pd.read_csv(OUTPUTS / "growth_by_practice.csv", index_col=0),
        "stage": pd.read_csv(OUTPUTS / "turnaround_stage_by_office.csv", index_col=0),
        "issues": pd.read_csv(OUTPUTS / "data_issues_log.csv"),
    }


def main() -> None:
    d = load()
    st = story_numbers()
    st["notes"] = NOTES
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = "PPK proposal performance: executive summary"
    slide_growth(prs, d, st)
    slide_speed_actions(prs, d, st)
    slide_quality(prs, d["issues"], st)
    out = REPORTING / "PPK_Executive_Summary.pptx"
    prs.save(out)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
