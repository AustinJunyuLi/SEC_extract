# Linkflow Extraction Guide

This is the operator guide for running the `deal_graph_v2` M&A extraction
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

Each claim must carry source-addressed evidence copied from the paragraph-local
`citation_units` in the extractor input:

```json
{"citation_unit_id": "page_35_paragraph_4", "quote_text": "exact filing substring"}
```

Python validates the citation-unit id and requires the quote to be an exact
substring inside that unit before canonicalization. Multiple `evidence_refs`
represent separated support. Provider-level `quote_text` and `quote_texts` are
retired and rejected.

The provider does not emit target-only actor claims. Target identity is
manifest/deal metadata owned by Python.

## Run Shape

```text
run.py / pipeline.run_pool
  -> responses.stream with strict claim-only schema
  -> raw_response.json
  -> Python evidence binding against Background citation units
  -> canonical deal graph
  -> graph validation
  -> review projection
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
  deal_graph_v2.json
  prompts/extractor.txt

output/audit/{slug}/latest.json
```

Latest derived outputs:

```text
output/review_rows/{slug}.jsonl
output/review_csv/{slug}.csv
```

## Validation

Graph validation is Python-owned. Hard flags include evidence-ref binding failures,
missing claim evidence, missing current dispositions, missing coverage links,
canonical rows without evidence, and review output write failures.

`validated` means the run finalized but has hard graph flags. `passed_clean`
means no graph flags remain.

Reference `verified` status requires Austin or agent filing-grounded verification with `quality_reports/reference_verification/{slug}.md`. An agent must not mark a deal verified solely because the model output passes schema validation. Verification reports are review records; they do not become stale only because a later clean rerun has a new run id. The current extraction, current audit raw response, and filing pages must still ground mechanically.

## Target Gate

Target extraction remains fail-closed. A selection containing non-reference
targets fails unless all reference deals are verified under `deal_graph_v2`,
the stability proof classifies the archive as
`STABLE_FOR_REFERENCE_REVIEW`, and the operator passes `--release-targets`.
