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

The provider must not emit retired event-table output, `BidderID`, `bidder_registry`,
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

Actor claims include `actor_class` with only `financial`, `strategic`, `mixed`,
or `unknown`. The provider must ignore U.S./non-U.S., public/private, and other
old bidder-type side descriptors.

## Run Shape

```text
run.py / pipeline.run_pool
  -> responses.stream with strict claim-only schema
  -> raw_response.json
  -> Python evidence binding against Background citation units
  -> canonical deal graph
  -> graph validation
  -> review projection
  -> deal_graph.duckdb, deal_graph_v2.json, and output/extractions/{slug}.json
```

There is no live correction loop, no response-chain reuse, no loose JSON
fallback, and no provider branch that disables structured output.

## Commands

```bash
python run.py --slug mac-gray --re-extract
python run.py --slug petsmart-inc --re-extract
python run.py --slug zep --re-extract
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract
python scripts/export_alex_event_ledger.py --scope all --output output/review_csv/alex_event_ledger_ref9_plus_targets5.csv
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
  deal_graph.duckdb
  deal_graph_v2.json
  prompts/extractor.txt

output/audit/{slug}/latest.json
```

Latest derived outputs:

```text
output/review_rows/{slug}.jsonl
output/review_csv/{slug}.csv
output/review_csv/alex_event_ledger_ref9_plus_targets5.csv
```

`alex_event_ledger_ref9_plus_targets5.csv` is the full human-review ledger for
Alex. It is regenerated from trusted `output/extractions/{slug}.json` graph
snapshots and contains event, bid, participation-count, advisor, financing,
support, and group-change rows. It does not include plain actor rows or static
membership facts. Bid rows carry `bid_value`, `bid_value_lower`,
`bid_value_upper`, and `bid_value_unit`, so aggregate values remain distinct
from per-share values. The canonical graph remains the source of truth.

## Validation

Graph validation is Python-owned. Graph-integrity failures include malformed
provider payloads, missing claim evidence, missing current dispositions, missing
coverage links, canonical rows without evidence, and review output write
failures.

Trusted run statuses are `passed_clean`, `needs_review`, and `high_burden`.
Review items are operator burden, not system failure. Runtime, schema, artifact,
or graph-integrity failures produce `failed_system`; failed reruns after prior
trusted output produce `stale_after_failure`.

Reference `verified: true` metadata requires Austin or agent filing-grounded
verification with `quality_reports/reference_verification/{slug}.md`. An agent
must not mark a deal verified solely because the model output passes schema
validation. The report must cite the current extraction run id.

## Target Gate

Target extraction is release-gated. A selection containing non-reference
targets fails unless all reference deals have current verified metadata under
`deal_graph_v2`, `quality_reports/stability/target-release-proof.json`
classifies the archive as `STABLE_FOR_REFERENCE_REVIEW`, and the operator
passes `--release-targets`. The current trusted non-reference outputs are the
five target deals listed in `state/progress.json`.
