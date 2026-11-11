# Presenter script: PPK proposal performance

Open `PPK_Proposal_Performance.html` in Edge or Chrome. Use the arrow keys to move, N for these notes on screen, F for full screen, and Ctrl+P to save a PDF. About 20 minutes plus questions.

**Headline:** Proposals are up ~12% and won value ~20% at a steady ~42% win rate; the FY27 upside is India & Middle East's win rate and Paris's slower decisions.

## Talk track

### 1. Title

Thank the panel. Frame: I was asked to build the fact base on proposal performance ahead of FY27 planning. Twenty minutes: the answer first, then growth, win rate, speed, data quality and the three actions. Everything is computed live from the cleaned data, and the dashboard pages filter by region, office, practice and period.

### 2. Executive summary

Lead with the answer. Demand is up about 12 percent once a data gap is corrected, and won value about 20 percent, at a steady win rate. So FY27 is about where we put proposal capacity and two specific hotspots. Be precise on win rate: the 1.3 point rise is not statistically significant, so I call it steady. Walk the six tiles, then the three findings, then the three actions.

### 3. Growth

Growth is like-for-like, 1 January to 15 October in both years, because 2026 is a partial year. Americas and APAC carry the growth; PI, TMT and Strategy lead the practices. Point at the monthly line: the gap between the lines narrows after Q1, which is why I plan on a 9 to 12 percent run-rate. Customer was renamed in January 2026, and I merged the two labels. Demo: filter to India & Middle East.

### 4. Office scorecard

Office scorecard. Boston and Sao Paulo grow fastest. Dubai looks like it collapsed in Q3, but August 2026 has zero submissions for Dubai and Riyadh while the system kept logging their status changes, so it is a data gap. Gap-adjusted, Dubai is down about 5 percent and Riyadh up about 12. I would confirm with the offices before acting. Toggle the gap-adjusted switch to show both views.

### 5. Win rate

Win rate. The year-on-year changes are mostly noise: the error bars overlap. The difference between regions is not noise: India & Middle East is about 10 points below the rest, and it is the same in Dubai, New Delhi and Riyadh and across practices, so it is regional, not mix. Each point there is worth about 19 wins a year.

### 6. Speed

Turnaround is business days excluding weekends and public holidays from the Nager API. The median is flat at 17. Paris is the outlier: 23 days, in every practice and quarter, and even proposals that skip formal review take 24, so it is the decision and sign-off step. Call out the trap: Q3 2026 looks faster only because slow proposals from that quarter have not closed, so I compare mature cohorts. Speed does not change win odds here: won and lost both take a median of 17 days.

### 7. Data quality

Thirteen issues. The ones that change the answer: IDs lost leading zeros, so a naive join matches nothing; values keyed in thousands plus one 1.5 billion typo that alone would be a quarter of 2025 value; the practice rename; and the missing Gulf submissions in August 2026. For each: detect, quantify, treat, and flag so it is reversible. Only exact duplicates and test records were removed.

### 8. Actions

Three actions, each with an owner, a measure and a size. Sizing is conservative and uses full-year 2025 volumes. The enabler underneath: confirm the Gulf gap, fix data at source, refresh monthly. Close by offering to extend live, for example local holidays for India, UAE and Saudi Arabia.

### 9. Appendix: definitions and method

Definitions and method, for questions. Win rate excludes Withdrawn and open proposals; significance is a two-proportion z-test. Task 1: holidays apply if national or listed for the office's ISO subdivision, which is why London gets England's bank holidays.

## Live demo moves

- Growth page: set Region to India & Middle East, then untick Gap-adjusted to show how the August gap changes the answer.
- Office scorecard: set Practice to one practice and show that the Paris and India & ME patterns hold.
- Win rate page: point at the overlapping 2025 and 2026 ranges (noise) vs the gap between regions (real).
- Speed page: set Office to Paris, then Period to a single quarter.

## Likely questions

**Is the win-rate improvement real?**

No. +1.3pp has p=0.13, so I call it steady. Value win rate rose from 38.9% to 41.7% and won value is up 20%: we are winning bigger, not more often. Energy's +8pp (p=0.014) does not survive testing 11 practices at once.

**Is Dubai collapsing?**

Mostly no. August 2026 has zero submissions for Dubai and Riyadh while the system kept logging their status changes, so it is an extract gap. Gap-adjusted, Dubai is -4.8% and Riyadh +11.9%; India & ME is +6.6%, not -1.2%. I would confirm with both offices before acting.

**Why is Paris slow?**

It is the decision step, not the review stage. Paris proposals that skip formal review still take 24 business days vs ~16 elsewhere, in every practice and quarter, and 30% of decisions take over 30 days. That points to how Paris signs off, so the first step is mapping its approval chain.

**Does speed affect winning?**

Not in this data: won and lost proposals both take a median of 17 and 17 business days, and Paris wins at the same rate as its EMEA peers. So the Paris fix is about capacity and client experience.

**Is turnaround improving?**

No. Q3 2026 looks faster only because 16% of that cohort is still open. On mature cohorts (submitted by 15 Jul) the median is 17 days in both years.

**Is India & ME's low win rate a mix effect?**

No. It is 32.6% vs 43.1% for the rest of PPK (p<0.001), and similar in Dubai, New Delhi and Riyadh and across practices. Each point is worth ~19 wins and ~$6.9M a year.

**Why rescale values rather than drop them?**

Every Tokyo proposal from 1 Apr 2026 is keyed in thousands and nothing else is, so it is a unit switch, not noise. Rescaling keeps 618 real proposals in the value numbers; each row is flagged in value_flag, so the change is reversible. The 1.5B row is the same keying error in reverse.

**How concentrated are clients?**

Not at all: 8,423 clients with ~2.9 proposals each, and repeat clients win at the same rate as new ones, so I left client analysis out of the story.

**What would you build next?**

Local holiday calendars for India, UAE and Saudi Arabia (the API has none) and a Friday-Saturday weekend for Riyadh; a monthly scheduled refresh; and a completeness alert that would have caught the Gulf gap on day one.
