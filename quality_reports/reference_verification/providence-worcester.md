# providence-worcester Agent Verification

## Run Metadata

- Slug: providence-worcester
- Target: PROVIDENCE & WORCESTER RR CO
- Acquirer: GENESEE & WYOMING INC
- Run ID: `6b5d393b6d5247a397c32db8672baecc`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.216202Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/831968/0001193125-16-713780-index.htm

Artifacts:
- Audit run: `output/audit/providence-worcester/runs/6b5d393b6d5247a397c32db8672baecc`
- Manifest: `output/audit/providence-worcester/runs/6b5d393b6d5247a397c32db8672baecc/manifest.json`
- Raw response: `output/audit/providence-worcester/runs/6b5d393b6d5247a397c32db8672baecc/raw_response.json`
- Graph JSON: `output/audit/providence-worcester/runs/6b5d393b6d5247a397c32db8672baecc/deal_graph_v2.json`
- DuckDB: `output/audit/providence-worcester/runs/6b5d393b6d5247a397c32db8672baecc/deal_graph.duckdb`
- Portable extraction: `output/extractions/providence-worcester.json`
- Review JSONL: `output/review_rows/providence-worcester.jsonl`
- Review CSV: `output/review_csv/providence-worcester.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs providence-worcester`

## Extraction And Flag Summary

- Review statuses: clean: 65
- Open review rows: 0
- Flag severities: none
- Actors: 25
- Events: 26
- Bids: 0
- Participation counts: 6
- Actor relations: 8
- Evidence spans: 58
- Review rows: 65

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `6b5d393b6d5247a397c32db8672baecc`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 65. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 37 / 39 / 39 | actor_claim | clean | BMO (which acquired the business of GHF on August 1, 2016) / BMO then rendered an oral opinion to the Board, subsequently confirmed by delivery of a w |
| Filing page 39 / 39 / 39 | actor_claim | clean | a BMO affiliate / a BMO affiliate / a BMO affiliate has a participation in G&W’s existing secured syndicated debt facility |
| Filing page 36 / 39 | actor_claim | clean | common stock and preferred stock held by the Eder Trusts / the Company, G&W and the Eder Trusts executed the voting agreement |
| Filing page 35 / 38 / 39 / 35 / 39 / 36 / 36 / 38 / 39 / 36 / 39 | actor_claim | clean | five potential strategic buyers (including G&W) / On August 10, 2016, representatives of Hinckley Allen and Simpson Thacher & Bartlett LLP (which we r |
| Filing page 37 / 37 | event_claim | clean | The Transaction Committee met by telephone conference on July 22, 2016 and in person after the regular quarterly Board meeting on July 27, 2016 / The  |
| Filing page 34 / 34 | actor_relation_claim | clean | the subcommittee recommended to the Board that the Company retain GHF as its investment banking firm / Following this presentation, the Board approved |
| Filing page 34 | actor_claim | clean | Greene Holcomb & Fisher LLC (the business of which was subsequently acquired by BMO Capital Markets Corp. and which we refer to as “GHF” prior to such |
| Filing page 35 / 35 | actor_claim | clean | the Company’s legal counsel, Hinckley, Allen & Snyder LLP (which we refer to as “Hinckley Allen”) / the Company’s legal counsel, Hinckley, Allen & Sny |
| Filing page 34 / 34 / 34 | actor_claim | clean | one of the Company’s Class I rail partners (“Party A”) / met with one of the Company’s Class I rail partners (“Party A”) to discuss joint commercial o |
| Filing page 35 / 35 | event_claim | clean | On March 24, 2016, the Transaction Committee met by telephone conference / The Transaction Committee authorized GHF to contact Party A as well as othe |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
