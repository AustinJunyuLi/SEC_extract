# imprivata Agent Verification

## Run Metadata

- Slug: imprivata
- Target: IMPRIVATA INC
- Acquirer: THOMA BRAVO, LLC
- Run ID: `4631a5b37f81439fa260b79c1e6be270`
- Schema version: `deal_graph_v2`
- Rulebook version: `5802eebbe682821ad16526031588d8ccca896a6d8cc91c9ea0c99e1ebc8ae490`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T15:54:39.237465Z
- Filing source: d226798ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1328015/000119312516677939/d226798ddefm14a.htm

Artifacts:
- Audit run: `output/audit/imprivata/runs/4631a5b37f81439fa260b79c1e6be270`
- Manifest: `output/audit/imprivata/runs/4631a5b37f81439fa260b79c1e6be270/manifest.json`
- Raw response: `output/audit/imprivata/runs/4631a5b37f81439fa260b79c1e6be270/raw_response.json`
- Graph JSON: `output/audit/imprivata/runs/4631a5b37f81439fa260b79c1e6be270/deal_graph_v2.json`
- DuckDB: `output/audit/imprivata/runs/4631a5b37f81439fa260b79c1e6be270/deal_graph.duckdb`
- Portable extraction: `output/extractions/imprivata.json`
- Review JSONL: `output/review_rows/imprivata.jsonl`
- Review CSV: `output/review_csv/imprivata.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 5 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py`
- `python -m pipeline.reconcile --scope reference`
- `python -m pipeline.stability --scope reference --runs 3 --json`

## Extraction And Flag Summary

- Review statuses: clean: 55
- Open review rows: 0
- Flag severities: none
- Actors: 18
- Events: 23
- Participation counts: 8
- Actor relations: 6
- Evidence spans: 54
- Review rows: 55

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `4631a5b37f81439fa260b79c1e6be270`. | SEC filing text controls the report; Alex material remains calibration material. |
| Current review rows | The CSV has 55 rows with review status counts `clean: 55`. | Rows are accepted only through exact source binding in the current artifact set. |
| Rule surface | The live prompt and rulebook are not changed by this report. | No deal-specific operating rule is introduced. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads the raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Claim summary | Evidence excerpt |
|---|---|---|---|
| Filing page 31 \| 31 | actor_claim | actor 15 potentially interested parties (cohort) | the 15 potentially interested parties \| During the period from May 6 through June 9, 2016, at the direction of the Board, Barclays contacted and had discussions with the 15 pot... |
| Filing page 30 \| 30 \| 30 | actor_claim | actor Barclays (organization) | Barclays as the Company’s financial advisor \| Barclays as the Company’s financial advisor \| On April 19, 2016, the Company countersigned an engagement letter with Barclays |
| Filing page 30 \| 29 \| 30 | actor_claim | actor Barclays (organization) | Barclays as the Company’s financial advisor \| the Company’s outside legal counsel, Goodwin Procter LLP (“ Goodwin ”) \| On April 19, 2016, the Company countersigned an engageme... |
| Filing page 29 \| 29 | actor_claim | actor Goodwin Procter LLP (organization) | Goodwin Procter LLP (“ Goodwin ”) \| the Company’s outside legal counsel, Goodwin Procter LLP (“ Goodwin ”) |
| Filing page 36 \| 36 | actor_claim | actor Kirkland & Ellis LLP (organization) | Kirkland & Ellis LLP (“ Kirkland ”) \| Thoma Bravo’s outside counsel, Kirkland & Ellis LLP (“ Kirkland ”) |
| Filing page 33 | actor_claim | actor Special Committee (committee) | the Board established a special committee of the Board (the “ Special Committee ”) |
| Filing page 31 \| 33 \| 32 \| 33 \| 32 \| 32 | actor_claim | actor Sponsor A (organization) | “ Sponsor A ,” \| On June 15, 2016, Sponsor A informed Barclays that in light of its view of the Company after its diligence, if it were to submit a second round bid, it would n... |
| Filing page 32 \| 32 \| 33 | event_claim | 2016-06-09 ioi_submitted Sponsor A, Sponsor B and Thoma Bravo | On June 9, 2016, three parties (Sponsor A, Sponsor B and Thoma Bravo) presented written preliminary non-binding indications of interest \| On June 12, 2016, the Board held a mee... |
| Filing page 31 \| 35 \| 32 \| 35 \| 32 \| 32 | actor_claim | actor Sponsor B (organization) | “ Sponsor B ” \| On June 29, 2016, Sponsor B informed Barclays that in light of its revised views on the Company’s growth outlook, if it were to submit a final bid, it would be... |
| Filing page 35 | event_claim | 2016-06-24 advancement_admitted Sponsor B and Thoma Bravo | Later on June 24, 2016, Barclays sent final bid process letters to Sponsor B and Thoma Bravo, requesting marked drafts of the Company’s proposed form of merger agreement (which... |
| Filing page 31 \| 32 | actor_claim | actor Strategic 1 (organization) | “ Strategic 1 ” \| Strategic 1 informed Barclays that after further internal consideration, an acquisition of the Company would not be a strategic fit for it, and therefore it w... |
| Filing page 31 \| 32 | actor_claim | actor Strategic 2 (organization) | “ Strategic 2 ” \| Strategic 2 informed representatives of Barclays that because of other internal corporate priorities, it was no longer interested in exploring a potential tra... |

## Contract Updates

No prompt, rulebook, reference JSON, compatibility path, or fallback path was changed for this verification report.

## Conclusion

Conclusion: VERIFIED
