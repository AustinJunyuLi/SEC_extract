# imprivata Agent Verification

## Run Metadata

- Slug: imprivata
- Target: IMPRIVATA INC
- Acquirer: THOMA BRAVO, LLC
- Run ID: `b740935fd0c04351b0d033d4e18ec698`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.510437Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1328015/0001193125-16-677939-index.htm

Artifacts:
- Audit run: `output/audit/imprivata/runs/b740935fd0c04351b0d033d4e18ec698`
- Manifest: `output/audit/imprivata/runs/b740935fd0c04351b0d033d4e18ec698/manifest.json`
- Raw response: `output/audit/imprivata/runs/b740935fd0c04351b0d033d4e18ec698/raw_response.json`
- Graph JSON: `output/audit/imprivata/runs/b740935fd0c04351b0d033d4e18ec698/deal_graph_v2.json`
- DuckDB: `output/audit/imprivata/runs/b740935fd0c04351b0d033d4e18ec698/deal_graph.duckdb`
- Portable extraction: `output/extractions/imprivata.json`
- Review JSONL: `output/review_rows/imprivata.jsonl`
- Review CSV: `output/review_csv/imprivata.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs imprivata`

## Extraction And Flag Summary

- Review statuses: clean: 46
- Open review rows: 0
- Flag severities: none
- Actors: 15
- Events: 20
- Bids: 8
- Participation counts: 7
- Actor relations: 4
- Evidence spans: 41
- Review rows: 46

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `b740935fd0c04351b0d033d4e18ec698`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 46. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 30 | 30 | 30 | actor_claim | clean | Barclays as the Company’s financial advisor / The Board engaged Barclays as the Company’s financial advisor to assist the Board in its evaluation of Thoma Bravo |
| Filing page 30 | 29 | 30 | actor_claim | clean | The Board engaged Barclays as the Company’s financial advisor to assist the Board in its evaluation of Thoma Bravo’s indication of interest / the Company’s outs |
| Filing page 39 | event_claim | clean | On July 13, 2016, before the stock market opened, the parties finalized and executed the merger agreement |
| Filing page 29 | 29 | actor_claim | clean | the Company’s outside legal counsel, Goodwin Procter LLP (“ Goodwin ”) / the Company’s outside legal counsel, Goodwin Procter LLP (“ Goodwin ”) |
| Filing page 36 | 36 | actor_claim | clean | Thoma Bravo’s outside counsel, Kirkland & Ellis LLP (“ Kirkland ”) / Thoma Bravo’s outside counsel, Kirkland & Ellis LLP (“ Kirkland ”) |
| Filing page 33 | actor_claim | clean | the Board established a special committee of the Board (the “ Special Committee ”) that included only independent and disinterested directors |
| Filing page 31 | 34 | 32 | 32 | actor_claim | clean | three financial sponsors (“ Sponsor A ,” “ Sponsor B ” and Thoma Bravo) / Sponsor A was going to cease participating in the strategic process unless subsequentl |
| Filing page 32 | 33 | event_claim | clean | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest / the Board authorized B |
| Filing page 31 | 35 | 32 | 35 | 32 | actor_claim | clean | three financial sponsors (“ Sponsor A ,” “ Sponsor B ” and Thoma Bravo) / Sponsor B had stated that its final bid, if it were to submit one, would be significan |
| Filing page 31 | 32 | actor_claim | clean | a telecommunications enterprise company (“ Strategic 1 ”) / On June 8, 2016, Strategic 1 informed Barclays that after further internal consideration, an acquisi |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
