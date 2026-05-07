# stec Agent Verification

## Run Metadata

- Slug: stec
- Target: S T E C INC
- Acquirer: WESTERN DIGITAL CORP
- Run ID: `4e67ce0214df43f2b3f5c3dfa756e9e1`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.229190Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1102741/0001193125-13-325730-index.htm

Artifacts:
- Audit run: `output/audit/stec/runs/4e67ce0214df43f2b3f5c3dfa756e9e1`
- Manifest: `output/audit/stec/runs/4e67ce0214df43f2b3f5c3dfa756e9e1/manifest.json`
- Raw response: `output/audit/stec/runs/4e67ce0214df43f2b3f5c3dfa756e9e1/raw_response.json`
- Graph JSON: `output/audit/stec/runs/4e67ce0214df43f2b3f5c3dfa756e9e1/deal_graph_v2.json`
- DuckDB: `output/audit/stec/runs/4e67ce0214df43f2b3f5c3dfa756e9e1/deal_graph.duckdb`
- Portable extraction: `output/extractions/stec.json`
- Review JSONL: `output/review_rows/stec.jsonl`
- Review CSV: `output/review_csv/stec.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs stec`

## Extraction And Flag Summary

- Review statuses: clean: 66
- Open review rows: 0
- Flag severities: none
- Actors: 25
- Events: 29
- Bids: 0
- Participation counts: 6
- Actor relations: 6
- Evidence spans: 66
- Review rows: 66

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `4e67ce0214df43f2b3f5c3dfa756e9e1`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 66. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 35 | actor_claim | clean | 18 prospective acquirers |
| Filing page 35 / 35 / 35 / 35 | actor_claim | clean | BofA Merrill Lynch / BofA Merrill Lynch to act as sTec’s financial advisor / On April 1, 2013, as directed by the special committee, BofA Merrill Lync |
| Filing page 32 / 32 | actor_claim | clean | Company A, a participant in the storage industry / On November 14, 2012, an investment bank representing Company A, a participant in the storage indus |
| Filing page 33 / 33 / 34 / 33 | actor_claim | clean | Company B, a participant in the electronics industry / On February 13, 2013, Mr. Manouch Moshayedi met with the President of Company B, a participant  |
| Filing page 34 / 34 / 36 / 34 | actor_claim | clean | Company C, a participant in the semiconductor industry / On March 13, 2013, Mr. Mark Moshayedi and Mr. Manouch Moshayedi met with representatives of C |
| Filing page 35 / 35 / 35 / 40 / 36 / 37 | actor_claim | clean | Company D, a participant in the storage industry / In mid-March, 2013, the head of corporate development for Company D, a participant in the storage i |
| Filing page 35 / 35 / 36 | actor_claim | clean | Company E, a participant in the storage industry / On April 4, 2013, sTec entered into a non-disclosure agreement with Company E / Company E indicated |
| Filing page 35 / 35 / 36 | actor_claim | clean | Company F / on April 11, it entered into a non-disclosure agreement with Company F / on April 24, Company F declined the invitation to schedule a mana |
| Filing page 36 / 36 / 37 | actor_claim | clean | Company G, a participant in the storage industry / on April 17, it entered into a non-disclosure agreement with Company G / Also on May 3, 2013, Compa |
| Filing page 35 / 37 / 37 / 38 / 37 | actor_claim | clean | Company H, a participant in the storage industry / On May 1, 2013, Company H contacted representatives of BofA Merrill Lynch expressing an interest in |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
