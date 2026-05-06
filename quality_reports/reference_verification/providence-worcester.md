# providence-worcester Agent Verification

## Run Metadata

- Slug: providence-worcester
- Target: PROVIDENCE & WORCESTER RR CO
- Acquirer: GENESEE & WYOMING INC
- Run ID: `d6ecdf547bc04b7fb17a8156f96206ee`
- Schema version: `deal_graph_v2`
- Rulebook version: `5802eebbe682821ad16526031588d8ccca896a6d8cc91c9ea0c99e1ebc8ae490`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T15:54:39.237465Z
- Filing source: d224035ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/831968/000119312516713780/d224035ddefm14a.htm

Artifacts:
- Audit run: `output/audit/providence-worcester/runs/d6ecdf547bc04b7fb17a8156f96206ee`
- Manifest: `output/audit/providence-worcester/runs/d6ecdf547bc04b7fb17a8156f96206ee/manifest.json`
- Raw response: `output/audit/providence-worcester/runs/d6ecdf547bc04b7fb17a8156f96206ee/raw_response.json`
- Graph JSON: `output/audit/providence-worcester/runs/d6ecdf547bc04b7fb17a8156f96206ee/deal_graph_v2.json`
- DuckDB: `output/audit/providence-worcester/runs/d6ecdf547bc04b7fb17a8156f96206ee/deal_graph.duckdb`
- Portable extraction: `output/extractions/providence-worcester.json`
- Review JSONL: `output/review_rows/providence-worcester.jsonl`
- Review CSV: `output/review_csv/providence-worcester.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 5 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py`
- `python -m pipeline.reconcile --scope reference`
- `python -m pipeline.stability --scope reference --runs 3 --json`

## Extraction And Flag Summary

- Review statuses: clean: 62
- Open review rows: 0
- Flag severities: none
- Actors: 24
- Events: 27
- Participation counts: 6
- Actor relations: 5
- Evidence spans: 53
- Review rows: 62

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `d6ecdf547bc04b7fb17a8156f96206ee`. | SEC filing text controls the report; Alex material remains calibration material. |
| Current review rows | The CSV has 62 rows with review status counts `clean: 62`. | Rows are accepted only through exact source binding in the current artifact set. |
| Rule surface | The live prompt and rulebook are not changed by this report. | No deal-specific operating rule is introduced. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads the raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Claim summary | Evidence excerpt |
|---|---|---|---|
| Filing page 34 | actor_claim | actor BMO Capital Markets Corp. (BMO) (organization) | BMO Capital Markets Corp. and which we refer to as “GHF” prior to such acquisition and “BMO” thereafter |
| Filing page 34 \| 35 \| 34 \| 34 | actor_relation_claim | Greene Holcomb & Fisher LLC (GHF) advises Company | Board’s regular quarterly meeting held on January 27, 2016 \| the Company’s legal counsel, Hinckley, Allen & Snyder LLP (which we refer to as “Hinckley Allen”) \| the Company re... |
| Filing page 36 \| 39 | actor_claim | actor Eder Trusts (organization) | the common stock and preferred stock held by the Eder Trusts \| the Company, G&W and the Eder Trusts executed the voting agreement |
| Filing page 35 \| 38 \| 35 \| 39 \| 36 \| 36 \| 38 \| 36 \| 36 | actor_claim | actor G&W (organization) | five potential strategic buyers (including G&W) \| Simpson Thacher & Bartlett LLP (which we refer to as “Simpson Thacher”), G&W’s legal counsel \| Between April 3, 2016 and Apri... |
| Filing page 37 | event_claim | undated advancement_admitted G&W and Party B | The Transaction Committee concluded that the Company should proceed with confirmatory due diligence and negotiations with G&W and Party B |
| Filing page 35 | event_claim | undated contact_initial GHF | representatives of GHF contacted 11 potential strategic buyers (including Party A) and 18 potential financial buyers |
| Filing page 34 \| 34 \| 34 \| 34 | actor_claim | actor Greene Holcomb & Fisher LLC (GHF) (organization) | Greene Holcomb & Fisher LLC (the business of which was subsequently acquired by BMO Capital Markets Corp. and which we refer to as “GHF” prior to such acquisition and “BMO” ther... |
| Filing page 35 \| 35 | actor_claim | actor Hinckley Allen (organization) | Hinckley, Allen & Snyder LLP (which we refer to as “Hinckley Allen”) \| the Company’s legal counsel, Hinckley, Allen & Snyder LLP (which we refer to as “Hinckley Allen”) |
| Filing page 36 | bid_claim | LOI bidders initial bid 19.2-24.0 | In late July 2016, the Company received six LOIs with offer prices per share ranging from $19.20 to $24.00 |
| Filing page 34 \| 34 | actor_claim | actor Party A (organization) | one of the Company’s Class I rail partners (“Party A”) \| Party A suggested possible joint venture arrangements and expressed some interest in acquiring equity in the Company |
| Filing page 35 \| 35 \| 36 | actor_claim | actor Party B (organization) | another potential strategic buyer (“Party B”) \| Subsequently, on April 21, 2016, the Company and representatives of GHF held an introductory meeting with another potential stra... |
| Filing page 36 \| 36 \| 36 \| 37 | actor_claim | actor Party C (organization) | a potential strategic buyer that had not previously been part of the process (“Party C”) \| After executing a confidentiality agreement, Party C was provided the memorandum conc... |

## Contract Updates

No prompt, rulebook, reference JSON, compatibility path, or fallback path was changed for this verification report.

## Conclusion

Conclusion: VERIFIED
