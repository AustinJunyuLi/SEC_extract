---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: medivation
extraction: output/extractions/medivation.json
reference: reference/alex/medivation.json
filing_pages: data/filings/medivation/pages.json
diff_markdown: scoring/results/medivation_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/medivation_report.md
---

# Medivation — rerun adjudication

## TL;DR
- **Disposition:** Ship-ready after reference refresh; no extraction blocker remains.
- **Current rerun verdict:** The live rerun is materially correct. The remaining divergence burden is driven mainly by Alex reference defects and one low-stakes round-extension inference choice.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`18` · last_run=`2026-04-21T16:57:33.421969Z`
- Rows: `21` · hard=`0` · soft=`10` · info=`8`
- Diff burden vs Alex: matched=`12` · AI-only=`5` · Alex-only=`6` · cardinality mismatches=`1` · field disagreements=`7` · deal-level disagreements=`3`
- Top current flag codes: `date_inferred_from_context` × 7, `final_round_inferred` × 6, `nda_without_bid_or_drop` × 3, `pre_nda_informal_bid` × 1, `unnamed_count_placeholder` × 1
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 1 (`Sanofi` · `Bid` · `2016-04-15` · p.24): Sanofi's first-contact bid belongs on 2016-04-15, the date Medivation received the letter, not on the letter's 2016-04-13 drafting date.
- **AI right, Alex wrong** — row 3 (`Pfizer` · `Bidder Interest` · `2016-05-02` · p.25): Pfizer's 2016-05-02 approach is a real `Bidder Interest` row; the filing describes Giordano expressing Pfizer's interest before any NDA or priced bid.
- **AI right, Alex wrong** — row 8 (`Sanofi` · `NDA` · `2016-07-05` · p.25), row 9 (`Strategic 1` · `NDA` · `2016-07-05` · p.25), row 10 (`Strategic 2` · `NDA` · `2016-07-05` · p.25): The July 5 disclosure that Medivation had entered into confidentiality agreements with 'several parties, including Sanofi' supports one Sanofi NDA plus two unnamed placeholders under the minimum-supported-count rule; Alex's undated Party A/Party B NDA rows are the older, less faithful encoding.
- **AI right, Alex wrong** — row 12 (`None` · `Final Round Inf Ann` · `2016-07-19` · p.26), row 14 (`None` · `Final Round Inf` · `2016-08-08` · p.26), row 15 (`None` · `Final Round Ann` · `2016-08-14` · p.26), row 17 (`Pfizer` · `Bid` · `2016-08-19` · p.27), row 18 (`None` · `Final Round` · `2016-08-19` · p.27), row 21 (`Pfizer` · `Executed` · `2016-08-20` · p.27, 27): The rerun's current round-date cluster corrects Alex's mis-dated 2016-08-14 block. The filing supports 2016-07-19 (`Final Round Inf Ann`), 2016-08-08 (`Final Round Inf`), 2016-08-10 (`Final Round Ann`), 2016-08-19 / 2016-08-20 Pfizer bids, and 2016-08-20 execution.
- **Both defensible** — row 16 (`None` · `Final Round Ext Ann` · `2016-08-19` · p.27), row 20 (`None` · `Final Round Ext` · `2016-08-20` · p.27): The added `Final Round Ext Ann` / `Final Round Ext` rows on 2016-08-19 and 2016-08-20 are plausible §K2 inferences from the advisors' 'best and final' reset, but Alex's omission of those extra extension rows is not a blocking error.

## Flag Analysis
- All current flags are soft/info only and are the expected mix of date anchoring, placeholder NDA atomization, and inferred round-structure flags. None of them indicate a missing or unsupported current row.

## Recommendation
- Regenerate the reference side for the Sanofi receipt-date correction and Alex's known final-round date errors.
- Optional prompt cleanup: keep 2016-08-19/2016-08-20 `Final Round Ext*` rows explicitly low-confidence, since the filing frames them as a best-and-final reset rather than an explicit extension notice.
