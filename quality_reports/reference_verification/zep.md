# zep Agent Verification

## Run Metadata

- Slug: zep
- Target: ZEP INC
- Acquirer: NEW MOUNTAIN CAPITAL
- Run ID: `293708d48d24439e80817820da552604`
- Schema version: `deal_graph_v2`
- Rulebook version: `5802eebbe682821ad16526031588d8ccca896a6d8cc91c9ea0c99e1ebc8ae490`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T15:54:39.237465Z
- Filing source: a2224840zdefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1408287/000104746915004989/a2224840zdefm14a.htm

Artifacts:
- Audit run: `output/audit/zep/runs/293708d48d24439e80817820da552604`
- Manifest: `output/audit/zep/runs/293708d48d24439e80817820da552604/manifest.json`
- Raw response: `output/audit/zep/runs/293708d48d24439e80817820da552604/raw_response.json`
- Graph JSON: `output/audit/zep/runs/293708d48d24439e80817820da552604/deal_graph_v2.json`
- DuckDB: `output/audit/zep/runs/293708d48d24439e80817820da552604/deal_graph.duckdb`
- Portable extraction: `output/extractions/zep.json`
- Review JSONL: `output/review_rows/zep.jsonl`
- Review CSV: `output/review_csv/zep.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 5 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py`
- `python -m pipeline.reconcile --scope reference`
- `python -m pipeline.stability --scope reference --runs 3 --json`

## Extraction And Flag Summary

- Review statuses: clean: 60
- Open review rows: 0
- Flag severities: none
- Actors: 18
- Events: 30
- Participation counts: 9
- Actor relations: 3
- Evidence spans: 46
- Review rows: 60

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `293708d48d24439e80817820da552604`. | SEC filing text controls the report; Alex material remains calibration material. |
| Current review rows | The CSV has 60 rows with review status counts `clean: 60`. | Rows are accepted only through exact source binding in the current artifact set. |
| Rule surface | The live prompt and rulebook are not changed by this report. | No deal-specific operating rule is introduced. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads the raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Claim summary | Evidence excerpt |
|---|---|---|---|
| Filing page 36 | actor_claim | actor Board Representatives (group) | Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nurkin and Mr. Squicciarino, the "Board Representatives") |
| Filing page 36 \| 35 \| 36 \| 42 \| 36 | actor_claim | actor BofA Merrill Lynch (organization) | BofA Merrill Lynch to act as our financial advisor in connection with reviewing our strategic alternatives. \| At a January 28, 2014 board meeting \| BofA Merrill Lynch, at the... |
| Filing page 35 \| 35 \| 36 | actor_claim | actor BofA Merrill Lynch (organization) | At a January 28, 2014 board meeting \| King & Spalding LLP ("King & Spalding"), legal counsel to the Company \| BofA Merrill Lynch to act as our financial advisor in connection... |
| Filing page 39 \| 39 \| 39 | actor_claim | actor Jefferies Finance LLC (organization) | Jefferies Finance LLC \| On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest to the Company \| The indication of interest was supported by... |
| Filing page 35 \| 35 | actor_claim | actor King & Spalding LLP (organization) | King & Spalding LLP ("King & Spalding"), legal counsel to the Company \| King & Spalding LLP ("King & Spalding"), legal counsel to the Company |
| Filing page 37 \| 37 \| 37 \| 37 \| 39 \| 39 \| 40 \| 40 \| 40 \| 39 \| 39 \| 40 | actor_claim | actor New Mountain Capital (organization) | One of the financial buyers contacted during such time was New Mountain Capital. \| We entered into a confidentiality agreement with New Mountain Capital on March 19, 2014. \| O... |
| Filing page 39 \| 39 | actor_relation_claim | Jefferies Finance LLC finances New Mountain Capital indication of interest | On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest to the Company \| The indication of interest was supported by a highly confident finan... |
| Filing page 37 \| 37 \| 38 \| 37 \| 37 | actor_claim | actor Party X (organization) | one financial party ("Party X") \| On May 9, 2014, Party X submitted a preliminary and non-binding indication of interest to BofA Merrill Lynch \| May 14, 2014, prior to receivi... |
| Filing page 37 | event_claim | undated contact_initial Party X and Party Y | two additional parties, comprising one financial party ("Party X") and one strategic party ("Party Y"), contacted representatives of BofA Merrill Lynch on an unsolicited basis t... |
| Filing page 37 \| 38 \| 38 \| 38 | actor_claim | actor Party Y (organization) | one strategic party ("Party Y") \| On May 20, 2014, Party Y submitted a preliminary and non-binding indication of interest \| On May 20, 2014, Party Y submitted a preliminary an... |
| Filing page 36 | event_claim | undated nda_signed a number of the potential buyers | we executed confidentiality agreements with a number of the potential buyers. |
| Filing page 38 | event_claim | 2014-06-26 cohort_closure board of directors | At a June 26, 2014 meeting of our board of directors, based on the lack of buyer interest and the uncertainty surrounding the impact of the fire at our aerosol manufacturing fac... |

## Contract Updates

No prompt, rulebook, reference JSON, compatibility path, or fallback path was changed for this verification report.

## Conclusion

Conclusion: VERIFIED
