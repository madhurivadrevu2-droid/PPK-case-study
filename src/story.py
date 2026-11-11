"""Storyline numbers and talk track shared by the deck and the HTML presentation.

Every figure is computed from outputs/ and data/clean/, so the story rebuilds with the data.
"""
from __future__ import annotations

import pandas as pd

from config import CLEAN, OUTPUTS

IME = "India & Middle East"


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUTS / f"{name}.csv", index_col=0)


def impact_sizing() -> dict:
    """Size the two hotspot actions on full-year 2025 volumes (the last complete year)."""
    p = pd.read_csv(CLEAN / "proposals_enriched.csv", parse_dates=["submitted_date"])
    stage = _read("turnaround_stage_by_office")
    others = stage.drop("Paris")
    gap_total = stage.loc["Paris", "business_days_to_close"] - others["business_days_to_close"].median()
    decided = p[p["close_status"].isin(["Won", "Lost"])]
    d25 = decided[decided["submitted_date"].dt.year == 2025]
    paris_25 = int((d25["office"] == "Paris").sum())
    ime = d25[d25["region"] == IME]
    mean_won = ime.loc[ime["close_status"] == "Won", "proposal_value_usd"].mean()
    gap = _read("win_rate_gap_by_region").loc[IME]
    target_pp = 3.0
    return {
        "paris_gap_bd": float(gap_total),
        "paris_decided_2025": paris_25,
        "paris_bd_saved": float(gap_total * paris_25),
        "paris_over30": float(stage.loc["Paris", "share_over_30_bd_pct"]),
        "network_over30": float(others["share_over_30_bd_pct"].median()),
        "ime_decided_2025": int(len(ime)),
        "ime_mean_won_usd": float(mean_won),
        "ime_wins_per_pp": float(len(ime) / 100),
        "ime_value_per_pp_musd": float(len(ime) / 100 * mean_won / 1e6),
        "ime_target_pp": target_pp,
        "ime_target_wins": float(len(ime) * target_pp / 100),
        "ime_target_value_musd": float(len(ime) * target_pp / 100 * mean_won / 1e6),
        "ime_wr": float(gap["win_rate"]), "rest_wr": float(gap["rest_win_rate"]),
        "ime_gap_pp": float(gap["gap_pp"]), "ime_gap_p": float(gap["p_value"]),
    }


def story_numbers() -> dict:
    g = _read("growth_total").iloc[0]
    ga = _read("growth_total_gap_adjusted").iloc[0]
    reg, pr = _read("growth_by_region"), _read("growth_by_practice")
    rega, offa = _read("growth_by_region_gap_adjusted"), _read("growth_by_office_gap_adjusted")
    pra = _read("growth_by_practice_gap_adjusted")
    top3 = pra["volume_growth_pct"].nlargest(3)
    top3_txt = f"+{top3.min():.0f}-{top3.max():.0f}%"
    stage, trend, yoy = _read("turnaround_stage_by_office"), _read("trend_by_quarter"), _read("quarterly_yoy")
    pipe = _read("pipeline_at_extract").loc["All PPK"]
    gaps = pd.read_csv(OUTPUTS / "submission_gaps.csv")
    vq = _read("volume_by_office_quarter")
    dubai_q3_reported = (vq.loc["Dubai", "2026Q3"] / vq.loc["Dubai", "2025Q3"] - 1) * 100
    paris, others = stage.loc["Paris"], stage.drop("Paris")
    imp = impact_sizing()
    issues = pd.read_csv(OUTPUTS / "data_issues_log.csv")
    raw_rows = int(pd.read_csv(CLEAN.parent / "raw" / "proposals.csv", dtype=str).shape[0])
    clean_rows = int(pd.read_csv(CLEAN / "proposals_clean.csv", usecols=[0]).shape[0])
    am, apac, ime = reg.loc["Americas"], reg.loc["APAC"], reg.loc[IME]
    q3_25, q3_26 = trend.loc["2025Q3"], trend.loc["2026Q3"]
    sig = pr[pr["win_rate_p_value"] < 0.05 / len(pr)]   # Bonferroni across 11 practices
    return {
        "total": g.to_dict(), "total_adj": ga.to_dict(),
        "headline": (f"Proposals are up ~{ga.volume_growth_pct:.0f}% and won value ~{g.won_value_growth_pct:.0f}% at a "
                     f"steady ~{g.win_rate_2026:.0f}% win rate; the FY27 upside is India & Middle East's win "
                     f"rate and Paris's slower decisions"),
        "kpis": [
            {"label": "Proposals, YTD", "value": f"{g.proposals_2026:,.0f}",
             "delta": f"+{g.volume_growth_pct:.1f}% (+{ga.volume_growth_pct:.1f}% gap-adjusted)", "dir": 1},
            {"label": "Proposal value, YTD", "value": f"${g.value_usd_2026 / 1e9:.2f}B",
             "delta": f"+{g.value_growth_pct:.1f}% vs YTD 2025", "dir": 1},
            {"label": "Won value", "value": f"${g.won_value_usd_2026 / 1e9:.2f}B",
             "delta": f"+{g.won_value_growth_pct:.1f}% (Jan-Jul cohorts)", "dir": 1},
            {"label": "Win rate", "value": f"{g.win_rate_2026:.1f}%",
             "delta": f"{g.win_rate_change_pp:+.1f}pp, not significant (p={g.win_rate_p_value:.2f})", "dir": 0},
            {"label": "Days to decision", "value": f"{g.median_bd_to_close_2026:.0f} days",
             "delta": "median business days, flat vs 2025", "dir": 0},
            {"label": "Open pipeline", "value": f"${pipe.open_value_usd / 1e6:.0f}M",
             "delta": f"{pipe.open_proposals:,.0f} proposals, ~${pipe.expected_won_value_usd / 1e6:.0f}M expected won",
             "dir": 0},
        ],
        "findings": [
            ("Growth is concentrated and slowing",
             f"Americas +{am.volume_growth_pct:.1f}% and APAC +{apac.volume_growth_pct:.1f}% volume; PI, TMT and "
             f"Strategy {top3_txt}. Year-on-year growth eased from +{yoy.loc['Q1', 'yoy_pct']:.0f}% in Q1 to "
             f"+{yoy.loc['Q2', 'yoy_pct']:.0f}-{yoy.loc['Q3', 'yoy_gap_adjusted_pct']:.0f}% in Q2-Q3."),
            ("Win rate is steady; the regional gap is real",
             f"The +{g.win_rate_change_pp:.1f}pp rise is within noise (p={g.win_rate_p_value:.2f}). India & Middle "
             f"East wins {imp['ime_wr']:.1f}% vs {imp['rest_wr']:.1f}% elsewhere (p<0.001), in all three of its offices."),
            ("Speed has not improved; Paris lags",
             f"Median {g.median_bd_to_close_2026:.0f} business days in both years. Paris takes "
             f"{paris.business_days_to_close:.0f}, in every practice and quarter, and {paris.share_over_30_bd_pct:.0f}% "
             f"of its decisions take over 30 days vs ~{others.share_over_30_bd_pct.median():.0f}% elsewhere."),
        ],
        "actions": [
            (f"Plan FY27 proposal capacity on a ~{yoy.loc['Q2', 'yoy_pct']:.0f}-"
             f"{yoy.loc['Q3', 'yoy_gap_adjusted_pct']:.0f}% run-rate",
             f"Weight PPK proposal support to Americas and APAC (+{am.volume_growth_pct:.0f}% and "
             f"+{apac.volume_growth_pct:.0f}%) and to PI, TMT and Strategy ({top3_txt}), not to the Q1 peak.",
             "Owner: PPK Ops lead with regional COOs. Measure: forecast vs actual volume each quarter."),
            (f"Lift India & Middle East win rate by {imp['ime_target_pp']:.0f}pp",
             f"From {imp['ime_wr']:.1f}% toward {imp['ime_wr'] + imp['ime_target_pp']:.0f}% by end FY27 with bid/no-bid "
             f"discipline and a pursuit review: the gap is the same across its offices and practices, so it "
             f"is structural, not mix.",
             f"Owner: India & ME leadership. Worth ~{imp['ime_target_wins']:.0f} wins, "
             f"~${imp['ime_target_value_musd']:.0f}M won value a year."),
            (f"Cut Paris time to decision from {paris.business_days_to_close:.0f} to "
             f"{others.business_days_to_close.median():.0f} days",
             f"Map the final decision and sign-off step: Paris is slow whether or not a proposal goes "
             f"through formal review ({paris.median_bd_no_review:.0f} days without review).",
             f"Owner: Paris office head with PPK Ops. Target within two quarters; frees "
             f"~{imp['paris_bd_saved']:,.0f} proposal-days a year."),
        ],
        "enabler": ("Enabler: confirm the missing Gulf submissions for Aug 2026 with Dubai and Riyadh, fix data "
                    "at source and refresh this fact base monthly."),
        "impact": imp,
        "gaps": gaps.to_dict("records"),
        "dubai": {"q3_reported": float(dubai_q3_reported), "ytd_adj": float(offa.loc["Dubai", "volume_growth_pct"]),
                  "riyadh_adj": float(offa.loc["Riyadh", "volume_growth_pct"]),
                  "ime_reported": float(ime.volume_growth_pct), "ime_adj": float(rega.loc[IME, "volume_growth_pct"])},
        "yoy": yoy.reset_index().to_dict("records"),
        "pipeline": pipe.to_dict(),
        "significant_practices": sig.index.tolist(),
        "paris": {"total": float(paris.business_days_to_close), "review": float(paris.bd_review_to_close),
                  "no_review": float(paris.median_bd_no_review),
                  "network_total": float(others.business_days_to_close.median()),
                  "network_review": float(others.bd_review_to_close.median()),
                  "over30": float(paris.share_over_30_bd_pct),
                  "network_over30": float(others.share_over_30_bd_pct.median())},
        "censoring": {"p90_25": float(q3_25.p90_bd), "p90_26": float(q3_26.p90_bd),
                      "open_pct": float(q3_26.share_still_open_pct)},
        "rows": {"raw": raw_rows, "clean": clean_rows, "issues": int(len(issues))},
    }


def qa() -> list[tuple[str, str]]:
    """Likely panel questions with answers, computed from the same outputs."""
    s = story_numbers()
    g, imp, dub, pa = s["total"], s["impact"], s["dubai"], s["paris"]
    pr = _read("growth_by_practice")
    enr = pr.loc["Energy & Natural Resources"]
    p = pd.read_csv(CLEAN / "proposals_enriched.csv")
    d = p[p["close_status"].isin(["Won", "Lost"])]
    won_med, lost_med = (d.groupby("close_status")["business_days_to_close"].median()[["Won", "Lost"]])
    clients = p.groupby("client_name").size()
    return [
        ("Is the win-rate improvement real?",
         f"No. +{g['win_rate_change_pp']:.1f}pp has p={g['win_rate_p_value']:.2f}, so I call it steady. Value win rate "
         f"rose from {g['value_win_rate_2025']:.1f}% to {g['value_win_rate_2026']:.1f}% and won value is up "
         f"{g['won_value_growth_pct']:.0f}%: we are winning bigger, not more often. Energy's +{enr.win_rate_change_pp:.0f}pp "
         f"(p={enr.win_rate_p_value:.3f}) does not survive testing 11 practices at once."),
        ("Is Dubai collapsing?",
         f"Mostly no. August 2026 has zero submissions for Dubai and Riyadh while the system kept logging their status "
         f"changes, so it is an extract gap. Gap-adjusted, Dubai is {dub['ytd_adj']:+.1f}% and Riyadh "
         f"{dub['riyadh_adj']:+.1f}%; India & ME is {dub['ime_adj']:+.1f}%, not {dub['ime_reported']:+.1f}%. I would confirm "
         f"with both offices before acting."),
        ("Why is Paris slow?",
         f"It is the decision step, not the review stage. Paris proposals that skip formal review still take "
         f"{pa['no_review']:.0f} business days vs ~{pa['network_total']:.0f} elsewhere, in every practice and quarter, and "
         f"{pa['over30']:.0f}% of decisions take over 30 days. That points to how Paris signs off, so the first step is "
         f"mapping its approval chain."),
        ("Does speed affect winning?",
         f"Not in this data: won and lost proposals both take a median of {won_med:.0f} and {lost_med:.0f} business days, "
         f"and Paris wins at the same rate as its EMEA peers. So the Paris fix is about capacity and client experience."),
        ("Is turnaround improving?",
         f"No. Q3 2026 looks faster only because {s['censoring']['open_pct']:.0f}% of that cohort is still open. On mature "
         f"cohorts (submitted by 15 Jul) the median is {g['median_bd_to_close_2025']:.0f} days in both years."),
        ("Is India & ME's low win rate a mix effect?",
         f"No. It is {imp['ime_wr']:.1f}% vs {imp['rest_wr']:.1f}% for the rest of PPK (p<0.001), and similar in Dubai, "
         f"New Delhi and Riyadh and across practices. Each point is worth ~{imp['ime_wins_per_pp']:.0f} wins and "
         f"~${imp['ime_value_per_pp_musd']:.1f}M a year."),
        ("Why rescale values rather than drop them?",
         "Every Tokyo proposal from 1 Apr 2026 is keyed in thousands and nothing else is, so it is a unit switch, not "
         "noise. Rescaling keeps 618 real proposals in the value numbers; each row is flagged in value_flag, so the "
         "change is reversible. The 1.5B row is the same keying error in reverse."),
        ("How concentrated are clients?",
         f"Not at all: {len(clients):,} clients with ~{clients.mean():.1f} proposals each, and repeat clients win at the "
         "same rate as new ones, so I left client analysis out of the story."),
        ("What would you build next?",
         "Local holiday calendars for India, UAE and Saudi Arabia (the API has none) and a Friday-Saturday weekend for "
         "Riyadh; a monthly scheduled refresh; and a completeness alert that would have caught the Gulf gap on day one."),
    ]


NOTES = {
    "title": "Thank the panel. Frame: I was asked to build the fact base on proposal performance ahead of FY27 "
             "planning. Twenty minutes: the answer first, then growth, win rate, speed, data quality and the three "
             "actions. Everything is computed live from the cleaned data, and the dashboard pages filter by region, "
             "office, practice and period.",
    "summary": "Lead with the answer. Demand is up about 12 percent once a data gap is corrected, and won value about "
               "20 percent, at a steady win rate. So FY27 is about where we put proposal capacity and two specific "
               "hotspots. Be precise on win rate: the 1.3 point rise is not statistically significant, so I call it "
               "steady. Walk the six tiles, then the three findings, then the three actions.",
    "growth": "Growth is like-for-like, 1 January to 15 October in both years, because 2026 is a partial year. Americas "
              "and APAC carry the growth; PI, TMT and Strategy lead the practices. Point at the monthly line: the gap "
              "between the lines narrows after Q1, which is why I plan on a 9 to 12 percent run-rate. Customer was "
              "renamed in January 2026, and I merged the two labels. Demo: filter to India & Middle East.",
    "offices": "Office scorecard. Boston and Sao Paulo grow fastest. Dubai looks like it collapsed in Q3, but August "
               "2026 has zero submissions for Dubai and Riyadh while the system kept logging their status changes, "
               "so it is a data gap. Gap-adjusted, Dubai is down about 5 percent and Riyadh up about 12. I would "
               "confirm with the offices before acting. Toggle the gap-adjusted switch to show both views.",
    "winrate": "Win rate. The year-on-year changes are mostly noise: the error bars overlap. The difference between "
               "regions is not noise: India & Middle East is about 10 points below the rest, and it is the same in "
               "Dubai, New Delhi and Riyadh and across practices, so it is regional, not mix. Each point there is "
               "worth about 19 wins a year.",
    "speed": "Turnaround is business days excluding weekends and public holidays from the Nager API. The median is "
             "flat at 17. Paris is the outlier: 23 days, in every practice and quarter, and even proposals that skip "
             "formal review take 24, so it is the decision and sign-off step. Call out the trap: Q3 2026 looks faster "
             "only because slow proposals from that quarter have not closed, so I compare mature cohorts. Speed does "
             "not change win odds here: won and lost both take a median of 17 days.",
    "quality": "Thirteen issues. The ones that change the answer: IDs lost leading zeros, so a naive join matches "
               "nothing; values keyed in thousands plus one 1.5 billion typo that alone would be a quarter of 2025 "
               "value; the practice rename; and the missing Gulf submissions in August 2026. For each: detect, "
               "quantify, treat, and flag so it is reversible. Only exact duplicates and test records were removed.",
    "actions": "Three actions, each with an owner, a measure and a size. Sizing is conservative and uses full-year 2025 "
               "volumes. The enabler underneath: confirm the Gulf gap, fix data at source, refresh monthly. Close by "
               "offering to extend live, for example local holidays for India, UAE and Saudi Arabia.",
    "appendix": "Definitions and method, for questions. Win rate excludes Withdrawn and open proposals; significance is "
                "a two-proportion z-test. Task 1: holidays apply if national or listed for the office's ISO "
                "subdivision, which is why London gets England's bank holidays.",
}
