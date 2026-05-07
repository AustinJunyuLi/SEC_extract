# stec Agent Verification

## Run Metadata

- Slug: stec
- Target: S T E C INC
- Acquirer: WESTERN DIGITAL CORP
- Run ID: `544ac7fe2706460db983c875d6b14476`
- Schema version: `deal_graph_v2`
- Rulebook version: `4a64eef546b7a8496600186879e4878cd5ae62b5bfc0385b93623b790d4a46d8`
- Model: `gpt-5.5`
- Reasoning effort: `high`
- Generated: 2026-05-07T11:06:07.517574Z
- Filing URL: https://www.sec.gov/Archives/edgar/data/1102741/0001193125-13-325730-index.htm

Artifacts:
- Audit run: `output/audit/stec/runs/544ac7fe2706460db983c875d6b14476`
- Manifest: `output/audit/stec/runs/544ac7fe2706460db983c875d6b14476/manifest.json`
- Raw response: `output/audit/stec/runs/544ac7fe2706460db983c875d6b14476/raw_response.json`
- Graph JSON: `output/audit/stec/runs/544ac7fe2706460db983c875d6b14476/deal_graph_v2.json`
- DuckDB: `output/audit/stec/runs/544ac7fe2706460db983c875d6b14476/deal_graph.duckdb`
- Portable extraction: `output/extractions/stec.json`
- Review JSONL: `output/review_rows/stec.jsonl`
- Review CSV: `output/review_csv/stec.csv`

## Commands

- `python -m pipeline.run_pool --filter all --workers 3 --re-extract --release-targets`
- `python scripts/check_reference_verification.py --slugs stec`

## Extraction And Flag Summary

- Review statuses: clean: 64
- Open review rows: 0
- Flag severities: none
- Actors: 22
- Events: 29
- Bids: 8
- Participation counts: 6
- Actor relations: 7
- Evidence spans: 59
- Review rows: 64

## Filing-Grounded Calibration Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| Current graph | Filing page evidence is bound through `evidence_refs` and Python-owned source spans for run `544ac7fe2706460db983c875d6b14476`. | SEC filing text controls the report; Alex calibration material is not an oracle. |
| Current review rows | Review status counts are clean: 64. | Rows are accepted only through exact source binding in the current artifact set. |
| Bidder class contract | Actor claims classify only `financial`, `strategic`, `mixed`, or `unknown`; U.S./non-U.S. and public/private details are out of scope. | This verification covers the restored minimal bidder-class contract. |

## Filing Evidence Review

The current artifact set was checked against the Background filing pages. The mechanical checker re-reads raw provider evidence refs, graph evidence spans, and review-row source quotes from the JSON artifacts and confirms exact filing-page grounding.

| Filing page | Claim type | Review status | Evidence excerpt |
|---|---|---|---|
| Filing page 35 | 35 | 35 | actor_claim | clean | BofA Merrill Lynch to act as sTec’s financial advisor / On March 28, 2013, sTec entered into an engagement letter with BofA Merrill Lynch to provide financial a |
| Filing page 32 | 32 | actor_claim | clean | Company A, a participant in the storage industry / On November 14, 2012, an investment bank representing Company A, a participant in the storage industry, conta |
| Filing page 33 | 33 | 34 | 33 | actor_claim | clean | Company B, a participant in the electronics industry / On February 13, 2013, Mr. Manouch Moshayedi met with the President of Company B, a participant in the ele |
| Filing page 34 | 36 | actor_claim | clean | Company C, a participant in the semiconductor industry / On April 15, 2013, Company C indicated that it was only interested in purchasing limited, select assets |
| Filing page 35 | 35 | 35 | 38 | 40 | 36 | 37 | 36 | actor_claim | clean | Company D, a participant in the storage industry / In mid-March, 2013, the head of corporate development for Company D, a participant in the storage industry, c |
| Filing page 35 | 35 | 36 | actor_claim | clean | Company E, a participant in the storage industry / On April 4, 2013, sTec entered into a non-disclosure agreement with Company E / Shortly thereafter, Company E |
| Filing page 35 | 35 | 36 | 36 | actor_claim | clean | Company F, another / on April 11, it entered into a non-disclosure agreement with Company F / on April 24, Company F declined the invitation to schedule a manag |
| Filing page 36 | 36 | 37 | actor_claim | clean | Company G, a participant in the storage industry / on April 17, it entered into a non-disclosure agreement with Company G / Also on May 3, 2013, Company G indic |
| Filing page 35 | 37 | 38 | 37 | actor_claim | clean | Company H, a participant in the storage industry / Also on May 8, 2013, sTec entered into a non-disclosure agreement with Company H. / the price range Company H |
| Filing page 33 | 33 | actor_claim | clean | Gibson, Dunn & Crutcher LLP (“Gibson Dunn”), which had been engaged in October 2012 as the company’s outside corporate counsel / Gibson, Dunn & Crutcher LLP (“G |

## Contract Updates

This report cites the current `deal_graph_v2` run and the live artifact contract. Only the artifact paths listed above are verification authorities.

## Conclusion

Conclusion: VERIFIED
