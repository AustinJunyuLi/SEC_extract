# Rulebook Contract Refactor Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the lean contract-first refactor needed before the next reference extraction run.

**Architecture:** Keep the direct SDK pipeline. Linkflow remains prompt-only JSON over the wire; Python performs strict local schema enforcement after parsing and before finalization. No backward compatibility paths, shims, or stale-output readers are added.

**Tech Stack:** Python standard library, pytest, existing `pipeline/` modules, markdown rule/docs.

---

## File Map

- `pipeline/llm/response_format.py`: strict local JSON-schema-like enforcement used after model JSON parsing.
- `pipeline/run_pool.py`: fresh-run audit invalidation and semantic-soft adjudicator routing.
- `pipeline/core.py`: deal-field hard rejection and visible promotion trace without private output fields.
- `tests/llm/test_response_format.py`: strict local schema tests.
- `tests/test_run_pool.py`: cache invalidation and adjudicator routing tests.
- `tests/test_pipeline_runtime.py`: deal-field rejection and promotion trace tests.
- `docs/superpowers/specs/2026-04-29-rulebook-contract-refactor-design.md`: align spec with executable rollout.
- `docs/linkflow-extraction-guide.md`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`: keep high-level docs in sync.
- `rules/schema.md`, `rules/bidders.md`, `rules/invariants.md`, `prompts/extract.md`: narrow consistency edits only where the contract is contradictory.

---

### Task 1: Strict Local Schema Enforcement

**Files:**
- Modify: `pipeline/llm/response_format.py`
- Modify: `tests/llm/test_response_format.py`

- [x] **Step 1: Write failing tests**

Add tests that prove prompt-only Linkflow output is locally rejected when it has top-level siblings, missing event fields, event extras, invalid enum values, invalid flag shape, or invalid `source_quote`/`source_page` list pairing.

- [x] **Step 2: Run the focused tests**

Run: `python -m pytest tests/llm/test_response_format.py -q`

Expected before implementation: new strict-validation tests fail.

- [x] **Step 3: Implement local schema validation**

Add a small standard-library validator for the existing `SCHEMA_R1` subset: `type`, type lists with `null`, `enum`, `required`, `properties`, `additionalProperties`, arrays, and `oneOf`. Raise `MalformedJSONError` with a path-bearing message.

- [x] **Step 4: Verify**

Run: `python -m pytest tests/llm/test_response_format.py -q`

Expected: pass.

### Task 2: Cache and Adjudicator Boundaries

**Files:**
- Modify: `pipeline/run_pool.py`
- Modify: `tests/test_run_pool.py`

- [x] **Step 1: Write failing tests**

Add one test proving fresh `run` / `re_extract` audit setup deletes stale `raw_response.json`, and one test proving only explicit semantic soft flag codes are sent to `adjudicate()`.

- [x] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_run_pool.py -q`

Expected before implementation: new tests fail.

- [x] **Step 3: Implement boundaries**

Delete `raw_response.json` in `_build_audit_writer()` for fresh run actions only. Add a `SEMANTIC_ADJUDICATION_SOFT_FLAGS` allow-list and filter `_soft_flags()` through it.

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_run_pool.py -q`

Expected: pass.

### Task 3: Core Contract Cleanup

**Files:**
- Modify: `pipeline/core.py`
- Modify: `tests/test_pipeline_runtime.py`

- [x] **Step 1: Write failing tests**

Replace the old extra-field stripping test with hard-failure behavior. Add a promotion-success test proving finalized output carries an `nda_promoted_from_placeholder` info flag and no `_unnamed_nda_promotions` field.

- [x] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_pipeline_runtime.py -q`

Expected before implementation: new tests fail.

- [x] **Step 3: Implement core cleanup**

Change `_enforce_extractor_deal_contract()` to raise on unexpected deal fields. On successful unnamed-NDA promotion, attach a row info flag to the promoted NDA row. Stop writing private promotion logs into finalized deal JSON.

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_pipeline_runtime.py -q`

Expected: pass.

### Task 4: Minimal Rule and Doc Alignment

**Files:**
- Modify: `docs/superpowers/specs/2026-04-29-rulebook-contract-refactor-design.md`
- Modify: `docs/linkflow-extraction-guide.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `SKILL.md`
- Modify only if necessary: `rules/schema.md`, `rules/bidders.md`, `rules/invariants.md`, `prompts/extract.md`

- [x] **Step 1: Remove unsafe artifact wording**

The spec must not casually delete `state/progress.json` / `state/flags.jsonl` without a seed-preserving reset tool. State reset is a separate explicit operation, not part of code-completion cleanup.

- [x] **Step 2: Separate code completion from post-API rollout**

The spec must distinguish local verification from the later reference re-extraction run Austin administers separately.

- [x] **Step 3: Remove stale doctrine blocks from high-level docs**

`AGENTS.md` / `CLAUDE.md` may point to rule owners, but should not restate current consortium, DropSilent, formal-stage, drop-classification, or comparison-noise doctrines.

- [x] **Step 4: Align contradictory rule prose**

Fix only contradictions that block implementation: `bidder_name` nullability for exact-count placeholders, reference JSON as comparison projection, and flag payload shape if current rules demand fields the schema forbids.

### Task 5: Verification and Commit

**Files:**
- No production edits.

- [x] **Step 1: Run focused tests**

Run the focused test files touched above.

- [x] **Step 2: Run required local verification**

Run:

```bash
python -m pytest -x
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
```

Then run the stale/secret `rg` scan requested for the active task. Secret
matches are blocking. Explicit stale-doctrine phrases must not appear in live
contract files.

- [x] **Step 3: Commit scoped changes**

Commit only files intentionally changed by this refactor. Do not add `state/progress.json` or `state/flags.jsonl` unless Austin explicitly asks.
