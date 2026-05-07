# mac-gray Agent Verification

## Run Metadata

- Slug: mac-gray
- Target: MAC GRAY CORP
- Acquirer: CSC SERVICEWORKS, INC.
- Run ID: `83014a227cf940a2ba54eaaf8719d233`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.515088Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1038280/0001047469-13-010973-index.htm

Artifacts:
- Audit run: `output/audit/mac-gray/runs/83014a227cf940a2ba54eaaf8719d233`
- Manifest: `output/audit/mac-gray/runs/83014a227cf940a2ba54eaaf8719d233/manifest.json`
- Raw response: `output/audit/mac-gray/runs/83014a227cf940a2ba54eaaf8719d233/raw_response.json`
- Graph JSON: `output/audit/mac-gray/runs/83014a227cf940a2ba54eaaf8719d233/deal_graph_v2.json`
- DuckDB: `output/audit/mac-gray/runs/83014a227cf940a2ba54eaaf8719d233/deal_graph.duckdb`
- Portable extraction: `output/extractions/mac-gray.json`
- Review JSONL: `output/review_rows/mac-gray.jsonl`
- Review CSV: `output/review_csv/mac-gray.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs mac-gray`

## Extraction And Flag Summary

- Review statuses: clean: 62
- Open review rows: 0
- Flag severities: none
- Actors: 21
- Events: 25
- Bids: 13
- Participation counts: 6
- Actor relations: 10
- Evidence spans: 51
- Review rows: 62

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `83014a227cf940a2ba54eaaf8719d233`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 62. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 37 | 38 | actor_claim | clean | the Special Committee determined to approach a total of / 50 parties, including CSC and Pamplona, who together we refer to as CSC/Pamplona, and Party A |
| Filing page 35 | 36 | actor_claim | clean | Mac-Gray engage BofA Merrill Lynch as Mac-Gray's financial advisor / On May 31, 2013, Mac-Gray entered into an engagement letter with BofA Merrill Lynch with re |
| Filing page 37 | 38 | 38 | actor_claim | clean | strategic parties, including CSC and Party A / CSC and Pamplona, who together we refer to as CSC/Pamplona / an acquisition of Mac-Gray by its portfolio company, |
| Filing page 38 | 44 | 38 | 38 | 39 | 44 | 47 | 39 | 41 | 42 | 43 | 38 | 42 | actor_claim | clean | CSC and Pamplona, who together we refer to as CSC/Pamplona / Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we refer to as Kirkland / CSC and |
| Filing page 41 | actor_relation_claim | clean | On September 9, 2013, CSC/Pamplona submitted a revised indication of interest with an all-cash purchase price of $19.50 per share, indicating that Pamplona was |
| Filing page 33 | 33 | actor_claim | clean | Goodwin Procter LLP, outside legal counsel to Mac-Gray / Goodwin Procter LLP, outside legal counsel to Mac-Gray |
| Filing page 44 | 44 | actor_claim | clean | Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we refer to as Kirkland / Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we |
| Filing page 36 | 33 | actor_claim | clean | On May 31, 2013, Mac-Gray entered into an engagement letter with BofA Merrill Lynch with respect to the Board's undertaking a review of strategic alternatives, |
| Filing page 47 | event_claim | clean | Later in the day, on October 14, 2013, the merger agreement was executed |
| Filing page 35 | 47 | actor_claim | clean | Moab Partners, L.P. and certain of its affiliates, which we refer collectively to as Moab / Moab and Parent executed the Moab voting agreement |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
