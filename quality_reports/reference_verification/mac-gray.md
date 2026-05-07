# mac-gray Agent Verification

## Run Metadata

- Slug: mac-gray
- Target: MAC GRAY CORP
- Acquirer: CSC SERVICEWORKS, INC.
- Run ID: `cb64ccd28c584471b3f1665d9787510a`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.226088Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1038280/0001047469-13-010973-index.htm

Artifacts:
- Audit run: `output/audit/mac-gray/runs/cb64ccd28c584471b3f1665d9787510a`
- Manifest: `output/audit/mac-gray/runs/cb64ccd28c584471b3f1665d9787510a/manifest.json`
- Raw response: `output/audit/mac-gray/runs/cb64ccd28c584471b3f1665d9787510a/raw_response.json`
- Graph JSON: `output/audit/mac-gray/runs/cb64ccd28c584471b3f1665d9787510a/deal_graph_v2.json`
- DuckDB: `output/audit/mac-gray/runs/cb64ccd28c584471b3f1665d9787510a/deal_graph.duckdb`
- Portable extraction: `output/extractions/mac-gray.json`
- Review JSONL: `output/review_rows/mac-gray.jsonl`
- Review CSV: `output/review_csv/mac-gray.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs mac-gray`

## Extraction And Flag Summary

- Review statuses: clean: 59
- Open review rows: 0
- Flag severities: none
- Actors: 19
- Events: 23
- Bids: 0
- Participation counts: 8
- Actor relations: 9
- Evidence spans: 50
- Review rows: 59

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `cb64ccd28c584471b3f1665d9787510a`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 59. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 36 / 36 | actor_claim | clean | Mac-Gray entered into an engagement letter with BofA Merrill Lynch / On May 31, 2013, Mac-Gray entered into an engagement letter with BofA Merrill Lyn |
| Filing page 33 / 38 / 33 | actor_claim | clean | CSC was purchased by Pamplona in May 2013 / CSC and Pamplona, who together we refer to as CSC/Pamplona / CSC was purchased by Pamplona in May 2013 |
| Filing page 38 / 38 / 38 / 44 / 41 / 39 / 44 / 47 / 39 / 41 / 42 / 43 / 42 | actor_claim | clean | CSC and Pamplona, who together we refer to as CSC/Pamplona / CSC and Pamplona, who together we refer to as CSC/Pamplona / CSC and Pamplona, who togeth |
| Filing page 33 / 33 | actor_claim | clean | Goodwin Procter LLP, outside legal counsel to Mac-Gray / Goodwin Procter LLP, outside legal counsel to Mac-Gray |
| Filing page 44 / 44 | actor_claim | clean | Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we refer to as Kirkland / On September 25, 2013, Goodwin Procter delivered to Kirkla |
| Filing page 36 / 33 | actor_claim | clean | On May 31, 2013, Mac-Gray entered into an engagement letter with BofA Merrill Lynch with respect to the Board's undertaking a review of strategic alte |
| Filing page 47 | event_claim | clean | Later in the day, on October 14, 2013, the merger agreement was executed |
| Filing page 35 / 47 | actor_claim | clean | Moab Partners, L.P. and certain of its affiliates, which we refer collectively to as Moab / Moab and Parent executed the Moab voting agreement |
| Filing page 33 | actor_claim | clean | Stewart G. MacDonald, Jr., our chief executive officer |
| Filing page 45 / 47 | actor_relation_claim | clean | the MacDonald voting agreements, which were entered into by Mr. MacDonald, his wife and one of his trusts on September 27, 2013, and which became effe |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
