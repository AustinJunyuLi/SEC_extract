# Linkflow Extraction Guide

This guide is the operator contract for running the M&A extraction pipeline
through the Linkflow/NewAPI-compatible Responses endpoint. It covers transport,
tooling, repair-loop behavior, audit expectations, and the reference-to-target
release gate. Extraction doctrine still lives in `rules/*.md`.

## Linkflow Facts

Use the Responses API through the Linkflow proxy:

```bash
OPENAI_BASE_URL=https://www.linkflow.run/v1
OPENAI_API_KEY=<set in shell or .env, never in docs>
EXTRACT_MODEL=gpt-5.5
ADJUDICATE_MODEL=gpt-5.5
EXTRACT_REASONING_EFFORT=xhigh
ADJUDICATE_REASONING_EFFORT=xhigh
LINKFLOW_XHIGH_MAX_WORKERS=5
```

Observed provider constraints:

- `xhigh` reasoning is the default for extractor and adjudicator calls.
- `xhigh` concurrency is capped at five workers by default; the runner rejects
  larger pools before model calls.
- Linkflow has a 300s streaming idle timeout. Full extraction and repair-body
  turns stream so long-running reasoning keeps the connection alive.
- `previous_response_id` returns 400. Every extraction, tool-output replay, and
  repair turn uses full-input replay.
- Short tool-call/tool-output turns are non-streaming because the SDK streaming
  accumulator can return empty output under tool use.
- There is no per-deal token-budget cap. Token totals are audit facts; worker
  count and reasoning effort are the cost controls.

## Extraction Shape

Every extractor turn that emits a full `{deal, events}` body uses strict
structured output:

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "strict": true,
      "schema": "SCHEMA_R1"
    }
  }
}
```

`SCHEMA_R1` is hardened with `additionalProperties: false`, complete
`required` lists, tightened enums, exact array shapes, and `maxLength: 1500`
on quote strings. It is strict as a provider shape, not a replacement for
Python validation.

Phase 1 Linkflow probes accepted the live schema only after removing two
provider-schema ambitions:

- no `oneOf` event variants for conditional row ownership/nullness;
- no dynamic `bidder_registry` enforcement in the provider schema.

Those are still live output-contract requirements. Python rebuilds and enforces
`bidder_registry` before validation/finalization, and
`pipeline.core.validate()` remains the authoritative invariant gate.

## Targeted Repair Tools

Initial extraction has no tools. This is intentional: initial tool-output
replay was too expensive under Linkflow because every replay must resend the
full input.

Repair turn 1 also has no tools. Repair turn 2, only when hard flags remain,
exposes `check_row`, `search_filing`, and `get_pages`. `check_row` is targeted
to hard-flagged, revised, or revision-dependent rows; it is not an initial
row-by-row checklist. Keep the repair-2 catalog small unless reference-run
evidence proves a specific gap.

### `check_row(row)`

Runs row-local Python checks against a candidate event row and returns:

```json
{"ok": true, "violations": []}
```

The wrapper covers structural row checks, quote/page substring verification,
date/BidderID basics, bid-type evidence, and conditional event-field ownership
such as §P-R9. In repair 2, use it for hard-flagged rows, directly revised
rows, and rows whose validity depends on those revisions.

Example use: after revising a hard-flagged `Bid` row, call `check_row` to catch
an overlong quote, a quote that is not on the cited page, missing
`bid_type_inference_note`, or fields that belong only on another event type.

### `search_filing(query, page_range, max_hits)`

Case-insensitive substring search over `data/filings/{slug}/pages.json`.
Returns page-numbered snippets, not array offsets.

Example use in repair 2: search for `"by and among"` or `"Schedule A"` to find
merger agreement party blocks before revising constituent-level Buyer Group or
Consortium rows, including inherited buyer-group `NDA` rows for late joiners.

### `get_pages(start_page, end_page)`

Fetches contiguous filing pages by page number and returns full page text:

```json
{"pages": [{"page": 41, "text": "..."}]}
```

The range cap is 10 pages per call. In repair 2, use it after `search_filing`
identifies a candidate page, or when a row's evidence needs surrounding
context.

## Multi-Turn Loop

Per deal, the extraction harness runs this shape:

```text
run.py / pipeline.run_pool
  -> full extractor input with strict json_schema, prompt-only
       model emits final {deal, events}
  -> prepare_for_validate()
       Python rebuilds/enforces bidder_registry
  -> validate()
  -> staged repair loop if hard flags remain
       repair_1 prompt-only
       repair_2 targeted tools only if hard flags remain
  -> scoped adjudicator for soft flags only
  -> finalize_prepared()
```

Do not chain turns with `previous_response_id`; replay the full input. Do not
switch to partial JSON patches during repair; every full-body model response is
a complete extraction.

Streaming policy:

- Stream full extraction-body turns, including repair turns.
- Use non-streaming Responses calls for short tool-call/tool-output turns.
- Reconstruct final JSON from the model's final message, not from intermediate
  tool-call output.

## Repair Loop

The repair loop starts only after Python validation sees hard flags in the
model's final draft.

Repair prompt contents:

- compact validator report with hard flag codes, severity, reason, and affected
  row index when available;
- affected event rows verbatim;
- filing snippets needed to fix the failure.

Repair protocol:

- The model must emit a complete revised `{deal, events}` extraction.
- Repair turn 1 has no tools.
- Repair turn 2, only when hard flags remain, exposes targeted repair tools.
- The cap is two repair turns.
- After each repair turn, Python prepares and validates again.
- If hard flags remain after turn 2, finalization uses the latest draft and
  appends a deal-level hard `repair_loop_exhausted` flag. The deal status is
  `validated`.
- The cap is an infinite-loop guard, not a cost-control mechanism.

The scoped Adjudicator runs after hard-flag repair is closed or exhausted. It
has no tools, does not rewrite extraction rows, and only appends verdict text to
soft-flag reasons.

## Audit Contract

Every extraction or re-validation attempt writes a new immutable run directory:

```text
output/audit/{slug}/runs/{run_id}/
  manifest.json
  calls.jsonl
  tool_calls.jsonl
  repair_turns.jsonl
  raw_response.json
  validation.json
  final_output.json
  prompts/
    extractor.txt
    adjudicator_{n}.txt

output/audit/{slug}/latest.json
```

`latest.json` is the only mutable audit pointer. Fresh attempts never overwrite
older run directories. Failed fresh attempts still write a manifest and update
`latest.json` with `cache_eligible=false`.

New audit expectations:

- `tool_calls.jsonl`: one row per tool invocation with turn, call ID, name,
  arguments, result, latency, and any error/truncation marker.
- `repair_turns.jsonl`: one row per repair turn with `tool_mode`, a validator
  summary, hard-flag counts before/after, and latency.
- `manifest.json` records `tools_contract_version`,
  `repair_loop_contract_version`, `extract_tool_mode`, `repair_strategy`,
  `repair_turns_used`, `repair_loop_outcome`, and `tool_calls_count`.

`repair_loop_outcome` is:

- `clean`: initial validation had no hard flags.
- `fixed`: at least one repair turn ran and hard flags cleared.
- `exhausted`: the cap was reached and `repair_loop_exhausted` was finalized.

The former schema-used audit boolean is retired; strict schema is
unconditional under the live contract.

## Cache Eligibility

`--re-validate` may reuse only cache-eligible audit v2 runs. The archived run
must match the current:

- `rulebook_version`
- `extractor_contract_version`
- `tools_contract_version`
- `repair_loop_contract_version`
- `extract_tool_mode`
- `repair_strategy`

Use `--audit-run-id <run_id>` to select an exact immutable run. Otherwise,
`--re-validate` reads `output/audit/{slug}/latest.json`. Loose legacy files
directly under `output/audit/{slug}/` are stale artifacts and are not cache
candidates.

Use `--re-extract` after any prompt, schema, tools, repair-loop, rulebook, or
output-contract change.

## Operator Commands

Before a real Linkflow run:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pytest -x
```

Single reference extraction:

```bash
python -m pipeline.run_pool \
  --slugs medivation \
  --workers 1 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
```

After the run:

```bash
python scoring/diff.py --slug medivation
python -m pipeline.reconcile --scope reference
```

Inspect:

- `output/audit/{slug}/latest.json`
- `output/audit/{slug}/runs/{run_id}/manifest.json`
- `output/audit/{slug}/runs/{run_id}/calls.jsonl`
- `output/audit/{slug}/runs/{run_id}/tool_calls.jsonl`
- `output/audit/{slug}/runs/{run_id}/repair_turns.jsonl`
- `output/audit/{slug}/runs/{run_id}/raw_response.json`
- `output/audit/{slug}/runs/{run_id}/validation.json`
- `output/audit/{slug}/runs/{run_id}/final_output.json`
- `output/extractions/{slug}.json`
- `state/progress.json`
- `state/flags.jsonl`

Full reference-run protocol after the overhaul:

```bash
python -m pytest -x
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
python -m pipeline.reconcile --scope reference
```

Repeat until at least three archived full-reference runs exist under unchanged
rulebook, extractor, tools, and repair-loop contract hashes.

## Stability And Target Release

Write the reference stability proof from immutable audit runs:

```bash
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --json \
  --write quality_reports/stability/target-release-proof.json
```

Target extraction remains closed until all of the following are true:

- all nine reference deals are manually marked `verified`;
- `pipeline.reconcile --scope reference` passes;
- the `target_gate_proof_v1` file classifies the archive as
  `STABLE_FOR_REFERENCE_REVIEW`;
- the proof records `requested_runs >= 3`;
- the proof includes at least three selected immutable run IDs for every
  reference slug;
- the operator explicitly supplies `--release-targets`.

Any prompt, schema, tools, repair-loop, rulebook, state, or output-format change
resets the stability clock and requires regenerating affected artifacts.

## Security

Never commit API keys. Use `OPENAI_API_KEY` from the shell or `.env`, and keep
local credential files ignored. If any prompt, audit file, log, shell history,
or markdown note captures a real key, stop and rotate the key before continuing.
