---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: stec
extraction: output/extractions/stec.json
reference: reference/alex/stec.json
filing_pages: data/filings/stec/pages.json
diff_markdown: scoring/results/stec_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/stec_report.md
---

# sTec — rerun adjudication

## TL;DR
- **Disposition:** Targeted extractor fix recommended before calling the deal fully clean.
- **Current rerun verdict:** The live rerun is much stronger than the earlier snapshot: it now carries the activist rows and the round structure. One dropout-agency call regressed and should be fixed.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`16` · last_run=`2026-04-21T16:57:33.681281Z`
- Rows: `36` · hard=`0` · soft=`3` · info=`13`
- Diff burden vs Alex: matched=`26` · AI-only=`7` · Alex-only=`0` · cardinality mismatches=`1` · field disagreements=`20` · deal-level disagreements=`3`
- Top current flag codes: `bid_range` × 3, `date_inferred_from_rough` × 2, `date_inferred_from_context` × 2, `unsolicited_letter_skipped` × 2, `bid_lower_only` × 1, `final_round_inferred` × 1
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 2 (`Balch Hill` · `Activist Sale` · `2012-11-16` · p.33), row 3 (`Balch Hill` · `Activist Sale` · `2012-12-06` · p.33), row 36 (`Potomac` · `Activist Sale` · `None` · p.33): The activist pressure should be split across Balch Hill and Potomac, not collapsed into Balch Hill alone or dropped.
- **AI right, Alex wrong** — row 15 (`None` · `Final Round Inf Ann` · `2013-04-23` · p.36), row 21 (`None` · `Final Round Inf` · `2013-05-03` · p.36), row 25 (`None` · `Final Round Ann` · `2013-05-16` · p.38), row 28 (`None` · `Final Round` · `2013-05-28` · p.38), row 29 (`None` · `Final Round Ext Ann` · `2013-05-29` · p.38), row 30 (`None` · `Final Round Ext` · `2013-05-30` · p.39): The current rerun now emits the round-structure rows that the older snapshot missed: `Final Round Inf Ann`, `Final Round Inf`, `Final Round Ann`, `Final Round`, `Final Round Ext Ann`, and `Final Round Ext`.
- **Both wrong** — row 26 (`Company H` · `Drop` · `2013-05-23` · p.38): Company H's 2013-05-23 exit should be target-initiated (`DropBelowInf`), not generic `Drop`. Alex made the same mistake; the filing says BofA told Company H its range was insufficient to move forward.
- **AI right, Alex wrong** — row 16 (`Company D` · `Bid` · `2013-04-23` · p.36): The single-bound Company D $5.60+ indication is represented correctly as a lower-only informal bid rather than as a collapsed point bid.
- **Both defensible** — row 36 (`Potomac` · `Activist Sale` · `None` · p.33): The undated Potomac activist row is a defensible way to preserve the filing's statement that Potomac later joined Balch Hill, even though the exact Potomac join date is not narrated.

## Flag Analysis
- The current flag mix is mostly healthy bid-shape and date-inference metadata. The substantive issue is not the validator profile; it is the regression on Company H's dropout agency.

## Recommendation
- Change Company H on 2013-05-23 from `Drop` to `DropBelowInf`.
- Keep the current activist and round-structure rows; those changes moved the live rerun closer to the filing.
