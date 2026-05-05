# Linkflow Extraction Guide

This is the operator guide for running the `deal_graph_v1` M&A extraction
pipeline through the Linkflow/NewAPI-compatible Responses endpoint.

## Environment

```bash
OPENAI_BASE_URL=https://www.linkflow.run/v1
OPENAI_API_KEY=<set in shell or .env, never in docs>
EXTRACT_MODEL=gpt-5.5
EXTRACT_REASONING_EFFORT=high
LINKFLOW_XHIGH_MAX_WORKERS=5
```

The runner defaults extractor reasoning effort to `high`. Use `xhigh` only for
one-off runs or pools within `LINKFLOW_XHIGH_MAX_WORKERS`.

## Provider Contract

Extraction uses strict structured output with the claim-only schema:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

The schema is provider-safe: no `oneOf`, no schema-valued
`additionalProperties`, no dynamic object keys, and no canonical graph ids.

The provider must not emit old row-event output, `BidderID`, `bidder_registry`,
source offsets/pages, `T`, `bI`, `bF`, admitted/dropout judgments, coverage
results, review rows, or projection rows.

Each claim must carry exact quote evidence. `quote_texts` is `null` when the
primary `quote_text` supports the claim; it is an ordered list of exact snippets
when the filing support is separated across sentences, paragraphs, or page
breaks.

## Run Shape

```text
run.py / pipeline.run_pool
  -> responses.stream with strict deal_graph_v1 claim schema
  -> raw_response.json
  -> Python quote binding against Background pages
  -> canonical deal graph
  -> graph validation
  -> review and estimation projections when unblocked
  -> final_output.json and output/extractions/{slug}.json
```

There is no live repair loop, no `previous_response_id` chain, no loose JSON
fallback, and no provider branch that disables structured output.

## Commands

```bash
python run.py --slug mac-gray --re-extract
python run.py --slug petsmart-inc --re-extract
python run.py --slug zep --re-extract
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract
```

Use `--dry-run` to inspect selection without requiring an API key.

## Audit Contract

Each attempt writes a new immutable run directory:

```text
output/audit/{slug}/runs/{run_id}/
  manifest.json
  calls.jsonl
  raw_response.json
  validation.json
  final_output.json
  deal_graph.duckdb
  deal_graph_v1.json
  prompts/extractor.txt

output/audit/{slug}/latest.json
```

Latest derived outputs:

```text
output/review_rows/{slug}.jsonl
output/review_csv/{slug}.csv
output/projections/estimation_bidder_rows/{slug}.jsonl
```

## Validation

Graph validation is Python-owned. Hard flags include quote-binding failures,
missing claim evidence, missing current dispositions, missing coverage links,
canonical rows without evidence, and projections blocked by unresolved review
flags.

`validated` means the run finalized but has hard graph flags. `passed_clean`
means no graph flags remain.

Reference `verified` status requires Austin or agent filing-grounded verification with `quality_reports/reference_verification/{slug}.md`. An agent must not mark a deal verified solely because the model output passes schema validation.

## Target Gate

Target extraction remains fail-closed. A selection containing non-reference
targets fails unless all reference deals are verified under `deal_graph_v1`,
the stability proof classifies the archive as
`STABLE_FOR_REFERENCE_REVIEW`, and the operator passes `--release-targets`.
