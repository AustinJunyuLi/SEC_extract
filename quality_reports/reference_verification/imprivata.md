# imprivata Agent Verification

## Run Metadata

- Slug: imprivata
- Target: IMPRIVATA INC
- Acquirer: THOMA BRAVO, LLC
- Run ID: `feba47dcf9534930a605371b1a4bace3`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.219041Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1328015/0001193125-16-677939-index.htm

Artifacts:
- Audit run: `output/audit/imprivata/runs/feba47dcf9534930a605371b1a4bace3`
- Manifest: `output/audit/imprivata/runs/feba47dcf9534930a605371b1a4bace3/manifest.json`
- Raw response: `output/audit/imprivata/runs/feba47dcf9534930a605371b1a4bace3/raw_response.json`
- Graph JSON: `output/audit/imprivata/runs/feba47dcf9534930a605371b1a4bace3/deal_graph_v2.json`
- DuckDB: `output/audit/imprivata/runs/feba47dcf9534930a605371b1a4bace3/deal_graph.duckdb`
- Portable extraction: `output/extractions/imprivata.json`
- Review JSONL: `output/review_rows/imprivata.jsonl`
- Review CSV: `output/review_csv/imprivata.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs imprivata`

## Extraction And Flag Summary

- Review statuses: clean: 52
- Open review rows: 0
- Flag severities: none
- Actors: 16
- Events: 26
- Bids: 0
- Participation counts: 5
- Actor relations: 5
- Evidence spans: 47
- Review rows: 52

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `feba47dcf9534930a605371b1a4bace3`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 52. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 30 / 30 / 31 / 30 | actor_claim | clean | Barclays as the Company’s financial advisor / On April 15, 2016, the Board held a meeting to discuss, among other things, the engagement of a financia |
| Filing page 30 / 29 / 30 | actor_relation_claim | clean | On April 15, 2016, the Board held a meeting to discuss, among other things, the engagement of a financial advisor and Thoma Bravo’s indication of inte |
| Filing page 29 / 29 | actor_claim | clean | Goodwin Procter LLP (“ Goodwin ”) / the Company’s outside legal counsel, Goodwin Procter LLP (“ Goodwin ”) |
| Filing page 36 / 36 | actor_claim | clean | Kirkland & Ellis LLP (“ Kirkland ”) / On July 7, 2016, Thoma Bravo’s outside counsel, Kirkland & Ellis LLP (“ Kirkland ”) sent a revised draft of the  |
| Filing page 33 | actor_claim | clean | the Board established a special committee of the Board (the “ Special Committee ”) |
| Filing page 31 / 34 / 32 | actor_claim | clean | three financial sponsors (“ Sponsor A ,” “ Sponsor B ” and Thoma Bravo) / Sponsor A said that it would not be in a position to meaningfully improve up |
| Filing page 32 / 33 | event_claim | clean | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest / the Board au |
| Filing page 31 / 36 / 32 | actor_claim | clean | three financial sponsors (“ Sponsor A ,” “ Sponsor B ” and Thoma Bravo) / On July 8, 2016, the date by which Sponsor B and Thoma Bravo had been invite |
| Filing page 35 / 35 | event_claim | clean | Later on June 24, 2016, Barclays sent final bid process letters to Sponsor B and Thoma Bravo / setting a final bid deadline of July 8, 2016 |
| Filing page 31 / 32 | actor_claim | clean | a telecommunications enterprise company (“ Strategic 1 ”) / On June 8, 2016, Strategic 1 informed Barclays that after further internal consideration,  |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
