# SKILL.md - M&A Background Claim Extraction

## Purpose

Given one SEC merger filing, extract source-backed claims from the Background
section for the `deal_graph_v2` pipeline. The model proposes facts; Python
constructs and validates the canonical graph.

## Invocation

Single deal:

```bash
python run.py --slug mac-gray --re-extract
```

Batch:

```bash
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract
```

Alex-facing full event ledger:

```bash
python scripts/export_alex_event_ledger.py --scope all --output output/review_csv/alex_event_ledger_ref9_plus_targets5.csv
```

The Alex ledger is generated from trusted graph snapshots. Bid rows expose
`bid_value`, `bid_value_lower`, `bid_value_upper`, and `bid_value_unit`; do not
collapse aggregate values into a per-share-only column.

`OPENAI_API_KEY` and `OPENAI_BASE_URL` are runtime-only secrets/configuration.
Do not write keys to repo files, reports, audit summaries, or docs.

## Provider Output

The extractor returns exactly:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Every claim must include `coverage_obligation_id` and at least one
`evidence_refs` entry:

```json
{"citation_unit_id": "page_35_paragraph_4", "quote_text": "exact filing substring"}
```

`citation_unit_id` must identify one embedded `citation_units[]` item, and
`quote_text` must be copied exactly from that unit's text. Use multiple refs
when a claim needs separated source support. Provider-level `quote_text` and
`quote_texts` are retired. The provider never emits canonical graph ids, source
offsets, old row fields, coverage results, review rows, or judgment/disposition
fields.

The provider does not emit target-only actor claims. Target identity is
manifest/deal metadata owned by Python; target labels appear in provider claims
only as part of substantive source-backed relations.

Actor claims include `actor_class`: `financial`, `strategic`, `mixed`, or
`unknown`. Do not emit U.S./non-U.S., public/private, `bidder_type`,
`bidder_class`, or `bid_note` fields.

## Python Pipeline

`pipeline.run_pool` calls `pipeline.llm.extract.extract_deal()` with strict
structured output and then calls
`pipeline.deal_graph.orchestrate.finalize_claim_payload()`.

Finalization:

1. parse claim payload;
2. bind evidence refs exactly to Background citation units;
3. canonicalize actors, relations, events, bids, and counts;
4. write graph artifacts in `output/audit/{slug}/runs/{run_id}/`;
5. validate evidence, dispositions, coverage, row evidence, and review output;
6. project review rows;
7. write latest output/state/flags.

## Consortium Rule

Preserve the filing's bidding unit. A group actor can be the bidder unit when
the filing treats the group as the bidding party. Member, support, financing,
and rollover facts are represented through actor relations and do not create
member bidder rows unless the filing shows separate bidding conduct.

## Validation

Trusted runs produce `passed_clean`, `needs_review`, or `high_burden` based on
review-row burden. Runtime, schema, artifact, or graph-integrity failures
produce `failed_system`; a failed rerun after prior trusted output produces
`stale_after_failure`. Old row-per-event JSON is stale and must not pass as
canonical input.

Reference `verified: true` metadata requires Austin or agent filing-grounded
verification with `quality_reports/reference_verification/{slug}.md`. An agent
must not mark a deal verified solely because the model output passes schema
validation. The report must cite the current extraction run id.
