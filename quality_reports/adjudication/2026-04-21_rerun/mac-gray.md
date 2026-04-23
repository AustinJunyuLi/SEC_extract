---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: mac-gray
extraction: output/extractions/mac-gray.json
reference: reference/alex/mac-gray.json
filing_pages: data/filings/mac-gray/pages.json
diff_markdown: scoring/results/mac-gray_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/mac-gray_report.md
---

# Mac-Gray — rerun adjudication

## TL;DR
- **Disposition:** Targeted extractor fix recommended, but the current rerun is otherwise directionally strong.
- **Current rerun verdict:** The live rerun is much closer to filing truth than the legacy reference, especially on the start-of-process structure and the treatment of the anonymous NDA cohort. One formality call still needs tightening.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`51` · last_run=`2026-04-21T16:57:33.606677Z`
- Rows: `45` · hard=`0` · soft=`35` · info=`16`
- Diff burden vs Alex: matched=`23` · AI-only=`5` · Alex-only=`9` · cardinality mismatches=`1` · field disagreements=`25` · deal-level disagreements=`3`
- Top current flag codes: `date_inferred_from_context` × 16, `nda_without_bid_or_drop` × 16, `bid_range` × 7, `bidder_type_provisional` × 3, `final_round_inferred` × 2, `drop_agency_ambiguous` × 2
- Non-issue note: Capitalization-only `TargetName` noise and `DateEffective=null` are not treated as extraction defects here; the substantive deal-level issue is the acquirer-name correction.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — Filing pp. 34 / 47 identify the buyer-side entity as CSC ServiceWorks, Inc. The deal-level acquirer should be 'CSC ServiceWorks, Inc.', not Alex's provenance string about Pamplona's earlier purchase of CSC.
- **AI right, Alex wrong** — row 2 (`Party A` · `Target Interest` · `2013-04-05` · p.33), row 3 (`Party A` · `Bidder Interest` · `2013-04-08` · p.33): The Party A start-of-process is better split into 2013-04-05 `Target Interest` and 2013-04-08 `Bidder Interest` than collapsed into Alex's older single-row treatment.
- **AI right, Alex wrong** — The filing does not narrate 16 individualized 2013-07-25 drops for the anonymous financial NDA signers. The current rerun is right not to fabricate per-placeholder drop rows for the 16 anonymous NDA signers. Alex's aggregated drop row is a legacy shorthand, not filing-ground truth.
- **AI wrong, Alex right** — row 38 (`Party B` · `Bid` · `2013-09-18` · p.42): Party B's $21.50 indication on 2013-09-18 belongs in the formal round, not the informal round. The live rerun under-classifies that row.
- **Both defensible** — row 43 (`Party A` · `DropBelowInf` · `2013-09-23` · p.44), row 44 (`Party B` · `DropBelowInf` · `2013-09-23` · p.43): The 2013-09-23 `DropBelowInf` coding for Party A and Party B is defensible from the filing even if Alex or earlier runs used a different drop-family label.

## Flag Analysis
- The soft flags are dominated by the 16 NDA-only financial placeholders, which is expected under the current no-synthetic-drop rule. The remaining soft flags are largely agency or contingency judgment calls, not unsupported rows.

## Recommendation
- Reclassify Party B's 2013-09-18 $21.50 row as formal rather than informal.
- Keep the no-synthetic-drop treatment for the 16 anonymous NDA signers; that is the current rulebook's intended behavior.
