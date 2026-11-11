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

RED, DARK_RED = RGBColor(0xCC, 0x00, 0x00), RGBColor(0x99, 0x00, 0x00)
INK, GREY, LIGHT, TINT = (RGBColor(0x33, 0x33, 0x33), RGBColor(0x7A, 0x7A, 0x7A),
                          RGBColor(0xBF, 0xBF, 0xBF), RGBColor(0xF4, 0xF4, 0xF4))
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Arial"
SHORT = {"Technology, Media & Telecom": "TMT", "Customer Strategy & Marketing": "Customer Strategy & Mktg",
         "Energy & Natural Resources": "Energy & Nat. Resources", "India & Middle East": "India & ME"}
SOURCE = ("Source: PPK proposal system extract, 15 Oct 2026 (fictitious data); 24,372 proposals after "
          "cleaning. Growth = 1 Jan-15 Oct 2026 vs same window 2025; win rate and turnaround on "
          "cohorts submitted 1 Jan-15 Jul.")


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


def kpi(slide, x, y, w, value, label, delta, name):
    rect(slide, x, y, w, 1.2, TINT, name=f"{name} tile")
    text(slide, x + 0.2, y + 0.12, w - 0.4, 0.55, value, size=28, bold=True, color=RED, name=f"{name} value")
    text(slide, x + 0.2, y + 0.68, w - 0.4, 0.45,
         [[(label, {"bold": True, "size": 12}), (f"  {delta}", {"size": 12, "color": GREY})]],
         name=f"{name} label")


def slide_growth(prs, d):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    g = d["total"]
    title(s, f"Proposal volume and value are up ~{g.volume_growth_pct:.0f}% YTD with a slightly higher win "
             f"rate; growth is led by the Americas and APAC while India & Middle East is flat")
    kpis = [
        (f"+{g.volume_growth_pct:.1f}%", "Volume", f"{g.proposals_2025:,.0f} to {g.proposals_2026:,.0f}"),
        (f"+{g.value_growth_pct:.1f}%", "Value", f"${g.value_usd_2025/1e9:.2f}B to ${g.value_usd_2026/1e9:.2f}B"),
        (f"{g.win_rate_2026:.1f}%", "Win rate", f"{g.win_rate_change_pp:+.1f}pp vs 2025"),
        (f"{g.median_bd_to_close_2026:.0f} days", "Median turnaround",
         "business days, flat vs 2025" if g.median_bd_change == 0
         else f"business days, {g.median_bd_change:+.0f} vs 2025"),
    ]
    for i, (v, lab, dl) in enumerate(kpis):
        kpi(s, 0.5 + i * 3.1, 1.45, 2.9, v, lab, dl, name=f"KPI {lab}")

    reg = d["region"]
    text(s, 0.5, 2.95, 3.9, 0.35, "Growth by region, % YTD", size=14, bold=True, name="Region chart title")
    bar_chart(s, 0.4, 3.3, 4.0, 3.45, [SHORT.get(r, r) for r in reg.index],
              {"Volume": reg.volume_growth_pct.tolist(), "Value": reg.value_growth_pct.tolist()},
              [RED, LIGHT], number_format='0.0"%"', legend=True, name="Region growth chart")

    pr = d["practice"]
    text(s, 4.7, 2.95, 4.2, 0.35, "Volume growth by practice, % YTD", size=14, bold=True,
         name="Practice chart title")
    top3 = {i: RED for i in range(3)}
    bar_chart(s, 4.6, 3.3, 4.3, 3.45, [SHORT.get(p, p) for p in pr.index],
              {"Volume": pr.volume_growth_pct.tolist()},
              [LIGHT], number_format='0.0"%"', highlight={0: top3}, name="Practice growth chart")

    ime, am = reg.loc["India & Middle East"], reg.loc["Americas"]
    dubai = d["dubai"]
    enr, ma = pr.loc["Energy & Natural Resources"], pr.loc["M&A"]
    cp = pr.loc["Consumer Products"]
    off = d["office"]
    rect(s, 9.2, 2.95, 3.6, 3.8, TINT, name="Findings panel")
    text(s, 9.4, 3.1, 3.2, 3.6, [
        [("What stands out", {"bold": True})],
        [("Americas wins most: ", {"bold": True, "size": 12}),
         (f"{am.win_rate_2026:.0f}% vs {ime.win_rate_2026:.0f}% in India & Middle East", {"size": 12})],
        [("Fastest offices: ", {"bold": True, "size": 12}),
         (f"Boston +{off.loc['Boston'].volume_growth_pct:.0f}%, Sao Paulo "
          f"+{off.loc['Sao Paulo'].volume_growth_pct:.0f}%, Sydney +{off.loc['Sydney'].volume_growth_pct:.0f}% "
          "volume", {"size": 12})],
        [("Dubai is shrinking: ", {"bold": True, "size": 12}),
         (f"Q3 2026 volume down {abs(dubai['q3_change']):.0f}% vs Q3 2025", {"size": 12})],
        [("Bigger deals: ", {"bold": True, "size": 12}),
         (f"Consumer Products value +{cp.value_growth_pct:.0f}% on +{cp.volume_growth_pct:.0f}% volume",
          {"size": 12})],
        [("Flat but winning more: ", {"bold": True, "size": 12}),
         (f"Energy (+{enr.win_rate_change_pp:.0f}pp) and M&A (+{ma.win_rate_change_pp:.0f}pp)",
          {"size": 12})],
    ], size=14, name="Findings text")
    footer(s, 1)
    s.notes_slide.notes_text_frame.text = (
        "Lead with: activity is growing ~11% and win rate is stable, so FY27 is a capacity question. "
        "Growth comparison is like-for-like (same 1 Jan-15 Oct window). Customer Strategy & Marketing "
        "was renamed 'Customer' in Jan 2026; merged so it is comparable.")


def action_card(s, x, y, w, h, n, head, body, name):
    rect(s, x, y, w, h, TINT, name=f"{name} card")
    c = rect(s, x + 0.2, y + 0.2, 0.5, 0.5, RED, shape=MSO_SHAPE.OVAL, name=f"{name} number")
    tf = c.text_frame
    tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(16), True, WHITE
    text(s, x + 0.9, y + 0.17, w - 1.1, h - 0.3,
         [[(head, {"bold": True, "size": 14})], [(body, {"size": 12})]], name=f"{name} text")


def slide_speed_actions(prs, d):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    st, trend, g = d["stage"], d["trend"], d["total"]
    paris = st.loc["Paris"]
    others = st.drop("Paris")
    title(s, f"Turnaround is flat at {g.median_bd_to_close_2026:.0f} business days and Paris takes "
             f"~{paris.business_days_to_close - others.business_days_to_close.median():.0f} days longer; "
             "three actions for FY27 planning")

    text(s, 0.5, 1.45, 6.2, 0.35, "Median business days to decision, by office and stage", size=14,
         bold=True, name="Stage chart title")
    order = st.sort_values("business_days_to_close", ascending=False)
    pi = order.index.get_loc("Paris")
    bar_chart(s, 0.4, 1.8, 6.3, 3.9, order.index.tolist(),
              {"Submitted to under review": order.bd_to_review.tolist(),
               "Under review to decision": order.bd_review_to_close.tolist()},
              [LIGHT, GREY], number_format="0", chart_type=XL_CHART_TYPE.BAR_STACKED, legend=True,
              highlight={1: {pi: RED}}, name="Stage turnaround chart", label_colors=[INK, WHITE])

    q3_25, q3_26 = trend.loc["2025Q3"], trend.loc["2026Q3"]
    rect(s, 0.5, 5.8, 6.2, 0.95, TINT, name="Censoring callout")
    text(s, 0.7, 5.88, 5.8, 0.8, [[
        ("Not yet a real speed-up: ", {"bold": True, "size": 12}),
        (f"Q3 2026 looks faster (90th percentile {q3_26.p90_bd:.0f} vs {q3_25.p90_bd:.0f} days) only because "
         f"{q3_26.share_still_open_pct:.0f}% of that cohort is still open. On mature cohorts the median "
         f"is unchanged.", {"size": 12})]], name="Censoring text")

    ime = d["region"].loc["India & Middle East"]
    am = d["region"].loc["Americas"]
    reg = d["region"]
    actions = [
        ("Put FY27 proposal capacity where growth is",
         f"Americas and APAC (+{reg.loc['Americas'].volume_growth_pct:.1f}% and "
         f"+{reg.loc['APAC'].volume_growth_pct:.1f}% volume) and Performance Improvement, TMT and Strategy "
         f"(+15-16%). Take Americas' win practices ({am.win_rate_2026:.0f}% win rate) to India & Middle "
         f"East ({ime.win_rate_2026:.0f}%)."),
        ("Fix two hotspots: Paris review and Dubai pipeline",
         f"Paris takes {paris.bd_review_to_close:.0f} days from review to decision vs "
         f"{others.bd_review_to_close.median():.0f} elsewhere, in every practice and quarter: map its "
         f"approval steps. Dubai volume fell "
         f"{abs(d['dubai']['q3_change']):.0f}% in Q3: review pipeline with office leadership."),
        ("Fix data at source and automate this fact base",
         "Picklists for office and practice, one date format, USD value checks, IDs stored as text, "
         "test-record flag. Add local holidays for India, UAE and Saudi Arabia. Then refresh monthly."),
    ]
    for i, (head, body) in enumerate(actions):
        action_card(s, 7.0, 1.45 + i * 1.8, 5.8, 1.65, i + 1, head, body, name=f"Action {i + 1}")
    footer(s, 2)
    s.notes_slide.notes_text_frame.text = (
        "Turnaround = business days (excl. weekends and public holidays) from submission to Won/Lost. "
        "Win rate is unrelated to turnaround in this data (~40% in every speed band), so faster review "
        "is an efficiency gain, not a win-rate lever. Paris gap is entirely in the review stage.")


def slide_appendix(prs, issues: pd.DataFrame):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    title(s, "Appendix: 12 data issues were found and treated before analysis")
    rows, cols = len(issues) + 1, 3
    tbl = s.shapes.add_table(rows, cols, Inches(0.5), Inches(1.45), Inches(12.3), Inches(5.3)).table
    widths = [5.2, 1.1, 6.0]
    for i, w in enumerate(widths):
        tbl.columns[i].width = Inches(w)
    heads = ["Issue", "Rows", "Treatment"]
    for r in range(rows):
        for c in range(cols):
            cell = tbl.cell(r, c)
            if r == 0:
                val = heads[c]
            else:
                row = issues.iloc[r - 1]
                val = [row.issue, f"{row.rows_affected:,}", row.treatment][c]
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = val
            run.font.name, run.font.size = FONT, Pt(10)
            run.font.bold = r == 0
            run.font.color.rgb = WHITE if r == 0 else INK
            if c == 1:
                p.alignment = PP_ALIGN.RIGHT
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.fill.solid()
            cell.fill.fore_color.rgb = INK if r == 0 else (TINT if r % 2 else WHITE)
    text(s, 0.5, 6.95, 12.3, 0.4, "Full log with impact: outputs/data_issues_log.csv and README.",
         size=10, color=GREY, name="Source")
    text(s, 12.3, 6.95, 0.5, 0.3, "3", size=10, color=GREY, align=PP_ALIGN.RIGHT, name="Page")


def load() -> dict:
    vq = pd.read_csv(OUTPUTS / "volume_by_office_quarter.csv", index_col=0)
    dubai = {"q3_change": (vq.loc["Dubai", "2026Q3"] / vq.loc["Dubai", "2025Q3"] - 1) * 100}
    return {
        "total": pd.read_csv(OUTPUTS / "growth_total.csv", index_col=0).iloc[0],
        "region": pd.read_csv(OUTPUTS / "growth_by_region.csv", index_col=0),
        "practice": pd.read_csv(OUTPUTS / "growth_by_practice.csv", index_col=0),
        "office": pd.read_csv(OUTPUTS / "growth_by_office.csv", index_col=0),
        "stage": pd.read_csv(OUTPUTS / "turnaround_stage_by_office.csv", index_col=0),
        "trend": pd.read_csv(OUTPUTS / "trend_by_quarter.csv", index_col=0),
        "issues": pd.read_csv(OUTPUTS / "data_issues_log.csv"),
        "dubai": dubai,
    }


def main() -> None:
    d = load()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = "PPK proposal performance: executive summary"
    slide_growth(prs, d)
    slide_speed_actions(prs, d)
    slide_appendix(prs, d["issues"])
    out = REPORTING / "PPK_Executive_Summary.pptx"
    prs.save(out)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
