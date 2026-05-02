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
EXTRACT_REASONING_EFFORT=high
ADJUDICATE_REASONING_EFFORT=high
LINKFLOW_XHIGH_MAX_WORKERS=5
```

Observed provider constraints:

- `high` reasoning is the default for extractor and adjudicator calls.
- Explicit `xhigh` reasoning remains available for one-off runs. `xhigh`
  concurrency is capped at five workers by default; the runner rejects larger
  pools before model calls.
- Linkflow has a 300s streaming idle timeout. Full extraction and repair-body
  turns stream so long-running reasoning keeps the connection alive.
- `previous_response_id` returns 400. Every extraction, tool-output replay, and
  repair call uses full-input replay.
- Repair calls stream even after tool outputs, because the model must emit a
  complete extraction body and non-streaming replay can hit proxy read
  timeouts on large reference deals.
- If a repair stream emits text/tool items and then the SDK raises a missing
  `response.completed` event, the client salvages the streamed body. Normal
  JSON/schema parsing remains the gate; incomplete bodies still fail.
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

Repair is a single obligation-gated round. When hard validator flags or hard
unmet obligations exist, repair has access to `check_row`, `search_filing`,
`get_pages`, and `check_obligations`. Keep the catalog small unless
reference-run evidence proves a specific gap.

### `check_row(row)`

Runs row-local Python checks against a candidate event row and returns:

```json
{"ok": true, "violations": []}
```

The wrapper covers structural row checks, quote/page substring verification,
date/BidderID basics, bid-type evidence, and conditional event-field ownership
such as §P-R9. Use it for hard-flagged rows, directly revised rows, and rows
whose validity depends on those revisions.

Example use: after revising a hard-flagged `Bid` row, call `check_row` to catch
an overlong quote, a quote that is not on the cited page, missing
`bid_type_inference_note`, or fields that belong only on another event type.

### `search_filing(query, page_range, max_hits)`

Case-insensitive substring search over `data/filings/{slug}/pages.json`.
Returns page-numbered snippets, not array offsets.

Example use: search for `"by and among"` or `"Schedule A"` to find
merger agreement party blocks before revising constituent-level Buyer Group or
Consortium rows, including inherited buyer-group `NDA` rows for late joiners.

### `get_pages(start_page, end_page)`

Fetches contiguous filing pages by page number and returns full page text:

```json
{"pages": [{"page": 41, "text": "..."}]}
```

The range cap is 10 pages per call. Use it after `search_filing` identifies a
candidate page, or when a row's evidence needs surrounding context.

### `check_obligations(candidate_extraction)`

Runs deterministic filing-derived obligation checks against a complete
candidate extraction and returns obligation ids, source pages, matched rows,
statuses, and reasons. This is a repair aid only. The orchestrator reruns the
same Python code after repair and uses that result as the authority.
For exact-count NDA and bid obligations, buyer-group constituent sibling rows
that cite the same aggregate filing event count as one filing-party unit, while
remaining atomized rows in the extraction. If an exact-count bid obligation
states a month/day, later bid rows on the same filing page do not satisfy that
obligation unless their event date matches the stated month/day.

## Multi-Turn Loop

Per deal, the extraction harness runs this shape:

```text
run.py / pipeline.run_pool
  -> full extractor input with strict json_schema, prompt-only
       model emits final {deal, events}
  -> prepare_for_validate()
       Python rebuilds/enforces bidder_registry
  -> validate()
  -> check_obligations()
  -> one obligation-gated repair round if hard validator flags or hard obligations remain
       check_row/search_filing/get_pages/check_obligations available
       row-conservation anchors protect unaffected chronology
  -> scoped adjudicator for soft flags only
  -> finalize_prepared()
```

Do not chain turns with `previous_response_id`; replay the full input. Do not
switch to partial JSON patches during repair; every full-body model response is
a complete extraction.

Streaming policy:

- Stream the initial full extraction.
- Stream every repair-body call, including calls made after tool outputs.
- Reconstruct final JSON from the model's final message, not from intermediate
  tool-call output.

## Repair Loop

The repair loop starts only after Python validation sees hard flags or the
obligation layer sees hard unmet filing obligations in the model's final draft.

Repair prompt contents:

- compact validator report with hard flag codes, severity, reason, and affected
  row index when available;
- derived filing obligations and current satisfaction status;
- protected row-conservation anchors for unaffected pre-repair rows;
- the previous complete extraction;
- unique deterministic filing pages from hard flag and obligation sources.

Repair protocol:

- The model must emit a complete revised `{deal, events, obligation_assertions}`
  repair response.
- The single repair round exposes all targeted repair tools immediately.
- Python strips `obligation_assertions`, prepares, validates, checks
  obligations, and checks row conservation again.
- Any remaining hard validator, obligation, or conservation flags finalize the
  deal as `validated`.

The scoped Adjudicator runs after hard-flag repair is closed. It has no tools,
does not rewrite extraction rows, and only appends verdict text to soft-flag
reasons.

## Audit Contract

Every extraction or re-validation attempt writes a new immutable run directory:

```text
output/audit/{slug}/runs/{run_id}/
  manifest.json
  calls.jsonl
  tool_calls.jsonl
  repair_turns.jsonl
  obligations.json
  repair_response.json
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
- `repair_turns.jsonl`: one row for the repair round when it runs, with
  `tool_mode`, validator and obligation counts before/after, row-count delta,
  conservation failures, and tool-call count.
- `obligations.json`: derived obligations and satisfaction results before and
  after repair.
- `repair_response.json`: raw parsed repair response, including repair-only
  `obligation_assertions`.
- `manifest.json` records `tools_contract_version`,
  `repair_loop_contract_version`, `obligation_contract_version`,
  `extract_tool_mode`, `repair_strategy`, `repair_turns_used`,
  `repair_loop_outcome`, and `tool_calls_count`.

`repair_loop_outcome` is:

- `clean`: initial validation had no hard flags.
- `fixed`: the repair round ran and hard validator, obligation, and
  conservation flags cleared.
- `hard_flags_remain`: the repair round ran and at least one hard issue remains.

The former schema-used audit boolean is retired; strict schema is
unconditional under the live contract.

## Cache Eligibility

`--re-validate` may reuse only cache-eligible audit v2 runs. The archived run
must match the current:

- `rulebook_version`
- `extractor_contract_version`
- `tools_contract_version`
- `repair_loop_contract_version`
- `obligation_contract_version`
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

- all nine reference deals are `verified` through Austin review or agent filing-grounded verification documented at
  `quality_reports/reference_verification/{slug}.md`;
- `pipeline.reconcile --scope reference` passes;
- the `target_gate_proof_v1` file classifies the archive as
  `STABLE_FOR_REFERENCE_REVIEW`;
- the proof records `requested_runs >= 3`;
- the proof includes at least three selected immutable run IDs for every
  reference slug;
- the operator explicitly supplies `--release-targets`.

The agent must not mark a deal verified solely because the model output passes schema validation; every AI-vs-Alex disagreement must be adjudicated against
filing text before `verified` is set. Before setting agent verification, run:

```bash
python scripts/check_reference_verification.py --slugs <slug>
python scripts/mark_reference_verified.py <slug> --reviewer "Codex agent"
```

`mark_reference_verified.py` is allowed only for reference deals with no hard
extraction flags and a completed verification report.

Any prompt, schema, tools, repair-loop, rulebook, state, or output-format change
resets the stability clock and requires regenerating affected artifacts.

## Security

Never commit API keys. Use `OPENAI_API_KEY` from the shell or `.env`, and keep
local credential files ignored. If any prompt, audit file, log, shell history,
or markdown note captures a real key, stop and rotate the key before continuing.
