# mac-gray Agent Verification

## Run Metadata

- Slug: mac-gray
- Target: MAC GRAY CORP
- Acquirer: CSC SERVICEWORKS, INC.
- Run ID: `974917dc458b4cde8d9b0ad352abc81b`
- Schema version: `deal_graph_v2`
- Rulebook version: `5802eebbe682821ad16526031588d8ccca896a6d8cc91c9ea0c99e1ebc8ae490`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-06T15:54:39.237465Z
- Filing source: a2217482zdefm14a.htm
- Filing URL: https://www.sec.gov/Archives/edgar/data/1038280/000104746913010973/a2217482zdefm14a.htm

Artifacts:
- Audit run: `output/audit/mac-gray/runs/974917dc458b4cde8d9b0ad352abc81b`
- Manifest: `output/audit/mac-gray/runs/974917dc458b4cde8d9b0ad352abc81b/manifest.json`
- Raw response: `output/audit/mac-gray/runs/974917dc458b4cde8d9b0ad352abc81b/raw_response.json`
- Graph JSON: `output/audit/mac-gray/runs/974917dc458b4cde8d9b0ad352abc81b/deal_graph_v2.json`
- DuckDB: `output/audit/mac-gray/runs/974917dc458b4cde8d9b0ad352abc81b/deal_graph.duckdb`
- Portable extraction: `output/extractions/mac-gray.json`
- Review JSONL: `output/review_rows/mac-gray.jsonl`
- Review CSV: `output/review_csv/mac-gray.csv`

## Commands

- `python -m pipeline.run_pool --filter reference --workers 5 --re-extract --extract-reasoning-effort high`
- `python scripts/check_reference_verification.py`
- `python -m pipeline.reconcile --scope reference`
- `python -m pipeline.stability --scope reference --runs 3 --json`

## Extraction And Flag Summary

- Review statuses: clean: 65
- Open review rows: 0
- Flag severities: none
- Actors: 22
- Events: 26
- Participation counts: 8
- Actor relations: 9
- Evidence spans: 52
- Review rows: 65

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `974917dc458b4cde8d9b0ad352abc81b`. | SEC filing text controls the report; Alex material remains calibration material. |
| Current review rows | The CSV has 65 rows with review status counts `clean: 65`. | Rows are accepted only through exact source binding in the current artifact set. |
| Rule surface | The live prompt and rulebook are not changed by this report. | No deal-specific operating rule is introduced. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads the raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Claim summary | Evidence excerpt |
|---|---|---|---|
| Filing page 35 \| 35 \| 36 | actor_claim | actor BofA Merrill Lynch (organization) | Mac-Gray engage BofA Merrill Lynch as Mac-Gray's financial advisor \| Mac-Gray engage BofA Merrill Lynch as Mac-Gray's financial advisor \| On May 31, 2013, Mac-Gray entered int... |
| Filing page 38 \| 38 \| 38 | actor_claim | actor CSC/Pamplona (group) | CSC and Pamplona, who together we refer to as CSC/Pamplona \| CSC and Pamplona, who together we refer to as CSC/Pamplona \| an acquisition of Mac-Gray by its portfolio company, CSC |
| Filing page 38 \| 38 \| 38 \| 44 \| 39 \| 44 \| 47 \| 39 \| 41 \| 42 \| 43 | actor_claim | actor CSC/Pamplona (group) | CSC and Pamplona, who together we refer to as CSC/Pamplona \| CSC and Pamplona, who together we refer to as CSC/Pamplona \| CSC and Pamplona, who together we refer to as CSC/Pam... |
| Filing page 33 \| 33 | actor_claim | actor Goodwin Procter LLP (organization) | Goodwin Procter LLP, outside legal counsel to Mac-Gray \| Goodwin Procter LLP, outside legal counsel to Mac-Gray |
| Filing page 44 \| 44 | actor_claim | actor Kirkland & Ellis LLP (organization) | Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we refer to as Kirkland \| Kirkland & Ellis LLP, outside legal counsel to CSC/Pamplona, whom we refer to as Kir... |
| Filing page 35 \| 33 \| 36 | actor_claim | actor BofA Merrill Lynch (organization) | Mac-Gray engage BofA Merrill Lynch as Mac-Gray's financial advisor \| Goodwin Procter LLP, outside legal counsel to Mac-Gray \| On May 31, 2013, Mac-Gray entered into an engagem... |
| Filing page 47 | event_claim | 2013-10-14 merger_agreement_executed Mac-Gray, CSC and Pamplona | Later in the day, on October 14, 2013, the merger agreement was executed, the Pamplona commitment letter was delivered |
| Filing page 45 \| 47 | actor_relation_claim | Mr. MacDonald, his wife and one of his trusts voting_support_for MacDonald voting agree... | the MacDonald voting agreements, which were entered into by Mr. MacDonald, his wife and one of his trusts on September 27, 2013, and which became effective upon entry into the m... |
| Filing page 35 | actor_claim | actor Michael M. Rothenberg (person) | Michael M. Rothenberg and James E. Hyman, candidates nominated by Mac-Gray's stockholder, Moab Partners, L.P. |
| Filing page 35 \| 47 | actor_claim | actor Moab (organization) | Moab Partners, L.P. and certain of its affiliates, which we refer collectively to as Moab \| Moab and Parent executed the Moab voting agreement |
| Filing page 47 | actor_relation_claim | Moab voting_support_for Moab voting agreement | Moab and Parent executed the Moab voting agreement |
| Filing page 45 \| 47 | actor_relation_claim | Mr. MacDonald, his wife and one of his trusts voting_support_for MacDonald voting agree... | the MacDonald voting agreements, which were entered into by Mr. MacDonald, his wife and one of his trusts on September 27, 2013, and which became effective upon entry into the m... |

## Contract Updates

No prompt, rulebook, reference JSON, compatibility path, or fallback path was changed for this verification report.

## Conclusion

Conclusion: VERIFIED
