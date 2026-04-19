# CLAUDE.md — M&A Takeover Auction Extraction Project

> Context file for any Claude (or human) picking up this project. Keep it current as the project evolves.

## What this project is

An **AI extraction pipeline** that reads the "Background of the Merger" section of SEC merger filings (DEFM14A, PREM14A, SC-TO-T, S-4) and produces a structured row-per-event spreadsheet matching the schema Alex Gorbenko uses in his M&A auction research.

**Why.** Alex's research studies informal bidding in corporate takeover auctions. The legacy dataset was collected by Chicago RAs with known inconsistencies. Alex has hand-corrected **9 reference deals**. The goal is to use those 9 deals plus Alex's written rulebook to prompt an AI extractor that processes the remaining ~392 deals at research-grade quality.

**Who's involved.**
- **Austin** — building the pipeline.
- **Alex Gorbenko** — senior collaborator, produced the instructions and reference extractions. Async; Austin relays his decisions.

## Ground-truth epistemology (IMPORTANT)

**The SEC filing is ground truth.** The filing text is the authoritative source of what happened in the deal.

**Alex's workbook is a reference guideline, not ground truth.** Alex is an expert but he is prone to the same human errors as anyone — transcription mistakes, judgment inconsistencies, ambiguous-case calls he might decide differently on another day, and the specific defects he has already flagged in his own work. His extractions are valuable as a calibration point, not as an oracle.

**Austin verifies correctness.** During the development phase, Austin reads each reference deal's filing himself and adjudicates every disagreement between the AI and Alex's workbook. There are four possible verdicts per disagreement:

1. **AI correct, Alex wrong** — record as an AI-identified correction to the reference dataset. Do not update the prompt/rulebook.
2. **AI wrong, Alex correct** — update the prompt or rulebook to close the gap.
3. **Both correct, different interpretations** — flag as a legitimate judgment call; document in the rulebook so the AI and Alex converge in future.
4. **Both wrong** — update the rulebook against the filing text.

**Implication for scoring.** There is no F1-vs-Alex number that gates shipping. The tool that compares AI output against Alex's extractions (`scoring/diff.py`) produces a diff report for human review. The report is a development aid, not a grade.

## Architecture (current MVP)

The live repo now uses a **per-deal Ralph/Claude loop** with **one LLM
Extractor, a deterministic Python Validator, and an optional scoped
Adjudicator for soft flags**. This replaced the earlier draft that used an
Extractor agent plus a separate Validator agent.

```
seeds.csv ──► for each deal ──► fresh Claude session ─────────────┐
                                                                   │
                                ┌── rules/ + prompts/ ─────────┐   │
                                │   rules/*.md                 │   │
                                │   prompts/extract.md         │──►│ Extractor subagent
                                └───────────────────────────────┘   │
                                                                   ▼
                                                    raw {deal, events} JSON
                                                                   │
                                                                   ▼
                                                     pipeline.validate()
                                                        (Python only)
                                                                   │
                                             row_flags + deal_flags + status
                                                                   │
                              if soft flags only: Adjudicator subagent (scoped)
                                                                   │
                                                                   ▼
                                                     pipeline.finalize()
                                                                   │
                         output/extractions/{deal}.json + state/flags.jsonl
                                                                   │
                                                                   ▼
                                                     state/progress.json
                                                                   │
                                                                   ▼
                                  if deal is reference:
                                    scoring/diff.py vs reference/alex/{deal}.json
                                    → Austin manually reviews the diff
                                                                   │
                                                                   ▼
                                                                 git commit
```

The deterministic validator lives in `pipeline.py`. There is no LLM validator
in the current pipeline.

**Still deferred.** Planner and Canonicalizer are not part of the current
pipeline. Add them only if the data shows the Extractor + Python Validator +
scoped Adjudicator shape is insufficient.

**Every row carries `source_quote` and `source_page`.** Non-negotiable. No un-cited rows ship. This is also what makes manual verification tractable.

## Project workflow — three stages

```
┌────────────────────────────────────────────────┐
│ Stage 1: Resolve open questions          [DONE]│
│   Walk through open questions in rules/*.md    │
│   Record Decision on each open question        │
│   Output: resolved rulebook                    │
└────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────┐
│ Stage 2: Build diff harness + Alex JSONs [DONE]│
│   Convert 9 reference deals from xlsx → schema │
│   JSON; these go in reference/alex/.           │
│   Write scoring/diff.py (AI-vs-Alex diff).     │
│   reference/alex/alex_flagged_rows.json        │
│   records Alex's own caveats on his own work.  │
└────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────┐
│ Stage 3: Build, iterate, manually verify       │  ◄── WE ARE HERE
│   MVP: Extractor + Validator, one archetype    │
│   at a time (Medivation → Imprivata → …)       │
│   For each reference deal: run pipeline,       │
│   diff against Alex, Austin reads the filing   │
│   and adjudicates each divergence.             │
│   Only crank 392 target deals once Austin has  │
│   manually verified all 9 reference deals and  │
│   the rulebook has stabilized across 3         │
│   consecutive unchanged-rulebook runs.         │
└────────────────────────────────────────────────┘
```

**Critical rule:** Stage 3 was opened only after Stage 1 had no 🟥 OPEN
questions remaining and Stage 2's diff harness ran end-to-end on at least
one reference deal. That gate has already been satisfied in the current
repo.

## Current status

- **Stage 1 complete (2026-04-18).** All 54 rule decisions ratified with Alex in a power-run session; full decision records in `rules/*.md`. Tracker `skill_open_questions.md` shows 0 🟥 / 54 🟩. Commit `f57a2aa`.
- **Stage 2 complete (2026-04-18).**
  - `scripts/build_reference.py` converts the xlsx → `reference/alex/{slug}.json` for all 9 reference deals, applying §Q1 (Saks delete), §Q2 (Zep expand), §Q3/§Q4 (Mac-Gray / Medivation renumber), §E3 canonical bidder IDs, §F1 bidder-type collapse, §A1–§A3 chronological BidderID reassignment, and Scope-3 drops. Commits `3241785` + `9dda10a`.
  - `scoring/diff.py` runs end-to-end against AI extractions and emits a human-review markdown + JSON report with verdict checkboxes per divergence. Commit `0b0d4d7`.
  - **Workstream C** — 25-deal lawyer-language study — **deferred indefinitely.** Reopen only if Stage 3 diffs surface systematic §G1/§L2 confusion the per-row manual-verification loop can't resolve.
- **Stage 3 implementation landed (2026-04-18).** Commit `031c371` added
  `pipeline.py` (filing loader, prompt builder, Python validator,
  finalization helpers) and rewrote `run.py` into a CLI shim that validates
  and finalizes a saved raw extraction instead of orchestrating the whole
  loop itself.
- **Iter-6 full reference-set rerun completed 2026-04-19** under the
  post-TIER-2 rulebook. `state/progress.json` now shows `392 pending`,
  `6 passed_clean`, `3 validated`.
  - **Passed clean (6):** medivation, imprivata, zep, mac-gray,
    petsmart-inc, saks.
  - **Validated with hard flags (3):** providence-worcester (13),
    penford (5), stec (2).
  - **20 hard flags total**, all extractor-side evidence gaps:
    20× `bid_type_unsupported` (§P-G2: extractor missed `bid_type_trigger`
    phrase or inference note).
  - **Zero rule-change triggers.** All three non-clean deals need
    extractor-side fixes, not rulebook changes.
  - Aggregate report:
    `quality_reports/plans/2026-04-19_stage3-iter6-rerun-results.md`.
  - Latest per-deal diff reports live in `scoring/results/` with the
    `20260419T15…` / `20260419T16…` timestamps (e.g.
    `medivation_20260419T153940Z.md`).
- **Iter-6 work summary.** TIER 0 reverted the §D1.a overfit from iter-5;
  TIER 1a–e added safety gates including the `_invariant_p_g2` check;
  TIER 2a–g ran a −601-line rulebook deletion pass (and moved §Q1–§Q5
  rationale from `rules/dates.md` into `scripts/build_reference.py`'s
  module docstring, deleted the old §K3 event label, etc.). Plans:
  `quality_reports/plans/2026-04-19_stage3-iter6-*-handoff.md`.
  Post-rerun commit `b355286` closed the §P-D5/§P-D6 rulebook gap:
  §P-D6 now explicitly documented in `rules/invariants.md`; §P-D5
  implemented in `pipeline.py` as the structural twin of §P-D6; §G2
  restructured to 3-condition form matching §P-G2; §D1.a exempts both
  §P-D5 and §P-D6.
- **Exit clock: 0/3 unchanged-rulebook clean runs.** Three deals are still
  non-clean, so the clock has not started. Conservative interpretation:
  stays at 0/3 until all 9 pass clean simultaneously.
- **Immediate next step (Austin's call):** re-run providence /
  penford / stec with the §P-G2 prompt reminder that batch-3 used in
  iter-6 (likely brings their hard flags to 0), then adjudicate the
  NDA atomization-vs-aggregation pattern across zep / mac-gray /
  providence / petsmart, and resolve the `bidder_type.public`
  inference policy in `scripts/build_reference.py`.
- **Target-deal gate remains closed.** Do **not** run on the 392 target
  deals until all 9 reference deals are manually verified against their
  filings and the rulebook is stable across 3 consecutive unchanged full
  reference-set runs.

## Repo layout

| Path | What it is |
|---|---|
| `CLAUDE.md` | This file. Project context for any session. |
| `SKILL.md` | Live architecture contract for the extraction skill. |
| `skill_open_questions.md` | Slim Stage 1 tracker. Indexes every 🟥 OPEN question across `rules/`. |
| `rules/schema.md` | Output schema: columns, types, deal-level vs event-level. |
| `rules/events.md` | Event vocabulary (closed list): start-of-process, NDA, IB, final rounds, dropouts, closing. |
| `rules/bidders.md` | Bidder identity, type classification (S/F/public/non-US), aggregation, joint bidders. |
| `rules/bids.md` | Bid value structure (ranges, composite, aggregate), informal-vs-formal classification, skip rules. |
| `rules/dates.md` | Rough-date mapping ("mid-July" → calendar date), event sequencing, BidderID. |
| `rules/invariants.md` | Hard/soft/info checks the Python validator runs. |
| `prompts/extract.md` | Extractor agent prompt. |
| `pipeline.py` | Live Python plumbing: filing loader, extractor prompt builder, validator, output writers, state updaters. |
| `scoring/diff.py` | AI-vs-Alex diff report generator. Produces human-readable reports for manual review. Not a grader. |
| `state/progress.json` | Per-deal status ledger (`pending`/`validated`/`passed`/`passed_clean`/`verified`/`failed`). |
| `state/flags.jsonl` | Append-only validator flag log. |
| `output/extractions/{deal}.json` | Per-deal extraction output (AI-produced). |
| `reference/CollectionInstructions_Alex_2026.pdf` | Alex's data-collection rulebook. Black = original Chicago RAs; **bold red = Alex's additions** (most important). |
| `reference/deal_details_Alex_2026.xlsx` | Legacy dataset. 9,336 rows × 35 columns. Red cells = Alex's corrections. |
| `reference/alex/{deal}.json` | Alex's extraction of the 9 reference deals, converted to pipeline schema. Built in Stage 2. |
| `reference/alex/alex_flagged_rows.json` | Rows in Alex's workbook that Alex himself has annotated as wrong/unresolved. See §Q1–§Q5 in `scripts/build_reference.py`'s module docstring. |
| `reference/alex/README.md` | How `reference/alex/` is organized. |
| `seeds.csv` | 401 candidate deals with SEC filing URLs. 9 flagged `is_reference=true` are Alex's hand-corrected set. |
| `run.py` | CLI shim: validate/finalize a saved raw extraction, write output/state, optionally commit. |

## The 9 reference deals

Alex hand-corrected these from the legacy dataset. They are the development / calibration set. Each exercises a different archetype. Rows refer to `reference/deal_details_Alex_2026.xlsx`.

| Deal slug | Target | Rows | Archetype it tests |
|---|---|---|---|
| `providence-worcester` | Providence & Worcester | 6024–6059 | English-auction; CVR consideration; many rough dates |
| `medivation` | Medivation | 6060–6075 | Classic `Bidder Sale`; `Bid Press Release` (simplest) |
| `imprivata` | Imprivata | 6076–6104 | `Bidder Interest` → `Bidder Sale`; `DropBelowInf` / `DropAtInf` |
| `zep` | Zep | 6385–6407 | `Terminated` then `Restarted` (two separate auctions) |
| `petsmart-inc` | Petsmart | 6408–6457 | `Activist Sale`; consortium winner; 15 NDAs same day |
| `penford` | Penford | 6461–6485 | Two stale prior attempts (2007, 2009); near-single-bidder endgame |
| `mac-gray` | Mac Gray | 6927–6960 | IB terminated and re-hired; target drops highest formal bid |
| `saks` | Saks | 6996–7020 | Rows Alex wants *deleted*; go-shop |
| `stec` | STec | 7144–7171 | Multiple `Bidder Interest` pre-IB; single-bound informals |

**Rollout order** (simple → complex): Medivation → Imprivata → Zep → Providence → Penford → Mac Gray → Petsmart → STec → Saks.

## Key data conventions

- **`BidderID` remains an event-sequence number, not a bidder identifier.**
  In AI output and regenerated reference JSONs it is a strict integer
  `1..N` sequence assigned per `rules/dates.md` §A1–§A4. Alex's old
  decimal insertions do not persist in the generated JSON.
- **A single bidder appears on many rows** — once for NDA, again for each
  bid, once for drop, once for execution.
- **Bid rows now use the §C3 unified form.** `bid_note="Bid"` and
  `bid_type` carries the informal/formal distinction. Legacy labels like
  `Inf`, `Formal Bid`, and `Revised Bid` are migration noise and should not
  appear in current AI output.
- **AI rows must carry `source_quote` and `source_page`.** Alex's reference
  JSONs intentionally omit evidence fields; they are a diff target, not a
  filing-cited extraction.
- **Reference JSONs are not literal xlsx dumps.** `scripts/build_reference.py`
  applies the resolved Stage 2/3 overrides and keeps provenance via flags.
  The rationale for each override (§Q1 Saks delete, §Q2 Zep expand,
  §Q3/§Q4 Mac-Gray / Medivation renumber, §Q5 Medivation "Several
  parties" atomization) now lives in that script's module docstring
  rather than in `rules/dates.md`, because the AI extractor never
  consults Alex's workbook.

## Alex's own flags on his own work

These are rows in Alex's workbook that Alex himself annotated as wrong or unresolved. They live in `reference/alex/alex_flagged_rows.json`. When the AI's extraction disagrees with one of these rows, the disagreement is expected — the AI may well be more correct than Alex here.

- **Saks rows 7013 and 7015** — Alex's own comments say delete.
- **Zep row 6390** — compresses 5 bidders into one row; Alex flagged for expansion.
- **Mac Gray row 6960** — `BidderID=21` duplicates row 6957.
- **Medivation rows 6066 and 6070** — both have `BidderID=5`.

Current handling:
- `scripts/build_reference.py` fixes the structurally invalid rows in the
  generated reference JSONs per its own §Q1–§Q5 module docstring (moved
  out of `rules/dates.md` in iter-6 TIER 2d), while preserving
  provenance in `alex_flagged_rows.json`.
- The Medivation converter also now atomizes the aggregated "Several
  parties" rows (§Q5), so the reference side matches the rulebook's
  atomization stance better than the raw workbook did.

## Conventions for future Claude sessions

- **Do not start target-deal extraction until the reference-set gate is met.**
  All 9 reference deals must be manually verified against their filings, and
  the rulebook must remain unchanged across 3 consecutive full
  reference-set runs.
- **Every design decision lives in a `rules/*.md` file**, not scattered across chat transcripts. When a decision is made, write it into that file's `Decision:` field and remove the 🟥.
- **The SEC filing text is ground truth.** Alex's workbook is a reference, not an oracle. Expect the AI and Alex to disagree — that's useful signal, not failure.
- **During manual verification, Austin reads the filing.** Any diff between AI and Alex is adjudicated against the filing, not by appeal to Alex.
- **Alex's PDF is authoritative on the RULES** (black = Chicago; **bold red = Alex's additions**). The rulebook encodes these rules. Where the PDF and Alex's own extractions disagree, treat it as a decision item and log it in `rules/99_pdf_overrides.md` (create on first use).
- **Be skeptical. Cite rows. Check dates.** Austin explicitly asks for accuracy over speed and is happy to be told he's wrong.
- **Every extracted row must carry `source_quote` and `source_page`.** Rows without evidence are rejected by the validator. This is also what makes manual verification tractable — Austin can confirm each row by reading the cited passage.
- **Reset context per deal.** No cross-deal state in the model. Everything persists through `rules/`, `state/progress.json`, and `output/`.
- **Treat dated planning docs as snapshots.** `quality_reports/` plans and
  session logs, plus older adjudication notes in `scoring/results/`, are
  useful history but not always live status. For current truth, prefer
  `state/progress.json`, `output/extractions/`, `pipeline.py`, `run.py`,
  `SKILL.md`, and this file.
- **Use the user's folder name ("the folder you selected") when referring to file locations**, not sandbox paths.
- **Before adding a new agent or rule file, name the assumption it encodes.** If you can't say what the model fails at without it, don't add it.

## Current Stage 3 follow-ups

- **Close out the 20 extractor-side hard flags on providence / penford /
  stec.** All 20 are `bid_type_unsupported` — extractor evidence gaps,
  not rule failures. Re-running those three deals with the §P-G2 prompt
  reminder that batch-3 used in iter-6 should bring the count to 0 and
  let all 9 deals pass clean simultaneously (starting the exit clock).
- **Adjudicate the NDA atomization-vs-aggregation pattern.** AI extracted
  many more NDA/Drop rows than Alex on zep / mac-gray /
  providence-worcester / petsmart-inc. Current §E2.b says atomize unless
  the filing narrates joint/consortium activity; Alex's workbook
  aggregates. This is a legitimate "both correct, different
  interpretation" — Austin's call per deal whether to tighten §E2.b or
  accept AI's atomization and regenerate Alex's reference.
- **Resolve the `bidder_type.public` inference policy** in
  `scripts/build_reference.py`. `bidder_type` dominates the field diffs
  across every deal (e.g. mac-gray=17, stec=17, imprivata=13,
  penford=13). A more aggressive public-strategic inference in the
  converter would collapse ~65 field diffs in one sweep. This is a
  converter-policy question, not a rulebook question.
- **Refresh the per-deal adjudication memos** in `scoring/results/` so
  they track the post-iter-6 diff reports (`*_20260419T15…Z.md` /
  `*_20260419T16…Z.md`), not the older pre-rerun timestamps.
- **Deal-level diffs remain `TargetName` / `Acquirer` casing plus
  `DateEffective`.** Same residual as iter-5 post-pin state; no new
  action beyond confirming the filing-verbatim policy continues to hold.

## Exit criteria for each stage

**Stage 1 done when:** every 🟥 in every `rules/*.md` is resolved to 🟩. `skill_open_questions.md` shows zero open items.

**Stage 2 done when:** `reference/alex/*.json` contains all 9 reference deals in schema-conformant form; `scoring/diff.py` runs end-to-end and emits a human-readable diff on one reference deal.

**Stage 3 done when:** Austin has manually verified the AI output against each of the 9 reference deals' filings. Every AI-vs-Alex disagreement has been adjudicated. Hard invariants pass 100%. The rulebook has remained unchanged across 3 consecutive full-reference-set runs. Only then turn the crank on the 392 target deals.
