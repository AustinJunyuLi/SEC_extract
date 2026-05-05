# Deal Graph V1 Schema Rewrite Handoff

**Date:** 2026-05-05

**Status:** Design-approved handoff for a breaking refactor. This is not yet
the live pipeline contract. The implementation agent must update `AGENTS.md`,
`CLAUDE.md`, `SKILL.md`, `rules/*.md`, prompts, tests, generated artifacts,
and stale docs in the same finished change before treating this as live.

## Purpose

Replace the current row-per-event extraction contract with a relational
`deal_graph_v1` architecture for M&A takeover-auction research.

The reason is substantive, not cosmetic: hard consortium atomization is
putting unsound strain on the pipeline. The filing's bidding unit is often a
buyer group, club bid, sponsor/corporate pair, or changing coalition. The
canonical representation must preserve that bidding unit while still tracking
source-backed member, vehicle, financing, rollover, support, and advisor
relations.

The accepted direction borrows the source-proof graph framework from
`/Users/austinli/Projects/sec_graph`, but `bids_try` remains its own auction
research system. Do not add `sec_graph` as a dependency. Adapt the pattern into
a native `pipeline/deal_graph/` subsystem.

## Core Decision

Canonical truth becomes a relational deal graph:

```text
filing text
-> source spans
-> AI typed claim payload
-> Python quote binding and claim insertion
-> relational deal_graph store
-> Python claim disposition
-> Python canonicalization
-> Python validation
-> deal_graph_v1 JSON snapshot
-> derived review rows and estimator bidder rows
```

The AI never emits the canonical graph directly. It emits typed claims with
quotes. Python owns source coordinates, canonical ids, duplicate handling,
coverage results, claim dispositions, relation timing, research judgments,
and projection.

## Non-Negotiables

- No backward compatibility with the old row-per-event extraction schema.
- No loose JSON fallback, non-strict structured-output bypass, or legacy output
  reader.
- No hidden adapter that allows stale row-per-event JSON to pass as canonical
  output.
- No model-emitted canonical ids, source offsets, projection rows, `BidderID`,
  `T`, `bI`, `bF`, admitted/dropout outcomes, or research judgments.
- No hard consortium atomization. A member relation does not create a bidder
  row unless the member separately acts as a bidder in the filing.
- SEC filing text remains factual ground truth. Alex/reference files remain
  review aids, not oracles.
- Target-deal extraction remains fail-closed until the reference gate is
  re-established under the new contract.

## Borrow Boundary From sec_graph

Borrow:

- claim-only provider payloads;
- strict provider-safe JSON schema generation;
- source spans and relational evidence links;
- `actors`, `events`, `event_actor_links`, `actor_relations`;
- claim coverage links and Python-owned coverage results;
- claim disposition before canonical projection;
- deterministic projection from canonical facts.

Do not blindly copy:

- `sec_graph`'s generic relation enum without auction review;
- one-cycle assumptions;
- generic SEC graph event ontology;
- current `sec_graph` canonicalization shortcuts;
- DuckDB file layout or run artifacts if they do not fit this repo's audit
  archive.

`bids_try` unique content:

- takeover-auction event vocabulary;
- NDA/IOI/first-round/final-round/exclusivity/drop/executed semantics;
- informal/formal bid classification;
- strategic/financial/mixed bidder classification;
- estimator projection fields and admission/dropout rules;
- Alex-style review CSV and AI-vs-reference diff;
- reference-set stability gate.

## New Output Authority

Working canonical authority is the relational store. The portable finalized
snapshot is `output/extractions/{slug}.json` with `schema_version:
"deal_graph_v1"`.

Old row-per-event files stop being canonical. Alex-style rows become derived
review output, for example:

```text
output/review_rows/{slug}.jsonl
output/review_csv/{slug}.csv
output/projections/estimation_bidder_rows/{slug}.jsonl
```

The exact output paths may change during implementation, but the authority
boundary must not: canonical graph first, projections second.

## Provider Payload

The provider emits one strict JSON object:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Every claim has:

- `claim_type`;
- `coverage_obligation_id`;
- `confidence`;
- `quote_text`.

Each claim family then has typed fields.

### Actor Claim

```json
{
  "claim_type": "actor",
  "coverage_obligation_id": "obl_actor_1",
  "actor_label": "CSC/Pamplona",
  "actor_kind": "group",
  "observability": "named",
  "confidence": "high",
  "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona"
}
```

`actor_kind` enum:

```text
organization
person
group
vehicle
cohort
committee
```

`observability` enum:

```text
named
anonymous_handle
count_only
```

### Event Claim

```json
{
  "claim_type": "event",
  "coverage_obligation_id": "obl_event_1",
  "event_type": "process",
  "event_subtype": "nda_signed",
  "event_date": "2013-08-01",
  "description": "CSC/Pamplona entered into a confidentiality agreement.",
  "actor_label": "CSC/Pamplona",
  "actor_role": "potential_buyer",
  "confidence": "high",
  "quote_text": "CSC/Pamplona entered into a confidentiality agreement with Mac-Gray"
}
```

`event_type` enum:

```text
process
bid
transaction
```

Initial `event_subtype` enum:

```text
contact_initial
nda_signed
consortium_ca_signed
ioi_submitted
first_round_bid
final_round_bid
exclusivity_grant
merger_agreement_executed
withdrawn_by_bidder
excluded_by_target
non_responsive
cohort_closure
advancement_admitted
advancement_declined
rollover_executed
financing_committed
go_shop_started
go_shop_ended
```

Implementation may tighten this list, but must keep closed-enum validation.
Do not preserve old `bid_note` values as the canonical ontology.

### Bid Claim

```json
{
  "claim_type": "bid",
  "coverage_obligation_id": "obl_bid_1",
  "bidder_label": "CSC/Pamplona",
  "bid_date": "2013-09-15",
  "bid_value": 18.5,
  "bid_value_lower": null,
  "bid_value_upper": null,
  "bid_value_unit": "per_share",
  "consideration_type": "cash",
  "bid_stage": "initial",
  "confidence": "high",
  "quote_text": "CSC/Pamplona submitted an indication of interest at $18.50 per share"
}
```

`bid_stage` enum:

```text
initial
revised
final
unspecified
```

Formal/informal is not provider-owned. Python derives it from source-backed
event, process, range, and stage facts.

### Participation Count Claim

```json
{
  "claim_type": "participation_count",
  "coverage_obligation_id": "obl_count_1",
  "process_stage": "nda_signed",
  "actor_class": "mixed",
  "count_min": 20,
  "count_max": 20,
  "count_qualifier": "exact",
  "confidence": "high",
  "quote_text": "20 potential bidders, including two strategic bidders, entered confidentiality agreements"
}
```

`process_stage` enum:

```text
contacted
nda_signed
ioi_submitted
first_round
final_round
exclusivity
```

`actor_class` enum:

```text
financial
strategic
mixed
unknown
```

### Actor Relation Claim

```json
{
  "claim_type": "actor_relation",
  "coverage_obligation_id": "obl_relation_1",
  "subject_label": "Pamplona",
  "object_label": "CSC/Pamplona",
  "relation_type": "member_of",
  "role_detail": "financing sponsor",
  "effective_date_first": null,
  "confidence": "high",
  "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona"
}
```

Initial `relation_type` enum for `bids_try`:

```text
member_of
joins_group
exits_group
affiliate_of
controls
acquisition_vehicle_of
advises
finances
supports
voting_support_for
rollover_holder_for
```

Relation direction:

- `member_of`: subject is the member; object is the group.
- `joins_group`: subject is the joining actor; object is the group.
- `exits_group`: subject is the exiting actor; object is the group.
- `affiliate_of`: subject is the affiliate; object is the related actor.
- `controls`: subject controls object.
- `acquisition_vehicle_of`: subject is the vehicle; object is parent/group.
- `advises`: subject is advisor; object is advised party.
- `finances`: subject provides financing/capital; object is buyer/group/vehicle.
- `supports`: subject supports object/transaction.
- `voting_support_for`: subject is supporting shareholder/person/entity; object
  is buyer, agreement, proposal, or transaction.
- `rollover_holder_for`: subject is holder rolling/contributing/retaining
  equity; object is buyer, vehicle, surviving company, target, or transaction.

If implementation keeps `committee_member_of` or `recused_from`, it must state
why those facts affect auction extraction or review. They are optional for the
first vertical slice.

## Relational Store

Use DuckDB unless the implementation agent finds a concrete blocker. DuckDB is
small enough for local artifacts, gives SQL validation/projection, and matches
the graph shape better than nested JSON mutation.

Recommended package:

```text
pipeline/deal_graph/
  __init__.py
  schema.py
  store.py
  ids.py
  evidence.py
  claims.py
  response_format.py
  obligations.py
  canonicalize.py
  validate.py
  project_review.py
  project_estimation.py
  export.py
```

Recommended store artifact:

```text
output/deal_graph/{slug}/runs/{run_id}/deal_graph.duckdb
output/deal_graph/{slug}/runs/{run_id}/deal_graph_v1.json
output/deal_graph/{slug}/latest.json
```

It is acceptable to keep the existing `output/audit/{slug}/runs/{run_id}/`
archive as the main run archive and put `deal_graph.duckdb` inside it instead.
Do not create two competing run ids or two competing latest pointers.

## Tables

### Source And Evidence

```text
filings(
  filing_id,
  run_id,
  deal_slug,
  source_path,
  raw_sha256,
  parser_version,
  page_count,
  section_count,
  process_scope
)

paragraphs(
  paragraph_id,
  filing_id,
  section,
  page_hint,
  char_start,
  char_end,
  paragraph_text,
  paragraph_hash
)

spans(
  evidence_id,
  filing_id,
  paragraph_id,
  span_basis,
  span_kind,
  parent_evidence_id,
  created_by_stage,
  char_start,
  char_end,
  quote_text,
  quote_text_hash,
  evidence_fingerprint
)
```

Evidence fingerprint:

```text
sha256(filing_id + char_start + char_end + quote_text_hash)
```

### Extraction

```text
evidence_regions(
  region_id,
  run_id,
  filing_id,
  deal_slug,
  region_kind,
  priority,
  start_paragraph_id,
  end_paragraph_id,
  paragraph_ids_json,
  trigger_phrases_json,
  expected_claim_types_json
)

coverage_obligations(
  obligation_id,
  run_id,
  region_id,
  filing_id,
  deal_slug,
  expected_claim_type,
  obligation_kind,
  obligation_label,
  importance,
  applicability,
  applicability_reason_code,
  applicability_basis_json,
  current
)

coverage_results(
  coverage_result_id,
  run_id,
  obligation_id,
  result,
  reason_code,
  reason,
  claim_count,
  current
)

claims(
  claim_id,
  run_id,
  filing_id,
  deal_slug,
  region_id,
  provider_source_stage,
  claim_type,
  confidence,
  raw_value,
  normalized_value,
  quote_text,
  quote_text_hash,
  status,
  claim_sequence
)

claim_coverage_links(
  claim_id,
  obligation_id,
  run_id,
  deal_slug,
  claim_type,
  current
)

actor_claims(...)
event_claims(...)
bid_claims(...)
participation_count_claims(...)
actor_relation_claims(...)

claim_evidence(claim_id, evidence_id, ordinal)
claim_dispositions(...)
```

`coverage_results` is Python-owned. Provider responses containing
`coverage_results` must fail.

### Canonical

```text
deals(
  deal_id,
  run_id,
  deal_slug,
  target_actor_id,
  announcement_date,
  effective_date,
  all_cash
)

process_cycles(
  cycle_id,
  run_id,
  deal_id,
  cycle_sequence,
  cycle_label,
  start_date,
  end_date
)

actors(
  actor_id,
  run_id,
  deal_id,
  actor_label,
  actor_kind,
  observability,
  bidder_class,
  lead_arranger_label,
  member_count_known,
  has_strategic_member,
  has_financial_member,
  has_sovereign_wealth_member
)

actor_relations(
  relation_id,
  run_id,
  deal_id,
  subject_actor_id,
  object_actor_id,
  relation_type,
  role_detail,
  cycle_id_first_observed,
  cycle_id_last_observed,
  effective_date_first,
  effective_date_last,
  confidence
)

events(
  event_id,
  run_id,
  deal_id,
  cycle_id,
  event_type,
  event_subtype,
  event_date,
  description,
  bid_value,
  bid_value_lower,
  bid_value_upper,
  bid_value_unit,
  consideration_type
)

event_actor_links(
  link_id,
  run_id,
  event_id,
  actor_id,
  role,
  role_detail
)

participation_counts(...)
row_evidence(row_table, row_id, evidence_id, ordinal)
judgments(...)
review_flags(...)
```

`bidder_class` is `strategic`, `financial`, `mixed`, or `unknown`. It is not
provider-owned. It is derived or review-flagged by Python.

### Projection

```text
projection_units(
  projection_unit_id,
  run_id,
  projection_name,
  deal_id,
  cycle_id,
  actor_id
)

projection_judgments(
  projection_judgment_id,
  run_id,
  projection_unit_id,
  rule_id,
  included,
  reason
)

review_rows(...)
estimation_bidder_rows(...)
```

`estimation_bidder_rows` must include the variables needed by
`Informal_bids`-style estimation, including:

```text
deal_slug
cycle_id
actor_id
actor_label
bI
bI_lo
bI_hi
bF
admitted
T
bid_value_unit
consideration_type
boundary_event_id
formal_boundary
dropout_mechanism
confidence_min
projection_rule_version
```

Do not place estimator rows inside the provider payload. Do not let provider
output directly determine `T`.

## Consortium Rule Under deal_graph_v1

The canonical actor can be a group. The estimator unit can be that same group.
Member relations are facts about composition, not automatic bidder rows.

Examples:

- Mac Gray: `CSC/Pamplona` is one group actor and one bidding unit. `CSC
  member_of CSC/Pamplona`; `Pamplona member_of CSC/Pamplona`; `Pamplona
  finances CSC/Pamplona` or `controls CSC` when the quote supports it. The
  estimator row is one row for `CSC/Pamplona`; `T = strategic` if Python's
  rule finds filing support that CSC is the auction-facing operating buyer.
- PetSmart: `Buyer Group` is one group actor. `Longview joins_group Buyer
  Group` or `Longview member_of Buyer Group` is dated only when the filing
  supports the timing. This relation does not create a Longview bidder row
  unless Longview separately acts as a bidder.
- Saks: `Sponsor A/E`, `Sponsor E/G`, or other coalition labels are separate
  actor-cycle facts when the filing treats the coalition differently over time.
  Relations must be time-aware and must not make permanent membership
  assumptions.

Target-side NDA counts follow the filing's unit of account. A group NDA counts
as one bidding unit unless the filing says members separately signed or were
separately bound. This supersedes the old forced constituent NDA-row doctrine.

`ConsortiumCA` should not be a canonical substitute for target-side NDA. In the
graph, bidder-bidder confidentiality or information-sharing facts can become
`consortium_ca_signed` events or relation-supporting evidence.

## Implementation Sequence

### Phase 0: Baseline

- Read `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and this spec.
- Record dirty worktree state. Do not revert unrelated changes.
- Run `python -m pytest -q` and record baseline failures.
- Inspect current outputs for `mac-gray`, `petsmart-inc`, and `saks`.

### Phase 1: Schema And Store

- Add `pipeline/deal_graph/schema.py` with Pydantic models and DuckDB DDL.
- Add `pipeline/deal_graph/store.py` for initialization, transaction handling,
  and artifact paths.
- Add deterministic ids in `pipeline/deal_graph/ids.py`.
- Add evidence span utilities in `pipeline/deal_graph/evidence.py`.
- Add tests that initialize the store, list expected tables, and reject stale
  row-per-event tables as canonical schema.

### Phase 2: Provider Contract

- Replace `SCHEMA_R1` with a claim-only provider schema.
- The schema must be strict and provider-safe: no `oneOf`, no schema-valued
  `additionalProperties`, no required dynamic object keys.
- Constrain `coverage_obligation_id` by claim family when possible.
- Constrain relation enum by obligation label when possible.
- Reject provider-owned `coverage_results`, canonical ids, source offsets,
  `BidderID`, projection rows, and scalar research judgments.
- Update `prompts/extract.md` so the model understands it is proposing claims,
  not final rows.

### Phase 3: Source Regions And Obligations

- Replace row-level obligation checks with graph obligations.
- Build evidence regions from `pages.json` or `raw.md` with paragraph/page
  coordinates.
- Start small: sale-process narrative plus buyer-group/transaction-structure
  triggers.
- Record inapplicable obligations for audit, but send only applicable
  obligations to the model.

### Phase 4: Claim Insertion And Quote Binding

- Parse provider payload into local models.
- Resolve each `quote_text` exactly and uniquely inside the request window.
- Insert `spans`, `claims`, typed claim rows, `claim_evidence`, and
  `claim_coverage_links`.
- Python writes `coverage_results`.
- Missing, ambiguous, or wrongly attributed quotes fail loudly or produce
  blocking review flags; do not salvage them into canonical rows.

### Phase 5: Claim Disposition And Canonicalization

- Every claim must receive exactly one current disposition:
  `supported`, `merged_duplicate`, `rejected_unsupported`,
  `queued_ambiguity`, or `out_of_scope`.
- Only supported or merged duplicate claims can influence canonical rows.
- Canonicalize actors, process cycles, events, event actor links,
  actor relations, and participation counts.
- Every canonical row must link to `row_evidence`.

### Phase 6: Validation

Hard validation must check:

- every claim has one current disposition;
- every current applicable obligation has one current coverage result;
- `claims_emitted` has matching `claim_coverage_links`;
- every claim has `claim_evidence`;
- every canonical row has `row_evidence`;
- source spans match the source text and fingerprint;
- bid claims have quote support for bidder, date when claimed, value when
  claimed, and bid/proposal context;
- actor relation claims have quote support for subject, object, and relation;
- projection rows have projection units and do not depend on unresolved
  blocking review flags.

### Phase 7: Projection

- Build `project_review.py` to render human review rows comparable to old
  output.
- Build `project_estimation.py` to render estimator bidder rows.
- Projection unit is actor-cycle scoped.
- Group actors are eligible bidder units when they submit bids.
- Member actors are not projected unless independently linked to bid events.
- `T` is Python-derived:
  - `strategic` when source/projection rules support an operating strategic
    bidder as the auction-facing unit;
  - `financial` when source/projection rules support sponsor/financial buyer;
  - `mixed` or `unknown` when not mechanically defensible.

### Phase 8: Live Contract And Cleanup

- Update `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `docs/linkflow-extraction-guide.md`,
  `rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`,
  `rules/dates.md`, and `rules/invariants.md`.
- Delete or rewrite stale docs, tests, reports, fixtures, and generated
  artifacts that describe the old row-per-event contract as live.
- Regenerate affected reference outputs after the demo succeeds.
- Do not leave compatibility shims.

## First Demo: mac-gray

The first vertical slice must be `mac-gray`.

Demo command shape may evolve, but it should be one explicit target, not a
reference batch:

```bash
python run.py --slug mac-gray --re-extract
python -m pipeline.deal_graph.project --slug mac-gray --projection bidder_cycle_baseline_v1
python -m pipeline.deal_graph.validate --slug mac-gray
```

If those CLIs do not exist yet, create equivalent testable entrypoints and
document the final commands.

Acceptance:

- `CSC/Pamplona` exists as one `actor_kind = "group"` actor.
- `CSC/Pamplona` has bid events linked through `event_actor_links` as
  `bid_submitter` or equivalent.
- `CSC` and `Pamplona` are represented through source-backed
  `actor_relations`.
- Pamplona's financing/capital role is represented as a relation or judgment,
  not as a second bidder row.
- The estimator projection emits exactly one bidder row for `CSC/Pamplona`
  and no separate bid rows for `CSC` or `Pamplona` unless separate bid conduct
  is source-supported.
- The projected `T` for `CSC/Pamplona` is `strategic` or review-flagged with
  a concrete reason. The preferred rule is `strategic` when the filing treats
  the auction-facing bidder as CSC/Pamplona and CSC supplies the operating
  strategic buyer role, despite Pamplona financing.
- Every claim and canonical row has source-backed evidence.
- No hard validator flags remain.

## Second And Third Demos

After Mac Gray:

### PetSmart

Acceptance:

- `Buyer Group` is a group actor and bidder unit.
- Longview membership or rollover relation is dated only when supported by the
  filing.
- Longview does not become a bidder row solely because it joined or rolled.
- Final Buyer Group bid remains a group bid.

### Saks

Acceptance:

- Sponsor coalitions are time-aware.
- Sponsor A/E and E/G style coalitions do not become permanent merged actors
  unless the filing supports permanent identity.
- A member's separate conduct can be represented without forcing all group
  actions onto each member.

## Test Plan

Add or rewrite tests in this order:

```text
tests/deal_graph/test_schema.py
tests/deal_graph/test_provider_contract.py
tests/deal_graph/test_quote_binding.py
tests/deal_graph/test_claim_disposition.py
tests/deal_graph/test_canonicalization.py
tests/deal_graph/test_consortium_projection.py
tests/deal_graph/test_review_projection.py
tests/deal_graph/test_estimation_projection.py
tests/test_prompt_contract.py
tests/test_run_pool.py
tests/test_reconcile.py
tests/test_stability.py
```

Required targeted checks:

- provider schema top-level properties are claim arrays only;
- provider payload rejects `coverage_results`;
- provider payload rejects `BidderID`, projection rows, and old scalar
  research fields;
- quote binding rejects missing and ambiguous quote text;
- actor relation quote validation requires subject, object, and relation
  support;
- generic count phrases do not become named bidder actors;
- group bid does not create member bid rows;
- Mac Gray projects one `CSC/Pamplona` bidder row;
- PetSmart Longview relation does not atomize Buyer Group bids;
- Saks time-varying coalition does not permanently merge all sponsor
  combinations;
- old row-per-event extraction JSON is not accepted as canonical input.

Final local gates:

```bash
python -m pytest -q
python -m pipeline.reconcile --scope reference
python -m pipeline.stability --scope reference --runs 3 --json --write quality_reports/stability/target-release-proof.json
```

The final two gates will not pass until the full reference set is regenerated
under `deal_graph_v1`; they are listed here as end-state gates, not Phase 1
requirements.

## Stale-Code Cleanup Checklist

Remove or rewrite every live reference to these retired concepts:

```text
SCHEMA_R1 as final row-per-event output
{deal, events} as provider-owned final extraction
BidderID as canonical identity
bidder_registry as canonical identity authority
aggregate_bidder_alias_unatomized
constituent NDA row as forced buyer-group default
ConsortiumCA as substitute for target-side NDA
output/extractions/{slug}.json as row-per-event canonical truth
```

Keep only projection/review references to old row fields, and label them
derived.

## Open Implementation Questions

Resolve these during Phase 1, before live extraction:

- Should `deal_graph.duckdb` live inside `output/audit/{slug}/runs/{run_id}/`
  or under `output/deal_graph/{slug}/runs/{run_id}/`?
- Should `filings/paragraphs/spans` be populated from `pages.json`, `raw.md`,
  or both? The first demo can use `raw.md` plus page hints if exact source
  binding remains auditable.
- What is the exact minimal event subtype enum needed for all nine reference
  deals?
- What is the exact `T` projection rule for mixed strategic/financial groups
  beyond the Mac Gray CSC/Pamplona case?
- How should old `DropSilent` become graph facts: event, judgment, or review
  projection only?

These are implementation decisions, not reasons to preserve the old schema.

## Success Criteria For This Refactor

The refactor is complete only when:

- `deal_graph_v1` is the only live canonical output contract.
- The provider emits claims only.
- Relational graph artifacts are created per run.
- Mac Gray, PetSmart, and Saks demos satisfy the acceptance checks above.
- All nine reference deals are regenerated or explicitly marked stale/absent
  until regenerated.
- Old row-per-event JSON cannot pass as live canonical extraction.
- Alex-style review rows and estimation bidder rows are deterministic
  projections from the graph.
- `python -m pytest -q` passes.
- Live docs and rules describe only the new architecture.
- Stale code, tests, fixtures, reports, and generated artifacts for the old
  architecture are deleted or rewritten.
