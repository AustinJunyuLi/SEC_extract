# Deal Graph Review Gate Redesign Implementation Plan

## Objective

Rebuild the live `deal_graph_v1` extraction gate around the production contract
we actually want:

- extraction produces a source-backed canonical graph;
- extraction produces a single review CSV/JSONL surface for human and
  agent-assisted review;
- extraction does not produce estimator rows;
- LLM variation is acceptable when it is quarantined and surfaced as review
  burden, not hidden behind a brittle byte-stability gate;
- system failures fail loudly and never refresh trusted extraction outputs.

This is a breaking architecture refactor. There are no fallbacks, no
compatibility aliases, no deprecated readers, and no migration shims. State,
outputs, audit history, and flags for non-reference deals are deleted at
cutover. Code, tests, prompts, rules, and docs are rewritten in one coherent
pass under one contract.

## Development Doctrine

These constraints are binding for every phase:

- **No fallback behavior.** No "if old, accept; if new, validate" branches.
- **No backward compatibility.** No aliases, no readers for retired schemas, no
  migration helpers. Retired data is deleted, not preserved.
- **No overengineering.** Simplest mechanism that satisfies the contract.
- **No overfit.** Mac Gray, PetSmart, Zep, and the reference nine are
  calibration cases. They never appear in live prompt or rulebook as named law.
- **No patchlike behavior.** Doctrine is one tight invariant per concept, not
  a stack of reactive paragraphs.
- **First principles only.** Filing text is ground truth. Python owns
  validation. Uncertainty is surfaced through review status, never hidden.
- **No commit of secrets.** Runtime credentials live in `.env` or shell
  environment only.
- **Respect in-flight work.** Inspect the dirty worktree before edits. Do not
  revert unrelated changes; do reconcile changes that contradict this plan.

## Locked Product Contract

### Provider Contract

The LLM provider emits claim-only payloads:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Every claim carries source-addressed `evidence_refs`:

```json
{"citation_unit_id": "page_35_paragraph_4", "quote_text": "exact filing substring"}
```

The provider does not emit:

- canonical ids;
- source offsets;
- dispositions;
- review status;
- coverage results;
- review rows;
- estimator rows;
- `BidderID`, `T`, `bI`, `bF`, admitted/dropout variables;
- target-only actor claims (target identity comes from the filing manifest).

Python owns all of those.

### Extraction Outputs

For per-run statuses `passed_clean`, `needs_review`, and `high_burden`,
extraction writes:

- `output/audit/{slug}/runs/{run_id}/raw_response.json`
- `output/audit/{slug}/runs/{run_id}/deal_graph.duckdb`
- `output/audit/{slug}/runs/{run_id}/deal_graph_v2.json`
- `output/audit/{slug}/runs/{run_id}/validation.json`
- `output/audit/{slug}/runs/{run_id}/final_output.json`
- `output/extractions/{slug}.json`
- `output/review_csv/{slug}.csv`
- `output/review_rows/{slug}.jsonl`
- `state/progress.json`
- `state/flags.jsonl`

Extraction writes nothing related to the estimator:

- no `output/projections/estimation_bidder_rows/` directory;
- no `estimation_bidder_rows` field in any artifact;
- no estimator row in audit `final_output.json`;
- no estimator metric/fingerprint in stability proof.

The estimator is a separate post-review product. It is not implemented in this
refactor.

`output/extractions/{slug}.json` declares `"schema_version": "deal_graph_v2"`.
The audit run JSON path is `deal_graph_v2.json`. Python rejects any artifact
with the retired `deal_graph_v1` schema string.

### Failed-System Behavior

`failed_system` fails loud. It writes raw audit and error artifacts for
debugging. It never creates or refreshes trusted extraction or review output:

- no canonical graph at `output/extractions/{slug}.json`;
- no review CSV at `output/review_csv/{slug}.csv`;
- no review JSONL at `output/review_rows/{slug}.jsonl`.

If a slug previously held trusted output and the newest run fails, the prior
output is left in place but the per-deal status flips to
`stale_after_failure`. Reconcile and the CLI surface this status as a loud
warning. The deal is not eligible for any reference or release gate while in
`stale_after_failure` and must be re-extracted to clear the state.

## Status Taxonomy

Per-run extraction statuses:

- `passed_clean` — canonical graph and review output exist; zero open review
  items.
- `needs_review` — canonical graph and review output exist; 1 to 10 open
  review items (manageable workload).
- `high_burden` — canonical graph and review output exist; more than 10 open
  review items (called out loudly).
- `failed_system` — runtime, schema, artifact, or graph-integrity failure.
  No trusted extraction output is written or refreshed.
- `stale_after_failure` — slug previously had trusted output, latest run
  failed; the prior output remains on disk but is not trusted.

Reference-level metadata (independent of per-run status):

- `verified` — boolean. Reference calibration label maintained by
  `scripts/mark_reference_verified.py`. Carries a `verification_report` path
  and a `last_verified_run_id`. Not a per-run extraction outcome.

Retired status names (must not appear in any code path, doc, or active test):

- `validated`
- `passed`
- `failed` (audit outcome literal — replaced by `failed_system`)
- `validated_reference_blocked` (reconcile issue code — replaced by
  `reference_artifact_stale`)
- `pending` only survives as the absence of a status entry; no code writes
  `pending` as an outcome.

## Review Burden Rule

Burden is defined directly on the review CSV. One row per canonical row, plus
one row per fully-rejected claim that produced no canonical row. A claim with
some refs that bound and some that failed contributes only its canonical row;
the failed refs become entries in that row's issues column.

Burden = count of CSV rows where `review_status != "clean"`.

- 0 → `passed_clean`
- 1 to 10 → `needs_review`
- more than 10 → `high_burden`

There is no scoring model. Burden is an operator signal, not a hidden quality
estimator.

## Review CSV Contract

`output/review_csv/{slug}.csv` and `output/review_rows/{slug}.jsonl` are the
single human and agent-assisted review surface. They share the same row
schema.

`review_status` values:

- `clean` — source-backed canonical row, no open issue.
- `needs_review` — canonical row with one or more open issues, or a flagged
  evidence ref that did not block the row from existing.
- `rejected_claim` — provider claim where every supporting ref failed to bind
  and no canonical row was produced.

Required fields:

- `deal_slug`
- `run_id`
- `review_status`
- canonical row fields where applicable (`event_id`, `event_date`,
  `event_type`, `event_subtype`, `actor_id`, `actor_label`, `actor_kind`,
  `actor_role`, `bid_value`, `bid_value_lower`, `bid_value_upper`,
  `bid_value_unit`, `consideration_type`, `bid_stage`,
  `cycle_id`)
- `claim_id` (always present; identifies the source claim of the row)
- `claim_type` (`event_claim`, `bid_claim`, `actor_claim`,
  `participation_count_claim`, `actor_relation_claim`)
- `claim_summary` (plain-language one-line summary)
- `confidence` (`low`, `medium`, `high` — informational column; does not
  drive `review_status`)
- `citation_unit_id`
- `supplied_quote` (the provider's `quote_text`)
- `bound_source_quote` (the exact substring Python actually bound to, or
  empty if binding failed)
- `bound_source_page` (page number where the bound substring was found, or
  empty)
- `issue_codes` (comma-joined list of fired `flag_id` codes; empty for
  `clean` rows)
- `issue_reasons` (joined list of human-readable issue reasons)
- `suggested_action` (terse hint for reviewer; empty for `clean` rows)
- `evidence_ref_index` (failing ref index for binding-failure rows; empty
  otherwise)

Resolution fields (always emitted, blank by default; reserved for future
review-tooling integration without changing the schema):

- `review_resolution`
- `reviewed_by`
- `reviewed_at`
- `resolution_reason`
- `corrected_citation_unit_id`
- `corrected_quote_text`

Field order in the CSV is deterministic and listed explicitly in
`pipeline/deal_graph/export.py`. JSONL preserves the same key order for
agent consumers.

## Failure Boundary

### Failed-System Cases

Classify as `failed_system` when the machinery is unsafe:

- provider response is invalid JSON or invalid strict schema;
- provider emits Python-owned fields;
- required claim fields are missing;
- evidence refs are malformed before binding can run;
- filing pages or citation units are missing or malformed;
- a supported canonical row lacks source evidence;
- claim disposition ledger is internally inconsistent;
- coverage links or results required by the live graph are missing;
- graph JSON, DuckDB, audit manifest, or progress state disagree;
- review output cannot be written;
- runtime, provider, auth, or timeout failure;
- artifact carries the retired `deal_graph_v1` schema string instead of
  `deal_graph_v2`.

### Review-Required Cases

Classify as review output, not system failure, only when the issue is
quarantined:

- claim is preserved for inspection;
- no canonical row is created from unsupported claim content (becomes
  `rejected_claim`), OR a canonical row was created from other refs and the
  failure is folded into its issues column (`needs_review`);
- review packet has claim id, claim type, summary, supplied quote, citation
  unit, reason, diagnostics, and suggested action;
- supported canonical rows remain source-backed.

Examples (calibration cases — do not encode as named law in prompts):

- exact quote is not a substring of the cited citation unit;
- citation unit appears wrong;
- quote is ambiguous inside the citation unit;
- group or member timing is unclear;
- bidder label or consortium boundary needs human judgment;
- date or value interpretation is source-local but uncertain.

Diagnostics are for review only. They are never used as a binding fallback.

## Implementation Phases

### Phase 0: Read Current Repo State

Before any edit:

```bash
git status --short
git diff --stat
sed -n '1,220p' AGENTS.md
sed -n '1,220p' SKILL.md
```

Read the live extraction paths:

- `pipeline/deal_graph/orchestrate.py`
- `pipeline/deal_graph/canonicalize.py`
- `pipeline/deal_graph/validate.py`
- `pipeline/deal_graph/project_review.py`
- `pipeline/deal_graph/export.py`
- `pipeline/deal_graph/store.py`
- `pipeline/deal_graph/schema.py`
- `pipeline/deal_graph/__init__.py`
- `pipeline/deal_graph/project.py`
- `pipeline/core.py`
- `pipeline/run_pool.py`
- `pipeline/stability.py`
- `pipeline/reconcile.py`
- `pipeline/llm/extract.py`

The dirty worktree already contains substantial preliminary work — the
implementer must respect it and build forward, not redo it. Specifically,
the worktree has already:

- gutted ~2200 LOC of legacy row-event code from `pipeline/core.py`
  (current file is ~326 LOC);
- deleted `scoring/diff.py`, `scripts/render_review_csv.py`,
  `tests/test_diff.py`, `tests/test_invariants.py`,
  `tests/test_review_csv.py`, `tests/test_zep_phase_regression.py`,
  and ~80 retired row-event fixtures under `tests/fixtures/`;
- introduced atomic file writes in `pipeline/deal_graph/export.py` and
  `pipeline/deal_graph/orchestrate.py`;
- wired Python-owned target identity through `_target_name(slug)` and
  `canonicalize.py`, with a `deals.target_name` DuckDB column;
- added canonical fields `bid_stage`, labels on `actor_relations`/
  `event_actor_links`, and `role_detail` in relation_id;
- shipped `validate.py:128-136` quarantine for blocking review flags so
  rejected claims do not auto-block;
- bumped stability proof to `target_gate_proof_v2` with `selected_run_dirs`
  and run-dir existence checks;
- tightened `mark_reference_verified` to require
  `extraction_run_id == progress.last_run_id`;
- rewrote `scripts/check_reference_verification.py` to mechanically ground
  evidence_refs against filing pages.

The worktree also contains two changes that contradict this plan and must be
reverted before Phase 9 runs:

- `prompts/extract.md` lines 54-77: stacked reactive quote-fidelity
  paragraphs ("Do not change the first letter's case", "Never remove other
  actors from a compound list"). These are patchlike accretion. Revert.
- `rules/schema.md`: a sentence beginning "Exact means byte-for-byte visible
  text copying...". Revert. The intent (curly versus straight quote
  handling) survives in the canonical Phase 9 invariant.

Stop and ask before proceeding only if the worktree contains other unrelated
changes whose ownership is unclear.

### Phase 1: Hard-Delete Non-Reference State

Cutover starts with a clean slate. The new gate is tested on the 9 reference
slugs first; non-reference deals are re-seeded from `seeds.csv` later as
needed.

Reference slugs (the only survivors):

```
imprivata, mac-gray, medivation, penford, petsmart-inc,
providence-worcester, saks, stec, zep
```

Delete from `state/progress.json` every entry whose slug is not in the
reference set. Do this with a one-shot script that reads the file, filters
the `deals` array, and writes the result atomically. The script is then
deleted (no migration helpers in the live tree).

Delete the following on disk for every non-reference slug:

- `output/extractions/{slug}.json`
- `output/review_csv/{slug}.csv`
- `output/review_rows/{slug}.jsonl`
- `output/audit/{slug}/` (entire directory, including all run history)

Filter `state/flags.jsonl` to retain only entries whose `slug` is in the
reference set. Rewrite the file atomically. The append-only invariant
applies to entries written after Phase 1 completes; the cutover filter is
the one allowed exception, performed by a one-shot script that is then
deleted.

Delete the entire `output/projections/estimation_bidder_rows/` directory if
present. The estimator is being removed for all deals (Phase 2), so even
reference slugs lose their estimator outputs.

After Phase 1 completes:

- only the 9 reference slugs appear in `state/progress.json`;
- only the 9 reference slugs have on-disk extraction, review, and audit
  artifacts;
- `state/flags.jsonl` contains only reference-slug entries;
- `output/projections/` does not contain `estimation_bidder_rows`.

The 9 reference progress entries retain their existing `status` and
`verified` metadata. They are about to be re-extracted in Phase 11 anyway,
which will overwrite the per-run fields under the new contract. Do not
attempt to migrate their statuses.

### Phase 2: Remove Estimator From Live Extraction

Edit `pipeline/deal_graph/orchestrate.py`:

- remove the call to `project_estimation_rows()`;
- remove `estimation_bidder_rows` from `final_output`;
- remove the estimator JSONL write to
  `output/projections/estimation_bidder_rows/`;
- remove every estimator path field from result objects.

Delete entirely:

- `pipeline/deal_graph/project_estimation.py`
- `pipeline/deal_graph/project.py` (the CLI subcommand module — the
  `--projection estimation` entry point is retired);
- `tests/deal_graph/test_estimation_projection.py`
- `tests/deal_graph/test_consortium_projection.py`

Edit `pipeline/deal_graph/__init__.py`: remove `project_estimation_rows`
from imports and `__all__` (currently lines 5 and 12). Remove the
`project_estimation` re-export.

Edit `pipeline/deal_graph/store.py`: remove the
`estimation_bidder_rows` entry from `table_map` (currently line 173).

Edit `pipeline/deal_graph/schema.py`:

- remove the `estimation_bidder_rows` DuckDB DDL block (currently lines
  580-587);
- remove `estimation_bidder_rows` from `TABLE_NAMES` (currently line 376);
- bump the canonical schema version to `deal_graph_v2` and rename the
  audit run JSON file from `deal_graph_v1.json` to `deal_graph_v2.json`
  (one rename across `orchestrate.py`, `canonicalize.py`, `store.py`,
  `validate.py`, `stability.py`, and any reader/writer that references
  the path or string).

Edit `pipeline/deal_graph/validate.py`: remove the
`DG_PROJECTION_BLOCKED` validator that reads
`graph["estimation_bidder_rows"]` (currently lines 145-151). The whole
projection-blocked check is retired.

Edit `pipeline/deal_graph/canonicalize.py`: remove or reword the
`# strategic for estimation` doc comment (currently line 465); the canonical
graph carries no projection coupling.

Edit `pipeline/stability.py` to remove every estimator surface:

- `LIVE_GRAPH_LIST_KEYS` entry for `estimation_bidder_rows` (line 39);
- estimation count, fingerprint, and metric collection (lines 101-103,
  136-138);
- `_load_archived_run` reading `final_output["estimation_bidder_rows"]`
  (lines 229-235);
- estimation drift comparators (lines 440-470, 488-503, 557-561);
- `_list_of_dicts(final_output, "estimation_bidder_rows", ...)` requirement
  (lines 606-617);
- estimation flag-count comparators (lines 744-746);
- estimation metric reporting in `build_json_summary` (lines 877-878);
- adds `"no_estimator": True` confirmation to the JSON summary so the
  stability proof explicitly records the absence.

Edit docs and rulebooks to remove estimator references:

- `AGENTS.md` line 63: remove the
  `output/projections/estimation_bidder_rows/{slug}.jsonl` artifact line.
- `SKILL.md` lines 51, 72, 78: remove "estimator variables", "estimation
  bidder rows", "estimator unit" — the provider has never owned estimator
  output and Python no longer projects it from the live extraction path.
- `docs/linkflow-extraction-guide.md` lines 64, 105: remove estimation
  projection references.
- `rules/schema.md` line 117: remove the estimator artifact reference.
- `rules/bids.md` line 4: remove "not carry estimator variables" — the
  provider rule is now stated positively at one site only.
- `prompts/extract.md`: scrub any estimator references (Phase 9 also
  rewrites this file; coordinate so estimator removal lands cleanly).
- All 9 reference verification reports (`quality_reports/reference_
  verification/*.md`) contain the literal phrase "current systematic
  estimator projection rule". Phase 11 regenerates these reports from
  scratch so this line will not survive; do not patch the existing
  files in this phase.

Tests (`tests/test_mark_reference_verified.py:101`, `tests/test_reference_
verification_reports.py:96`) currently seed `"estimation_bidder_rows": []`
into extraction JSON. Remove those seed lines.

### Phase 3: Build Review Status Projection

Update `pipeline/deal_graph/project_review.py` to emit three row classes,
all sharing the schema in the Review CSV Contract section:

- **Clean canonical rows** — every supported canonical event/relation/count
  row that has no open review flag.
- **Needs-review canonical rows** — canonical rows that exist and have one
  or more open review flags. Bundle all flags into `issue_codes` and
  `issue_reasons` for the row.
- **Rejected-claim rows** — provider claims that produced no canonical row.
  These are sourced from `graph["claims"]`,
  `graph["claim_dispositions"]` (where `disposition == "rejected_unsupported"`),
  `graph["review_flags"]`, and evidence binding failure metadata.

Implementation notes:

- partial-failure claims (some refs bound, some failed) contribute only
  their canonical row, with the failed-ref details folded into
  `issue_codes`, `issue_reasons`, and `evidence_ref_index`. They do not
  produce a separate `rejected_claim` row;
- thread `confidence` from the source claim through to the row;
- preserve `claim_id` and `claim_type` even on `clean` rows;
- the `bid_stage` canonical field flows through unchanged.

Remove the `hard_count == 0` gate at `orchestrate.py:81` (current behavior
skips review projection entirely when any hard validation flag fires;
under the new contract review projection always runs).

Update `pipeline/deal_graph/schema.py` `review_rows` DuckDB DDL to add the
new columns. Update `pipeline/deal_graph/export.py:31` to use a stable,
explicit fieldnames list so column order is deterministic across rows that
omit some fields.

Retire `output/review_csv/_combined.csv` (legacy estimator-shape combined
CSV). It is regenerated at extraction time from per-deal review CSVs only
if a future tool needs it; under the current contract it is not written.

This phase is review output only. It does not produce estimator rows.

### Phase 4: Preserve Sharp Review Metadata

Update validation and flag logging so review packets stay actionable:

- propagate `flag_id` from `graph.review_flags` into the gate-facing flags;
- preserve or link to review metadata in `state/flags.jsonl`;
- record the failing `evidence_ref_index` for multi-ref claims;
- include all supplied refs (not just the first) in the row's diagnostics;
- keep candidate-unit diagnostics as diagnostics only — they never re-bind.

Files likely to change:

- `pipeline/deal_graph/orchestrate.py`
- `pipeline/deal_graph/validate.py`
- `pipeline/core.py`
- `tests/deal_graph/test_quote_binding.py`
- `tests/test_pipeline_runtime.py`

Do not add an automatic quote fixer.

### Phase 5: Replace Status Classification

Update status computation in:

- `pipeline/deal_graph/orchestrate.py`
- `pipeline/core.py` (the skip predicate currently at line 267 must
  reference the new status set)

Status computation (per run):

1. If runtime, schema, artifact, or graph-integrity failure occurs before a
   trusted graph and review output can be written → `failed_system`.
2. If a slug previously held trusted output and the newest run is
   `failed_system` → set per-deal status to `stale_after_failure`. The
   prior trusted output is left in place; reconcile and CLI surface the
   warning.
3. If the graph is trusted and burden = 0 → `passed_clean`.
4. If 1 ≤ burden ≤ 10 → `needs_review`.
5. If burden > 10 → `high_burden`.

Where burden is the count of CSV rows with `review_status != "clean"`.

Update `pipeline/llm/extract.py:342`: the audit `outcome` literal must be
`failed_system`, not `failed`.

Update `pipeline/reconcile.py`:

- rename `ACTIVE_STATUSES` (line 24) to the new set:
  `{"passed_clean", "needs_review", "high_burden", "stale_after_failure"}`;
- rename the issue code `validated_reference_blocked` (line 743) to
  `reference_artifact_stale`;
- delete the `verified_has_hard_flags` check (lines 723-747) — verified
  references are allowed to have review items under the new contract.

Important boundary:

- rejected unsupported claims, when quarantined into the review CSV as
  `rejected_claim` rows, are not graph-integrity failures;
- supported canonical rows missing evidence remain graph-integrity failures
  (`failed_system`).

### Phase 6: Update Batch Runtime

Update `pipeline/run_pool.py`.

Success statuses (extraction work proceeds, deal is reportable):

- `passed_clean`
- `needs_review`
- `high_burden`

Failure statuses (extraction work blocks gates):

- `failed_system`
- `stale_after_failure`

Reference-level metadata `verified` is independent and applies on top of
any success status.

Replace `DONE_STATUSES` and `FINALIZED_STATUSES` (lines 34-35) with the new
sets. Replace the skip predicate at `pipeline/core.py:267` so it accepts
the new statuses and rejects retired ones. Treat any deal whose stored
status string is not in the new taxonomy as a hard error (no silent
tolerance).

Batch summary reports per run:

- selected count
- `passed_clean` count
- `needs_review` count
- `high_burden` count
- `failed_system` count
- `stale_after_failure` count
- review item count per deal
- review CSV path per deal

Dry-run behavior and target-gate preflight remain fail-closed before audit
directories, SDK clients, or model calls.

### Phase 7: Update Reconcile

Update `pipeline/reconcile.py`.

Reconcile enforces:

- per-deal status is one of `passed_clean`, `needs_review`, `high_burden`,
  `failed_system`, or `stale_after_failure` — anything else is a hard
  error;
- latest output, progress, and audit run ids agree;
- graph JSON (`deal_graph_v2.json`) and DuckDB are present for every
  trusted-output status;
- review JSONL and CSV exist for `passed_clean`, `needs_review`, and
  `high_burden`;
- no trusted outputs are written for `failed_system` (the latest run did
  not refresh them);
- prior trusted outputs are present but flagged when status is
  `stale_after_failure`;
- no estimator rows or directories exist anywhere;
- artifacts declare `schema_version: deal_graph_v2`; any artifact carrying
  retired schema strings is a hard error;
- `verified` references retain a calibration report and a
  `last_verified_run_id` matching the current `last_run_id`. Verification
  is reference-level metadata, not a per-run extraction outcome.

There is no legacy-status tolerance. Phase 1's hard delete removed every
non-reference deal whose status would have been retired, and Phase 11
re-extracts the 9 references under the new contract. After Phase 11,
no retired status string can exist anywhere; reconcile's strict check is
safe.

### Phase 8: Update Stability And Target Gate

Update `pipeline/stability.py`.

Eligible archived outcomes:

- `passed_clean`
- `needs_review`
- `high_burden`

Ineligible or blocking:

- `failed_system`
- `stale_after_failure`
- artifacts declaring retired schema (`deal_graph_v1`, `audit_run_v2`);
- raw provider payload that is not claim-only;
- contract drift inside the selected proof window (defined as any change
  in `config_identity`: model, reasoning effort, provider, prompt hash,
  schema hash, rulebook hash, extractor contract version);
- missing graph or review artifacts;
- missing selected run directories;
- accepted canonical rows missing evidence.

Do not block merely because:

- review row counts differ across runs;
- claim counts differ across runs;
- source quote wording differs while still exact-bound;
- some runs have review items;
- LLM content granularity varies.

Replace `ELIGIBLE_OUTCOMES` (line 27). Stop treating hard or soft flags as
instability in `_classify_slug` (lines 693-727); flags are now review
output, not stability failures.

Bump the proof schema string from `target_gate_proof_v2` to
`target_gate_proof_v3`. Update both the writer in `stability.py` and the
reader checks in `pipeline/run_pool.py:_stability_proof_status`. The
existing `quality_reports/stability/target-release-proof.json` is
discarded; Phase 11 generates a fresh proof window.

Proof output explicitly reports:

- selected run ids
- selected run directories
- per-slug status (one of the three eligible outcomes)
- review item counts per slug
- high-burden counts per slug
- `"no_estimator": true` confirmation

Update `pipeline/run_pool.py` target-gate proof checks so targets require:

- proof schema version equals `target_gate_proof_v3` (exact-match);
- reference slugs match `core.REFERENCE_SLUGS` (the canonical source of
  truth — `seeds.csv` is read for seeding only, not for gate identity);
- at least three selected runs per reference slug;
- selected run directories exist;
- proof accepts `passed_clean`, `needs_review`, and `high_burden`;
- no `failed_system` or `stale_after_failure` in the selected proof
  window;
- operator passes `--release-targets`.

### Phase 9: Prompt And Rulebook Cleanup

The provider schema does not change. Phase 9 rewrites prompt and rulebook
to remove deal-specific law and patchlike accretion.

Revert worktree edits flagged in Phase 0:

- `prompts/extract.md` lines 54-77 (stacked reactive paragraphs);
- `rules/schema.md` "byte-for-byte" sentence.

Remove deal-specific law from live prompt and rulebook:

- `prompts/extract.md` lines 121-128 (Mac Gray CSC/Pamplona, PetSmart Buyer
  Group/Longview);
- `prompts/extract.md` lines 130-131 (changing-coalition guidance, recast
  to deal-agnostic);
- `rules/bidders.md` lines 34-44 (Mac Gray, PetSmart, Sponsor A/E
  examples);
- `rules/bids.md` lines 44-45 (Mac Gray strategic-T projection example);
- `AGENTS.md` lines 119-133 (Consortium Doctrine section using Mac Gray
  and PetSmart as live law);
- `SKILL.md` lines 81-85 (Mac Gray, PetSmart consortium examples).

Calibration examples that remain useful (Mac Gray, PetSmart, Sponsor A/E)
move to test fixtures under `tests/deal_graph/fixtures/calibration/` or to
the per-slug verification reports under
`quality_reports/reference_verification/`. They never appear in live
prompt or rulebook.

Replace with first-principles invariants:

1. Preserve the filing's bidding unit. Do not atomize group bids unless
   the filing shows separate bidding conduct.
2. Member, support, financing, and rollover facts are
   `actor_relation_claims`, not new bidder rows.
3. Relation timing is source-backed. `effective_date_first` is populated
   only when the filing supports it.
4. **Quote fidelity invariant.** `quote_text` must be an exact contiguous
   substring of `citation_units[citation_unit_id].text` — byte-for-byte,
   including punctuation, capitalization, and curly versus straight
   quote marks. (This is the single canonical statement of the rule. No
   other sentence in any prompt or rulebook restates it.)
5. Exact-or-omit. If no exact substring supports the typed fields
   sharply, omit the claim.
6. Ambiguity surfacing. Ambiguity goes through low confidence (column on
   review CSV), omission, or Python-owned review status. The provider
   never invents content.
7. Provider scope. Claim-only payload. Python owns canonical ids, source
   offsets, dispositions, coverage, review status, and projections.
8. Target identity from the filing manifest only. The provider does not
   emit a target-only actor claim.

Python binding enforces invariant 4. The prompt does not stack additional
warnings.

After this phase, the deal-name greppable surface in live operating
guidance must be empty. The Final Verification grep confirms.

### Phase 10: Test Updates

Delete:

- `tests/deal_graph/test_estimation_projection.py`
- `tests/deal_graph/test_consortium_projection.py`

Update with the new status taxonomy and contract:

- `tests/test_run_pool.py:81-89, 134-144, 710-738, 858-891` — drop
  `validated`/`passed`/`failed` literals; assert that retired statuses are
  rejected as hard errors;
- `tests/test_reconcile.py:249-279, 352-371` — drop `validated`/`passed`
  literals; rewrite `validated_reference_blocked` test to assert
  `reference_artifact_stale`;
- `tests/test_stability.py:212, 234, 284-323, 345-362` — drop
  `estimation_bidder_rows` seeds and retired outcome literals;
- `tests/test_mark_reference_verified.py:101` and
  `tests/test_reference_verification_reports.py:96` — remove
  `"estimation_bidder_rows": []` extraction-JSON seeds.

Invert `tests/test_prompt_contract.py:88-99`:

- assert ABSENCE of `CSC|Pamplona|Buyer Group|Longview|Sponsor [A-Z]` in
  `prompts/extract.md`, `rules/bidders.md`, `rules/bids.md`,
  `AGENTS.md`, `SKILL.md`;
- assert PRESENCE of the eight first-principles invariants from Phase 9.

Add new tests:

- provider schema remains claim-only (covered today by
  `tests/deal_graph/test_provider_contract.py` and
  `tests/llm/test_response_format.py`);
- provider cannot emit Python-owned fields (covered);
- extraction emits no estimator rows — assert
  `extract_deal`/`finalize_claim_payload`/`final_output` carry no
  `estimation_bidder_rows`, no `output/projections/...` is written;
- quote-binding failure for every supplied ref produces a
  `rejected_claim` row in CSV/JSONL (extends
  `tests/deal_graph/test_quote_binding.py`);
- partial quote-binding failure (1 of 2 refs binds) produces a single
  canonical row with `review_status=needs_review` and the failed ref
  details in `issue_codes`/`evidence_ref_index`;
- clean canonical rows carry `review_status=clean`;
- review burden boundaries: 0 → `passed_clean`, 1 → `needs_review`,
  10 → `needs_review`, 11 → `high_burden`;
- `failed_system` writes no review CSV/JSONL and no
  `output/extractions/{slug}.json`;
- `stale_after_failure`: a slug with prior trusted output where the next
  run fails ends in `stale_after_failure`, prior outputs remain on disk,
  reconcile flags the slug;
- batch exits success with each of `passed_clean`, `needs_review`,
  `high_burden`;
- batch exits failure with `failed_system`;
- batch surfaces `stale_after_failure` as a warning, not a clean exit;
- target gate accepts proof windows containing all three eligible
  outcomes;
- target gate blocks on `failed_system` in window, on
  `stale_after_failure` in window, on missing `--release-targets`, on
  schema mismatch (`target_gate_proof_v2` is rejected as stale), and on
  missing proof directories.

Suggested focused command:

```bash
python -m pytest \
  tests/deal_graph \
  tests/llm/test_response_format.py \
  tests/llm/test_extract.py \
  tests/test_prompt_contract.py \
  tests/test_run_pool.py \
  tests/test_reconcile.py \
  tests/test_stability.py \
  -q
```

Full suite:

```bash
python -m pytest -q
```

### Phase 11: Reference Rerun

After unit tests and the full suite pass:

```bash
set -a; [ -f .env ] && source .env; set +a
python -m pipeline.run_pool --filter reference --workers 5 --re-extract \
  --extract-reasoning-effort high
python -m pipeline.reconcile --scope reference
python -m pipeline.stability --scope reference --runs 3 --json
```

After the first reference run completes:

- regenerate every `quality_reports/reference_verification/{slug}.md`
  report under the new contract. Each report cites the new run id, the
  new artifact paths, the new schema version, and contains no estimator,
  no `validated`/`passed` text, and no live-doctrine deal-specific law
  language;
- run `python scripts/check_reference_verification.py`. The script
  continues to require `extraction_run_id == progress.last_run_id`
  (no decoupling).

After three runs under one frozen contract pass cleanly, generate the
target-release proof:

```bash
python -m pipeline.stability --scope reference --runs 3 --json \
  > quality_reports/stability/target-release-proof.json
```

Inspect:

- every reference per-run status is one of `passed_clean`,
  `needs_review`, or `high_burden`;
- no reference run is `failed_system` or `stale_after_failure`;
- every trusted extraction has graph JSON (`deal_graph_v2.json`),
  DuckDB, review JSONL, and review CSV;
- no estimator rows or directories anywhere;
- review CSVs include `review_status`;
- rejected claims appear as `review_status=rejected_claim` rows.

If stability fails because the latest three selected runs cross a prompt,
schema, or rulebook change, do not patch prompts. Establish a fresh proof
window under one frozen contract.

## Post-Implementation Staleness Cleanse

Mandatory. No old live surfaces remain beside the new contract.

### Code And Output Surfaces

After Phase 1 hard-deletes the non-reference data, the following must be
unreachable from the live tree:

- `validated`, `passed`, `failed` (audit literal),
  `validated_reference_blocked`, `pending` (as a written status),
  `estimation_bidder_rows`, `project_estimation`,
  `project_estimation_rows`, `output/projections/estimation_bidder_rows`,
  `previous_response_id`, provider-level `quote_text`/`quote_texts`,
  `scoring/diff.py`, `scripts/render_review_csv.py`, row-event schema,
  repair loop, repair schema, repair tools, adjudicator path.

### Doc Rewrites

Each of the following describes one live contract:
`claim-only provider → Python-bound graph → review JSONL/CSV →
later post-review estimator phase`.

Update:

- `AGENTS.md`
- `SKILL.md`
- `CLAUDE.md`
- `docs/linkflow-extraction-guide.md`
- `rules/schema.md`
- `rules/invariants.md`
- `rules/bidders.md`
- `rules/bids.md`
- `prompts/extract.md`
- `quality_reports/reference_verification/README.md`

### Reference Reports

The 9 reference reports in
`quality_reports/reference_verification/{slug}.md` are regenerated as part
of Phase 11. The cleanse confirms none of them retain the literal
phrase "current systematic estimator projection rule", deal-specific
prompt law, retired status names, or
`python scoring/diff.py --slug ...` invocations.

### Historical Review Cleanup

`quality_reports/research-reviews/2026-05-06_team-review.md` and
`quality_reports/research-reviews/2026-05-06_gate-redesign-impact-map.md`:
move both to `quality_reports/research-reviews/_archive/` and add a
top-of-file note stating they are pre-redesign documents superseded by
this plan and are not active operating guidance.

### Generated Artifact Cleanup

Clean local cruft:

```bash
find . -name .DS_Store -delete
find . -type d -name __pycache__ -prune -exec rm -rf {} +
```

Phase 1 already deleted non-reference audit history. Reference audit
directories from before the cutover remain on disk but they exist under
the retired schema (`deal_graph_v1`, `audit_run_v2`). After Phase 11,
new reference runs land under the new schema; the pre-cutover audit
runs are kept as historical evidence and never reloaded by reconcile or
stability (both now require `deal_graph_v2` and `target_gate_proof_v3`).

## Final Verification

Run:

```bash
python -m pytest -q
python -m pipeline.reconcile --scope reference
python scripts/check_reference_verification.py
python -m pipeline.stability --scope reference --runs 3 --json
```

Then inspect:

```bash
git status --short
rg -n "validated|estimation_bidder_rows|project_estimation|scoring/diff|render_review_csv|adjudicat|repair|previous_response_id|SCHEMA_R1|row-event|row event|deal_graph_v1|target_gate_proof_v2|validated_reference_blocked" \
  AGENTS.md SKILL.md CLAUDE.md docs rules prompts pipeline scripts tests quality_reports
rg -n "Mac Gray|CSC|Pamplona|PetSmart|Buyer Group|Longview|Sponsor [A-Z]" \
  AGENTS.md SKILL.md CLAUDE.md docs/linkflow-extraction-guide.md rules prompts
```

The first grep must return no live operating matches. Calibration
references inside `tests/`, `quality_reports/reference_verification/`, or
`quality_reports/research-reviews/_archive/` are allowed.

The second grep must return no live operating matches. The reference
verification reports under `quality_reports/reference_verification/` and
test fixtures under `tests/` may keep deal names as calibration data.

## Final Commit Guidance

After implementation and verification:

1. Stage code, doc, test, state, and proof updates.
2. Stage Phase 1 hard-deletions explicitly (`git add -u` will pick them up).
3. Do not force-add ignored audit or output artifacts unless repo policy
   changes.
4. Commit with a message like:

```text
Redesign deal graph extraction gate around review outputs
```

The final handoff summarizes:

- estimator extraction removal (Phase 2);
- new per-run status taxonomy and `stale_after_failure` semantics
  (Phase 5);
- review CSV shape with `review_status`, `confidence`, and resolution
  fields (Phase 3);
- target gate change with `target_gate_proof_v3` and explicit
  `--release-targets` flag (Phase 8);
- prompt and rulebook reduction to first-principles invariants
  (Phase 9);
- non-reference data hard-delete and clean cutover (Phase 1);
- test inversions and additions (Phase 10);
- reference rerun results and three-run proof window (Phase 11).
