# rules/bids.md - Bid Claims and Projection Rules

Provider `bid_claims` record source-backed bid/proposal submissions. They do
not carry Python-owned judgments.

## Bid Claim Fields

- `bidder_label`: filing label for the bidding actor or group.
- `bid_date`: ISO date when supported, otherwise null.
- `bid_value`: point value when supported.
- `bid_value_lower` / `bid_value_upper`: range bounds when supported.
- `bid_value_unit`: `per_share`, `enterprise_value`, `equity_value`, or
  `unspecified`.
- `consideration_type`: `cash`, `stock`, `mixed`, `other`, or `unspecified`.
- `bid_stage`: `initial`, `revised`, `final`, or `unspecified`.

If a quote supports only a willingness to bid and no economics, emit a bid
claim with value fields null and explain through the quote/description in a
related event claim when useful.

Use `equity_value` when the filing supports an aggregate equity transaction
price. Use `enterprise_value` only when the filing itself supports enterprise
value. Use `unspecified` when the filing supports a number but does not support
which aggregate value basis it represents. Do not emit `other` for
`bid_value_unit`.

## Python-Owned Post-Review Projection

The live extraction artifact stops at the source-backed graph and review rows.
Later post-review estimator tooling may derive:

- `bI`, `bI_lo`, `bI_hi`, `bF`
- `admitted`
- `formal_boundary`
- `dropout_mechanism`
- bidder class / `T`

The post-review projection unit is actor-cycle scoped. Group actors are
eligible bidder units when they submit bids. Member actors are not projected
unless they are independently linked to bid events.

`T` is assigned only by Python-owned post-review logic, never by the provider.
