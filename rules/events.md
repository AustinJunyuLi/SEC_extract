# rules/events.md - deal_graph_v2 Event Ontology

The provider emits `event_claims`; Python turns supported claims into canonical
events and projections. Old `bid_note` row values are retired as canonical
ontology.

## Event Types

- `process`: sale-process steps, contacts, confidentiality, withdrawals,
  exclusions, advancement, go-shop, financing, and rollover facts.
- `bid`: bid/proposal submission facts. Actual economics should usually be a
  `bid_claim`.
- `transaction`: merger agreement execution and closing-structure facts.

## Event Subtypes

Closed enum:

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

Do not invent new subtypes in provider output. If the filing contains a fact
outside this list, emit the closest supported claim at low confidence only when
the quote clearly supports it, otherwise leave it for rulebook expansion.

## Process Semantics

`nda_signed` is target-bidder confidentiality status. A bidder-bidder or
intra-consortium confidentiality agreement is `consortium_ca_signed` and does
not substitute for a target-side NDA.

`advancement_admitted` and `advancement_declined` describe movement into or
out of a round. They are process facts, not bidder rows.

`withdrawn_by_bidder`, `excluded_by_target`, and `non_responsive` are supported
dropout facts. Silent dropout is a review/projection judgment, not a provider
event unless the filing states the non-response or exclusion.

`merger_agreement_executed` is the signing/execution fact. Price belongs in bid
claims only when the filing supports a bid/proposal claim; execution restating
the price is transaction evidence, not a provider-owned canonical bid.
