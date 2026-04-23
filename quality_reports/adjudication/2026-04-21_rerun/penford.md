---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: penford
extraction: output/extractions/penford.json
reference: reference/alex/penford.json
filing_pages: data/filings/penford/pages.json
diff_markdown: scoring/results/penford_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/penford_report.md
---

# Penford — rerun adjudication

## TL;DR
- **Disposition:** Blocked. Fix and rerun before treating this deal as adjudicated-good.
- **Current rerun verdict:** Penford remains the only hard-blocked deal. The live rerun contains real signal, but it still ships six §P-G2 hard failures and one unsupported Ingredion bid row.

## Current rerun snapshot
- `state/progress.json`: status=`validated` · flag_count=`39` · last_run=`2026-04-21T16:57:33.571052Z`
- Rows: `35` · hard=`6` · soft=`14` · info=`19`
- Diff burden vs Alex: matched=`17` · AI-only=`8` · Alex-only=`6` · cardinality mismatches=`2` · field disagreements=`2` · deal-level disagreements=`1`
- Top current flag codes: `resolved_name_not_observed` × 10, `bid_type_inference_note` × 6, `bid_type_unsupported` × 6, `date_inferred_from_context` × 4, `bid_range` × 3, `date_inferred_from_rough` × 2
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 1 (`2007 unsolicited party` · `NDA` · `2007-07-01` · p.29), row 2 (`2007 unsolicited party` · `Drop` · `2007-07-01` · p.29), row 3 (`2009 unsolicited party` · `NDA` · `2009-07-01` · p.29), row 4 (`2009 unsolicited party` · `Drop` · `2009-07-01` · p.29): The 2007 and 2009 stale-prior NDA/drop history belongs in the dataset. Alex's generic unlabeled rows encode the same history less faithfully.
- **AI right, Alex wrong** — row 18 (`Party B` · `Drop` · `2014-09-12` · p.34), row 23 (`Party F` · `Drop` · `2014-09-29` · p.36): Party B's 2014-09-12 withdrawal and Party F's 2014-09-29 withdrawal are explicit in the filing and should remain in the row set.
- **Both wrong** — row 29 (`Ingredion` · `Bid` · `2014-10-08` · p.37): The current 2014-10-08 Ingredion bid row is unsupported: the cited text is only Sidley Austin circulating a revised merger agreement draft. Alex is also wrong because the reference side effectively pulls execution too early.
- **AI right, Alex wrong** — row 35 (`Ingredion` · `Executed` · `2014-10-14` · p.39, 39): Execution belongs on 2014-10-14, not on Alex's earlier 2014-10-08 date.
- **Both defensible** — row 32 (`Party A` · `Bid` · `2014-10-14` · p.38): Party A's 2014-10-14 $16 indication can stay informal despite the filing's 'formal letter' wording, because the content is still a non-binding indication of interest. The current problem is not the row's existence; it is the missing §P-G2 evidence note.

## Flag Analysis
- This is the one deal where validator hard findings are substantive, not bookkeeping noise. The missing `bid_type_inference_note` content and the unsupported 2014-10-08 bid row are real output problems.

## Recommendation
- Delete the unsupported 2014-10-08 Ingredion bid row currently sitting at row 29.
- Populate actual `bid_type_inference_note` values for rows 9, 10, 25, 26 and 32 so the validator sees the evidence that the current reasoning already implies.
