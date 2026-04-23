---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: zep
extraction: output/extractions/zep.json
reference: reference/alex/zep.json
filing_pages: data/filings/zep/pages.json
diff_markdown: scoring/results/zep_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/zep_report.md
---

# Zep — rerun adjudication

## TL;DR
- **Disposition:** Fix and rerun. The current saved extraction still misses material round-structure and final-bid formality details.
- **Current rerun verdict:** The rerun is far better than the over-fabricated older pipeline, but the live output still under-encodes the phase-1 round structure and mishandles the NMC endgame formality.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`114` · last_run=`2026-04-21T16:57:33.496221Z`
- Rows: `51` · hard=`0` · soft=`66` · info=`48`
- Diff burden vs Alex: matched=`9` · AI-only=`9` · Alex-only=`10` · cardinality mismatches=`2` · field disagreements=`6` · deal-level disagreements=`3`
- Top current flag codes: `unnamed_count_placeholder` × 29, `date_inferred_from_context` × 26, `bidder_type_ambiguous` × 19, `nda_without_bid_or_drop` × 19, `bid_range` × 7, `date_inferred_from_rough` × 6
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 45 (`New Mountain Capital` · `Restarted` · `2015-02-10` · p.39), row 46 (`New Mountain Capital` · `Bid` · `2015-02-19` · p.39): The restart date / first phase-2 bid sequence is correct as saved: NMC re-engages on 2015-02-10 and delivers the $19.25 indication on 2015-02-19. Alex's dating compresses those into the wrong order.
- **AI wrong, Alex right** — Filing pp. 36-37: March 27 process letter; April 14 IOI deadline. The live rerun still omits the phase-1 `Final Round Inf Ann` and `Final Round Inf` structure. Alex is directionally right that those round markers belong in the dataset.
- **AI right, Alex wrong** — Filing p. 38: the May 7 step is data-room access and continued diligence, not a new final-round deadline. Alex's extra 2014-05-07 `Final Round` row is over-coded; the live rerun is right not to create a second formal-round event there.
- **Both wrong** — row 49 (`New Mountain Capital` · `Bid` · `2015-03-13` · p.40), row 50 (`New Mountain Capital` · `Bid` · `2015-03-29` · p.41): The key final formal bid should attach to NMC's 2015-03-13 'best and final' communication. Alex places the formal bid too late, while the live rerun splits it into an informal 2015-03-13 row plus a later formal 2015-03-29 row tied to document finalization.
- **AI right, Alex wrong** — Filing p. 37: 'twenty-five potential buyers executed confidentiality agreements'. The filing's NDA count is 25, not Alex's reduced aggregate count. The live rerun's 25-party phase-1 NDA structure is correct.

## Flag Analysis
- The large soft/info count is mostly expected atomization signal: 25 NDA placeholders, bidder-type ambiguity on unnamed buyers, date inference, and cohort-level NDA-without-follow-up flags. Those are not the main problem here.

## Recommendation
- Add the missing 2014-03-27 `Final Round Inf Ann` and 2014-04-14 `Final Round Inf` rows for phase 1.
- Retime/reclassify the NMC endgame so the best-and-final formal bid sits on 2015-03-13 rather than on a later document-finalization date.
