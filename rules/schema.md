# rules/schema.md - deal_graph_v2 Schema Contract

## Live Contract

The live canonical contract is `deal_graph_v2`. The provider emits claims only.
Python binds quotes, assigns canonical ids, writes graph tables, validates the
graph, and projects review rows.

Provider output is exactly:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Top-level `deal` / `events` row JSON is retired and must not be accepted as a
canonical extraction. `output/extractions/{slug}.json` is a portable
`deal_graph_v2` snapshot containing graph data plus deterministic review rows.

## Claim Requirements

Every claim includes:

- `claim_type`
- `coverage_obligation_id`
- `confidence`: `high`, `medium`, or `low`
- `evidence_refs`: one or more source-addressed evidence refs; each ref has
  `citation_unit_id` and `quote_text`

Each `citation_unit_id` must identify one extractor-input
`citation_units[].id`. Each `quote_text` must be an exact substring of that
unit's text and max 1500 characters. Use multiple refs when a claim needs
separated source support. Exact means byte-for-byte visible text copying:
preserve capitalization, punctuation, spacing, and curly/straight quote marks.
Provider-level `quote_text` and `quote_texts` are retired.

Provider-owned fields are forbidden: canonical ids, source offsets, source
pages, `BidderID`, bidder registry, `T`, `bI`, `bF`, admitted/dropout
judgments, coverage results, projection rows, provider-level `quote_text`,
provider-level `quote_texts`, and old row-event scalar fields.

Target identity is Python-owned manifest/deal metadata. The provider does not
emit target-only actor claims; target labels appear only when a substantive
source-backed relation needs the target as subject or object.

## Actor Claims

Fields: `actor_label`, `actor_kind`, `observability`.

`actor_kind`: `organization`, `person`, `group`, `vehicle`, `cohort`,
`committee`.

`observability`: `named`, `anonymous_handle`, `count_only`.

## Event Claims

Fields: `event_type`, `event_subtype`, `event_date`, `description`,
`actor_label`, `actor_role`.

`event_type`: `process`, `bid`, `transaction`.

`event_subtype` is the closed vocabulary in `rules/events.md`.

## Bid Claims

Fields: `bidder_label`, `bid_date`, `bid_value`, `bid_value_lower`,
`bid_value_upper`, `bid_value_unit`, `consideration_type`, `bid_stage`.

`bid_stage`: `initial`, `revised`, `final`, `unspecified`.

Formal/informal classification, bidder class, admission, dropout, and `T` are
outside the live extraction artifact.

## Participation Count Claims

Fields: `process_stage`, `actor_class`, `count_min`, `count_max`,
`count_qualifier`.

`process_stage`: `contacted`, `nda_signed`, `ioi_submitted`, `first_round`,
`final_round`, `exclusivity`.

`actor_class`: `financial`, `strategic`, `mixed`, `unknown`.

`count_qualifier`: `exact`, `at_least`, `at_most`, `range`, `approximate`.

## Actor Relation Claims

Fields: `subject_label`, `object_label`, `relation_type`, `role_detail`,
`effective_date_first`.

Relation direction is defined in `rules/bidders.md`. The quote must support
the subject, object, and relationship.

## Finalized Artifacts

Per run:

```text
output/audit/{slug}/runs/{run_id}/raw_response.json
output/audit/{slug}/runs/{run_id}/deal_graph.duckdb
output/audit/{slug}/runs/{run_id}/deal_graph_v2.json
output/audit/{slug}/runs/{run_id}/validation.json
output/audit/{slug}/runs/{run_id}/final_output.json
```

Latest portable outputs:

```text
output/extractions/{slug}.json
output/review_rows/{slug}.jsonl
output/review_csv/{slug}.csv
```

Rows without source-backed evidence do not project. Blocking graph flags make
the deal `validated`; clean graph outputs are `passed_clean`.
