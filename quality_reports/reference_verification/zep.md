# zep Agent Verification

## Run Metadata

- Slug: zep
- Target: ZEP INC
- Acquirer: NEW MOUNTAIN CAPITAL
- Run ID: `4db2e86fd86b482f9486e1daa5f5fc1b`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.511800Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1408287/0001047469-15-004989-index.htm

Artifacts:
- Audit run: `output/audit/zep/runs/4db2e86fd86b482f9486e1daa5f5fc1b`
- Manifest: `output/audit/zep/runs/4db2e86fd86b482f9486e1daa5f5fc1b/manifest.json`
- Raw response: `output/audit/zep/runs/4db2e86fd86b482f9486e1daa5f5fc1b/raw_response.json`
- Graph JSON: `output/audit/zep/runs/4db2e86fd86b482f9486e1daa5f5fc1b/deal_graph_v2.json`
- DuckDB: `output/audit/zep/runs/4db2e86fd86b482f9486e1daa5f5fc1b/deal_graph.duckdb`
- Portable extraction: `output/extractions/zep.json`
- Review JSONL: `output/review_rows/zep.jsonl`
- Review CSV: `output/review_csv/zep.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs zep`

## Extraction And Flag Summary

- Review statuses: clean: 57
- Open review rows: 0
- Flag severities: none
- Actors: 16
- Events: 24
- Bids: 9
- Participation counts: 11
- Actor relations: 6
- Evidence spans: 49
- Review rows: 57

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `4db2e86fd86b482f9486e1daa5f5fc1b`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 57. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 36 | 36 | 36 | 36 | actor_claim | clean | Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nurkin and Mr. Squicciarino, the "Board Representatives") / Mr. Nurkin and Mr. Squicciarino, |
| Filing page 35 | 35 | 36 | 42 | 36 | actor_claim | clean | representatives of BofA Merrill Lynch and three other investment banks / At a January 28, 2014 board meeting / During the next several weeks, BofA Merrill Lynch |
| Filing page 35 | 35 | 36 | actor_claim | clean | At a January 28, 2014 board meeting / King & Spalding LLP ("King & Spalding"), legal counsel to the Company / BofA Merrill Lynch to act as our financial advisor |
| Filing page 39 | 39 | 39 | actor_claim | clean | Jefferies Finance LLC / On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest / The indication of interest was supported by |
| Filing page 35 | 35 | actor_claim | clean | King & Spalding LLP ("King & Spalding"), legal counsel to the Company / King & Spalding LLP ("King & Spalding"), legal counsel to the Company |
| Filing page 34 | 36 | actor_claim | clean | Mr. Joseph Squicciarino ("Mr. Squicciarino") / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nu |
| Filing page 34 | 36 | actor_claim | clean | Mr. Sidney J. Nurkin ("Mr. Nurkin") / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nurkin and |
| Filing page 36 | 36 | actor_claim | clean | Mr. Timothy M. Manganello ("Mr. Manganello" / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nur |
| Filing page 37 | 37 | 37 | 39 | 40 | 40 | 42 | 39 | 39 | 40 | actor_claim | clean | One of the financial buyers contacted during such time was New Mountain Capital. / We entered into a confidentiality agreement with New Mountain Capital on Marc |
| Filing page 39 | 39 | actor_relation_claim | clean | On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest / The indication of interest was supported by a highly confident fina |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
