# Design — api_call Direct SDK Refactor

**Status:** DRAFT, written from the stalled 2026-04-28 Claude session export.
**Target branch:** `api_call`.
**Created:** 2026-04-28.
**Scope:** replace conversation-orchestrated Extractor / Adjudicator subagents with code-orchestrated direct SDK calls against an OpenAI-compatible backend, currently `https://www.linkflow.run/v1`.

## Goal

Keep the extraction workflow the same, but move the LLM call mechanism into Python:

```
rules/ + prompts/ + filing
  -> direct SDK Extractor call
  -> pipeline.validate()
  -> optional direct SDK Adjudicator calls for soft flags
  -> pipeline.finalize()
  -> output/extractions/{slug}.json + state/progress.json + state/flags.jsonl
```

The rulebook, validator, finalizer, scoring harness, reference JSONs, and Stage 3 gate remain load-bearing. The only conceptual change is replacing "outer conversation spawns a subagent" with "Python coroutine calls an OpenAI-compatible API".

## Prior-Session Decisions

The prior session resolved these design choices before it got stuck:

| Topic | Decision | Implication |
|---|---|---|
| Refactor scope | Minimal swap + concurrency + audit | Keep current extraction architecture; add SDK calls, `--workers`, and persistent audit. |
| Provider abstraction | `LLMClient` ABC + `OpenAICompatibleClient` | One concrete backend now, but call sites are backend-agnostic. |
| Watchdog policy | Warn + bounded retry | Retry transient idle/timeouts/5xx with exponential backoff. |
| Adjudicator model | Separate `--extract-model` / `--adjudicate-model` | Same client, separately configurable models, sequential per deal. |
| Concurrency | `asyncio` | One process, async coroutines, semaphore-gated workers. |
| Prompt construction | System/user split | System = static rules/procedure; user = per-deal filing/manifest. |
| JSON output | Strict JSON schema, repair fallback | Use structured output when supported; retain parse/repair fallback for noncompliant providers. |
| CLI shape | `run.py` for one deal, `pipeline.run_pool` for batches | Single-deal debugging stays easy; batch runner owns concurrency. |
| Resume/cache | Default skip, `--re-validate`, `--re-extract` | Revalidate cached raw responses without paying the LLM again when rulebook hash matches. |
| Audit/budget | Full audit + per-deal token cap | Store prompts, raw response, per-call JSONL, summary manifest, and enforce token budget. |

Austin later clarified that backward compatibility is not needed. Stale subagent/offline-replay interfaces should be hard-deleted, not shimmed.

## Linkflow Probe Findings

The prior session made small real API probes against linkflow with GPT-5.5 high reasoning. Do not copy the key from that transcript into repo files.

Confirmed:

- Linkflow supports the OpenAI Responses API style `text={"format": {"type": "json_schema", "name": "extraction_schema_r1", "schema": SCHEMA_R1, "strict": true}}`.
- Reasoning settings work and usage reports reasoning tokens.
- System/user split works.
- GPT-5 family model names are exposed, including `gpt-5.4` and `gpt-5.5`.

Gotchas:

- Streaming is batched, not token-by-token. A long response arrived as one text delta after a long gap. The watchdog should warn later than the old 30-second default.
- `max_output_tokens` did not behave like a hard cap in the probe. Client-side token budget enforcement is therefore a real safety check.
- Prompt caching is not observable through `cached_tokens`; budget assuming no measurable caching discount.
- The Responses API does not use the older Chat Completions `response_format` parameter. Use `text.format`.

Updated defaults:

| Knob | Default |
|---|---|
| `LLM_HEARTBEAT_SECONDS` | `5` |
| `LLM_STALE_WARNING_SECONDS` | `90` |
| `LLM_STREAM_IDLE_SECONDS` | `120` |
| `LLM_TOTAL_CALL_SECONDS` | `600` |
| `LLM_MAX_ATTEMPTS` | `3` |
| `LLM_BACKOFF_BASE_SECONDS` | `5` |
| `LLM_BACKOFF_FACTOR` | `3` |
| `MAX_TOKENS_PER_DEAL` | `200000` |

## Package Layout

Convert top-level `pipeline.py` into a package. This is a hard break; no top-level compatibility module remains.

```
pipeline/
  __init__.py
  core.py
  llm/
    __init__.py
    client.py
    watchdog.py
    retry.py
    response_format.py
    audit.py
    extract.py
    adjudicate.py
  run_pool.py
```

Responsibilities:

- `pipeline/core.py` contains the current deterministic code from `pipeline.py`: filing loader, validator, pre-finalize transforms, finalizer, state writers, failure recorder, and git-commit helpers that remain shared with `run.py`.
- `pipeline/__init__.py` re-exports the public core API used by existing tests and scripts.
- `pipeline/llm/client.py` defines `LLMClient`, `CompletionResult`, and `OpenAICompatibleClient`.
- `pipeline/llm/watchdog.py` handles heartbeat, stale warnings, stream-idle timeout, and total-call timeout.
- `pipeline/llm/retry.py` classifies transient vs permanent failures and applies bounded exponential backoff.
- `pipeline/llm/response_format.py` owns the §R1 JSON schema, linkflow-compatible structured-output call shape, provider support probe, fenced-JSON parser, and one-shot repair fallback.
- `pipeline/llm/audit.py` writes `output/audit/{slug}/` artifacts and enforces token budgets.
- `pipeline/llm/extract.py` builds `(system, user)` extractor messages and performs one extractor call.
- `pipeline/llm/adjudicate.py` builds scoped soft-flag adjudication prompts and performs sequential adjudicator calls.
- `pipeline/run_pool.py` owns batch selection, skip/cache policy, semaphore-gated asyncio dispatch, and pool summary reporting.

## Hard Deletions

Delete, not deprecate:

- `run.py --raw-extraction <file>`.
- `run.py --print-extractor-prompt`.
- Any prose in `AGENTS.md`, `CLAUDE.md`, and `SKILL.md` saying the live Extractor/Adjudicator are Claude Code subagents.
- `pipeline.build_extractor_prompt(slug)` as a path-only "Read these files" string.
- Top-level `pipeline.py`.

New replacements:

- `run.py --slug X --extract` for a fresh SDK extraction.
- `run.py --slug X --re-validate` to replay cached `output/audit/{slug}/raw_response.json`.
- `run.py --slug X --re-extract` to force a fresh SDK extraction.
- `run.py --slug X --print-prompt` to render the actual SDK system/user messages.
- `pipeline.llm.extract.build_messages(slug) -> tuple[str, str]`.

## Per-Deal Flow

`pipeline.run_pool.process_deal()` is the shared path for both `run.py` and `python -m pipeline.run_pool`.

1. Capture the current `rulebook_version()` once per pool run.
2. Resolve skip/cache policy:
   - default skips statuses `validated`, `passed`, `passed_clean`, and `verified` only when their stored `rulebook_version` equals the current hash;
   - `--re-validate` loads cached `raw_response.json` only when the cache hash matches the current hash;
   - `--re-extract` and `--force` bypass cache and skip checks.
3. Extract:
   - write exact prompt text under `output/audit/{slug}/prompts/extractor.txt`;
   - call `LLMClient.complete()` with the §R1 schema through `text.format`;
   - retry transient errors;
   - parse/repair only if structured output is unavailable or malformed.
4. Validate using `pipeline.core.validate()`.
5. If soft flags exist, adjudicate them sequentially with the adjudicator model. Adjudicator failures leave the flag unannotated and do not fail the deal.
6. Finalize using `pipeline.core.finalize()` on the executor thread pool so the event loop remains responsive.
7. Write the audit manifest and pool outcome.
8. If `--commit`, commit only the current deal's output/state/audit paths.

## Audit Contract

Each deal writes:

```
output/audit/{slug}/
  manifest.json
  raw_response.json
  prompts/
    extractor.txt
    adjudicator_{flag_index}.txt
  calls.jsonl
```

`manifest.json`:

```json
{
  "schema_version": "v1",
  "slug": "medivation",
  "rulebook_version": "sha256",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "models": {"extract": "gpt-5.5", "adjudicate": "gpt-5.5"},
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "total_reasoning_tokens": 0,
  "total_attempts": 0,
  "total_seconds": 0.0,
  "watchdog_warnings": 0,
  "outcome": "passed_clean"
}
```

`raw_response.json`:

```json
{
  "schema_version": "v1",
  "slug": "medivation",
  "rulebook_version": "sha256",
  "model": "gpt-5.5",
  "raw_text": "{\"deal\":{\"auction\":true},\"events\":[]}",
  "parsed_json": {"deal": {}, "events": []}
}
```

`calls.jsonl` one-line shape:

```json
{
  "ts": "ISO8601",
  "phase": "extract",
  "flag_index": null,
  "model": "gpt-5.5",
  "prompt_hash": "sha256",
  "json_schema_used": true,
  "input_tokens": 0,
  "output_tokens": 0,
  "reasoning_tokens": 0,
  "latency_seconds": 0.0,
  "attempts": 1,
  "finish_reason": "stop",
  "watchdog": {"warnings": 0, "max_idle_seconds": 0.0},
  "outcome": "ok",
  "error": null
}
```

## CLI Contracts

Single deal:

```
python run.py --slug medivation --extract
python run.py --slug medivation --re-validate
python run.py --slug medivation --re-extract
python run.py --slug medivation --print-prompt
python run.py --slug medivation --extract --commit
```

Batch:

```
python -m pipeline.run_pool --filter reference --workers 4 --extract-model gpt-5.5 --adjudicate-model gpt-5.5
python -m pipeline.run_pool --slugs medivation,imprivata --workers 2 --re-extract
python -m pipeline.run_pool --filter failed --workers 4
python -m pipeline.run_pool --filter reference --re-validate
```

Common flags:

- `--extract-model NAME`
- `--adjudicate-model NAME`
- `--max-tokens-per-deal N`
- `--commit`
- `--dry-run`

Batch-only flags:

- `--slugs A,B,C`
- `--filter pending|reference|failed|all`
- `--workers N`
- `--force`

`--slugs` and `--filter` are mutually exclusive.

## Environment

Add `python-dotenv` and `openai` to `requirements.txt`.

Add `.env.example`:

```
OPENAI_API_KEY=
OPENAI_BASE_URL=https://www.linkflow.run/v1
EXTRACT_MODEL=gpt-5.5
ADJUDICATE_MODEL=gpt-5.5
LLM_HEARTBEAT_SECONDS=5
LLM_STALE_WARNING_SECONDS=90
LLM_STREAM_IDLE_SECONDS=120
LLM_TOTAL_CALL_SECONDS=600
LLM_MAX_ATTEMPTS=3
LLM_BACKOFF_BASE_SECONDS=5
LLM_BACKOFF_FACTOR=3
MAX_TOKENS_PER_DEAL=200000
```

`.env*` is already gitignored. The implementation must never log `OPENAI_API_KEY`.

## Prompt Contract

Rewrite `prompts/extract.md` from a subagent prompt to an SDK prompt:

- remove "Read these files" instructions;
- state that the filing text and manifest are embedded in the user message;
- state that rules/procedure are embedded in the system message;
- state that when JSON schema is supported, output must be JSON only, no fenced block;
- keep all extraction procedure, non-negotiable constraints, examples, and self-checks;
- keep `rules/invariants.md` validator-facing only.

`build_messages(slug)`:

- system message includes `prompts/extract.md`, `rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`, and `rules/dates.md`;
- user message includes deal slug, `manifest.json`, and page-numbered `pages.json`;
- neither message tells the model it can read local files.

## Testing Strategy

All CI tests mock the provider. Real linkflow calls live in an opt-in smoke script.

New tests:

- `tests/llm/test_client.py`
- `tests/llm/test_watchdog.py`
- `tests/llm/test_retry.py`
- `tests/llm/test_response_format.py`
- `tests/llm/test_audit.py`
- `tests/llm/test_extract.py`
- `tests/llm/test_adjudicate.py`
- `tests/test_run_pool.py`

Rewrite:

- `tests/test_run_cli.py`
- `tests/test_prompt_contract.py`

Preserve:

- `tests/test_invariants.py`
- `tests/test_pipeline_runtime.py`
- `tests/test_diff.py`
- `tests/test_fetch_filings.py`
- `tests/test_reference_converter.py`

Manual smoke:

```
python scripts/smoke_linkflow.py --model gpt-5.5
python run.py --slug medivation --extract --extract-model gpt-5.5 --adjudicate-model gpt-5.5
python scoring/diff.py --slug medivation
```

## Risks

| Risk | Mitigation |
|---|---|
| JSON schema drifts from `rules/schema.md` §R1 | Keep `SCHEMA_R1` in `pipeline/llm/response_format.py`, test required fields and `additionalProperties: false`, update in same commit as schema changes. |
| Async finalize corrupts state | Keep POSIX atomic writes and `fcntl.flock`; add a process-local `threading.Lock` around public state writes because executor threads share a PID. |
| Linkflow batches streaming and trips watchdog warnings | Use 90-second stale warning and 120-second idle timeout. |
| Linkflow does not enforce max output caps | Enforce `TokenBudget.consume()` after every call and fail the deal if cumulative usage exceeds the cap. |
| Prompt caching unobservable | Budget assuming no cache; keep system/user split because it is still the right provider-agnostic prompt shape. |
| Prompt rewrite drops a load-bearing instruction | Rewrite surgically and diff old vs new before running Medivation. |
| Existing scripts/tests import `pipeline` | `pipeline/__init__.py` re-exports the core public API after package conversion. |

## Out of Scope

- Running the 392 target deals.
- Changing event taxonomy or extraction rules.
- Adding section preprocessing / "Background" page slicing.
- Adding cost accounting in USD.
- Native Anthropic SDK support.
- Parallel adjudication inside a single deal.
- Any backward-compatible readers for stale raw-extraction files.
