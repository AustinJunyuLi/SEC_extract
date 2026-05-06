# rules/dates.md - Dates Under deal_graph_v2

Dates in provider claims are filing-supported facts, not sequence numbers.

Use ISO `YYYY-MM-DD` only when the filing supports a precise date. Use null when the filing gives only vague sequencing such as "subsequently" or
"thereafter". Do not copy vague phrases into date fields.

For rough windows or anchored duration phrases, prefer an event claim with the
quote and null date unless the date can be mechanically resolved from the
surrounding filing text without outside knowledge.

Relation timing matters. For `joins_group`, `exits_group`,
`rollover_holder_for`, `voting_support_for`, and financing/support relations,
populate `effective_date_first` only when the filing supports the timing.

Python owns ordering, process cycles, admission/dropout boundaries, and any
later post-review estimator variables. Provider claims should not emit
`BidderID`, sequence numbers, `T`, `bI`, `bF`, or `admitted`.
