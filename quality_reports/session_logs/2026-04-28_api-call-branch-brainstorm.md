# Session Log - 2026-04-28 api_call Branch Brainstorm

## Context

User asked to brainstorm a new branch `api_call` that refactors the codebase
from subagent-based orchestration (current `main`) to **code-orchestrated
direct SDK calls with an agent-agnostic backend**, targeting linkflow.run/v1
(OpenAI-compatible third-party API) and including a heartbeat watchdog.

User referenced their previous attempt at
`https://github.com/AustinJunyuLi/bids_pipeline` (branch `cowork`) for prior
art on the watchdog + SDK layer, but explicitly asked to *tailor to this
pipeline* (preserve `rules/`, `pipeline.validate()`, `finalize()`, state
contracts, scoring/diff). Used `superpowers:brainstorming` skill.

## Decisions captured (10 multiple-choice questions)

| # | Topic | Pick | Effect |
|---|---|---|---|
| 1 | Scope | B | Minimal swap + per-deal concurrency + audit log |
| 2 | Provider abstraction | B | `LLMClient` ABC + `OpenAICompatibleClient` (one impl today) |
| 3 | Watchdog action | B | Warn + bounded retry, exponential backoff (5s/15s/45s) |
| 4 | Adjudicator | B | Separate `--extract-model`/`--adjudicate-model`, sequential |
| 5 | Concurrency | C | asyncio (one process, async coroutines, semaphore-gated) |
| 6 | Prompt construction | B | system msg = rules+procedure (cacheable) / user msg = filing |
| 7 | JSON parsing | C | `response_format=json_schema` + repair fallback if linkflow doesn't honor |
| 8 | CLI shape | B | `run.py` (single-deal) + `pipeline/run_pool.py` (batch) |
| 9 | Resume / cache | C | Three-tier: skip-if-rulebook-unchanged / `--re-validate` / `--re-extract` |
| 10 | Audit + budget | B | Full prompts + `calls.jsonl` + `--max-tokens-per-deal` |

## Hard-delete commitments (no backward compat)

- `run.py --raw-extraction <file>` mode + `pipeline.finalize_deal()` shim →
  replaced by `--re-validate` against cached `output/audit/{slug}/raw_response.json`.
- `pipeline.build_extractor_prompt(slug)` returning a single "Read these files"
  string → replaced by `pipeline.llm.extract.build_messages(slug) -> (system, user)`.
- `pipeline.py` at top level → moved to `pipeline/core.py` (package conversion).
- `--print-extractor-prompt` → renamed `--print-prompt`, renders system + user.
- `SKILL.md` / `AGENTS.md` / `CLAUDE.md` subagent-orchestration prose → rewritten.

## Module map (final)

```
pipeline/
├── core.py              # what was pipeline.py (validator, finalize, state, locks)
├── llm/
│   ├── client.py        # LLMClient ABC + OpenAICompatibleClient (AsyncOpenAI)
│   ├── watchdog.py      # APICallWatchdog (async heartbeat)
│   ├── retry.py         # bounded retry + error classification
│   ├── response_format.py # JSON schema for §R1 + linkflow probe + repair fallback
│   ├── audit.py         # output/audit/{slug}/ writers + token budget
│   ├── extract.py       # async extract_deal()
│   └── adjudicate.py    # async adjudicate()
└── run_pool.py          # asyncio dispatcher (CLI: python -m pipeline.run_pool)
```

## Status

- Sections 1–4 of design presented and approved by user.
- Sections 5 (CLI shape, env config, prompt rewrites) and 6 (tests + risks)
  pending presentation.
- Design doc has NOT been written yet (writes to
  `docs/superpowers/specs/2026-04-28-api-call-branch-design.md` after Section 6
  approval).
- Implementation plan NOT created yet (next step after design doc + user review).

## Open questions to resolve in remaining sections

- Final list of CLI flags for `run.py` and `pipeline.run_pool` (Section 5).
- How `prompts/extract.md` gets rewritten for the system/user split (Section 5).
- Test surface — what gets mocked, what gets real-call coverage (Section 6).
- Branch creation step + commit-strategy for the refactor (in plan, not design).
