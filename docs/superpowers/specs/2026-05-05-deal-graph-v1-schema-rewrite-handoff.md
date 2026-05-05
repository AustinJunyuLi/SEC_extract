# Deal Graph V1 Live Contract Handoff

**Date:** 2026-05-05

**Status:** Live breaking contract. This file records the current
`deal_graph_v1` architecture; `AGENTS.md`, `SKILL.md`, `rules/schema.md`,
`prompts/extract.md`, and `docs/linkflow-extraction-guide.md` are the operating
authorities.

## Contract

The provider emits one strict claim-only JSON object:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Every claim includes `coverage_obligation_id`, `confidence`, typed claim
fields, and one or more `evidence_refs`:

```json
{"citation_unit_id": "page_35_paragraph_4", "quote_text": "exact filing substring"}
```

`citation_unit_id` must match an extractor-input `citation_units[].id`.
`quote_text` must be an exact substring inside that citation unit. Multiple refs
represent separated support. Provider-level `quote_text` and `quote_texts` are
retired and rejected.

## Runtime Shape

```text
filing Background pages
-> paragraph-local citation_units
-> prompt-only strict provider claim payload
-> Python evidence binding before canonicalization
-> unsupported claims rejected with one blocking review flag
-> supported claims canonicalized into deal_graph_v1
-> deterministic graph validation
-> review and estimation projections
-> audit v3 run archive and latest output/state/flags
```

Python owns source spans, canonical ids, dispositions, coverage results,
actor/event/relation rows, validation flags, review rows, and estimator rows.
The provider never emits canonical ids, source offsets, `BidderID`, bidder
registry, `T`, `bI`, `bF`, admitted/dropout outcomes, coverage results, or
projection rows.

## Enum Authority

Provider schemas derive closed enums from the Pydantic graph models. There is no
separate provider enum list.

`CountQualifier` includes `range`.

`bid_value_unit` is `per_share`, `enterprise_value`, `equity_value`, or
`unspecified`. Use `equity_value` for supported aggregate equity transaction
prices; use `unspecified` when the filing gives a number but not the aggregate
value basis. `other` is not a valid bid value unit.

## Audit Contract

New cache-eligible runs use:

```text
raw_response_v3
audit_run_v3
audit_v3
```

Old audit v2 responses and old row-event `{deal, events}` raw payloads are
stale and fail loudly. There are no adapters for old `quote_text`,
`quote_texts`, repair artifacts, tool contracts, adjudicator fields, or
obligation-gated manifest fields.

## Doctrine

- No fallback.
- No backward compatibility.
- No deal-specific prompt patching.
- No hidden repair/adjudicator path.
- No overfit fixes for one reference deal.
- Preserve the filing's bidding unit; member relations do not automatically
  create bidder rows.
- Hard flags are acceptable when evidence is unsupported; they must be sharp
  enough for human and AI review.
