# saks Agent Verification

## Run Metadata

- Slug: saks
- Target: SAKS INC
- Acquirer: HUDSON'S BAY COMPANy
- Run ID: `19a4e52122c44c5c8ff992f0b00eab3a`
- Schema version: `deal_graph_v2`
- Rulebook version: `7db52e6d8890413332504aaacddf0e2e8895e7725d22d00662c5ad94d3575194`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T22:10:55.227872Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/812900/0001193125-13-390275-index.htm

Artifacts:
- Audit run: `output/audit/saks/runs/19a4e52122c44c5c8ff992f0b00eab3a`
- Manifest: `output/audit/saks/runs/19a4e52122c44c5c8ff992f0b00eab3a/manifest.json`
- Raw response: `output/audit/saks/runs/19a4e52122c44c5c8ff992f0b00eab3a/raw_response.json`
- Graph JSON: `output/audit/saks/runs/19a4e52122c44c5c8ff992f0b00eab3a/deal_graph_v2.json`
- DuckDB: `output/audit/saks/runs/19a4e52122c44c5c8ff992f0b00eab3a/deal_graph.duckdb`
- Portable extraction: `output/extractions/saks.json`
- Review JSONL: `output/review_rows/saks.jsonl`
- Review CSV: `output/review_csv/saks.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 3 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py --slugs saks`

## Extraction And Flag Summary

- Review statuses: clean: 57
- Open review rows: 0
- Flag severities: none
- Actors: 20
- Events: 22
- Bids: 0
- Participation counts: 3
- Actor relations: 12
- Evidence spans: 47
- Review rows: 57

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `19a4e52122c44c5c8ff992f0b00eab3a`. | SEC filing text controls the report; calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 57. | Rows are accepted only through exact source binding in the current artifact set. |
| Open review burden | 0 row(s) have review issues in the current run. | Open issues remain visible in review output and do not become hidden compatibility gates. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 32 / 32 / 32 | actor_claim | clean | a privately held retail company, which we refer to as Company F / Company F, had indicated interest in participating with Sponsor A and Sponsor E in a |
| Filing page 34 / 34 / 34 | actor_claim | clean | Company H, a privately held company based in the U.S. unknown to Saks and its advisors / Neither Saks nor Goldman Sachs received any subsequent commun |
| Filing page 35 / 35 | actor_claim | clean | which we refer to as Company I / only one of the six (which we refer to as Company I) executed a confidentiality agreement with, and conducted a due d |
| Filing page 37 / 37 | actor_claim | clean | the Equity Provider / the definitive nature of the equity financing offered by the Equity Provider |
| Filing page 30 / 30 | actor_claim | clean | Goldman Sachs, one of Saks’ longstanding financial advisors / Goldman Sachs, one of Saks’ longstanding financial advisors |
| Filing page 30 / 30 / 31 / 33 / 34 / 32 / 34 / 33 / 35 | actor_claim | clean | Richard Baker, the Director, Governor, and Chief Executive Officer of Hudson’s Bay / On April 1, 2013, Mr. Sadove met with Richard Baker, the Director |
| Filing page 37 | event_claim | clean | Hudson’s Bay and Merger Sub had already obtained committed debt and equity financing for the transaction |
| Filing page 33 | event_claim | clean | On July 11, 2013, each of Hudson’s Bay, on the one hand, and Sponsor E, together with Sponsor G, on the other hand, submitted proposals expressing the |
| Filing page 35 | actor_claim | clean | Saks, Hudson’s Bay and Merger Sub finalized and executed |
| Filing page 35 / 35 | actor_claim | clean | Morgan Stanley & Co. LLC (a long-time advisor to Saks, referred to as “Morgan Stanley”) / Morgan Stanley & Co. LLC (a long-time advisor to Saks, refer |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
