# Plan — Field-scope tightening + Bucket 6 fixes

**Status:** COMPLETED — executed 2026-04-28.
**Branch:** `main` (will commit per logical chunk).
**Created:** 2026-04-28, after triage of [2026-04-28_bucket4-and-bucket6-handoff.md](2026-04-28_bucket4-and-bucket6-handoff.md).
**Supersedes:** the Bucket 4 + Bucket 6 work items in that handoff plan.

## Closing notes

Execution used Austin's production directive as the tie-breaker: removed
fields were hard-deleted from live schema, rules, prompt, converter, diff
harness, tests, and regenerated reference JSONs. The dropped field names are
recorded in this historical plan and in
`quality_reports/session_logs/2026-04-28_field-scope-decision.md`, not in
operative extraction docs.

Verification completed:

- `python -m pytest -x` -> 145 passed.
- `python scripts/build_reference.py --all` -> all 9 reference JSONs
  regenerated.
- Structured retained-field comparison vs `HEAD` -> only deleted keys changed.
- `python scoring/diff.py --all-reference` -> graceful pending-extraction
  output for all 9 reference deals.
- Stale-field grep over operative files -> no hits.

## Goal

Tighten `rules/schema.md` §R1 to match what Alex's research actually uses, and clean up the diff harness. Concretely:

1. **Drop 11 schema fields** that Alex never collected and the research doesn't require.
2. **Keep 7 fields** (5 from prior round + 2 added by Austin: `consideration_components`, `exclusivity_days`).
3. **Document the dropped fields** so they can be re-added later if needed.
4. **Apply the 4 Bucket 6 small fixes** (filename bug, add `bid_value` to compare, drop closed-list issue, add flagged-rows integration test).
5. **Regenerate** the 9 reference JSONs against the new schema.

This work is an enabler for the next clean re-extract on the 9 reference deals — Bucket 4's "teach the AI 18 missing fields" goal collapses to "teach the AI 5 fields" once the 11 unused ones are removed from the schema entirely.

## Decisions baked in (already approved by Austin)

### KEEP (7 fields)

| Field | Level | Status in §R1 today | Action |
|---|---|---|---|
| `target_legal_counsel` | deal | already listed | add to prompt skeleton |
| `acquirer_legal_counsel` | deal | already listed | add to prompt skeleton |
| `bid_type_inference_note` | event | NOT in §R1 (validator-only) | add to §R1 + skeleton |
| `invited_to_formal_round` | event | already in §R1 + skeleton | (no change) |
| `submitted_formal_bid` | event | already in §R1 + skeleton | (no change) |
| `consideration_components` | event | already listed | add to skeleton |
| `exclusivity_days` | event | already listed | add to skeleton |

### DROP (11 fields — delete from schema, code, references)

**Deal-level (4):**
- `go_shop_days`
- `termination_fee`
- `termination_fee_pct`
- `reverse_termination_fee`

**Event-level (7):**
- `cash_per_share`
- `stock_per_share`
- `contingent_per_share`
- `aggregate_basis`
- `financing_contingent`
- `highly_confident_letter`
- `process_conditions_note`

**Rationale.** Empirical scan: Alex populates none of these across 9 reference deals × 276 events × 35 xlsx columns. The fields are well-collected by other M&A databases (FactSet, SDC) if a future paper needs them. Keeping them here would inflate Austin's manual-verification surface for fields nobody reads.

### Bucket 6 fixes (folded in)

- **E.** `--write` filename → stable `{slug}.md` / `{slug}.json` (overwrite mode). Fix [scoring/diff.py:526](../../scoring/diff.py).
- **F.** Add `bid_value` to `COMPARE_EVENT_FIELDS` ([diff.py:34](../../scoring/diff.py:34)). Surfaces §H4 aggregate-vs-per-share disagreements.
- **G.** Composite fields stay out of `COMPARE_EVENT_FIELDS` — N/A now since they're being deleted from the schema entirely.
- **H.** Closed-list annotation issue — DROP per the handoff plan's recommendation (validator §P-R3 already covers it).
- **I.** Add `alex_flagged_rows.json` integration test exercising `_alex_flag_note_for` ([diff.py:181](../../scoring/diff.py:181)).

## Phased execution

### Phase 1 — Schema + rules (the contract)

**Files:** `rules/schema.md`, `rules/bids.md`.

- `rules/schema.md` §R1:
  - Delete the 4 deal-level + 7 event-level dropped fields from the field listings.
  - Add `bid_type_inference_note` to the event-level field listing (currently only validator-facing).
  - New subsection at end of §R1: **"Deferred fields (excluded from current scope)"** — table listing each of the 11 dropped fields, what it would mean, why it was deferred (Alex doesn't collect; not central to informal-bidding research), and a one-line note on how to re-add (re-introduce in §R1 + prompt skeleton + run regen).
- `rules/bids.md`:
  - **§H2** — keep the `consideration_components` spec; gut the `cash_per_share` / `stock_per_share` / `contingent_per_share` dollar-decomposition spec. Replace with a one-line pointer to "deferred — see schema §R1 deferred-fields appendix".
  - **§H4** — keep the aggregate-dollar bids spec but drop the `aggregate_basis` field reference; pointer to deferred appendix.
  - **§O1** — keep `exclusivity_days` spec; drop the `financing_contingent` / `highly_confident_letter` / `process_conditions_note` and the deal-level termination-fee / go-shop spec; pointer to deferred appendix.

### Phase 2 — Code conformance

**Files:** `scripts/build_reference.py`, `scoring/diff.py`.

- `scripts/build_reference.py`:
  - Remove None-padding for the 11 dropped fields ([lines 449–453, 794–797, 1139–1148](../../scripts/build_reference.py)).
  - Keep `exclusivity_days` and `consideration_components` padding (they remain in the schema; Alex still doesn't fill them).
  - Update the module docstring's "OTHER SUBSTANTIVE TRANSFORMS" section if it references dropped fields.
- `scoring/diff.py`:
  - Remove the 7 dropped event-level fields from `AI_ONLY_EVENT_FIELDS` ([lines 59–64](../../scoring/diff.py:59)).
  - Keep `exclusivity_days` and `consideration_components` in `AI_ONLY_EVENT_FIELDS` (Alex's references stay null on them; AI fills them in; we don't want false positives).

### Phase 3 — Prompt update

**File:** `prompts/extract.md`.

- Update the JSON skeleton ([lines 110–156](../../prompts/extract.md)) to:
  - Add to the deal object: `all_cash`, `target_legal_counsel`, `acquirer_legal_counsel`, `deal_flags` (these were already in §R1 but absent from the skeleton — Bucket 4 finding).
  - Add to the event row: `bid_type_inference_note`, `consideration_components`, `exclusivity_days`.
- Audit prose for any mention of the 11 dropped fields and remove. Spot-check shows extract.md doesn't currently reference them, but verify with grep.
- Update the Step 8 self-check / final self-checks to reference the kept fields. Most edits should be additive (new fields to populate) rather than restructuring.

### Phase 4 — Bucket 6 small fixes

**File:** `scoring/diff.py`, `tests/test_diff.py`.

- **E** Stable filename: change `write_results` ([line 524](../../scoring/diff.py:524)) to `{slug}.md` / `{slug}.json`. Overwrites on rerun. Drop the timestamp from the filename.
- **F** `COMPARE_EVENT_FIELDS` — add `bid_value`.
- **I** New test in `tests/test_diff.py` exercising `_alex_flag_note_for`: build a synthetic Alex-flagged row (e.g., Saks 7013), confirm `diff_deal` annotates the matching divergence with the flag note in `alex_self_flag` / `alex_flagged_hits`.

### Phase 5 — Regeneration

```bash
python scripts/build_reference.py --all
```

Confirm: `git diff reference/alex/*.json` shows only the 11 dropped keys disappearing — no value changes on retained fields. Spot-check 1 deal (e.g., medivation) by eye.

### Phase 6 — Verification

```bash
python -m pytest -x                                    # 141/141 minus any test deletions
python scripts/build_reference.py --all                # idempotent rerun
python scoring/diff.py --all-reference                 # exits gracefully — extractions absent (deals are pending)
grep -rn "termination_fee\|cash_per_share\|go_shop_days\|aggregate_basis\|financing_contingent\|highly_confident_letter\|process_conditions_note\|stock_per_share\|contingent_per_share\|reverse_termination_fee\|termination_fee_pct" rules/ pipeline.py prompts/ scoring/ scripts/ tests/
```

The grep should return zero hits in operative files (matches in this plan, the prior handoff plan, and any session logs are expected and OK).

### Phase 7 — Documentation + commits

- Write session log: `quality_reports/session_logs/2026-04-28_field-scope-decision.md` capturing:
  - The empirical scan (9 deals × 276 events showing field-by-field population)
  - Austin's iterative decision (drop legal counsel? → no, keep; drop composite components? → keep `consideration_components` only; drop exclusivity? → keep)
  - The 7-keep / 11-drop final list with rationale
- Mark this plan COMPLETED with closing notes after execution.

**Commit boundaries:**

1. `schema: drop 11 deferred fields from §R1; add deferred-fields appendix; reflect in rules/bids.md` (Phase 1)
2. `scripts: stop padding deferred fields in build_reference; refresh references` (Phases 2 + 5, since they couple)
3. `diff: trim AI_ONLY_EVENT_FIELDS; add bid_value to compare; stable --write filenames; alex_flagged_rows test` (Phases 2 + 4 — Bucket 6 fixes)
4. `prompts: skeleton + self-checks now cover all kept §R1 fields` (Phase 3)
5. `logs: session log + plan completion` (Phase 7)

Per Austin's atomic-commit preference. If any chunk fails verification, fix in place — do not amend prior commits.

## Risks

- **Schema deletion cascade.** Some test or pipeline path may reference a dropped field at runtime in a way grep doesn't catch (e.g., dynamic field iteration). Mitigation: `pytest -x` after every commit catches this.
- **Reference regeneration drift.** If `build_reference.py` changes affect field ordering on retained fields, `git diff` will show noise. Mitigation: confirm by visual diff of one deal first; the conversion is deterministic.
- **Prompt skeleton scope creep.** Adding 7 fields might tempt rewriting the prose. Mitigation: stay surgical — add to the JSON example + add 1-2 self-check bullets — do not rewrite Step 8.
- **CLAUDE.md / SKILL.md staleness.** Both reference §R1 fields. Mitigation: post-execution scan; update only if specific dropped fields are named.

## Out of scope

- The 9 reference deals stay in `pending` status. The next clean re-extract is a separate effort, gated on this plan landing.
- The 392 target deals stay untouched (target-deal gate stays closed).
- Bucket 7 (additional fixture matrix for §P-S3 phase-0 rationales, §P-G2 paired-Final-Round-fallback) — separate pass.
- `apply_q5_medivation` inline `_next_cid` collapse — pre-existing tech debt, separate pass.
- Adjudicator subagent scope changes — not relevant to this work.

## How to resume if interrupted

```bash
git status                              # confirm what's staged
git log --oneline -10                   # confirm progress
python -m pytest -x                     # confirm test state
cat quality_reports/plans/2026-04-28_field-scope-tightening.md
```

The plan is phased so any commit boundary is a clean stopping point. If interrupted mid-phase, the unfinished phase's edits are uncommitted and can be reviewed via `git diff`.
