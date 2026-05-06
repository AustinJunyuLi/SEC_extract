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

Preserve the filing's bidding unit. A buyer group can be the bidder unit. Member
facts are represented through actor relations and do not create member bidder
rows unless the filing shows separate bidding conduct.

Mac Gray `CSC/Pamplona`: one group actor/bidder unit; CSC and Pamplona are
relations; Pamplona financing is not a second bidder row by itself.

PetSmart `Buyer Group`: one group actor/bidder unit; Longview membership,
rollover, or support is a dated relation only when source-supported.

## Validation

Hard flags produce `validated`. Zero flags produce `passed_clean`. Old
row-per-event JSON is stale and must not pass as canonical input.

Reference `verified` status requires Austin or agent filing-grounded verification with `quality_reports/reference_verification/{slug}.md`. An agent must not mark a deal verified solely because the model output passes schema validation. The report records a review, not a binding to the latest run id; current extraction artifacts still have to be consistent and filing-grounded.
