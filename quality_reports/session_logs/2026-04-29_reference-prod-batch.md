---
session: 2026-04-29 prod reference-batch extraction
branch: api-call
operator: Austin (executed by Claude in auto mode)
---

## Goal

Extract all 9 reference deals against the live SEC filing pages, using
Linkflow Responses with `gpt-5.5` (extract: high reasoning, adjudicate: xhigh
reasoning), 5 workers (the xhigh worker ceiling).

## Configuration

- `OPENAI_BASE_URL=https://www.linkflow.run/v1`
- `EXTRACT_MODEL=gpt-5.5`, `--extract-reasoning-effort high`
- `ADJUDICATE_MODEL=gpt-5.5`, `--adjudicate-reasoning-effort xhigh`
- `--filter reference --workers 5`
- API key supplied inline via env (not committed); audit/log scrubbed for the key string.

## Result

`Pool summary: selected=9 succeeded=9 skipped=0 failed=0`

| slug | status | rows | total flags | hard | warn | info | soft |
|---|---|---:|---:|---:|---:|---:|---:|
| medivation | passed | 25 | 15 | 0 | 0 | 9 | 6 |
| imprivata | passed | 27 | 15 | 0 | 0 | 13 | 2 |
| stec | passed | 38 | 20 | 0 | 0 | 13 | 7 |
| penford | passed | 38 | 26 | 0 | 0 | 13 | 13 |
| mac-gray | passed | 63 | 47 | 0 | 0 | 45 | 2 |
| petsmart-inc | passed | 59 | 49 | 0 | 0 | 48 | 1 |
| **zep** | **validated** | 51 | 47 | **1** | 0 | 18 | 28 |
| saks | passed | 42 | 61 | 0 | 0 | 45 | 16 |
| providence-worcester | passed | 80 | 112 | 0 | 0 | 62 | 50 |

All 9 stamped with `rulebook_version=eaeb2c7d…` and matched
`extractor_contract_version=05ff4f6dc…`. `api_endpoint=responses` everywhere.
`json_schema_used=false` (Linkflow prompt-only JSON, expected).

## SDK call profile

- 9 extractor calls (high), 9 scoped adjudicator calls (xhigh, all on
  `providence-worcester` for `missing_nda_dropsilent` soft flags).
- 1 attempt per call, 0 retries, 0 watchdog warnings.
- Extractor latencies: 183-336s. Adjudicator latencies: 5-8s (scoped).
- Token totals: input 795,287 / output 281,495 / reasoning 110,587.

## Hard flag for Austin's review

- **zep**, row_index 50, `ca_type_ambiguous` (severity=hard):
  "NDA inferred from data-room access; filing does not explicitly state
  Party Y executed confidentiality agreement."

This is the single hard flag that pushed `zep` to `validated`. Austin should
read the relevant filing pages and resolve via rulebook update, reference JSON
edit, or accepting the row as-is.

## AI-vs-Alex comparator

`python -m scoring.diff --all-reference --write` produced one markdown report
per deal under `scoring/results/`. Suppressions and divergences match the
documented behavior in `scoring/diff.py` (DropSilent filtering, formal-stage
enrichment suppression, legacy per-share placement noise). Austin should walk
each report manually; the comparator is a human-review aid, not a gate.

## Reference-set gate status

This is the first run on the new contract. Per CLAUDE.md, the gate requires
three consecutive clean full-reference runs against the same rulebook with
all nine deals manually verified. Today's run is run 1 — no manual
verification yet. None of the deals advanced to `verified`.

## Artifacts

- `output/extractions/{slug}.json` (9 files)
- `output/audit/{slug}/raw_response.json|manifest.json|calls.jsonl|prompts/*` (9 trees)
- `state/progress.json` (updated entries for all 9)
- `state/flags.jsonl` (current-run rows appended)
- `quality_reports/runs/2026-04-29_reference-batch.log`
- `scoring/results/{slug}.md` (9 diff reports)

## Followups

1. Austin to adjudicate zep row 50 hard flag against the filing.
2. Austin to walk the nine `scoring/results/*.md` diffs and apply verdicts
   per `reference/alex/README.md`.
3. After verification, decide whether any rulebook edits are required;
   if any, the reference-stability clock resets per `CLAUDE.md`.
4. No commit was made — outputs are left in the worktree for review.
