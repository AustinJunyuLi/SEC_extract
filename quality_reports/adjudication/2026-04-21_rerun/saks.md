---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: saks
extraction: output/extractions/saks.json
reference: reference/alex/saks.json
filing_pages: data/filings/saks/pages.json
diff_markdown: scoring/results/saks_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/saks_report.md
---

# Saks — rerun adjudication

## TL;DR
- **Disposition:** Hot-fix one row and rerun; otherwise the current row set is strong.
- **Current rerun verdict:** The live rerun fixes several older issues, but it now emits one post-signing `Sale Press Release` row that should be folded into `Executed`.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`37` · last_run=`2026-04-21T16:57:33.717969Z`
- Rows: `29` · hard=`0` · soft=`13` · info=`24`
- Diff burden vs Alex: matched=`10` · AI-only=`2` · Alex-only=`1` · cardinality mismatches=`5` · field disagreements=`4` · deal-level disagreements=`3`
- Top current flag codes: `resolved_name_not_observed` × 7, `date_inferred_from_context` × 6, `date_range_collapsed` × 6, `bid_range` × 5, `date_inferred_from_rough` × 3, `pre_nda_informal_bid` × 2
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 3 (`Hudson's Bay` · `Bidder Interest` · `2013-04-01` · p.30), row 7 (`Hudson's Bay` · `Bid` · `2013-04-17` · p.31): The April 1 Hudson's Bay meeting belongs as a separate `Bidder Interest` event from the later week-of-April-15 priced indication. Alex's merged treatment loses that distinction.
- **AI right, Alex wrong** — row 21 (`Company H` · `Bid` · `2013-07-21` · p.34): Company H's 2013-07-21 aggregate $2.6 billion approach should stay in the dataset under the current unsolicited-first-contact rule; Alex's delete note is stale relative to the live rulebook.
- **AI right, Alex wrong** — row 17 (`Sponsor E` · `Bid` · `2013-07-11` · p.33), row 18 (`Sponsor G` · `Bid` · `2013-07-11` · p.33): The July 11 joint sponsor bid is correctly encoded as Sponsor E + Sponsor G. Alex's Sponsor A/E label is filing-wrong.
- **AI wrong, Alex right** — row 27 (`None` · `Sale Press Release` · `2013-07-29` · p.35): The standalone 2013-07-29 `Sale Press Release` row should not exist. Under the project convention, post-signing publicity is folded into `Executed` rather than emitted as a separate row.
- **AI right, Alex wrong** — The current rerun omits the Sponsor C / Sponsor D financing-side NDA rows that older try snapshots emitted. The live rerun is correct to keep Sponsor C / Sponsor D out of the Saks-side auction row set; those NDAs belong to the separate Saks→Company B financing context, not the inbound Saks sale process.

## Flag Analysis
- The remaining flags are all soft/info only. Most are ordinary range/date flags on the April–July bid sequence; the substantive live issue is the extra 2013-07-29 publicity row after signing.

## Recommendation
- Delete the standalone 2013-07-29 `Sale Press Release` row and fold that publicity into the 2013-07-28 `Executed` row.
- Keep the current separation of the April 1 Hudson's Bay meeting from the later priced bid and keep the Company H 7/21 row.
