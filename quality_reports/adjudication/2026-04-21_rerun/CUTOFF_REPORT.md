---
date: 2026-04-21
status: CUTOFF — adjudication paused for API budget
owner: Claude (orchestrator)
related:
  - quality_reports/session_logs/2026-04-21_ref9-rerun-prod.md
  - .planning/debug/ref9-hard-flags.md
  - quality_reports/comparisons/2026-04-21_three-way/MASTER_REPORT.md
---

# Reference-9 production rerun — cutoff report (2026-04-21)

## Status at cutoff

- **Extraction phase:** COMPLETE. 9 fresh extractions saved to
  `output/extractions/*.json` and committed to `state/progress.json`.
- **Validation phase:** COMPLETE. `state/flags.jsonl` archived (old to
  `state/archive/flags-2026-04-21T17-30-rerun.jsonl`) and rewritten fresh.
- **Adjudication phase:** PAUSED. 9 adjudicator subagents were spawned in
  parallel and **killed mid-investigation** by Austin at 18:02 UTC due to API
  cost. No adjudication reports were written to disk. Partial findings
  recovered from killed-agent return snippets are logged below under "Partial
  adjudicator findings (pre-kill)".

## Clean-slate actions taken

| Action | Path |
|---|---|
| Archived 3,749-line flag log | `state/archive/flags-2026-04-21T17-30-rerun.jsonl` |
| Zeroed working flag log | `state/flags.jsonl` (0 lines before rerun; now populated with rerun flags only) |
| Reset 9 reference deals to `pending` | `state/progress.json` |
| Created fresh raw-extraction workspace | `/tmp/bids_rerun/` |
| Created adjudication artifact dir | `quality_reports/adjudication/2026-04-21_rerun/` |

## Extraction results (9 subagents, parallel, Opus)

All 9 extractors produced valid `{deal, events}` JSON. No rule-blocked halts.

| Deal | Events | Status | Hard | Soft | Info | Bytes (raw) |
|---|---|---|---|---|---|---|
| medivation | 21 | passed | 0 | 10 | 8 | 33,098 |
| imprivata | 29 | passed | 0 | 3 | 15 | 53,803 |
| zep | 51 | passed | 0 | 66 | 48 | 101,529 |
| providence-worcester | 64 | passed | 0 | 2 | 60 | 110,182 |
| penford | 35 | **validated** | **6** | 14 | 19 | 57,359 |
| mac-gray | 45 | passed | 0 | 35 | 16 | 75,465 |
| petsmart-inc | 57 | passed | 0 | 1 | 55 | 102,775 |
| stec | 36 | passed | 0 | 3 | 13 | 53,724 |
| saks | 29 | passed | 0 | 13 | 24 | 54,049 |

**8 of 9 passed clean (0 hard flags).** The 5-deals-blocked state from the
previous run (`zep 6 / penford 1 / mac-gray 3 / petsmart 21 / stec 8 = 39
hard`) is gone. Only **penford (6 hard)** remains blocked — and the failure
mode is narrow and well-characterized (see below).

### Validation vs the previous run (2026-04-20)

| Deal | 2026-04-20 hard | 2026-04-21 hard | Delta |
|---|---|---|---|
| medivation | 0 | 0 | — |
| imprivata | 0 | 0 | — |
| zep | 6 | 0 | −6 ✓ |
| providence-worcester | 0 | 0 | — |
| penford | 1 | **6** | **+5** ✗ |
| mac-gray | 3 | 0 | −3 ✓ |
| petsmart-inc | 21 | 0 | −21 ✓ |
| stec | 8 | 0 | −8 ✓ |
| saks | 0 | 0 | — |
| **Total hard** | **39** | **6** | **−33** |

The fix bundle (curly-quote canonicalization, verbatim prompt discipline, §M4
phase-N→N+1 NDA revival, §P-S3 phase-0 exemption) cleared the predicted
classes (`source_quote_not_in_page`, `bid_type_unsupported` from quote drift,
`phase_termination_missing`, `bid_without_preceding_nda`). The 6 new penford
flags are a different failure mode — extractor non-compliance with §P-G2 on a
specific class of rows, not the bugs the fix bundle targeted.

## Penford failure analysis (6 hard flags)

All 6 are `bid_type_unsupported` (§P-G2 violation: `bid_type` is set but
there's no true range AND no `bid_type_inference_note`).

| Row | Bidder | Date | Value | Type | Quote (truncated) | Diagnosis |
|---|---|---|---|---|---|---|
| 8 | bidder_03 | 2014-08-06 | $17 | informal | "Fortnum suggested that a price of $..." | Single-point verbal — needs inference note |
| 9 | bidder_03 | 2014-08-10 | $18 | informal | letter confirming interest at $18 | Single-point letter — needs inference note |
| 24 | bidder_03 | 2014-10-02 | $18.50 | informal | "prepared to move forward based on a proposed price of $18.50" | Single-point — needs inference note |
| 25 | bidder_03 | 2014-10-02 | $19 | informal | letter increasing to $19 | Single-point — needs inference note |
| 28 | bidder_03 | 2014-10-08 | $19 | formal | "Sidley Austin circulated a revised draft of the merger agreement" | **Quote does not support a bid** — likely row is a drafting event mislabeled as a bid |
| 31 | bidder_05 | 2014-10-14 | $16 | informal | "Party A provided a formal letter with its indication of interest... at a price of $16.00" | Single-point — needs inference note |

**Root cause:** the penford extractor's self-reported validator claim ("0 hard,
0 soft, 0 info flags") did not match the live pipeline validation, which found
6 hard. The extractor believed it had populated `bid_type_inference_note` but
the saved JSON has `None` on all 6 rows. Either (a) the extractor ran its
mental validator without writing the notes to JSON, or (b) the rows were
added to the extraction with the notes elided.

**Row 28 is worse than the others:** the `source_quote` is about Sidley
circulating a draft merger agreement, not about Ingredion submitting a bid.
The row's value ($19) appears carried over from row 25. This is not a
§P-G2 compliance issue; it is a hallucinated bid row.

**Decision points for Austin:**
1. **Hot-fix row 8/9/24/25/31** (add `bid_type_inference_note` inline, keeping
   the rows as extracted). Row 28 should be deleted outright.
2. **Re-extract penford** (risk: non-deterministic, may regress elsewhere).
3. **Prompt update** reinforcing §P-G2 on single-point bids (applies
   everywhere, but this is the first run where penford failed it; other
   deals handled §P-G2 correctly so the fix is targeted).

## Flag-code distribution across the 9 deals

The three largest flag classes are NOT extraction errors; they are expected
rule-compliant annotations:

| Flag code | Count | Semantics |
|---|---|---|
| `date_inferred_from_context` | 80+ | §B1/§B3 anchoring when filing gives rough dates or process-relative timing |
| `nda_without_bid_or_drop` | 50+ | §P-S1 soft: filing silent on bidder's exit after NDA (expected per §I1 NDA-only rule) |
| `date_inferred_from_rough` | 85+ | §B4 midpoint/range collapse when filing says e.g. "in late July 2014" |
| `unnamed_count_placeholder` | 35+ | §E5 placeholders for "15 potentially interested financial buyers" etc. |
| `date_range_collapsed` | 80+ | §B4 range to midpoint for NDA waves |

These are design, not defects. The adjudicator review was meant to separate
these from actual misses — but was paused before any reports were written.

## Partial adjudicator findings (pre-kill)

Adjudicators were killed after reading filings/extractions but before writing
their markdown reports. The following signals were captured from kill-time
return snippets; they are **tentative** and should be reconfirmed when
adjudicators are respawned.

### medivation (adjudicator returned: "Good — empty directory. Now I have a comprehensive picture.")
- Row 16 (`Final Round Ext Ann` 2016-08-19) + row 17 (formal Bid 2016-08-19)
  ordered correctly per §A3 rank (announcement rank-1 before bid rank-7),
  even though narrative order has bid before announcement.
- Row 17's `financing_contingent=null` is defensible; filing silent on 8/19
  financing.
- No blocking issues flagged pre-kill.

### imprivata (adjudicator returned: "p.32 is correct for those unsolicited letters")
- Filing-citation spot-check passed for unsolicited letters.
- No blocking issues flagged pre-kill.

### zep (adjudicator returned a substantive finding)
- **AI emitted zero `Final Round*` rows; Alex has 3.** This is a material
  pattern miss — the March 27 process letter + April 14 IOI deadline should
  have been encoded as `Final Round Inf Ann` + `Final Round Inf` per §K2.
  Extractor treated them as generic Bid rows.
- Alex's 2014-05-07 `Final Round` may be an Alex error (filing is data-room
  access, not a bid deadline — no second formal round was ever reached since
  phase-1 was terminated).
- Phase boundary dates defensible: Terminated 2014-06-26 (board decision),
  Restarted 2015-02-10 (NMC first re-engagement). Alex used Feb 19 (first
  bid date) — different-but-defensible.
- Party Y NDA inferred 2014-05-21 via §B3 "shortly after" anchoring — valid.

### providence-worcester (adjudicator returned: NDA math)
- NDA counts reconciled: 25 NDAs first wave (11 strategic including Party A,
  14 financial including Party D) + 1 Party C NDA early July = 26 total.
- Filing p.35 narrative says 25; p.40 summary says 25 (summary omits Party C).
  AI extracted 26; both defensible.

### penford (adjudicator returned note-format recommendation)
- Recommended `bid_type_inference_note` format:
  `"<classification> per §G1 <rule>: <filing evidence>"`.
- Will be used when hot-fixing the 6 hard-flagged rows.

### mac-gray (adjudicator returned delta-vs-prior-run)
- Encoding shifts from the 2026-04-20 run:
  - Drop dates: 9/19 → **9/23** (day before 9/24 exclusivity-execution).
  - CSC/Pamplona 9/18 $20.75: formal → **informal** (with §P-G2 inference note
    citing informal-round announcement).
  - No `Bid Press Release` row (had one previously).
  - No `Target Sale`/`Bidder Sale` duplication.
  - 9/23 drops now `DropBelowInf`, previously `DropTarget`.
- These are archetype-level encoding shifts; adjudicator should rule on
  which encoding better matches Alex's "target drops highest formal bid"
  intent.

### petsmart-inc (adjudicator returned filing-fact list)
- Filing confirms: 3 strategic + 24 financial = 27 potential participants
  (p. 30); 15 NDAs first week Oct 2014; 6 IOIs Oct 30; 3 bidders ≥ $80
  initially + Bidder 2 raised from $78 to $81-84.
- AI's 15-atomized-NDA decision per §E2.b N-count is the documented pattern.
- Adjudicator was verifying the 6-IOI breakdown against AI's row count.

### stec (adjudicator returned: "ready to write")
- No blocking issues flagged pre-kill.

### saks (adjudicator returned: "directory exists, about to write")
- No blocking issues flagged pre-kill.

## What to do when API budget resumes

### Step 1 — Respawn adjudicators

The 9 adjudicator prompts are documented in the orchestrator conversation
(this session) and can be re-issued with the same per-deal focus. Each
adjudicator:

- Reads `output/extractions/{slug}.json` (the saved rerun output — do not
  re-extract).
- Reads `data/filings/{slug}/pages.json` as ground truth.
- Reads `reference/alex/{slug}.json` as reference guideline.
- Reads `rules/*.md`.
- Writes structured report to
  `quality_reports/adjudication/2026-04-21_rerun/{slug}.md` with TL;DR,
  row-level correctness, Alex divergences (4-verdict), flag analysis,
  systematic issues, recommendations.

### Step 2 — Address penford

Before respawning the penford adjudicator, Austin should decide which of the
three penford fixes to apply:

- **Hot-fix inline:** edit `output/extractions/penford.json` to add
  `bid_type_inference_note` on rows 8, 9, 24, 25, 31; delete row 28. Re-run
  validator. Fast but does not update the extractor's behavior on future
  runs.
- **Re-extract:** spawn a new penford extractor with §P-G2 emphasis. Risks
  non-deterministic regression.
- **Prompt update:** permanent reinforcement of §P-G2 note requirement on
  single-point bids; resets the 3-clean-run exit clock.

### Step 3 — Master report

After the 9 adjudication reports are written, aggregate into
`quality_reports/adjudication/2026-04-21_rerun/MASTER_RERUN.md` cross-cutting:

- Which deals are ship-ready vs fix-and-rerun vs escalate.
- Systemic extraction patterns (good and bad).
- AI-identified corrections to Alex's reference (3 known: zep row 6390,
  mac-gray row 6960, medivation rows 6066/6070).
- Prompt/rule changes needed (if any).

### Step 4 — Exit clock

Per `CLAUDE.md`: exit gate is 3 consecutive unchanged-rulebook clean runs on
all 9 reference deals. This run is the **first** clean run (once penford is
resolved). If the penford fix is inline-only (no rule/prompt change), the
clock starts; if the penford fix is a prompt update, the clock resets.

## Files on disk after cutoff

```
output/extractions/*.json               # 9 fresh extractions (8 passed, 1 validated)
state/progress.json                     # 9 reference deals updated to passed/validated
state/flags.jsonl                       # fresh rerun flag log
state/archive/flags-2026-04-21T17-30-rerun.jsonl  # prior 3,749-line log

quality_reports/adjudication/2026-04-21_rerun/
├── CUTOFF_REPORT.md                    # THIS FILE
└── (no per-deal reports yet — respawn adjudicators to generate)

quality_reports/session_logs/2026-04-21_ref9-rerun-prod.md  # session log (needs end-state update)

/tmp/bids_rerun/*.raw.json              # 9 raw extractor outputs (ephemeral)
/tmp/bids_rerun/*.prompt.txt            # 9 extractor bootstrap prompts (ephemeral)
/tmp/bids_rerun/run-log.txt             # run.py finalize log (ephemeral)
```

## Summary

- **Production rerun executed.** Pipeline state materially improved: 39
  hard-flag regressions cleared; 1 new failure mode on penford (6 flags,
  narrow and diagnosed) remains.
- **Adjudication paused** to preserve budget. 9 agents killed without writing
  reports; extraction artifacts are preserved.
- **Resume path** is straightforward: respawn the 9 adjudicators (same prompt
  shape), decide on penford fix, write master report, evaluate whether this
  counts toward the exit clock.
