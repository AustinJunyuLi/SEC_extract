# penford Agent Verification

## Run Metadata

- Slug: penford
- Target: PENFORD CORP
- Acquirer: INGREDION INC
- Run ID: `57148524ea5e4316bb4a09f8402c6a85`
- Schema version: `deal_graph_v2`
- Rulebook version: `5802eebbe682821ad16526031588d8ccca896a6d8cc91c9ea0c99e1ebc8ae490`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T15:54:39.237465Z
- Filing source: d834783ddefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/739608/000119312514455030/d834783ddefm14a.htm

Artifacts:
- Audit run: `output/audit/penford/runs/57148524ea5e4316bb4a09f8402c6a85`
- Manifest: `output/audit/penford/runs/57148524ea5e4316bb4a09f8402c6a85/manifest.json`
- Raw response: `output/audit/penford/runs/57148524ea5e4316bb4a09f8402c6a85/raw_response.json`
- Graph JSON: `output/audit/penford/runs/57148524ea5e4316bb4a09f8402c6a85/deal_graph_v2.json`
- DuckDB: `output/audit/penford/runs/57148524ea5e4316bb4a09f8402c6a85/deal_graph.duckdb`
- Portable extraction: `output/extractions/penford.json`
- Review JSONL: `output/review_rows/penford.jsonl`
- Review CSV: `output/review_csv/penford.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 5 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py`
- `python -m pipeline.reconcile --scope reference`
- `python -m pipeline.stability --scope reference --runs 3 --json`

## Extraction And Flag Summary

- Review statuses: clean: 50
- Open review rows: 0
- Flag severities: none
- Actors: 17
- Events: 25
- Participation counts: 2
- Actor relations: 6
- Evidence spans: 48
- Review rows: 50

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `57148524ea5e4316bb4a09f8402c6a85`. | SEC filing text controls the report; Alex material remains calibration material. |
| Current review rows | The CSV has 50 rows with review status counts `clean: 50`. | Rows are accepted only through exact source binding in the current artifact set. |
| Rule surface | The live prompt and rulebook are not changed by this report. | No deal-specific operating rule is introduced. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads the raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Claim summary | Evidence excerpt |
|---|---|---|---|
| Filing page 31 \| 31 \| 31 | actor_claim | actor Deutsche Bank (organization) | Deutsche Bank as the Company’s financial advisor \| the Executive Committee directed management to proceed to retain Deutsche Bank as the Company’s financial advisor and to advi... |
| Filing page 30 \| 33 \| 37 \| 30 \| 30 \| 30 \| 31 \| 33 \| 39 \| 31 \| 31 \| 35 \| 36 \| 36 \| 35 \| 36 | actor_claim | actor Ingredion (organization) | Ingredion’s Chairman and Chief Executive Officer \| J.P. Morgan Securities, Ingredion’s financial advisor \| Sidley Austin LLP (referred to as Sidley Austin), Ingredion’s legal... |
| Filing page 33 \| 33 | actor_claim | actor J.P. Morgan Securities (organization) | J.P. Morgan Securities, Ingredion’s financial advisor \| J.P. Morgan Securities, Ingredion’s financial advisor |
| Filing page 37 \| 37 | actor_claim | actor Milbank (organization) | Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank), legal counsel to SEACOR \| Milbank, Tweed, Hadley & McCloy, LLP (referred to as Milbank), legal counsel to SEACOR |
| Filing page 31 \| 32 \| 36 \| 38 \| 38 \| 38 | actor_claim | actor Party A (organization) | a company in the industry (referred to as Party A) \| Also on August 11, 2014, Mr. Malkoski met with the Chief Executive Officer of Party A. Mr. Malkoski and Party A’s Chief Exe... |
| Filing page 34 \| 34 | actor_claim | actor Party B (organization) | another strategic counterparty contacted by Deutsche Bank (referred to as Party B) \| On September 12, 2014, Party B informed Deutsche Bank that it had decided not to move forwa... |
| Filing page 34 \| 34 | actor_claim | actor Party C (organization) | a third potential strategic counterparty contacted by Deutsche Bank (referred to as Party C) \| On September 15, 2014, Penford and Party C executed a nondisclosure and standstil... |
| Filing page 34 \| 35 \| 37 | actor_claim | actor Party D (organization) | a fourth potential strategic counterparty contacted by Deutsche Bank (referred to as Party D) \| On September 23, 2014, Penford and Party D executed a nondisclosure and standsti... |
| Filing page 34 \| 34 | actor_claim | actor Party E (organization) | another strategic counterparty (referred to as Party E) \| Also on September 12, 2014, Deutsche Bank left a voicemail for another strategic counterparty (referred to as Party E)... |
| Filing page 35 \| 36 | actor_claim | actor Party F (organization) | the two largest companies in Penford’s industry (referred to as Party F and Party G) \| On September 29, 2014, Party F communicated to Deutsche Bank that a combination with Penf... |
| Filing page 35 \| 35 | actor_claim | actor Party F (organization) | the two largest companies in Penford’s industry (referred to as Party F and Party G) \| The board determined that Party F should be approached regarding a potential transaction... |
| Filing page 31 \| 31 \| 31 | actor_claim | actor Perkins Coie (organization) | the Executive Committee directed management to proceed to retain Deutsche Bank as the Company’s financial advisor and to advise on shareholder matters and to evaluate strategic... |

## Contract Updates

No prompt, rulebook, reference JSON, compatibility path, or fallback path was changed for this verification report.

## Conclusion

Conclusion: VERIFIED
