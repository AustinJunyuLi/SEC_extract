# providence-worcester Agent Verification

## Run Metadata

- Slug: providence-worcester
- Target: PROVIDENCE & WORCESTER RR CO
- Acquirer: GENESEE & WYOMING INC
- Run ID: `e86858425fcc4b9db2411b747fcb1f4b`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.507604Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/831968/0001193125-16-713780-index.htm

Artifacts:
- Audit run: `output/audit/providence-worcester/runs/e86858425fcc4b9db2411b747fcb1f4b`
- Manifest: `output/audit/providence-worcester/runs/e86858425fcc4b9db2411b747fcb1f4b/manifest.json`
- Raw response: `output/audit/providence-worcester/runs/e86858425fcc4b9db2411b747fcb1f4b/raw_response.json`
- Graph JSON: `output/audit/providence-worcester/runs/e86858425fcc4b9db2411b747fcb1f4b/deal_graph_v2.json`
- DuckDB: `output/audit/providence-worcester/runs/e86858425fcc4b9db2411b747fcb1f4b/deal_graph.duckdb`
- Portable extraction: `output/extractions/providence-worcester.json`
- Review JSONL: `output/review_rows/providence-worcester.jsonl`
- Review CSV: `output/review_csv/providence-worcester.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs providence-worcester`

## Extraction And Flag Summary

- Review statuses: clean: 64
- Open review rows: 0
- Flag severities: none
- Actors: 25
- Events: 27
- Bids: 15
- Participation counts: 6
- Actor relations: 6
- Evidence spans: 51
- Review rows: 64

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `e86858425fcc4b9db2411b747fcb1f4b`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 64. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 35 | event_claim | clean | During the week of March 28, 2016, in accordance with the Transaction Committee’s directives, representatives of GHF contacted 11 potential strategic buyers (in |
| Filing page 34 | 39 | actor_claim | clean | BMO Capital Markets Corp. and which we refer to as “GHF” prior to such acquisition and “BMO” thereafter / BMO then rendered an oral opinion to the Board, subseq |
| Filing page 39 | actor_relation_claim | clean | BMO then rendered an oral opinion to the Board, subsequently confirmed by delivery of a written opinion, dated August 12, 2016 |
| Filing page 34 | 35 | 34 | actor_claim | clean | the subcommittee recommended to the Board that the Company retain GHF as its investment banking firm / the Company’s legal counsel, Hinckley, Allen & Snyder LLP |
| Filing page 36 | 39 | actor_claim | clean | common stock and preferred stock held by the Eder Trusts / the Company, G&W and the Eder Trusts executed the voting agreement |
| Filing page 35 | 38 | 39 | 39 | 36 | 36 | 38 | 36 | actor_claim | clean | five potential strategic buyers (including G&W) / Simpson Thacher & Bartlett LLP (which we refer to as “Simpson Thacher”), G&W’s legal counsel / the Company, G& |
| Filing page 37 | event_claim | clean | The Transaction Committee concluded that the Company should proceed with confirmatory due diligence and negotiations with G&W and Party B |
| Filing page 34 | 34 | 34 | 34 | actor_claim | clean | Greene Holcomb & Fisher LLC (the business of which was subsequently acquired by BMO Capital Markets Corp. and which we refer to as “GHF” prior to such acquisiti |
| Filing page 35 | 35 | actor_claim | clean | the Company’s legal counsel, Hinckley, Allen & Snyder LLP (which we refer to as “Hinckley Allen”) / the Company’s legal counsel, Hinckley, Allen & Snyder LLP (w |
| Filing page 34 | 34 | 34 | actor_claim | clean | one of the Company’s Class I rail partners (“Party A”) / met with one of the Company’s Class I rail partners (“Party A”) to discuss joint commercial opportuniti |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
