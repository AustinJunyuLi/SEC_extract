# Session Log — 2026-04-27 — Code Review + Simplify Pass

**Status:** in progress
**Branch:** main (2 commits ahead of origin)

## Goal

Austin requested an ultra-thorough multi-agent code review of the recent
taxonomy-redesign cleanup, followed by a `/simplify` pass. Treat as
production: the next milestone is the rulebook-stabilization gate
(3 consecutive unchanged-rulebook clean runs across all 9 reference
deals) before turning the crank on the 392 target deals.

## Key context

Recent commits under review (last 5):

- `652e5de` Implement taxonomy redesign cleanup
- `7b7bb65` specs: taxonomy redesign — bid_note 31→18 + 8 structured columns
- `29faee5` session log: code-review + simplify pass — final outcomes
- `34c4f0d` polish: align new code with existing module conventions
- `a044025` scripts: build_reference §Q1–§Q7 docstring + drop dead bt_nonUS load

Earlier same-pass commits also in scope:
- `26977b2` validator: §P-R6 scalar bidder_type + §P-S4 wrong-phase test
- `9c3c4cf` schema: range bids unconditionally informal; new validator + auto-coerce
- `20644dc` schema: universal atomization; delete §E2.a
- `27c1a8c` schema: drop Acquirer_legal sidecar

Diff stat HEAD~5..HEAD: 4029 insertions, 7760 deletions. pipeline.py
+408 lines. All 9 reference/alex/*.json regenerated. Tests grew
(test_invariants.py +287, test_reference_converter.py +67).

## Approach

Four parallel code-review agents dispatched (one per independent
domain) to keep main context clean and surface issues concurrently:

- **A** — pipeline.py validator core (state machine, §P-* checks,
  side-effect determinism)
- **B** — rules ↔ extractor prompt alignment (taxonomy consistency,
  closed-list discipline, §G2 satisfiers, §B5 directionality)
- **C** — reference data + builder (§Q1–§Q7 overrides, schema
  conformance of the 9 alex/*.json, determinism of build_reference.py)
- **D** — tests + scoring/diff.py (coverage of new validator paths,
  diff harness trustworthiness, no grading)

Each agent instructed to bucket findings as CRITICAL / MAJOR / MINOR
with file:line cites and a final VERDICT.

After agents return: consolidate, triage with Austin if any
destructive fixes needed, apply, run `/simplify`, verify (tests +
reference converter rerun), commit.

## Open questions / decisions to revisit

- NDA atomization-vs-aggregation pattern (§E2.b) — flagged in CLAUDE.md
  as Austin's call per deal; not in scope for this pass unless an
  agent surfaces a hard inconsistency.
- Whether MEMORY.md for this repo should capture the
  parallel-review-then-simplify workflow as a reusable pattern after
  this session ends.

## Incremental updates

### 2026-04-28 — Review reports back, triage, fix scope agreed

- All four review agents returned. Aggregate: **17 CRITICAL,
  37 MAJOR, 48 MINOR**. Validator logic itself was confirmed correct end-to-end
  by Agent A (every §P-* check encodes its rule correctly). Concentrated
  risk lives in the state-management layer + extractor-prompt fidelity.
- Austin authorized scope **Buckets 1+2+3+5** with sensible defaults +
  full re-extract: stale extractions/flags log/progress entries cleared,
  references regenerated, target-deal gate stays closed.
- Deferred to a separate pass: Bucket 4 (extractor prompt skeleton
  rewrite — 13 missing schema fields), Bucket 6 (diff harness
  improvements — closed-list annotation, deterministic --write,
  COMPARE_EVENT_FIELDS expansion), Bucket 7 (additional fixture matrix
  for §P-S3 phase-0 rationales, §P-D7 drop-reason matrix).

### 2026-04-28 — Fixes applied

**State durability:**
- `_atomic_write_text` POSIX-atomic helper (tmp + fsync + os.replace,
  with `.tmp` cleanup on Python-level exception).
- `_state_file_lock` advisory `flock` context manager; documented as
  NOT re-entrant within a single process.
- `_update_progress_locked` / `_append_flags_log_locked` inner helpers;
  public wrappers acquire the lock; `finalize()` acquires once and holds
  across both writes (correctness improvement: a concurrent run cannot
  interleave its progress write between our progress + flags pair).
- Per-run `run_id` (UUID) stamped on the deal extraction JSON, the
  progress.json deal entry, and every flags.jsonl line. The
  `(deal, run_id)` pair is the audit primary key for the rulebook
  stability gate — independent of `last_run` even when reruns share a
  timestamp.
- TOCTOU `if not exists()` rewritten to `try: read; except`.

**Defensive type guards (§P-R0 + §P-R8):**
- New §P-R0 row-shape invariant: events must be dicts; process_phase
  must be int>=0 or null; bidder_name/alias must be str or null.
  Validator filters non-dict events before downstream invariants run.
- New §P-R8 flag-shape invariant: flag dicts must have non-empty `code`,
  `severity ∈ {hard, soft, info}`, string `reason`. Catches typo
  severities (`"Hard"`, `"warn"`) that `count_flags` would silently
  demote to `"hard"`. Returns flat list with `deal_level: True`
  marker, consistent with the rest of the §P-R series.
- Defensive isinstance guards on `_apply_unnamed_nda_promotions`
  (registry entry) and `_invariant_p_r5` (alias filtering).
- Empty pages.json `min(valid_pages)` guard.

**§D1.a unsolicited_first_contact exemption coherence:**
- `prompts/extract.md` rewritten to mention BOTH §P-D5 and §P-D6
  exemption (was §P-D6 only); `rules/events.md` cross-reference updated.
- Phantom `date_source_phrase` field replaced with `bid_date_rough`
  (per §B2) in two places.
- 4 new fixtures + parametrized matrix test covering the exemption
  symmetrically: pd5 exempt, pd5 wrong-phase-still-flags, pd6 exempt,
  pd6 no-flag-fails. Validator logic was correct; the gap was test
  coverage + prompt fidelity.

**Reference data + builder:**
- `apply_q2_zep` now allocates fresh canonical IDs via the existing
  `_next_canonical_ids` helper (was sharing one bidder_name across all
  5 atomized parties — the diff harness would have mass-false-positived
  on Zep's 5-party slice).
- Providence row 6028 silent repair now emits a `bid_note_repaired_blank`
  info flag for provenance — every other override carries one.
- Module docstring extended with an "OTHER SUBSTANTIVE TRANSFORMS"
  section listing the 5 transforms outside the §Q1–§Q7 numbering
  (taxonomy redesign collapse, `_migrate_bid_note`, exclusivity event
  collapse, blank-bid-note repair, range-bid informal coercion).

**Test infrastructure:**
- `_assert_fixture` rewritten with consume-on-match: each expected
  flag pairs with one distinct actual flag and is removed from the
  candidate pool. Without this a single actual flag could spuriously
  satisfy multiple expected entries with the same code.
- New concurrent-write test for `append_flags_log` (60 lines × 2
  threads, asserts no JSON-line interleaving).
- New byte-idempotency test for `finalize()` extraction output (modulo
  per-run stamps); load-bearing precondition for the rulebook
  stability gate.
- New §P-R0 and §P-R8 fixtures + parametrized tests.

### 2026-04-28 — Stale data cleared for clean re-extract

- All 9 reference extractions in `output/extractions/` deleted.
- `state/flags.jsonl` truncated.
- `state/progress.json`: 9 reference deals reset from `passed` →
  `pending`; rulebook_version_history cleared on those entries; 392
  target deals untouched (already pending). All 401 deals now `pending`.

### 2026-04-28 — Final state

- 141/141 tests passing (was 109 before the session).
- All 9 reference JSONs regenerate cleanly via
  `python scripts/build_reference.py --all`.
- Zep's 5 atomized parties now hold distinct canonical ids
  (bidder_09–bidder_13).
- Diff stat: +775 / -574 lines across 12 files; 8 new test fixtures.
- Branch state: 2 commits ahead of origin/main; current changes
  uncommitted, awaiting Austin's review before commit.

## Open questions for next session

- Bucket 4 (extractor prompt skeleton rewrite) — 13 missing
  schema-required fields. Touches LLM behavior; review before applying.
- Bucket 6 (diff harness improvements) — `--write` filename
  determinism, COMPARE_EVENT_FIELDS expansion, closed-list annotation,
  alex_flagged_rows.json integration test.
- Pre-existing tech debt: `apply_q5_medivation`'s inline `_next_cid`
  could collapse into the shared `_next_canonical_ids`. Out of scope
  for this hardening pass.
- §P-S3 phase-0 exemption fixture matrix (only 1 of 3 documented
  rationales is currently tested).
- §P-G2 fixture matrix asymmetric (paired-Final-Round-fallback only
  has the happy path tested).

---
**Context compaction (manual) at 00:47**
Check git log and quality_reports/plans/ for current state.

### 2026-04-28 — End-of-day handoff for cross-machine continuation

Austin requested a handoff so work resumes seamlessly on a different machine
tomorrow. Bucket 4 (extractor prompt skeleton — 18 missing schema fields,
not 13 as the earlier triage estimated) and Bucket 6 (diff harness) were
investigated meticulously but **not implemented** — Austin asked to discuss
first and wait on decision items A–I. State of the discussion is captured
in `quality_reports/plans/2026-04-28_bucket4-and-bucket6-handoff.md`.

Committed and pushed at end of day with all 12 modified files + 8 new
fixtures from the prior session in the same commit, so the next machine
pulls a complete, test-green state.
