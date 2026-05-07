# saks Agent Verification

## Run Metadata

- Slug: saks
- Target: SAKS INC
- Acquirer: HUDSON'S BAY COMPANy
- Run ID: `fb4299d7c2ed4a2d9cf3c87c3b8cee01`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.516248Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/812900/0001193125-13-390275-index.htm

Artifacts:
- Audit run: `output/audit/saks/runs/fb4299d7c2ed4a2d9cf3c87c3b8cee01`
- Manifest: `output/audit/saks/runs/fb4299d7c2ed4a2d9cf3c87c3b8cee01/manifest.json`
- Raw response: `output/audit/saks/runs/fb4299d7c2ed4a2d9cf3c87c3b8cee01/raw_response.json`
- Graph JSON: `output/audit/saks/runs/fb4299d7c2ed4a2d9cf3c87c3b8cee01/deal_graph_v2.json`
- DuckDB: `output/audit/saks/runs/fb4299d7c2ed4a2d9cf3c87c3b8cee01/deal_graph.duckdb`
- Portable extraction: `output/extractions/saks.json`
- Review JSONL: `output/review_rows/saks.jsonl`
- Review CSV: `output/review_csv/saks.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python -m pipeline.run_pool --slugs petsmart-inc,saks --workers 2 --re-extract`
- `python scripts/check_reference_verification.py --slugs saks`

## Extraction And Flag Summary

- Review statuses: clean: 51
- Open review rows: 0
- Flag severities: none
- Actors: 14
- Events: 23
- Bids: 9
- Participation counts: 3
- Actor relations: 11
- Evidence spans: 42
- Review rows: 51

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `fb4299d7c2ed4a2d9cf3c87c3b8cee01`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 51. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 35 | 35 | actor_claim | clean | 58 potentially interested third parties, including private equity firms, companies involved in the retail industry and other potential acquirors / During the go |
| Filing page 32 | actor_claim | clean | a privately held retail company, which we refer to as Company F |
| Filing page 34 | 34 | 34 | 34 | actor_claim | clean | Company H, a privately held company based in the U.S. unknown to Saks and its advisors / Goldman Sachs subsequently attempted on more than one occasion to conta |
| Filing page 35 | 35 | 35 | actor_claim | clean | only one of the six (which we refer to as Company I) executed a confidentiality agreement / only one of the six (which we refer to as Company I) executed a conf |
| Filing page 30 | 30 | actor_claim | clean | Goldman Sachs, one of Saks’ longstanding financial advisors / Goldman Sachs, one of Saks’ longstanding financial advisors |
| Filing page 30 | 30 | 31 | 33 | 33 | 35 | 32 | 33 | 34 | 35 | 35 | actor_claim | clean | a potential acquisition of Saks by Hudson’s Bay / On April 1, 2013, Mr. Sadove met with Richard Baker, the Director, Governor, and Chief Executive Officer of Hu |
| Filing page 35 | 35 | actor_claim | clean | Morgan Stanley & Co. LLC (a long-time advisor to Saks, referred to as “Morgan Stanley”) / Morgan Stanley & Co. LLC (a long-time advisor to Saks, referred to as |
| Filing page 30 | 31 | 35 | actor_claim | clean | Goldman Sachs, one of Saks’ longstanding financial advisors / Wachtell, Lipton, Rosen & Katz, referred to as Wachtell Lipton, Saks’ external counsel / Morgan St |
| Filing page 30 | 31 | 31 | 33 | 30 | 31 | 33 | actor_claim | clean | a representative of a private equity firm, which we refer to as Sponsor A / On April 26, 2013, Saks entered into a confidentiality agreement with each of Sponso |
| Filing page 31 | 31 | 31 | 31 | 33 | 32 | 33 | actor_claim | clean | Sponsor A and Sponsor E, who were considering participating in a potential joint acquisition of Saks / On April 26, 2013, Saks entered into a confidentiality ag |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
