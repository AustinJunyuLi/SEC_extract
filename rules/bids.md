# rules/bids.md - Bid Claims and Projection Rules

Provider `bid_claims` record source-backed bid/proposal submissions. They do
not carry estimator variables or formal/informal judgments.

## Bid Claim Fields

- `bidder_label`: filing label for the bidding actor or group.
- `bid_date`: ISO date when supported, otherwise null.
- `bid_value`: point value when supported.
- `bid_value_lower` / `bid_value_upper`: range bounds when supported.
- `bid_value_unit`: `per_share`, `enterprise_value`, `equity_value`, or
  `other`.
- `consideration_type`: `cash`, `stock`, `mixed`, or `other`.
- `bid_stage`: `initial`, `revised`, `final`, or `unspecified`.

If a quote supports only a willingness to bid and no economics, emit a bid
claim with value fields null and explain through the quote/description in a
related event claim when useful.

## Python-Owned Projection

Python derives:

- `bI`, `bI_lo`, `bI_hi`, `bF`
- `admitted`
- `formal_boundary`
- `dropout_mechanism`
- bidder class / `T`

The projection unit is actor-cycle scoped. Group actors are eligible bidder
units when they submit bids. Member actors are not projected unless they are
independently linked to bid events.

`T` is `strategic` when source/projection rules support an operating strategic
bidder as the auction-facing unit; `financial` for sponsor/financial buyers;
`mixed` or `unknown` when mechanically unresolved. Mac Gray
`CSC/Pamplona` is projected as strategic when the filing treats the group as
the bidder and CSC supplies the operating strategic role.
