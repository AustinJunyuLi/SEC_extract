# 2026-04-30 — Reference batch, gpt-5.5 high effort, 5 workers

## Goal

Run all 9 reference deals through the extractor + adjudicator on Linkflow with
`gpt-5.5` and `reasoning_effort=high`, batched with 5 concurrent workers.

## Invocation

```
python -m pipeline.run_pool \
  --filter reference --workers 5 \
  --extract-model gpt-5.5 --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort high --adjudicate-reasoning-effort high
```

API key passed via `OPENAI_API_KEY` env (Linkflow). Base URL from `.env`:
`https://www.linkflow.run/v1`. Logs at
`quality_reports/run_logs/2026-04-30_reference-gpt55-high.log` (mostly empty
due to nohup buffering — per-deal detail lives in audit dirs).

Batch start ~08:57Z, finished ~09:09Z. Total wall time ~12 min for first pass.

## Outcome

| Deal | Status | Flags | Notes |
|---|---|---:|---|
| providence-worcester | passed | 97 | |
| medivation | passed | 21 | |
| imprivata | passed | 23 | First attempt failed with `MalformedJSONError: Extra data: line 1 column 43230` (Linkflow prompt-only mode trailing content). Single retry passed. |
| zep | **validated** | 92 | Hard flags — review needed. |
| petsmart-inc | **validated** | 58 | Hard flags — review needed. |
| penford | passed | 26 | |
| mac-gray | passed | 57 | |
| saks | passed | 36 | |
| stec | passed | 27 | |

**Totals:** 7 passed, 2 validated, 0 failed (after one retry). 437 flags
across all deals.

## Pool log summary

`Pool summary: selected=9 succeeded=6 skipped=0 failed=1` — `succeeded` only
counts `passed` deals; `validated` deals are not counted as "succeeded" by the
runner's summary line. The `failed=1` was imprivata's first attempt before
retry.

## Open questions / next steps

- `zep` and `petsmart-inc` returned `validated` — need to inspect hard flags
  via `state/flags.jsonl` filtered on each deal's `last_run_id` to decide
  rulebook updates vs. extraction fixes.
- Imprivata's malformed-JSON failure on Linkflow prompt-only mode is a known
  fragility on long responses. One-off this run; if it recurs, may warrant a
  post-hoc JSON repair step in `pipeline/llm/`.
- Stability proof not yet generated. For target-gate release we need 3
  consecutive unchanged-rulebook stable runs per slug. This was 1 run.
- Reference comparison via `scoring/diff.py` against `reference/alex/` not run
  this session.

## Audit pointers

Latest run IDs:
- providence-worcester: `8090646b605c41aca568280e712b4995`
- medivation: `0c3c9b7306424fe7abc9e5db767d6de5`
- imprivata: `b6e5ebb372b84f47830e06515c53077c` (retry; first failed run was
  `cb689cdb77db46b4b429a03b23d2c65a`)
- zep: `eda9c32276c04e9281c3caf89db46af0`
- petsmart-inc: `244f76aeb141438f8a6b6f0c34815c88`
- penford: `f1409c20e19d4ae695c1c0cafcd842fa`
- mac-gray: `7f280b6542ea4bed97e07758c8d5d8c7`
- saks: `d085615f2312424ca22601d6556ae5d7`
- stec: `a2852aba...`

Full per-deal audit at `output/audit/{slug}/runs/{run_id}/`.

## Security note

API key was pasted in chat by the user and used via env var (never written to
disk). Recommend rotation since the key now lives in chat history.
