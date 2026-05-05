# rules/invariants.md - deal_graph_v1 Validation

Python validation is the authority after provider extraction.

Hard graph checks include:

- provider payload is claim-only and schema-valid;
- no provider-owned canonical ids, source offsets, old row fields, coverage
  results, or projection rows;
- every claim has exactly one current disposition;
- every emitted claim has source evidence;
- every claim tied to an obligation has a current coverage link;
- every current applicable obligation has one current coverage result;
- every canonical actor, event, actor relation, and participation count has
  row evidence;
- source spans match the filing text and evidence fingerprints;
- bid claims have quote support for bidder, date when claimed, value/range
  when claimed, and bid/proposal context;
- actor relation claims have quote support for subject, object, and relation;
- projections are not emitted while blocking review flags remain.

Old row-event invariants are retained in git history only. They are not the
live canonical validator for `deal_graph_v1`.
