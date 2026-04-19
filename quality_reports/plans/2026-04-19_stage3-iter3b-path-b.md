# Stage 3 Iter 3b — Path B: Extract the 4 Unrun Reference Deals

**Status:** APPROVED (Austin confirmed 2026-04-19)
**Started from:** `2026-04-19_stage3-iter3-handoff.md` — Path B recommendation.

## Goal

Run mac-gray, petsmart-inc, stec, saks through the pipeline under the
**current infrastructure** (commit `97fc4d3`'s Fix 1 + Fix 2C + §P-D6). Surface
every new defect class these deals carry BEFORE committing to another
prompt patch cycle. No rulebook changes.

## Why Path B (recap)

Any prompt patch resets the 3-iteration exit clock for every deal. If we
patch §B3 (Providence residuals) now, re-run 5 deals, then discover a
novel defect class when finally running one of the 4 remaining deals, we
reset again. Better: absorb all unknowns in ONE iteration.

## Approach

### Step 1 — 4-way parallel extraction (background subagents)

For each slug ∈ {mac-gray, petsmart-inc, stec, saks}:
- Spawn `Agent(subagent_type="general-purpose", model="opus",
  run_in_background=true)`.
- Prompt: full text of `pipeline.build_extractor_prompt(slug)` + two
  supplements:
  1. **Write-to-/tmp supplement.** "Write your final JSON to
     `/tmp/<slug>.raw.json` via the Write tool. Your final message should
     confirm the write and contain the JSON inline; both delivery modes are
     expected."
  2. **Anti-skeletal guard.** "Do not produce a skeleton. You MUST read
     pages.json in full, extract every event, and emit every row with
     populated `source_quote` and `source_page`. Expected row count is in
     the range of the 28–50 events Alex enumerated for these deals; a
     deliverable with <15 rows is almost certainly incomplete."

### Step 2 — Finalize each deal (deterministic)

Once each subagent completes:
```
python run.py --slug <slug> --raw-extraction /tmp/<slug>.raw.json --no-commit
```

This runs Fix 1 (canonical sort) + Fix 2C (NDA promotion) + validate() +
writes `output/extractions/<slug>.json` + updates `state/progress.json` +
appends `state/flags.jsonl`.

### Step 3 — Diff against Alex (per deal)

```
python scoring/diff.py --slug <slug>
```

Produces `scoring/results/<slug>_<timestamp>.md` + `.json`.

### Step 4 — Adjudicate divergences (per deal)

For each deal, spawn a **fresh** `general-purpose` Opus subagent pointed
at the diff report. Adjudicator produces `scoring/results/<slug>_adjudicated.md`
following the template used in iter 3 (per-divergence verdict: AI correct,
Alex correct, both defensible, prompt-fix candidate).

### Step 5 — Commit each deal atomically

After finalization + adjudication, one commit per deal:
```
git add state/progress.json state/flags.jsonl
git commit -m "<slug> iter 3b extraction: <n> events, <flags> hard flags, <defects> AI defects"
```

Output JSONs (`output/extractions/*.json`) and diff reports
(`scoring/results/`) are gitignored by design — only state ledger moves.

### Step 6 — Consolidated handoff

Write `2026-04-19_stage3-iter3b-handoff.md` summarizing:
- Per-deal: event count, validator flags, genuine AI defects.
- **All new defect classes surfaced** across the 4 deals + existing
  Providence §B3 residuals.
- Recommended iter-4 consolidated prompt patch covering all surfaced
  defects.
- Exit-clock status (all 9 deals will need a fresh 3-iteration bank once
  the consolidated patch lands).

## Verification gates

- Every raw extraction JSON must parse as valid JSON and contain `deal`
  + `events` keys.
- `python run.py --slug X --raw-extraction /tmp/X.raw.json --dry-run`
  must emit a status (not crash).
- Adjudication memo must exist at `scoring/results/<slug>_adjudicated.md`
  before committing that deal.

## Files touched

- `state/progress.json` (4 deals promoted from `pending` → terminal status)
- `state/flags.jsonl` (append-only)
- `output/extractions/{mac-gray,petsmart-inc,stec,saks}.json` (gitignored,
  written fresh)
- `scoring/results/*` (gitignored)

## Files NOT touched

- `rules/*.md` — frozen.
- `prompts/extract.md` — no patches in this iteration. Consolidated patch
  comes AFTER surfacing all defect classes.
- `pipeline.py` — frozen.
- Austin's uncommitted edits (AGENTS.md, CLAUDE.md, reference/alex/*.json,
  scripts/build_reference.py) — left untouched.

## Failure modes

1. **Subagent timeout / skeletal output.** Mitigation: anti-skeletal
   guard in the prompt; verify row count is plausible before accepting.
   If output is <15 rows, re-prompt the same subagent with the
   filing-row-count evidence.
2. **Validator explodes with unknown flag code.** The validator returning
   a new flag is fine — that's the point of iter 3b. If it _crashes_,
   roll back and investigate pipeline.py.
3. **Diff report too noisy to adjudicate manually.** Use the adjudicator
   subagent approach to shard the work per deal. If a single deal's diff
   has >100 divergences, the extractor probably misread the filing
   (structural error); investigate before adjudicating.
