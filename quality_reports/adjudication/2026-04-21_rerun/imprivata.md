---
date: 2026-04-21
status: COMPLETE — adjudicated against filing
owner: Codex
slug: imprivata
extraction: output/extractions/imprivata.json
reference: reference/alex/imprivata.json
filing_pages: data/filings/imprivata/pages.json
diff_markdown: scoring/results/imprivata_20260421T171059Z.md
prior_comparison: quality_reports/comparisons/2026-04-21_three-way/imprivata_report.md
---

# Imprivata — rerun adjudication

## TL;DR
- **Disposition:** Fix and rerun. Two material filing-truth issues remain in the live rerun.
- **Current rerun verdict:** The rerun gets the broad process right, but the current saved output still misses one pre-process Thoma Bravo approach and regresses on the Sponsor A dropout code.

## Current rerun snapshot
- `state/progress.json`: status=`passed` · flag_count=`18` · last_run=`2026-04-21T16:57:33.460098Z`
- Rows: `29` · hard=`0` · soft=`3` · info=`15`
- Diff burden vs Alex: matched=`24` · AI-only=`3` · Alex-only=`4` · cardinality mismatches=`1` · field disagreements=`11` · deal-level disagreements=`3`
- Top current flag codes: `date_range_collapsed` × 7, `range_with_formal_trigger` × 2, `legal_counsel_evidence` × 2, `date_inferred_from_rough` × 1, `pre_nda_informal_bid` × 1, `unnamed_count_placeholder` × 1
- Non-issue note: Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below.

## Adjudicated rerun divergences
- **AI right, Alex wrong** — row 5 (`Barclays` · `IB` · `2016-04-15` · p.30): Barclays belongs on 2016-04-15, the date the Board engaged Barclays subject to final paperwork, not on 2016-03-09.
- **AI right, Alex wrong** — row 6 (`None` · `Target Sale` · `2016-05-05` · p.31): A standalone `Target Sale` row on 2016-05-05 is supported by the Board's decision to launch the outreach process.
- **Both wrong** — row 23 (`Sponsor A` · `DropAtInf` · `2016-06-15` · p.33): Sponsor A on 2016-06-15 should be `DropBelowInf`, not `DropAtInf`. The filing's deciding action is target-side: Barclays tells Sponsor A that the Board would not be interested at essentially the same valuation.
- **Both wrong** — Filing p. 28: 'In early 2015, and again in June 2015, representatives of Thoma Bravo informally approached...' The live rerun still compresses Thoma Bravo's early-2015 and June-2015 approaches into one pre-2016 row, and Alex does too. The filing narrates two separate pre-March-2016 meetings.
- **AI right, Alex wrong** — row 24 (`None` · `Final Round Ann` · `2016-06-24` · p.35): June 24 is a `Final Round Ann`, not Alex's `Final Round Ext Ann` + `Final Round Ann` + `Final Round Ext` bundle. The filing treats the June 24 letters as the first formal-final announcement.
- **AI right, Alex wrong** — row 13 (`Financial 1` · `NDA` · `2016-05-23` · p.31): The unnamed fourth financial sponsor NDA/drop pair is supported by the filing's 'four financial sponsors executed confidentiality agreements' language and the later note that one financial sponsor dropped shortly thereafter.

## Flag Analysis
- The soft/info profile is otherwise healthy: date-range collapse on the NDA wave is expected, and the formal-trigger flags on the June 9 round are exactly the sort of borderline cases the rules anticipate.

## Recommendation
- Add the missing June 2015 Thoma Bravo `Bidder Interest` row called out explicitly in the filing.
- Change Sponsor A on 2016-06-15 from `DropAtInf` to `DropBelowInf`; the decisive language is Barclays telling Sponsor A the Board would not be interested at essentially the same price.
