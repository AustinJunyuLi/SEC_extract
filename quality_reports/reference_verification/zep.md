# zep Agent Verification

## Run Metadata

- Slug: zep
- Target: ZEP INC
- Acquirer: NEW MOUNTAIN CAPITAL
- Run ID: `fd76f2e8a1454ccc9d85342b5144fecd`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.220650Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1408287/0001047469-15-004989-index.htm

Artifacts:
- Audit run: `output/audit/zep/runs/fd76f2e8a1454ccc9d85342b5144fecd`
- Manifest: `output/audit/zep/runs/fd76f2e8a1454ccc9d85342b5144fecd/manifest.json`
- Raw response: `output/audit/zep/runs/fd76f2e8a1454ccc9d85342b5144fecd/raw_response.json`
- Graph JSON: `output/audit/zep/runs/fd76f2e8a1454ccc9d85342b5144fecd/deal_graph_v2.json`
- DuckDB: `output/audit/zep/runs/fd76f2e8a1454ccc9d85342b5144fecd/deal_graph.duckdb`
- Portable extraction: `output/extractions/zep.json`
- Review JSONL: `output/review_rows/zep.jsonl`
- Review CSV: `output/review_csv/zep.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs zep`

## Extraction And Flag Summary

- Review statuses: clean: 60
- Open review rows: 0
- Flag severities: none
- Actors: 18
- Events: 27
- Bids: 0
- Participation counts: 9
- Actor relations: 6
- Evidence spans: 54
- Review rows: 60

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `fd76f2e8a1454ccc9d85342b5144fecd`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 60. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 36 / 35 / 35 / 35 / 36 / 36 / 36 | actor_claim | clean | Mr. Timothy M. Manganello ("Mr. Manganello", and together with Mr. Nurkin and Mr. Squicciarino, the "Board Representatives") / At a January 28, 2014 b |
| Filing page 35 / 35 / 42 / 35 / 36 | actor_claim | clean | representatives of BofA Merrill Lynch and two other investment banks / At a January 28, 2014 board meeting / Representatives of BofA Merrill Lynch com |
| Filing page 35 / 35 / 35 / 36 | actor_claim | clean | At a January 28, 2014 board meeting / King & Spalding LLP ("King & Spalding"), legal counsel to the Company / our board of directors unanimously appro |
| Filing page 39 / 39 / 39 | actor_claim | clean | Jefferies Finance LLC / On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest / The indication of interest was su |
| Filing page 35 / 35 | actor_claim | clean | King & Spalding LLP ("King & Spalding"), legal counsel to the Company / King & Spalding LLP ("King & Spalding"), legal counsel to the Company |
| Filing page 34 / 35 / 36 | actor_claim | clean | Mr. Joseph Squicciarino ("Mr. Squicciarino") / At a January 28, 2014 board meeting / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Mangan |
| Filing page 34 / 35 / 36 | actor_claim | clean | Mr. Sidney J. Nurkin ("Mr. Nurkin") / At a January 28, 2014 board meeting / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Manganello ("Mr |
| Filing page 36 / 35 / 36 | actor_claim | clean | Mr. Timothy M. Manganello ("Mr. Manganello" / At a January 28, 2014 board meeting / Mr. Nurkin and Mr. Squicciarino, as well as Mr. Timothy M. Mangane |
| Filing page 37 / 37 / 37 / 37 / 39 / 39 / 39 / 40 / 40 / 40 / 42 / 39 / 39 / 40 | actor_claim | clean | One of the financial buyers contacted during such time was New Mountain Capital. / We entered into a confidentiality agreement with New Mountain Capit |
| Filing page 39 / 39 | actor_relation_claim | clean | On February 19, 2015, New Mountain Capital delivered an unsolicited indication of interest / The indication of interest was supported by a highly conf |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
