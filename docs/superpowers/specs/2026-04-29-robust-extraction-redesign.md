# Robust Extraction Implementation Blueprint

Date: 2026-04-29

Status: approved implementation blueprint. This document supersedes the broader
candidate-fact redesign previously committed under this path.

Audience: fresh-context implementation agents. Each workstream below is written
so a new agent can read this document, `AGENTS.md`, `SKILL.md`, and
`docs/linkflow-extraction-guide.md`, then execute a bounded slice without
needing chat history.

## Operating Thesis

The pipeline is not yet reliable enough to run the 392 target deals, but the
right first move is not a full replacement of the extractor architecture.

The current evidence proves that high vs xhigh reference runs changed row
cardinality, flag composition, hard-flag identity, anonymous bidder accounting,
and some final-round/date behavior. The current evidence does not yet prove
that a fixed-config repeated xhigh run is fundamentally unstable after the live
contract is tightened, because earlier audit artifacts were overwritten.

Therefore the first implementation must make failures observable, make unsafe
production execution impossible, and remove known contract drift. Only then do
we run controlled reference-set experiments. A candidate-fact compiler is a
conditional escalation, not Phase 1.

This is still a breaking redesign. The no-backward-compatibility rule applies:
when a contract changes, update the live docs/code/tests and delete stale paths.
Do not add old-format readers, hidden migrations, compatibility fallbacks, JSON
repair calls, or docs that describe old and new formats as simultaneously live.
Git history is the compatibility record.

## Goal

Produce a stable, auditable extraction pipeline for the 401 deals in
`seeds.csv`, with the 392 target deals blocked until the reference gate is met.

The implementation must support:

- immutable comparison of repeated runs;
- fail-closed target-deal protection;
- Linkflow-safe prompt-only JSON extraction;
- local schema/contract enforcement;
- coherent rule/prompt/validator taxonomy;
- a read-only stability harness for the 9 reference deals;
- a clean decision point for whether a deeper candidate-fact architecture is
  actually needed.

## Non-Negotiable Constraints

1. The SEC filing is ground truth. Alex's workbook is calibration, not an
   oracle.
2. The target-deal gate stays closed until all 9 reference deals are manually
   verified and the unchanged-rulebook stability gate is met.
3. Every shipped event row must have `source_quote` and `source_page`.
4. Linkflow/NewAPI extraction calls must use Responses streaming plus
   prompt-only JSON. Do not require strict OpenAI Structured Outputs,
   `json_schema`, or `text.format` payloads on the Linkflow path.
5. Do not add JSON repair model calls. Malformed JSON is a failed run with an
   archived audit record.
6. Do not add broad second-pass full-output rewrite agents. The only model calls
   allowed now are the existing extractor and scoped adjudicator.
7. Do not run the 392 target deals during this implementation.
8. Do not add new taxonomy fields unless this document assigns them to the
   active work. Most proposed fields are deferred until the stability harness
   proves they are necessary.
9. Do not preserve legacy audit/state/output layouts. If a layout changes, old
   loose artifacts should fail loudly or be deleted/regenerated.
10. Before adding a new rule file, state the specific model failure it encodes.

## Current Facts From The Codebase Scan

### Already Present

- Direct `AsyncOpenAI` Responses streaming path.
- Linkflow/NewAPI structured-output disablement.
- Background-section slicing before extraction.
- Prompt/audit capture for current singleton audit layout.
- Extractor contract version hashing over prompt and local schema mirror.
- Python validation of evidence quotes, event vocabulary, date/BidderID
  consistency, auction count, bid-type support, lifecycle checks, and final
  output finalization.
- Canonical event ordering and `BidderID` reassignment in Python.
- Scoped adjudication only for `missing_nda_dropsilent`.
- xhigh worker cap for Linkflow.
- Tests for many invariants, prompt-contract details, Linkflow response-format
  behavior, and runner skip/cache logic.

### Missing Or Insufficient

- Runtime target-deal gate. A default pending run can select target deals.
- Immutable per-run audit archive. Current `output/audit/{slug}/` files are
  overwritten, preventing true run-to-run diagnosis.
- Stable run selection for revalidation by run ID.
- Strong cache failure behavior for corrupted `raw_response.json`.
- Local validation for custom model-call schemas beyond the main extractor
  schema.
- General local enforcement of schema `maxLength`.
- Accurate `total_attempts`/attempt accounting in the audit manifest.
- Contract coherence for a small number of known prompt/rule/validator drifts:
  same-day final-round pairing, advisor NDA treatment, `date_phrase_unmapped`,
  raw-only promotion fields, nullability, conditional fields, and severity prose.
- Reconciliation tooling across progress, output, flags, and audit archives.
- Stability harness that compares archived repeated runs by substantive metrics.

### Deferred Unless Evidence Requires It

- Candidate-fact IR and deterministic compiler.
- Paragraph-ID evidence spine.
- New `date_basis`, `bid_type_basis`, `final_round_role`,
  `formal_round_status`, `cohort_id`, and `drop_group_basis` fields.
- Work-claiming for multiple simultaneous production pool processes.
- Broad schema redesign of final output.

## Target Architecture After This Implementation

```text
seeds.csv
  -> fail-closed runner selection
  -> one reference deal per extraction task
  -> direct Responses streaming model call
  -> prompt-only JSON on Linkflow
  -> immutable run archive
  -> local schema and contract validation
  -> deterministic Python prepare/validate/finalize
  -> output/extractions/{slug}.json
  -> state/progress.json and state/flags.jsonl
  -> reconciliation report
  -> stability report across archived reference runs
```

The extractor still emits final `{deal, events}` JSON in this implementation.
The candidate-fact architecture is explicitly not active until the stability
harness proves that direct final-row emission remains unstable after the
fail-closed/audit/contract fixes.

## Team Operating Rules

Every implementation agent must:

- start by reading this document, `AGENTS.md`, `SKILL.md`, and
  `docs/linkflow-extraction-guide.md`;
- own one workstream and only its file set;
- avoid touching unrelated dirty files, especially generated state or quality
  reports from another session;
- write tests before or alongside behavior changes;
- keep Linkflow prompt-only JSON intact;
- never run target deals;
- never add backward-compatibility readers for stale layouts;
- finish with a handoff containing changed files, tests run, assumptions,
  remaining risks, and exact commands needed by the next workstream.

Handoff template:

```markdown
## Workstream
<ID and title>

## Changed Files
- path: summary

## Tests
- command: result

## Contract Decisions
- decision or "none"

## Assumptions
- assumption or "none"

## Blockers For Other Agents
- blocker or "none"
```

## Merge And Coordination Rules

This plan is designed for parallel agents, but not every file can be edited in
parallel safely.

1. Workstreams A, B, and D can start immediately.
2. A owns runner selection and target-gate semantics inside `pipeline/run_pool.py`.
3. B owns audit path construction and run-archive writing inside
   `pipeline/run_pool.py`.
4. If A or B needs to edit the other's owned functions, stop and record the
   dependency instead of making a silent cross-scope change.
5. C should start after B has at least sketched the archive v2 helper API.
6. E should start after A and B have landed or their helper interfaces are
   stable.
7. F should start after B's archive layout is testable.
8. G is a docs/protocol integration pass after A-F.
9. H is a design-review pass after archived stability evidence exists.

Recommended integration order:

```text
D first if clean -> A -> B -> C -> E -> F -> G -> H
```

If multiple agents return patches together, merge the one with the smallest
shared-file footprint first, rerun its targeted tests, then rebase the next
agent's patch on the updated tree.

## Parallelization Map

| Workstream | Owner Scope | Can Start | Blocks | Must Not Touch |
|---|---|---:|---|---|
| A | Runtime gate and status semantics | immediately | G, H | archive internals except tests |
| B | Immutable audit archive v2 | immediately | C, F, G, H | rule taxonomy |
| C | Linkflow/cache/schema hardening | after B interface is sketched | G, H | target gate |
| D | Prompt/rule/validator coherence fixes | immediately | G, H | archive layout |
| E | Reconciliation command | after A and B interfaces are sketched | G, H | extractor prompt semantics |
| F | Stability harness | after B archive shape exists | H | model-call code |
| G | Reference run protocol and operator docs | after A-E | target gate release | core validators except doc fixes |
| H | Candidate-fact escalation decision | after F and G evidence | optional future architecture | current production code unless approved |

The most efficient team split is:

1. Agent A: implement fail-closed runner gate and status semantics.
2. Agent B: implement immutable audit archive v2.
3. Agent D: fix known prompt/rule/validator drift.
4. Agent C: harden schema/cache/Linkflow behavior using B's archive API.
5. Agent E: add reconciliation reporting after A/B stabilize.
6. Agent F: add stability harness after B archive data is available.
7. Agent G: update run protocol and docs after A-F.
8. Agent H: only analyze whether candidate facts are now justified.

## Workstream A - Fail-Closed Runtime Gate

### Assumption

The observed production risk is that target deals can be selected before the
reference gate is satisfied. This is a real current failure mode, not a
hypothetical one.

### Files Owned

- `pipeline/run_pool.py`
- `tests/test_run_pool.py`
- `SKILL.md`
- `AGENTS.md`
- `docs/linkflow-extraction-guide.md`

### Required Behavior

1. Any runner selection that includes non-reference target deals must fail
   before model calls unless all of the following are true:
   - all 9 reference deals are `verified` in `state/progress.json`;
   - the stability gate has been satisfied by archived reference runs;
   - the operator supplied an explicit target-release flag.
2. The default pending selection must not silently select target deals.
3. Dry runs must report whether a selection would include target deals and
   whether the gate is open or closed.
4. `validated` must not be treated as a completed/success status. A hard-flagged
   deal is not usable and must not count toward the reference exit gate.
5. The error message must list counts by reference/target and name the command
   or condition that keeps the gate closed.

### Suggested Implementation Shape

- Add a small pure function:

```python
def target_gate_status(state: dict, audit_root: Path) -> TargetGateStatus:
    ...
```

- Add a selection guard:

```python
def enforce_target_gate(selected_slugs: list[str], state: dict, cfg: PoolConfig) -> None:
    ...
```

- Keep the first implementation conservative. It can require an explicit
  stability proof file produced by Workstream F rather than trying to infer all
  stability facts from scratch in `run_pool.py`.
- Do not add automatic unlocking. The target release should be explicit and
  auditable.

### Tests

Add or update tests proving:

- default/dry-run selection cannot include targets while gate is closed;
- explicit target slugs fail while gate is closed;
- reference-only selection still works;
- `validated` is not in `DONE_STATUSES`;
- an open-gate fixture plus explicit release flag allows target selection in
  dry-run mode without making model calls;
- failure happens before audit directories or SDK clients are created.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/test_run_pool.py
```

passes, and a dry run cannot select target deals unless the explicit target
release path is satisfied.

## Workstream B - Immutable Audit Archive V2

### Assumption

The largest diagnostic gap is overwritten run artifacts. Without immutable
archives, the team cannot tell whether instability is stochastic, model-effort
dependent, rulebook-dependent, or caused by stale cache.

### Files Owned

- `pipeline/llm/audit.py`
- `pipeline/llm/extract.py`
- `pipeline/llm/adjudicate.py`
- `pipeline/run_pool.py`
- `run.py`
- `tests/llm/test_audit.py`
- `tests/llm/test_extract.py`
- `tests/llm/test_adjudicate.py`
- `tests/test_run_pool.py`
- `tests/test_run_cli.py`
- `docs/linkflow-extraction-guide.md`
- `SKILL.md`

### New Layout

Every fresh extraction attempt writes:

```text
output/audit/{slug}/runs/{run_id}/
  manifest.json
  calls.jsonl
  raw_response.json
  validation.json
  prompts/
    extractor.txt
    adjudicator_{n}.txt

output/audit/{slug}/latest.json
```

`latest.json` is the only mutable file in the audit tree. It points to the
latest completed attempt and records:

```json
{
  "schema_version": "audit_v2",
  "slug": "medivation",
  "run_id": "...",
  "outcome": "passed | passed_clean | validated | failed",
  "cache_eligible": true,
  "manifest_path": "runs/{run_id}/manifest.json",
  "raw_response_path": "runs/{run_id}/raw_response.json"
}
```

### Required Behavior

1. Fresh runs never delete or overwrite prior run directories.
2. Failed fresh runs still get immutable run directories.
3. `cache_eligible=false` for malformed JSON, transport failure, local schema
   failure, contract hash mismatch, or incomplete run metadata.
4. `--re-validate` reads the latest pointer by default.
5. `--re-validate --audit-run-id <run_id>` reads that exact run.
6. Loose legacy files directly under `output/audit/{slug}/` are not accepted as
   a fallback cache. Tests should assert failure on old layout.
7. `manifest.json` records run ID, slug, started/finished timestamps,
   provider/model/reasoning settings, endpoint, prompt hashes, schema hash,
   rulebook version, final outcome, attempt counts, and error summary.
8. `validation.json` records row/deal flag counts, hard/soft/info counts, and
   final status for that run.

### Suggested Implementation Shape

- Make `AuditWriter` take an explicit `run_dir` and `run_id`.
- Create run IDs before constructing the writer.
- Move path construction into one small module-level helper so `run.py` and
  `pipeline.run_pool` cannot drift.
- Update tests to assert paths under `runs/{run_id}`.
- Delete code that clears `calls.jsonl`, `raw_response.json`, or `prompts/` in a
  singleton audit directory. Clearing is no longer the right operation.

### Tests

Add or update tests proving:

- two fresh runs create two run directories;
- `latest.json` points to the second run;
- a failed fresh run does not make old raw responses cache-eligible;
- `--re-validate` uses latest when cache-eligible;
- `--audit-run-id` uses the selected run;
- old loose audit shape is rejected;
- prompt and raw-response files are never overwritten across runs.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/llm/test_audit.py tests/llm/test_extract.py tests/llm/test_adjudicate.py tests/test_run_pool.py tests/test_run_cli.py
```

passes and the docs no longer describe singleton audit files as the live layout.

## Workstream C - Linkflow, Cache, And Local Schema Hardening

### Assumption

Linkflow instability should be handled by transport discipline and local
contract enforcement, not by Structured Outputs or repair calls.

### Files Owned

- `pipeline/llm/client.py`
- `pipeline/llm/response_format.py`
- `pipeline/llm/retry.py`
- `pipeline/llm/watchdog.py`
- `pipeline/run_pool.py`
- `tests/llm/test_client.py`
- `tests/llm/test_response_format.py`
- `tests/llm/test_retry.py`
- `tests/llm/test_watchdog.py`
- `tests/test_run_pool.py`
- `docs/linkflow-extraction-guide.md`

### Required Behavior

1. Linkflow/NewAPI providers continue to send no `text.format`,
   `json_schema`, `response_format`, or Structured Outputs payload.
2. Native OpenAI structured-output support may remain only if the provider is
   known to support it and tests prove Linkflow does not receive it.
3. All model-call schemas used by the repo, including adjudicator schemas, must
   be locally validated against the subset of JSON Schema the repo uses:
   - `type`;
   - `required`;
   - `additionalProperties`;
   - `enum`;
   - `items`;
   - `minItems` if used;
   - `maxLength`.
4. Corrupt `raw_response.json` must block revalidation with a clear error, not
   crash with an unhandled traceback and not fall back to any older response.
5. Manifest attempt counts must be real. If a retry wrapper performs three
   attempts, the manifest should say three attempts.
6. Truncated JSON is a failed run. Do not repair it with another model call.
7. Keep extractor `max_output_tokens` unset unless a user explicitly supplies a
   cap for an experiment. Do not add per-deal token-budget aborts.

### Tests

Add or update tests proving:

- Linkflow calls have `json_schema_used=false` and no structured-output payload;
- native OpenAI path behavior remains explicit and tested;
- `maxLength` violations fail local schema validation;
- adjudicator malformed output fails local validation;
- corrupt cached raw responses block revalidation;
- retry attempt counts are reflected in manifests or call metadata;
- no JSON repair call is made after malformed output.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/llm tests/test_run_pool.py
```

passes and `docs/linkflow-extraction-guide.md` still describes prompt-only JSON
as the Linkflow contract.

## Workstream D - Prompt, Rule, Schema, And Validator Coherence

### Assumption

Some instability is self-inflicted by small contradictions between the prompt,
rules, schema mirror, and validator. Fix these before redesigning the whole
architecture.

### Files Owned

- `prompts/extract.md`
- `rules/schema.md`
- `rules/events.md`
- `rules/bidders.md`
- `rules/bids.md`
- `rules/dates.md`
- `rules/invariants.md`
- `pipeline/core.py`
- `pipeline/llm/response_format.py`
- `tests/test_invariants.py`
- `tests/test_prompt_contract.py`
- `tests/llm/test_response_format.py`
- relevant `tests/fixtures/*.json`

### Required Fixes

1. Same-day final-round pairing:
   - The rules allow one non-announcement `Final Round` milestone to support
     same-day bids.
   - Canonical ordering can put same-day bids before the non-announcement
     `Final Round` row.
   - Validator pairing must search the same phase and same date even when the
     milestone sorts after the bid.
   - Add a Mac Gray-style regression fixture.

2. Advisor NDA contradiction:
   - `rules/bids.md` says advisor NDAs are emitted with
     `role = "advisor_financial"` or `role = "advisor_legal"`.
   - The prompt must not tell the extractor to skip rows merely because they
     match advisor NDA logic.
   - Update prompt tests so advisor NDA treatment is unambiguous.

3. `date_phrase_unmapped` contract:
   - The prompt and validator must agree whether an unmapped rough-date phrase
     can coexist with `bid_date_rough`.
   - Minimal active fix: if the row deliberately uses a rough date with
     `date_phrase_unmapped`, the P-D2 symmetry check must treat that flag as an
     accepted date-inference flag.
   - Do not add `date_basis` yet.

4. Raw-only vs final schema fields:
   - If `unnamed_nda_promotion` is raw-only pre-validation input, document that
     explicitly in code comments and tests.
   - It must not appear in finalized outputs.
   - The response schema, final schema, and docs must name the distinction.

5. Nullability alignment:
   - Align `role` and `process_phase` across rules, `SCHEMA_R1`, and validator.
   - If a field is required but nullable, say so consistently.

6. Conditional field enforcement:
   - Final-round fields must be required on `Final Round` rows and null
     otherwise.
   - `press_release_subject` must be required only where the rules require it.
   - formal-stage fields must remain evidence-bound.
   - consideration and bid unit requirements must match the rule text.

7. Severity prose:
   - `rules/invariants.md` must match code severity for P-D7/P-D8 and any other
     known hard/soft/info mismatch.

### Tests

Add or update tests proving each required fix. Prefer small synthetic fixtures
over regenerated reference outputs unless the schema itself changes.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/test_invariants.py tests/test_prompt_contract.py tests/llm/test_response_format.py
```

passes, and this command shows no contradictory live instructions:

```bash
rg -n "advisor NDA|date_phrase_unmapped|Final Round" prompts rules pipeline tests
```

## Workstream E - State, Output, And Audit Reconciliation

### Assumption

Before running repeated reference experiments, the repo needs a deterministic
way to say whether progress, outputs, flags, and audit archives agree.

### Files Owned

- new module under `pipeline/`, for example `pipeline/reconcile.py`
- `pipeline/run_pool.py` only for optional command integration
- `tests/test_reconcile.py`
- `SKILL.md`
- `docs/linkflow-extraction-guide.md`

### Required Behavior

Implement a read-only reconciliation command. Suggested command:

```bash
python -m pipeline.reconcile --scope reference
```

It should check:

- all 9 reference slugs exist in `state/progress.json`;
- target slugs are not marked `verified`;
- latest output exists for every non-pending reference deal;
- output `last_run_id` matches progress `last_run_id`;
- progress status matches hard/soft/info counts in latest output;
- latest audit pointer exists for every finalized run;
- latest audit run ID matches progress/output when applicable;
- cache eligibility is false for failed or malformed runs;
- `state/flags.jsonl` entries for the latest run match output flags by run ID;
- no loose legacy audit files are being treated as live;
- rulebook version in output/progress/audit agrees.

The command must not modify files by default. A future `--write-report` can
write a markdown/JSON report, but the first implementation should be read-only
and deterministic.

### Tests

Add tests for:

- clean synthetic state passes;
- missing output fails;
- mismatched run ID fails;
- `validated` with hard flags is reported as blocked, not complete;
- target marked verified fails;
- legacy loose audit files fail or warn according to the chosen strictness;
- corrupt flags jsonl reports the exact bad line.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/test_reconcile.py
python -m pipeline.reconcile --scope reference
```

runs without modifying repo files. If the live repo is currently inconsistent,
the command may exit nonzero, but the errors must be precise and actionable.

## Workstream F - Stability Harness

### Assumption

The decision to rewrite extraction around candidate facts must be evidence-led.
The harness should measure substantive instability across archived runs without
calling a model.

### Files Owned

- new module under `pipeline/`, for example `pipeline/stability.py`
- `tests/test_stability.py`
- `quality_reports/` only for generated reports when explicitly requested
- `docs/linkflow-extraction-guide.md`
- `SKILL.md`

### Required Behavior

Implement a read-only stability command. Suggested command:

```bash
python -m pipeline.stability --scope reference --runs 3 --write quality_reports/stability/reference-latest.md
```

The harness consumes immutable audit/output artifacts and reports:

- run manifest table: slug, run ID, model, reasoning effort, timestamps,
  provider, prompt hash, schema hash, rulebook hash, status;
- row count by slug and by `bid_note`;
- hard/soft/info flag matrix by slug and code;
- hard-flag identity deltas;
- auction value stability;
- bidder lifecycle counts: NDA, Bid, Drop, DropSilent, Executed;
- anonymous placeholder counts and exact-count cohort-like patterns using
  existing fields only;
- final-round metrics: announcement rows, non-announcement rows, same-day
  bid/milestone pairs, P-G2/P-G3 flags;
- date diagnostics: precise/rough/null counts, accepted date-inference flags,
  rough-date mismatch flags;
- bid-value representation: lower/upper/bid_type/null state counts;
- quote diagnostics: missing quote, overlength quote, page mismatch,
  substring failure;
- AI-vs-Alex diff summary for reference deals if existing diff artifacts are
  available, clearly labeled as calibration only.

The primary stability gate should ignore raw info-flag volume unless the flag
code itself is part of a known structural instability. xhigh can be more verbose
without being substantively worse.

### Stable Identity

For final rows, start with a pragmatic fingerprint:

```text
slug | process_phase | bid_note | bid_date_precise | bid_date_rough |
bidder_alias_normalized | bidder_type | bid_value_lower | bid_value_upper |
source_page | normalized_source_quote_prefix
```

This is not a permanent row ID. It is a comparison tool for archived runs.

### Output

The report must end with one of:

- `STABLE_FOR_REFERENCE_REVIEW`
- `UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED`
- `UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE`
- `INSUFFICIENT_ARCHIVED_RUNS`

Include the reason for that classification.

### Tests

Add tests for:

- identical synthetic runs classify stable;
- hard-flag movement classifies unstable;
- row-count movement classifies unstable;
- pure info-count increase with same rows does not by itself force unstable;
- missing archived runs returns insufficient evidence;
- report output is deterministic.

### Acceptance

This workstream is complete when:

```bash
python -m pytest -q tests/test_stability.py
```

passes and the command can classify a synthetic archived reference set without
model calls.

## Workstream G - Reference Experiment Protocol

### Assumption

After A-F, the next valuable evidence is not more design discussion. It is three
archived xhigh reference-set runs under an unchanged rulebook and prompt.

### Files Owned

- `docs/linkflow-extraction-guide.md`
- `SKILL.md`
- `AGENTS.md`
- optional `docs/superpowers/specs/2026-04-29-reference-run-protocol.md` only
  if the protocol becomes too long for existing docs

### Required Protocol

The operator protocol must say:

1. Run tests:

```bash
python -m pytest -x
```

2. Dry-run reference selection:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
```

3. Run exactly the 9 reference deals, not targets, with Linkflow xhigh:

```bash
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
```

4. Reconcile:

```bash
python -m pipeline.reconcile --scope reference
```

5. Repeat until three archived full-reference xhigh runs exist under the same
   prompt/schema/rulebook hashes.

6. Run stability:

```bash
python -m pipeline.stability --scope reference --runs 3 --write quality_reports/stability/reference-xhigh-3run.md
```

7. Austin manually reviews any AI-vs-Alex differences against the SEC filings.

8. Only after manual verification and stable unchanged-rulebook runs should the
   target-release flag be considered.

### Required Documentation Updates

- `docs/linkflow-extraction-guide.md` must use the audit v2 paths.
- `SKILL.md` must describe archive v2 and target-gate semantics.
- `AGENTS.md` must remain consistent with the live package paths and gate.

### Acceptance

This workstream is complete when a fresh operator can follow the docs without
asking which audit path, runner filter, or gate status is authoritative.

## Workstream H - Candidate-Fact Escalation Decision

### Assumption

Candidate facts are expensive and invasive. They should be built only if the
stability harness shows that the direct final-row extractor remains unstable in
substantive ways after A-G.

### Files Owned

- design docs only, unless Austin explicitly approves implementation

### Entry Conditions

Do not implement candidate facts unless at least one of these is true across
three same-config archived xhigh reference runs:

- hard flags move between deals or rows after D fixes;
- row cardinality changes in a way not explained by rulebook changes;
- anonymous bidder lifecycle counts remain unstable after prompt/rule fixes;
- final-round same-day metrics remain unstable after validator pairing fixes;
- date diagnostics show row-level substitutions that cannot be represented by
  current fields and flags;
- bid-type classification changes without evidence changes;
- Austin's manual filing review identifies repeated model bookkeeping failures
  that Python could compile deterministically from smaller facts.

### If Escalated

The candidate-fact design should begin with a paragraph indexer and a reference
coverage report, not a replacement final compiler. The first deliverable would
be:

```text
SEC Background section
  -> stable paragraph IDs
  -> model candidate facts with paragraph IDs
  -> paragraph coverage and candidate-count report
```

Only after coverage is inspectable should a deterministic compiler be designed.

### Deferred Fields

These remain deferred until escalation:

- `date_basis`;
- `bid_type_basis`;
- `formal_round_status`;
- `final_round_role`;
- `cohort_id`;
- `cohort_size`;
- `cohort_basis`;
- `drop_group_basis`.

Do not sneak these into the active schema as isolated patches.

## Global Acceptance Criteria

The implementation is complete when all of the following are true:

1. Target deals cannot be selected while the reference gate is closed.
2. `validated` is not counted as a successful or complete status.
3. Every fresh extraction attempt creates an immutable audit run directory.
4. `latest.json` is the only mutable audit pointer.
5. `--re-validate` reads only cache-eligible archived runs.
6. Old loose audit files are not accepted as live cache.
7. Linkflow calls still use Responses streaming and prompt-only JSON.
8. Local schema validation rejects stale fields, missing required fields,
   invalid enums, additional properties, malformed custom-call outputs, and
   `maxLength` violations.
9. Known prompt/rule/validator contradictions are resolved and tested.
10. Reconciliation can explain whether progress/output/flags/audit agree.
11. Stability harness can classify three archived reference runs without model
    calls.
12. Operator docs describe the exact reference-run protocol and audit v2 paths.
13. No target deal has been extracted during implementation.
14. No fallback JSON repair, broad rewrite agent, or backward-compatible old
    reader has been added.

Minimum verification before merging implementation:

```bash
python -m pytest -x
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pipeline.reconcile --scope reference
```

The reconcile command may report existing live artifact problems until the
reference set is regenerated under audit v2. It must not crash or silently pass
inconsistent state.

## What Not To Build Now

Do not build these in the first implementation wave:

- candidate-fact extractor;
- paragraph-index evidence spine;
- deterministic candidate compiler;
- new basis/status/cohort/drop-group schema fields;
- OpenAI Structured Outputs dependency for Linkflow;
- JSON repair model;
- broad model-based validator;
- full-output adjudicator/rewrite pass;
- target-deal extraction;
- old audit/state/output compatibility layer;
- automated work claiming for multiple production pool processes.

The project rule is to watch the pipeline fail before adding new machinery.
After this implementation, the stability harness is how we watch it fail.

## Agent Review Checklist

Before an agent returns work, it must answer:

1. Did I preserve the Linkflow prompt-only JSON path?
2. Did I avoid target-deal extraction?
3. Did I avoid backward-compatible readers or fallback repair paths?
4. Did I update every live contract touched by my code?
5. Did I add tests that fail on the old behavior?
6. Did I leave generated artifacts alone unless the workstream explicitly owned
   them?
7. Did I document any new assumption in the rulebook or this implementation doc?

If any answer is no, the workstream is not done.

## Source Files Reviewed For This Blueprint

- `AGENTS.md`
- `SKILL.md`
- `docs/linkflow-extraction-guide.md`
- `prompts/extract.md`
- `rules/schema.md`
- `rules/events.md`
- `rules/bidders.md`
- `rules/bids.md`
- `rules/dates.md`
- `rules/invariants.md`
- `pipeline/core.py`
- `pipeline/run_pool.py`
- `pipeline/llm/audit.py`
- `pipeline/llm/client.py`
- `pipeline/llm/extract.py`
- `pipeline/llm/adjudicate.py`
- `pipeline/llm/response_format.py`
- `tests/test_run_pool.py`
- `tests/test_invariants.py`
- `tests/test_prompt_contract.py`
- `tests/llm/test_audit.py`
- `tests/llm/test_client.py`
- `tests/llm/test_extract.py`
- `tests/llm/test_response_format.py`
- `state/progress.json`
- `state/flags.jsonl`
- `output/extractions/*.json`
- `reference/alex/*.json`
