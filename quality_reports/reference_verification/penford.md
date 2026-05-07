# penford Agent Verification

## Run Metadata

- Slug: penford
- Target: PENFORD CORP
- Acquirer: INGREDION INC
- Run ID: `25c7b26d2e07423ab9b6d81d0fccd361`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.223687Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/739608/0001193125-14-455030-index.htm

Artifacts:
- Audit run: `output/audit/penford/runs/25c7b26d2e07423ab9b6d81d0fccd361`
- Manifest: `output/audit/penford/runs/25c7b26d2e07423ab9b6d81d0fccd361/manifest.json`
- Raw response: `output/audit/penford/runs/25c7b26d2e07423ab9b6d81d0fccd361/raw_response.json`
- Graph JSON: `output/audit/penford/runs/25c7b26d2e07423ab9b6d81d0fccd361/deal_graph_v2.json`
- DuckDB: `output/audit/penford/runs/25c7b26d2e07423ab9b6d81d0fccd361/deal_graph.duckdb`
- Portable extraction: `output/extractions/penford.json`
- Review JSONL: `output/review_rows/penford.jsonl`
- Review CSV: `output/review_csv/penford.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs penford`

## Extraction And Flag Summary

- Review statuses: clean: 52
- Open review rows: 0
- Flag severities: none
- Actors: 18
- Events: 26
- Bids: 0
- Participation counts: 2
- Actor relations: 6
- Evidence spans: 47
- Review rows: 52

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `25c7b26d2e07423ab9b6d81d0fccd361`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 52. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 31 / 31 / 31 | actor_claim | clean | retain Deutsche Bank as the Company’s financial advisor / retain Deutsche Bank as the Company’s financial advisor and to advise on shareholder matters |
| Filing page 30 | actor_claim | clean | the Executive Committee of the Penford board |
| Filing page 30 / 33 / 37 / 30 / 30 / 33 / 39 / 31 / 31 / 35 / 36 / 38 | actor_claim | clean | Ingredion’s interest in acquiring Penford / J.P. Morgan Securities, Ingredion’s financial advisor / Sidley Austin LLP (referred to as Sidley Austin),  |
| Filing page 33 / 33 | actor_claim | clean | J.P. Morgan Securities, Ingredion’s financial advisor / J.P. Morgan Securities, Ingredion’s financial advisor |
| Filing page 37 / 37 | actor_claim | clean | Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank), legal counsel to SEACOR / Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank) |
| Filing page 31 / 32 / 34 / 36 / 38 / 38 / 38 | actor_claim | clean | a company in the industry (referred to as Party A) / Party A’s Chief Executive Officer also informally discussed Party A’s potential interest in acqui |
| Filing page 34 / 34 / 34 | actor_claim | clean | another strategic counterparty contacted by Deutsche Bank (referred to as Party B) / Party B) expressed interest in further discussions / Party B info |
| Filing page 34 / 34 / 34 | actor_claim | clean | a third potential strategic counterparty contacted by Deutsche Bank (referred to as Party C) / On September 10, 2014, a third potential strategic coun |
| Filing page 34 / 34 / 35 / 37 | actor_claim | clean | a fourth potential strategic counterparty contacted by Deutsche Bank (referred to as Party D) / On September 11, 2014, a fourth potential strategic co |
| Filing page 34 / 34 | actor_claim | clean | another strategic counterparty (referred to as Party E) / In the following two weeks, Deutsche Bank also left several other voicemails for Party E reg |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
