---
date: 2026-04-21
status: CUTOFF — adjudication paused for API budget; resume with respawn
owner: Claude (orchestrator) + 9 parallel extractor subagents + 9 parallel adjudicator subagents
related:
  - quality_reports/session_logs/2026-04-21_supervisor-report-for-alex.md
  - .planning/debug/ref9-hard-flags.md
  - quality_reports/comparisons/2026-04-21_three-way/MASTER_REPORT.md
---

# Reference-9 production rerun (2026-04-21)

## Goal

Production-grade rerun of all 9 reference deals with a clean-slate state
ledger, using the fix bundle landed in this session (curly-quote
canonicalization, verbatim prompt discipline, §M4 phase-N→N+1 NDA revival,
§P-S3 phase-0 exemption). Follow each extraction with a per-deal Adjudicator
subagent to investigate the output against the filing and Alex's reference.

User directive: "proceed the 9 deal run. overwrite the original results. start
and record in a cleanslate. spawn for each deal an adjudicator to investigate.
be very thorough and serious. we are in prod".

## Clean slate state

- `state/flags.jsonl` — 3,749 lines from 2026-04-18 through 2026-04-20 archived
  to `state/archive/flags-2026-04-21T17-30-rerun.jsonl`; fresh empty file in
  place.
- `state/progress.json` — 9 reference deals reset to `status=pending`,
  `flag_count=0`, `last_run=null` (done in earlier fix bundle).
- `output/extractions/` — empty before rerun (gitignored).
- Raw extractor outputs written to `/tmp/bids_rerun/{slug}.raw.json` before
  being piped into `run.py --no-commit`.
- Adjudicator reports landing at
  `quality_reports/adjudication/2026-04-21_rerun/{slug}.md`.

## Extraction phase — 9 parallel subagents

Each subagent received the standard `run.py --print-extractor-prompt` bootstrap
plus an override to save the final JSON to `/tmp/bids_rerun/{slug}.raw.json`
and return a short summary (event count, phase pattern, judgment calls).

Results so far (byte count = signal that a real extraction landed, not a
one-line error):

| Slug | Status | Events | Bytes | Phase pattern | Notes |
|---|---|---|---|---|---|
| medivation | DONE | 21 | 33,098 | 1 only | Pre-NDA informal bid §C4; §E5 `Several parties` atomized; 4 IB rows; 3 expected `nda_without_bid_or_drop` softs |
| imprivata | DONE | 29 | 53,803 | 1 only | §B4 range-midpoint for 6 NDAs (May 6–Jun 9 window); §C4 pre-NDA informal on Thoma Bravo 3/9; 2 `range_with_formal_trigger` softs flagged for adjudication |
| zep | PENDING | — | — | — | — |
| providence-worcester | PENDING | — | — | — | — |
| penford | PENDING | — | — | — | — |
| mac-gray | PENDING | — | — | — | — |
| petsmart-inc | PENDING | — | — | — | — |
| stec | DONE | 36 | 53,724 | 1 only | WDC reengagement §I2 kept in phase 1 (drop + return, no phase transition); §G2 single-bound informals with inference notes |
| saks | DONE | 29 | 54,049 | 1 only | 40-day go-shop kept in phase 1; §M1 skipped 52 unresponsive contacts; only Company I emitted as post-signing NDA/Drop |

## Final state (cutoff)

All 9 extractors completed. Validation completed. **Adjudication killed
mid-investigation by Austin at 18:02 UTC to preserve API budget.** Per-deal
adjudication reports were not written; partial findings captured in
`quality_reports/adjudication/2026-04-21_rerun/CUTOFF_REPORT.md`.

### Pipeline state summary

| Deal | Status | Hard | Soft | Info |
|---|---|---|---|---|
| medivation | passed | 0 | 10 | 8 |
| imprivata | passed | 0 | 3 | 15 |
| zep | passed | 0 | 66 | 48 |
| providence-worcester | passed | 0 | 2 | 60 |
| penford | **validated** | **6** | 14 | 19 |
| mac-gray | passed | 0 | 35 | 16 |
| petsmart-inc | passed | 0 | 1 | 55 |
| stec | passed | 0 | 3 | 13 |
| saks | passed | 0 | 13 | 24 |

**Delta from the 2026-04-20 run:** 39 hard flags → 6 hard flags; 8/9 deals
now pass clean. The 6 remaining are all `bid_type_unsupported` on penford
(§P-G2 compliance miss — single-point bids without `bid_type_inference_note`;
one row appears to be a hallucinated bid from a merger-agreement-drafting
event).

See `CUTOFF_REPORT.md` for the full analysis and resume path.
