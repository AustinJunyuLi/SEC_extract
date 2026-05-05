# CLAUDE.md - M&A Takeover Auction Extraction Project

This file mirrors `AGENTS.md` for Claude-oriented sessions. The live contract
is `deal_graph_v1`: provider claim extraction, Python-owned quote binding and
canonical graph construction, deterministic graph validation, and derived
review/estimation projections. Read `AGENTS.md` and `SKILL.md` before changing
extraction behavior.

Key rules:

- SEC filing text in `data/filings/{slug}/pages.json` is ground truth.
- Provider output is claim-only: `actor_claims`, `event_claims`, `bid_claims`,
  `participation_count_claims`, and `actor_relation_claims`.
- Extractor input includes paragraph-local `citation_units`.
- Each claim includes `evidence_refs`. Every ref has a `citation_unit_id` from
  `citation_units[]` and an exact `quote_text` substring from that unit.
- Provider-level `quote_text` and `quote_texts` are retired and must not be
  emitted.
- Target identity comes from the filing manifest and Python-owned deal metadata;
  the provider does not emit a target-only actor claim.
- The provider must not emit canonical ids, source offsets, `BidderID`,
  bidder registry, `T`, `bI`, `bF`, admitted/dropout outcomes, coverage
  results, or projection rows.
- Python owns source spans, dispositions, coverage results, canonical actors,
  actor relations, events, validation flags, review rows, and estimator rows.
- Preserve filing bidding units. Buyer groups and consortiums are actors;
  member relations do not automatically become bidder rows.
- No backward compatibility shims or stale row-per-event outputs.
- Keep API keys in runtime environment only and never commit secrets.
- Reference `verified` status requires Austin or agent filing-grounded verification with `quality_reports/reference_verification/{slug}.md`; an agent must not mark a deal verified solely because the model output passes schema validation.

Use:

```bash
python run.py --slug mac-gray --re-extract
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract
python -m pytest -q
```
