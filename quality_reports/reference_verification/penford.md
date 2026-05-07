# penford Agent Verification

## Run Metadata

- Slug: penford
- Target: PENFORD CORP
- Acquirer: INGREDION INC
- Run ID: `b3e23fa40f3642df85eaec9e1f20e69f`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.513911Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/739608/0001193125-14-455030-index.htm

Artifacts:
- Audit run: `output/audit/penford/runs/b3e23fa40f3642df85eaec9e1f20e69f`
- Manifest: `output/audit/penford/runs/b3e23fa40f3642df85eaec9e1f20e69f/manifest.json`
- Raw response: `output/audit/penford/runs/b3e23fa40f3642df85eaec9e1f20e69f/raw_response.json`
- Graph JSON: `output/audit/penford/runs/b3e23fa40f3642df85eaec9e1f20e69f/deal_graph_v2.json`
- DuckDB: `output/audit/penford/runs/b3e23fa40f3642df85eaec9e1f20e69f/deal_graph.duckdb`
- Portable extraction: `output/extractions/penford.json`
- Review JSONL: `output/review_rows/penford.jsonl`
- Review CSV: `output/review_csv/penford.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs penford`

## Extraction And Flag Summary

- Review statuses: clean: 45
- Open review rows: 0
- Flag severities: none
- Actors: 17
- Events: 21
- Bids: 5
- Participation counts: 1
- Actor relations: 6
- Evidence spans: 40
- Review rows: 45

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `b3e23fa40f3642df85eaec9e1f20e69f`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 45. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 31 | 31 | 31 | actor_claim | clean | retain Deutsche Bank as the Company’s financial advisor / retain Deutsche Bank as the Company’s financial advisor and to advise on shareholder matters and to ev |
| Filing page 31 | 33 | 37 | 30 | 30 | 30 | 33 | 37 | 39 | 31 | 35 | 36 | actor_claim | clean | Ingredion’s interest in a possible business combination between Ingredion and the Company, citing certain strategic reasons for the proposed acquisition / J.P. |
| Filing page 33 | 33 | actor_claim | clean | J.P. Morgan Securities, Ingredion’s financial advisor / J.P. Morgan Securities, Ingredion’s financial advisor |
| Filing page 37 | 37 | actor_claim | clean | Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank), legal counsel to SEACOR / Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank), legal co |
| Filing page 31 | 32 | 36 | 38 | actor_claim | clean | a representative acting on behalf of a company in the industry (referred to as Party A) / Also on August 11, 2014, Mr. Malkoski met with the Chief Executive Off |
| Filing page 34 | 34 | actor_claim | clean | another strategic counterparty contacted by Deutsche Bank (referred to as Party B) / On September 12, 2014, Party B informed Deutsche Bank that it had decided n |
| Filing page 34 | 34 | actor_claim | clean | a third potential strategic counterparty contacted by Deutsche Bank (referred to as Party C) / On September 15, 2014, Penford and Party C executed a nondisclosu |
| Filing page 34 | 35 | 37 | actor_claim | clean | a fourth potential strategic counterparty contacted by Deutsche Bank (referred to as Party D) / On September 23, 2014, Penford and Party D executed a nondisclos |
| Filing page 34 | 34 | actor_claim | clean | another strategic counterparty (referred to as Party E) / Also on September 12, 2014, Deutsche Bank left a voicemail for another strategic counterparty (referre |
| Filing page 35 | 35 | 36 | actor_claim | clean | the two largest companies in Penford’s industry (referred to as Party F and Party G) / On September 24, 2014, in accordance with the board’s authorization, Deut |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
