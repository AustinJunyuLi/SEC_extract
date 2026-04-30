# Prompt-First Staged Repair Design

Date: 2026-04-30

## Purpose

Recalibrate the extraction pipeline away from first-pass exploratory tool use
and toward a cheaper prompt-first workflow. The current strict schema plus
tool-heavy extractor produced useful auditability, but reference-run evidence
showed that repeated full-input tool replay drove input tokens into the
millions, created provider idle-timeout failures, and did not clearly improve
accuracy enough to justify the default cost.

The repair loop remains the valuable part of the refactor. This design keeps
strict structured output, deterministic Python validation, immutable audit
artifacts, and model repair, while spending tool budget only after a prompt-only
repair fails to clear hard validator flags.

## Goals

- Make prompt-only extraction the default first pass.
- Make the first repair turn prompt-only.
- Expose targeted repair tools only on the second repair turn, and only if hard
  flags remain after repair 1.
- Keep `check_row` available in repair 2 so the model can validate affected or
  revised rows before returning the final repair draft. Python validation
  remains the authoritative row checking gate.
- Preserve strict `SCHEMA_R1` structured output for every full extraction and
  repair body.
- Keep audit artifacts explicit enough to compare cost, hard flags, repair
  behavior, and tool use across recalibration runs.

## Non-Goals

- No fallback to free-form JSON.
- No partial JSON patches during repair; repairs still return complete
  `{deal, events}` payloads.
- No target-deal extraction changes.
- No new model role or external agent loop.
- No compatibility shim for retired tool-heavy audit contracts.

## Architecture

The live extraction flow becomes:

```text
extract_v1: strict schema, no tools, Background prompt
  -> validate_v1: deterministic Python
  -> if hard flags:
       repair_1: strict schema, no tools, validator report + affected rows + snippets
       validate_v2
  -> if hard flags remain:
       repair_2: strict schema, targeted repair tools
                 (search_filing/get_pages/check_row)
       validate_v3
  -> if hard flags remain:
       finalize latest draft with repair_loop_exhausted
  -> scoped Adjudicator for configured soft flags
  -> finalize_prepared + audit/state/output writes
```

The first extraction no longer advertises or supplies any native tools. The
first repair turn also has no tools. The second repair turn is the only point
where the model may call tools, and the exposed catalog is limited to
`search_filing`, `get_pages`, and `check_row`.

`check_row` is removed from first-pass extraction and repair 1 because Python
validation already performs deterministic row checks. In repair 2, `check_row`
is available only as a targeted quality aid for rows touched by the repair,
rather than a row-by-row first-pass verification routine.

## Components

### `pipeline.llm.extract`

Add a prompt-only call path for first extraction and repair 1. It sends strict
`text.format=json_schema` with `SCHEMA_R1` and does not pass `tools` or
`tool_choice`.

Keep a smaller tool-enabled call path for repair 2. It accepts an explicit tool
catalog and receives only the targeted repair tools: `search_filing`,
`get_pages`, and `check_row`. It must still emit a full schema-valid extraction
body after any tool calls.

`extract_deal(...)` always uses the prompt-only path.

`run_repair_loop(...)` becomes staged:

- turn 1: prompt-only;
- turn 2: targeted repair tools only;
- cap remains two turns;
- each turn validates the complete revised draft before deciding whether to
  continue.

### `pipeline.llm.tools`

Expose `search_filing`, `get_pages`, and `check_row` only for repair 2 in the
recalibrated pipeline.

Do not expose `check_row` during first extraction or repair 1. Repair 2 prompts
should instruct the model to call `check_row` only for hard-flagged rows,
directly revised rows, and rows whose validity depends on those revisions.

### Prompts And Contracts

`prompts/extract.md` should remove first-pass tool instructions and every
instruction that says the model must call `check_row` during initial
extraction.

`prompts/repair.md` should describe the staged behavior: repair 1 has no tools;
repair 2 may use targeted repair tools if hard flags remain.

`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and
`docs/linkflow-extraction-guide.md` should replace "strict Extractor + tools"
language with "strict prompt-first extractor + deterministic validator +
staged repair, with targeted tools only on second repair."

## Audit And State Contract

Keep existing fields:

- `repair_turns_used`
- `repair_loop_outcome`
- `tool_calls_count`
- token totals
- model names and reasoning efforts
- contract versions

Add or update manifest fields:

- `extract_tool_mode: "none"`
- `repair_strategy: "prompt_then_targeted_tools"`

Each `repair_turns.jsonl` record should include:

- `turn`
- `tool_mode`: `"none"` for repair 1, `"targeted_repair_tools"` for repair 2
- `hard_flags_before`
- `hard_flags_after`
- `completion_turns`
- `tool_calls_count`
- `outcome`

Contract hashes should change naturally:

- `extractor_contract_version` changes because prompt and first-pass call path
  change.
- `tools_contract_version` changes because the exposed LLM tool catalog changes.
- `repair_loop_contract_version` changes because repair turn semantics change.

Archived tool-heavy runs become stale for `--re-validate`. That is expected and
consistent with the repo's no-backward-compatibility doctrine.

## Error Handling

If first extraction fails at the provider or schema layer, the deal fails under
the existing per-deal isolation behavior.

If repair 1 fails as a model call, record the failed repair attempt in audit and
allow the deal to fail through the existing exception path. Do not silently jump
to repair 2 without a valid revised draft.

If repair 1 succeeds but hard flags remain, repair 2 runs with targeted repair
tools only.

If repair 2 succeeds but hard flags remain, finalize the latest draft and append
the deal-level hard `repair_loop_exhausted` flag.

If repair 2 fails at the provider layer, preserve the last good finalized state
behavior already used by fresh failed reruns and record the failed attempt in
audit metadata.

## Testing Plan

Unit and integration tests should assert:

- `extract_deal` calls the client with no tools on first extraction.
- `run_repair_loop` repair 1 calls the client with no tools.
- `run_repair_loop` repair 2 exposes exactly `search_filing`, `get_pages`, and
  `check_row`.
- No extractor prompt text instructs the model to call `check_row` during the
  first extraction.
- `tools_contract_version` changes when exposed tool definitions change.
- `repair_turns.jsonl` records `tool_mode` for each repair turn.
- `--re-validate` rejects stale audits with old extractor, tool, or repair-loop
  contract hashes.

## Recalibration Run

After implementation:

1. Run a single-deal smoke test on `petsmart-inc` with prompt-first extraction
   and staged repair.
2. Run the nine reference deals with `gpt-5.5`, reasoning effort `high`, and
   five workers.
3. Compare against the best prior prompt-only/high and strict-tools/high runs:
   wall time, input/output/reasoning tokens, hard flags, repair turns, tool
   calls, timeout/error rate, and reference diff noise.
4. Inspect any hard-flag clusters to determine whether repair 2 targeted tools
   were triggered and whether they helped.

## Success Criteria

- Reference batch token use returns near prompt-only scale rather than
  multi-million replay scale.
- Normal reference runs have zero provider idle-timeout failures.
- Hard flags are no worse than the prior prompt-only baseline and ideally
  improve because repair is retained.
- Tool calls are rare, only appear in repair 2, and are explainable from
  remaining hard validator failures.
- Audit artifacts make the staged behavior visible without reading logs.
