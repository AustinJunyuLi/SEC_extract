# Session Log — 2026-04-29: Switch to api-call branch

## Goal

Continue SEC_extract development on the `api-call` branch instead of `main`.

## Key Context

- `git pull` revealed two new remote branches: `origin/api-call` and `origin/subagent`.
- `origin/subagent` is 8 commits ahead of `main` (field-scope tightening, deferred-fields spec, schema/skeleton trimming, refactor-plan doc).
- `origin/api-call` is 38 commits ahead of `main`, on a separate line of history from `subagent`. Highlights:
  - Pipeline converted to a package; direct `AsyncOpenAI` SDK orchestration via Linkflow/NewAPI-compatible `OPENAI_BASE_URL` (Responses streaming endpoint, prompt-only JSON).
  - `pipeline.run_pool` batch runner; `xhigh` reasoning-effort default with `LINKFLOW_XHIGH_MAX_WORKERS=5` ceiling.
  - DropSilent classification, buyer-group consortium doctrine, validator boundary polish, anonymous-cohort tightening.
  - Removed compatibility shims; rulebook contract refactor spec preserved.
- User decision: `main` can be wiped out; develop on `api-call`.
- Working tree was clean before checkout. Local branch `api-call` is now tracking `origin/api-call`.

## Status

Branch switched. No code changes this session.

## Open Questions / Next Steps

- None pending. Awaiting next instruction from Austin.
