# api_call Direct SDK Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the pipeline onto the `api_call` branch so Extractor and Adjudicator LLM calls are made by Python through an OpenAI-compatible SDK backend with watchdogs, retries, audit artifacts, cache-aware reruns, and asyncio batch dispatch.

**Architecture:** Convert `pipeline.py` into a package, preserving deterministic validator/finalizer code in `pipeline/core.py` while adding a new `pipeline/llm/` subsystem for provider calls. `run.py` becomes a single-deal wrapper around the same `process_deal()` path used by `python -m pipeline.run_pool`, with no backward-compatible `--raw-extraction` mode.

**Tech Stack:** Python 3, `openai.AsyncOpenAI`, `httpx`, `python-dotenv`, `pytest`, existing JSON/state files.

---

## File Map

- Create `pipeline/__init__.py`: public re-exports from `pipeline.core`.
- Create `pipeline/core.py`: current deterministic contents of `pipeline.py`, plus a process-local lock for state writes.
- Delete `pipeline.py`: hard package conversion.
- Create `pipeline/llm/__init__.py`: LLM subsystem exports.
- Create `pipeline/llm/client.py`: `CompletionResult`, `LLMClient`, `OpenAICompatibleClient`.
- Create `pipeline/llm/watchdog.py`: watchdog config and async heartbeat/timeout state.
- Create `pipeline/llm/retry.py`: retry config, retryable/non-retryable classification, retry wrapper.
- Create `pipeline/llm/response_format.py`: §R1 JSON schema, structured-output helper, fenced JSON parser, repair fallback, provider probe.
- Create `pipeline/llm/audit.py`: `TokenBudget`, `AuditWriter`, audit paths.
- Create `pipeline/llm/extract.py`: `build_messages()` and `extract_deal()`.
- Create `pipeline/llm/adjudicate.py`: scoped adjudicator prompt builder and sequential adjudicator runner.
- Create `pipeline/run_pool.py`: batch CLI, selection, skip/cache policy, `process_deal()`.
- Modify `run.py`: replace raw-extraction finalizer CLI with SDK single-deal CLI.
- Modify `prompts/extract.md`: remove subagent file-read language; make it SDK-message-compatible.
- Modify `SKILL.md`, `AGENTS.md`, `CLAUDE.md`: update architecture prose.
- Modify `requirements.txt`: add `openai`, `httpx`, `python-dotenv`.
- Create `.env.example`: backend/model/watchdog/retry/token-budget template.
- Create `scripts/smoke_linkflow.py`: opt-in real API smoke probe.
- Create tests under `tests/llm/` and update existing CLI/prompt tests.

## Task 1: Create Branch And Baseline

**Files:**
- No code changes.

- [ ] **Step 1: Create and switch to the feature branch**

Run:

```bash
git switch -c api_call
```

Expected: branch `api_call` is active.

- [ ] **Step 2: Check for unrelated local changes**

Run:

```bash
git status --short
```

Expected: only the design/plan/session-log docs are untracked or modified. If user changes exist, leave them untouched and continue with isolated edits.

- [ ] **Step 3: Run baseline tests**

Run:

```bash
python -m pytest -x
```

Expected: current suite passes before refactor begins.

- [ ] **Step 4: Commit planning docs if desired by Austin**

Run only if Austin wants the docs committed before implementation:

```bash
git add quality_reports/specs/2026-04-28-api-call-branch-design.md quality_reports/plans/2026-04-28-api-call-branch-implementation.md quality_reports/session_logs/2026-04-28_api-call-branch-brainstorm.md
git commit -m "docs: plan api_call direct sdk refactor"
```

Expected: one docs-only commit.

## Task 2: Convert `pipeline.py` To A Package

**Files:**
- Create: `pipeline/core.py`
- Create: `pipeline/__init__.py`
- Delete: `pipeline.py`
- Test: existing suite plus import smoke.

- [ ] **Step 1: Move current deterministic code**

Run:

```bash
mkdir -p pipeline
git mv pipeline.py pipeline/core.py
```

Expected: `pipeline/core.py` contains the old `pipeline.py` content.

- [ ] **Step 2: Add package re-exports**

Create `pipeline/__init__.py`:

```python
"""Public API for the M&A extraction pipeline package."""

from .core import *  # noqa: F401,F403
```

- [ ] **Step 3: Add a process-local state lock in `pipeline/core.py`**

Near imports, add:

```python
import threading
```

Near `PROGRESS_LOCK_PATH`, add:

```python
_PROCESS_STATE_LOCK = threading.Lock()
```

Change `_state_file_lock()` body to wrap the file lock:

```python
@contextlib.contextmanager
def _state_file_lock() -> Iterator[None]:
    """Advisory exclusive lock for state-file mutations."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _PROCESS_STATE_LOCK:
        fd = os.open(PROGRESS_LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
```

This avoids same-PID executor threads deadlocking on nested `flock` attempts.

- [ ] **Step 4: Verify imports**

Run:

```bash
python - <<'PY'
import pipeline
print(pipeline.rulebook_version()[:8])
print(pipeline.load_filing)
PY
```

Expected: prints an 8-character hash prefix and a function object.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest -x
```

Expected: tests pass or failures are import-path-specific and fixed before continuing.

- [ ] **Step 6: Commit package conversion**

Run:

```bash
git add pipeline
git add -u pipeline.py
git commit -m "refactor: convert pipeline module to package"
```

Expected: package conversion commit.

## Task 3: Add Dependencies And Environment Template

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Update requirements**

Append:

```text
openai>=2.31.0
httpx>=0.28.0
python-dotenv>=1.2.0
```

- [ ] **Step 2: Add `.env.example`**

Create:

```dotenv
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

- [ ] **Step 3: Verify `.env` stays ignored**

Run:

```bash
git check-ignore .env .env.local
```

Expected: both paths print as ignored.

- [ ] **Step 4: Commit dependency/env template**

Run:

```bash
git add requirements.txt .env.example
git commit -m "chore: add OpenAI-compatible SDK dependencies"
```

Expected: dependency commit.

## Task 4: Implement Watchdog And Retry Primitives

**Files:**
- Create: `pipeline/llm/__init__.py`
- Create: `pipeline/llm/watchdog.py`
- Create: `pipeline/llm/retry.py`
- Test: `tests/llm/test_watchdog.py`, `tests/llm/test_retry.py`

- [ ] **Step 1: Create LLM package init**

Create `pipeline/llm/__init__.py`:

```python
"""LLM SDK orchestration helpers for the extraction pipeline."""
```

- [ ] **Step 2: Add watchdog**

Create `pipeline/llm/watchdog.py`:

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WatchdogConfig:
    heartbeat_seconds: float = 5.0
    stale_warning_seconds: float = 90.0
    stream_idle_seconds: float = 120.0
    total_call_seconds: float = 600.0


@dataclass
class WatchdogStats:
    warnings: int = 0
    max_idle_seconds: float = 0.0
    events: list[dict] = field(default_factory=list)


class APICallWatchdog:
    def __init__(self, *, label: str, cfg: WatchdogConfig):
        self.label = label
        self.cfg = cfg
        self.owner_task: asyncio.Task | None = None
        self.timeout_error: asyncio.TimeoutError | None = None
        self.started_at = time.monotonic()
        self.last_activity_at = self.started_at
        self.stats = WatchdogStats()
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def __aenter__(self) -> "APICallWatchdog":
        self.owner_task = asyncio.current_task()
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.timeout_error is not None and exc_type is asyncio.CancelledError:
            raise self.timeout_error

    def mark_activity(self, *, chars: int = 0, phase: str = "stream") -> None:
        now = time.monotonic()
        idle = now - self.last_activity_at
        self.stats.max_idle_seconds = max(self.stats.max_idle_seconds, idle)
        self.last_activity_at = now
        self.stats.events.append({"phase": phase, "chars": chars, "t": now - self.started_at})

    async def _run(self) -> None:
        while not self._stopped.is_set():
            await asyncio.sleep(self.cfg.heartbeat_seconds)
            now = time.monotonic()
            elapsed = now - self.started_at
            idle = now - self.last_activity_at
            self.stats.max_idle_seconds = max(self.stats.max_idle_seconds, idle)
            if elapsed > self.cfg.total_call_seconds:
                self._timeout(f"{self.label}: total_call timeout after {elapsed:.1f}s")
                return
            if idle > self.cfg.stream_idle_seconds:
                self._timeout(f"{self.label}: stream idle timeout after {idle:.1f}s")
                return
            if idle > self.cfg.stale_warning_seconds:
                self.stats.warnings += 1
                print(f"WARN: {self.label} elapsed={elapsed:.1f}s idle={idle:.1f}s")
            else:
                print(f"HEARTBEAT: {self.label} elapsed={elapsed:.1f}s idle={idle:.1f}s")

    def _timeout(self, message: str) -> None:
        self.timeout_error = asyncio.TimeoutError(message)
        if self.owner_task is not None:
            self.owner_task.cancel()
```

- [ ] **Step 3: Add retry helper**

Create `pipeline/llm/retry.py`:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

import httpx
import openai

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    backoff_base_seconds: float = 5.0
    backoff_factor: float = 3.0
    backoff_cap_seconds: float = 60.0


class RetryExhaustedError(RuntimeError):
    pass


RETRYABLE_EXCEPTIONS = (
    asyncio.TimeoutError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

NON_RETRYABLE_EXCEPTIONS = (
    openai.AuthenticationError,
    openai.BadRequestError,
    openai.PermissionDeniedError,
)


def retry_delay(attempt_index: int, cfg: RetryConfig) -> float:
    return min(cfg.backoff_cap_seconds, cfg.backoff_base_seconds * (cfg.backoff_factor ** attempt_index))


async def with_retry(factory: Callable[[int], Awaitable[T]], cfg: RetryConfig) -> tuple[T, int]:
    last_error: BaseException | None = None
    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await factory(attempt), attempt
        except NON_RETRYABLE_EXCEPTIONS:
            raise
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            if attempt == cfg.max_attempts:
                break
            await asyncio.sleep(retry_delay(attempt - 1, cfg))
    raise RetryExhaustedError(f"retry exhausted after {cfg.max_attempts} attempts: {last_error}") from last_error
```

- [ ] **Step 4: Write focused tests**

Create tests that monkeypatch `asyncio.sleep` to avoid real waits:

```python
async def instant_sleep(_seconds):
    return None
```

Cover:

- `retry_delay(0..2)` returns `5, 15, 45`.
- retryable error succeeds on second attempt.
- non-retryable error raises immediately.
- exhausted retry raises `RetryExhaustedError`.
- watchdog records activity and warning counts under controlled timing.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/llm/test_retry.py tests/llm/test_watchdog.py -q
```

Expected: new primitive tests pass.

- [ ] **Step 6: Commit primitives**

Run:

```bash
git add pipeline/llm tests/llm
git commit -m "feat: add async watchdog and retry primitives"
```

Expected: primitives commit.

## Task 5: Implement LLM Client And Response Formatting

**Files:**
- Create: `pipeline/llm/client.py`
- Create: `pipeline/llm/response_format.py`
- Test: `tests/llm/test_client.py`, `tests/llm/test_response_format.py`

- [ ] **Step 1: Add client interfaces**

Create `pipeline/llm/client.py` with:

```python
from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from .retry import RetryConfig, with_retry
from .watchdog import APICallWatchdog, WatchdogConfig, WatchdogStats


@dataclass
class CompletionResult:
    text: str
    parsed_json: dict | None
    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_seconds: float
    attempts: int
    finish_reason: str | None
    watchdog: WatchdogStats


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        text_format: dict | None = None,
        max_output_tokens: int = 32000,
    ) -> CompletionResult:
        raise NotImplementedError


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        watchdog_cfg: WatchdogConfig | None = None,
        retry_cfg: RetryConfig | None = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.watchdog_cfg = watchdog_cfg or WatchdogConfig()
        self.retry_cfg = retry_cfg or RetryConfig()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        text_format: dict | None = None,
        max_output_tokens: int = 32000,
    ) -> CompletionResult:
        async def attempt_once(attempt: int) -> CompletionResult:
            started = time.monotonic()
            text = ""
            async with APICallWatchdog(label=f"{model} attempt {attempt}", cfg=self.watchdog_cfg) as wd:
                request = {
                    "model": model,
                    "input": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_output_tokens": max_output_tokens,
                }
                if text_format is not None:
                    request["text"] = {"format": text_format}
                stream = self.client.responses.stream(**request)
                async with stream as events:
                    async for event in events:
                        wd.mark_activity(chars=len(getattr(event, "delta", "") or ""), phase=getattr(event, "type", "event"))
                        if getattr(event, "type", None) == "response.output_text.delta":
                            text += event.delta or ""
                    final = await events.get_final_response()
            usage = getattr(final, "usage", None)
            output_details = getattr(usage, "output_tokens_details", None) if usage else None
            return CompletionResult(
                text=text or getattr(final, "output_text", "") or "",
                parsed_json=None,
                model=model,
                input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                reasoning_tokens=getattr(output_details, "reasoning_tokens", 0) if output_details else 0,
                latency_seconds=time.monotonic() - started,
                attempts=attempt,
                finish_reason=getattr(final, "finish_reason", None),
                watchdog=wd.stats,
            )

        result, attempts = await with_retry(attempt_once, self.retry_cfg)
        result.attempts = attempts
        return result
```

Adjust exact stream handling if the SDK version differs; keep the public `complete()` contract stable.

- [ ] **Step 2: Add response-format helpers**

Create `pipeline/llm/response_format.py` with:

```python
from __future__ import annotations

import json
import re
from typing import Any

from openai import BadRequestError

from .client import CompletionResult, LLMClient


class MalformedJSONError(ValueError):
    pass


SCHEMA_R1: dict[str, Any] = {
    "type": "object",
    "properties": {
        "deal": {"type": "object", "additionalProperties": True},
        "events": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
    },
    "required": ["deal", "events"],
    "additionalProperties": False,
}


def json_schema_format(schema: dict[str, Any] = SCHEMA_R1) -> dict[str, Any]:
    return {"type": "json_schema", "name": "extraction_schema_r1", "schema": schema, "strict": True}


def parse_json_text(text: str) -> dict:
    stripped = text.strip()
    match = re.search(r"```json\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if match:
        stripped = match.group(1)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise MalformedJSONError(str(exc)) from exc
    if not isinstance(parsed, dict) or "deal" not in parsed or "events" not in parsed:
        raise MalformedJSONError("expected object with deal and events")
    return parsed


async def supports_json_schema(client: LLMClient, *, model: str) -> bool:
    try:
        result = await client.complete(
            system="Return JSON only.",
            user="Return {\"ok\": true}.",
            model=model,
            text_format={
                "type": "json_schema",
                "name": "probe",
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            max_output_tokens=100,
        )
        parse_json_text(result.text)
        return True
    except BadRequestError as exc:
        msg = str(exc).lower()
        if "json_schema" in msg or "text" in msg or "format" in msg:
            return False
        raise


async def call_json(
    client: LLMClient,
    *,
    system: str,
    user: str,
    model: str,
    schema_supported: bool,
    schema: dict[str, Any] = SCHEMA_R1,
    max_output_tokens: int = 32000,
) -> CompletionResult:
    result = await client.complete(
        system=system,
        user=user,
        model=model,
        text_format=json_schema_format(schema) if schema_supported else None,
        max_output_tokens=max_output_tokens,
    )
    try:
        result.parsed_json = parse_json_text(result.text)
        return result
    except MalformedJSONError as first_error:
        repair = await client.complete(
            system="You repair malformed JSON. Output JSON only.",
            user=f"Parser error: {first_error}\n\nOriginal response:\n{result.text}\n\nRe-emit valid JSON only.",
            model=model,
            text_format=json_schema_format(schema) if schema_supported else None,
            max_output_tokens=max_output_tokens,
        )
        repair.parsed_json = parse_json_text(repair.text)
        repair.attempts += result.attempts
        return repair
```

Start with a permissive `SCHEMA_R1` to land the pipeline; tighten to full §R1 in Task 11.

- [ ] **Step 3: Write tests with stub clients**

Use a stub `LLMClient` returning canned `CompletionResult`. Test:

- fenced JSON parsing;
- malformed JSON repair path;
- schema-supported calls pass `text_format`;
- schema-unsupported calls pass `None`;
- `supports_json_schema()` returns true on valid probe and false on schema `BadRequestError`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/llm/test_client.py tests/llm/test_response_format.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit client/formatting**

Run:

```bash
git add pipeline/llm tests/llm
git commit -m "feat: add OpenAI-compatible LLM client"
```

Expected: client commit.

## Task 6: Implement Audit And Token Budget

**Files:**
- Create: `pipeline/llm/audit.py`
- Test: `tests/llm/test_audit.py`

- [ ] **Step 1: Add audit writer**

Create `pipeline/llm/audit.py`:

```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.core import _atomic_write_text, _now_iso

from .client import CompletionResult


class TokenBudgetExceeded(RuntimeError):
    pass


@dataclass
class TokenBudget:
    max_tokens: int
    input_used: int = 0
    output_used: int = 0

    def consume(self, result: CompletionResult) -> None:
        self.input_used += result.input_tokens
        self.output_used += result.output_tokens
        if self.input_used + self.output_used > self.max_tokens:
            raise TokenBudgetExceeded(
                f"token_budget_exceeded: used={self.input_used + self.output_used} cap={self.max_tokens}"
            )


def prompt_hash(system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\n---\n")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


class AuditWriter:
    def __init__(self, root: Path, slug: str):
        self.root = root
        self.slug = slug
        self.prompts_dir = root / "prompts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = _now_iso()

    def write_prompt(self, *, phase: str, system: str, user: str, flag_index: int | None = None) -> str:
        suffix = phase if flag_index is None else f"{phase}_{flag_index}"
        path = self.prompts_dir / f"{suffix}.txt"
        text = f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n"
        _atomic_write_text(path, text)
        return prompt_hash(system, user)

    def append_call(self, entry: dict) -> None:
        path = self.root / "calls.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=False) + "\n")

    def write_raw_response(self, *, result: CompletionResult, parsed_json: dict, rulebook_version: str) -> None:
        payload = {
            "schema_version": "v1",
            "slug": self.slug,
            "rulebook_version": rulebook_version,
            "model": result.model,
            "raw_text": result.text,
            "parsed_json": parsed_json,
        }
        _atomic_write_text(self.root / "raw_response.json", json.dumps(payload, indent=2) + "\n")

    def write_manifest(self, payload: dict) -> None:
        base = {"schema_version": "v1", "slug": self.slug, "started_at": self.started_at, "finished_at": _now_iso()}
        base.update(payload)
        _atomic_write_text(self.root / "manifest.json", json.dumps(base, indent=2) + "\n")
```

- [ ] **Step 2: Test audit artifacts**

Test:

- prompts write exact system/user text;
- `calls.jsonl` appends two valid JSON lines;
- `raw_response.json` stores `parsed_json` and rulebook hash;
- `TokenBudget.consume()` raises when cumulative total exceeds cap.

- [ ] **Step 3: Run tests**

Run:

```bash
python -m pytest tests/llm/test_audit.py -q
```

Expected: audit tests pass.

- [ ] **Step 4: Commit audit layer**

Run:

```bash
git add pipeline/llm/audit.py tests/llm/test_audit.py
git commit -m "feat: add per-deal LLM audit artifacts"
```

Expected: audit commit.

## Task 7: Implement Extractor Message Builder And Call

**Files:**
- Create: `pipeline/llm/extract.py`
- Modify: `prompts/extract.md`
- Test: `tests/llm/test_extract.py`, `tests/test_prompt_contract.py`

- [ ] **Step 1: Rewrite prompt introduction**

In `prompts/extract.md`, replace the subagent-specific intro and "Context you will be given" section with:

```markdown
You are the Extractor in an M&A auction extraction pipeline. Your output is a
single JSON object conforming to `rules/schema.md` §R1. The SDK call may enforce
the JSON schema directly; when it does, return JSON only, with no fenced block
and no prose.

## Context embedded in this SDK call

- The system message contains this prompt and the full contents of
  `rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`,
  and `rules/dates.md`.
- The user message contains the deal slug, `manifest.json`, and page-numbered
  filing text from `pages.json`.
- `rules/invariants.md` remains validator-facing only.

The filing text embedded in the user message is the sole extraction source.
Do not fetch from SEC/EDGAR, browse the web, or assume local file access.
```

Keep procedure, constraints, output skeleton, and self-checks.

- [ ] **Step 2: Add `build_messages()`**

Create `pipeline/llm/extract.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline import core

from .audit import AuditWriter, TokenBudget
from .client import CompletionResult, LLMClient
from .response_format import SCHEMA_R1, call_json


EXTRACTOR_RULE_FILES = ("schema.md", "events.md", "bidders.md", "bids.md", "dates.md")


@dataclass
class ExtractResult:
    raw_extraction: dict
    completion: CompletionResult
    rulebook_version: str


def build_messages(slug: str) -> tuple[str, str]:
    prompt = (core.PROMPTS_DIR / "extract.md").read_text()
    rule_chunks = []
    for name in EXTRACTOR_RULE_FILES:
        path = core.RULES_DIR / name
        rule_chunks.append(f"\n\n# {path.name}\n\n{path.read_text()}")
    manifest = json.loads((core.DATA_DIR / slug / "manifest.json").read_text())
    pages = json.loads((core.DATA_DIR / slug / "pages.json").read_text())
    system = prompt + "\n\n" + "\n".join(rule_chunks)
    user = json.dumps({"slug": slug, "manifest": manifest, "pages": pages}, indent=2)
    return system, user


async def extract_deal(
    slug: str,
    *,
    llm_client: LLMClient,
    extract_model: str,
    audit: AuditWriter,
    token_budget: TokenBudget,
    rulebook_version: str,
    schema_supported: bool,
    max_output_tokens: int = 32000,
) -> ExtractResult:
    system, user = build_messages(slug)
    phash = audit.write_prompt(phase="extractor", system=system, user=user)
    completion = await call_json(
        llm_client,
        system=system,
        user=user,
        model=extract_model,
        schema_supported=schema_supported,
        schema=SCHEMA_R1,
        max_output_tokens=max_output_tokens,
    )
    token_budget.consume(completion)
    parsed = completion.parsed_json or {}
    audit.write_raw_response(result=completion, parsed_json=parsed, rulebook_version=rulebook_version)
    audit.append_call({
        "ts": core._now_iso(),
        "phase": "extract",
        "flag_index": None,
        "model": completion.model,
        "prompt_hash": phash,
        "json_schema_used": schema_supported,
        "input_tokens": completion.input_tokens,
        "output_tokens": completion.output_tokens,
        "reasoning_tokens": completion.reasoning_tokens,
        "latency_seconds": completion.latency_seconds,
        "attempts": completion.attempts,
        "finish_reason": completion.finish_reason,
        "watchdog": {
            "warnings": completion.watchdog.warnings,
            "max_idle_seconds": completion.watchdog.max_idle_seconds,
        },
        "outcome": "ok",
        "error": None,
    })
    return ExtractResult(raw_extraction=parsed, completion=completion, rulebook_version=rulebook_version)
```

- [ ] **Step 3: Update prompt contract tests**

Replace assertions for `"Read these files"` with assertions that:

- `build_messages("medivation")` returns two strings;
- system contains `rules/schema.md` content and `prompts/extract.md`;
- user contains `"slug": "medivation"` and `"pages"`;
- no system/user text claims the model has a Read tool.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/llm/test_extract.py tests/test_prompt_contract.py -q
```

Expected: prompt/extract tests pass.

- [ ] **Step 5: Commit extractor path**

Run:

```bash
git add pipeline/llm/extract.py prompts/extract.md tests/llm/test_extract.py tests/test_prompt_contract.py
git commit -m "feat: build SDK extractor prompt and call path"
```

Expected: extractor commit.

## Task 8: Implement Adjudicator SDK Path

**Files:**
- Create: `pipeline/llm/adjudicate.py`
- Test: `tests/llm/test_adjudicate.py`

- [ ] **Step 1: Add adjudicator module**

Create:

```python
from __future__ import annotations

import json

from pipeline import core

from .audit import AuditWriter, TokenBudget
from .client import LLMClient
from .response_format import call_json

ADJUDICATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["upheld", "dismissed"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


def build_adjudicator_messages(slug: str, raw_extraction: dict, soft_flag: dict, filing: core.Filing) -> tuple[str, str]:
    system = (
        "You are the scoped Adjudicator for soft validator flags in an M&A extraction. "
        "Return JSON only: {\"verdict\":\"upheld|dismissed\",\"reason\":\"short rationale\"}. "
        "Do not rewrite the extraction."
    )
    source_page = soft_flag.get("source_page") or soft_flag.get("row", {}).get("source_page")
    pages = []
    if isinstance(source_page, int):
        for page in filing.pages:
            if abs(page.get("number", -999) - source_page) <= 1:
                pages.append(page)
    user = json.dumps({
        "slug": slug,
        "soft_flag": soft_flag,
        "events": raw_extraction.get("events", []),
        "filing_pages": pages,
    }, indent=2)
    return system, user


async def adjudicate(
    slug: str,
    raw_extraction: dict,
    soft_flags: list[dict],
    filing: core.Filing,
    *,
    llm_client: LLMClient,
    adjudicate_model: str,
    audit: AuditWriter,
    token_budget: TokenBudget,
    schema_supported: bool,
) -> list[dict]:
    annotated = []
    for index, flag in enumerate(soft_flags):
        system, user = build_adjudicator_messages(slug, raw_extraction, flag, filing)
        phash = audit.write_prompt(phase="adjudicator", flag_index=index, system=system, user=user)
        try:
            completion = await call_json(
                llm_client,
                system=system,
                user=user,
                model=adjudicate_model,
                schema_supported=schema_supported,
                schema=ADJUDICATOR_SCHEMA,
                max_output_tokens=1000,
            )
            token_budget.consume(completion)
            verdict = completion.parsed_json or {}
            flag["reason"] = f"{flag.get('reason', '')} | adjudicator={verdict.get('verdict')}: {verdict.get('reason')}"
            audit.append_call({
                "ts": core._now_iso(),
                "phase": "adjudicate",
                "flag_index": index,
                "model": completion.model,
                "prompt_hash": phash,
                "json_schema_used": schema_supported,
                "input_tokens": completion.input_tokens,
                "output_tokens": completion.output_tokens,
                "reasoning_tokens": completion.reasoning_tokens,
                "latency_seconds": completion.latency_seconds,
                "attempts": completion.attempts,
                "finish_reason": completion.finish_reason,
                "watchdog": {
                    "warnings": completion.watchdog.warnings,
                    "max_idle_seconds": completion.watchdog.max_idle_seconds,
                },
                "outcome": "ok",
                "error": None,
            })
        except Exception as exc:
            flag["reason"] = f"{flag.get('reason', '')} | adjudicator_unavailable: {type(exc).__name__}"
            audit.append_call({
                "ts": core._now_iso(),
                "phase": "adjudicate",
                "flag_index": index,
                "model": adjudicate_model,
                "prompt_hash": phash,
                "json_schema_used": schema_supported,
                "outcome": "failed",
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
            })
        annotated.append(flag)
    return annotated
```

- [ ] **Step 2: Test sequential behavior**

Test:

- two soft flags produce two LLM calls in order;
- failure on first flag still processes second flag;
- failed flag reason contains `adjudicator_unavailable`;
- token budget is consumed per successful call.

- [ ] **Step 3: Run tests**

Run:

```bash
python -m pytest tests/llm/test_adjudicate.py -q
```

Expected: adjudicator tests pass.

- [ ] **Step 4: Commit adjudicator**

Run:

```bash
git add pipeline/llm/adjudicate.py tests/llm/test_adjudicate.py
git commit -m "feat: add scoped SDK adjudicator"
```

Expected: adjudicator commit.

## Task 9: Implement `pipeline.run_pool`

**Files:**
- Create: `pipeline/run_pool.py`
- Test: `tests/test_run_pool.py`

- [ ] **Step 1: Add config and skip decision**

Create `pipeline/run_pool.py` with `PoolConfig`, `DealOutcome`, `resolve_selection()`, and `decide_skip()`.

Key skip logic:

```python
DONE_STATUSES = {"validated", "passed", "passed_clean", "verified"}

def decide_skip(slug: str, cfg: PoolConfig, current_rulebook_version: str) -> SkipDecision:
    if cfg.rerun_mode in {"force", "re_extract"}:
        return SkipDecision("run", "forced fresh extraction")
    if cfg.rerun_mode == "re_validate":
        cache_path = cfg.audit_root / slug / "raw_response.json"
        if not cache_path.exists():
            return SkipDecision("run", "no cache for re-validate")
        cache = json.loads(cache_path.read_text())
        if cache.get("rulebook_version") != current_rulebook_version:
            return SkipDecision("run", "cache rulebook_version stale")
        return SkipDecision("re_validate", "valid cached raw_response.json")
    state = json.loads(core.PROGRESS_PATH.read_text())
    deal = state["deals"].get(slug, {})
    if deal.get("status") in DONE_STATUSES and deal.get("rulebook_version") == current_rulebook_version:
        return SkipDecision("skip", f"status={deal.get('status')} rulebook unchanged")
    return SkipDecision("run", "pending, failed, or stale rulebook")
```

- [ ] **Step 2: Add `process_deal()`**

Implement the shared per-deal coroutine:

- load cached raw on `re_validate`;
- otherwise call `extract_deal()`;
- run `core.load_filing`, `core.validate`, and `core.finalize` through `loop.run_in_executor`;
- adjudicate soft flags before finalize;
- record known failures via `core.mark_failed`;
- write audit manifest with final outcome.

- [ ] **Step 3: Add dispatcher**

Implement:

```python
async def run_pool(cfg: PoolConfig) -> PoolSummary:
    current = core.rulebook_version()
    client = OpenAICompatibleClient(api_key=cfg.api_key, base_url=cfg.base_url, watchdog_cfg=cfg.watchdog_cfg, retry_cfg=cfg.retry_cfg)
    schema_supported = await supports_json_schema(client, model=cfg.extract_model)
    plan = [(slug, decide_skip(slug, cfg, current)) for slug in cfg.slugs]
    if cfg.dry_run:
        print_plan(plan)
        return PoolSummary.from_outcomes(plan, [])
    sem = asyncio.Semaphore(cfg.workers)
    async def gated(slug, decision):
        async with sem:
            return await process_deal(slug, skip_decision=decision, config=cfg, llm_client=client, schema_supported=schema_supported, rulebook_version=current)
    outcomes = await asyncio.gather(*(gated(slug, dec) for slug, dec in plan), return_exceptions=True)
    return PoolSummary.from_outcomes(plan, outcomes)
```

- [ ] **Step 4: Add CLI parser**

Support:

```text
--slugs A,B,C
--filter pending|reference|failed|all
--workers N
--extract-model NAME
--adjudicate-model NAME
--max-tokens-per-deal N
--re-validate
--re-extract
--force
--commit
--dry-run
```

Read `.env` using `load_dotenv()` and require `OPENAI_API_KEY` unless `--dry-run`.

- [ ] **Step 5: Test run-pool behavior**

Test:

- skip decisions for done/current, failed, stale rulebook, `--re-validate`, and `--re-extract`;
- semaphore limits concurrency with a stub `process_deal`;
- one exception appears in summary without cancelling other deals;
- dry run makes no LLM calls.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_run_pool.py -q
```

Expected: run-pool tests pass.

- [ ] **Step 7: Commit run pool**

Run:

```bash
git add pipeline/run_pool.py tests/test_run_pool.py
git commit -m "feat: add asyncio deal pool runner"
```

Expected: run-pool commit.

## Task 10: Replace `run.py`

**Files:**
- Modify: `run.py`
- Test: `tests/test_run_cli.py`

- [ ] **Step 1: Delete old raw-extraction CLI flow**

Replace `run.py` with a single-deal wrapper around `pipeline.run_pool.process_deal()`. Preserve `commit_deal_outputs()` either by moving it to `pipeline/core.py` or keeping it in `run.py` and importing it from `run_pool.py`.

CLI modes:

```text
--slug NAME
--extract
--re-validate
--re-extract
--print-prompt
--commit
--extract-model NAME
--adjudicate-model NAME
--max-tokens-per-deal N
--dry-run
```

- [ ] **Step 2: Implement `--print-prompt`**

Use:

```python
from pipeline.llm.extract import build_messages

system, user = build_messages(args.slug)
print("=== SYSTEM ===")
print(system)
print("=== USER ===")
print(user)
```

- [ ] **Step 3: Implement one-deal run**

Build a `PoolConfig` with `slugs=[args.slug]`, `workers=1`, and mode from args. Call `asyncio.run(run_one_deal(args.slug, cfg))` through a helper that shares the same schema probe and client setup as the batch runner.

- [ ] **Step 4: Rewrite CLI tests**

Delete old tests for:

- `--raw-extraction`;
- missing raw extraction;
- malformed raw JSON;
- `--print-extractor-prompt`.

Add tests for:

- `--print-prompt` prints system and user sections;
- default mode is extract;
- `--re-validate` sets rerun mode;
- `--re-extract` sets rerun mode;
- `--commit` passes through to config;
- `--dry-run` does not require API key.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
python -m pytest tests/test_run_cli.py -q
```

Expected: new CLI tests pass.

- [ ] **Step 6: Commit CLI replacement**

Run:

```bash
git add run.py tests/test_run_cli.py
git commit -m "feat: replace run.py with SDK single-deal runner"
```

Expected: run.py commit.

## Task 11: Tighten `SCHEMA_R1`

**Files:**
- Modify: `pipeline/llm/response_format.py`
- Test: `tests/llm/test_response_format.py`

- [ ] **Step 1: Translate `rules/schema.md` §R1 into JSON Schema**

Update `SCHEMA_R1` so the top-level, deal, and event objects are strict. Python validator remains the semantic enforcer; JSON schema catches stale keys, missing structural fields, and impossible primitive types before validation.

```python
FLAG_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "severity": {"type": "string", "enum": ["hard", "soft", "info"]},
        "reason": {"type": "string"},
    },
    "required": ["code", "severity", "reason"],
    "additionalProperties": False,
}

REGISTRY_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "resolved_name": {"type": ["string", "null"]},
        "aliases_observed": {"type": "array", "items": {"type": "string"}},
        "first_appearance_row_index": {"type": ["integer", "null"]},
    },
    "required": ["resolved_name", "aliases_observed", "first_appearance_row_index"],
    "additionalProperties": False,
}

SCHEMA_R1 = {
    "type": "object",
    "properties": {
        "deal": {
            "type": "object",
            "properties": {
                "TargetName": {"type": ["string", "null"]},
                "Acquirer": {"type": ["string", "null"]},
                "DateAnnounced": {"type": ["string", "null"]},
                "DateEffective": {"type": ["string", "null"]},
                "auction": {"type": "boolean"},
                "all_cash": {"type": ["boolean", "null"]},
                "target_legal_counsel": {"type": ["string", "null"]},
                "acquirer_legal_counsel": {"type": ["string", "null"]},
                "bidder_registry": {
                    "type": "object",
                    "additionalProperties": REGISTRY_ENTRY_SCHEMA,
                },
                "deal_flags": {"type": "array", "items": FLAG_SCHEMA},
            },
            "required": ["TargetName", "Acquirer", "DateAnnounced", "DateEffective", "auction", "all_cash", "target_legal_counsel", "acquirer_legal_counsel", "bidder_registry", "deal_flags"],
            "additionalProperties": False
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "BidderID": {"type": "integer"},
                    "process_phase": {"type": "integer"},
                    "role": {"type": ["string", "null"], "enum": ["bidder", "advisor_financial", "advisor_legal", None]},
                    "exclusivity_days": {"type": ["integer", "null"]},
                    "bidder_name": {"type": ["string", "null"]},
                    "bidder_alias": {"type": ["string", "null"]},
                    "bidder_type": {"type": ["string", "null"], "enum": ["s", "f", None]},
                    "bid_note": {"type": "string"},
                    "bid_type": {"type": ["string", "null"], "enum": ["formal", "informal", None]},
                    "bid_type_inference_note": {"type": ["string", "null"], "maxLength": 300},
                    "drop_initiator": {"type": ["string", "null"], "enum": ["bidder", "target", "unknown", None]},
                    "drop_reason_class": {"type": ["string", "null"], "enum": ["below_market", "below_minimum", "target_other", "no_response", "never_advanced", "scope_mismatch", None]},
                    "final_round_announcement": {"type": ["boolean", "null"]},
                    "final_round_extension": {"type": ["boolean", "null"]},
                    "final_round_informal": {"type": ["boolean", "null"]},
                    "press_release_subject": {"type": ["string", "null"], "enum": ["bidder", "sale", "other", None]},
                    "invited_to_formal_round": {"type": ["boolean", "null"]},
                    "submitted_formal_bid": {"type": ["boolean", "null"]},
                    "bid_date_precise": {"type": ["string", "null"]},
                    "bid_date_rough": {"type": ["string", "null"]},
                    "bid_value": {"type": ["number", "null"]},
                    "bid_value_pershare": {"type": ["number", "null"]},
                    "bid_value_lower": {"type": ["number", "null"]},
                    "bid_value_upper": {"type": ["number", "null"]},
                    "bid_value_unit": {"type": ["string", "null"]},
                    "consideration_components": {"type": ["array", "null"], "items": {"type": "string"}},
                    "additional_note": {"type": ["string", "null"]},
                    "comments": {"type": ["string", "null"]},
                    "source_quote": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "source_page": {"oneOf": [{"type": "integer"}, {"type": "array", "items": {"type": "integer"}}]},
                    "flags": {"type": "array", "items": FLAG_SCHEMA},
                },
                "required": ["BidderID", "process_phase", "role", "exclusivity_days", "bidder_name", "bidder_alias", "bidder_type", "bid_note", "bid_type", "bid_type_inference_note", "drop_initiator", "drop_reason_class", "final_round_announcement", "final_round_extension", "final_round_informal", "press_release_subject", "invited_to_formal_round", "submitted_formal_bid", "bid_date_precise", "bid_date_rough", "bid_value", "bid_value_pershare", "bid_value_lower", "bid_value_upper", "bid_value_unit", "consideration_components", "additional_note", "comments", "source_quote", "source_page", "flags"],
                "additionalProperties": False
            }
        }
    },
    "required": ["deal", "events"],
    "additionalProperties": False,
}
```

Do not add orchestration fields (`slug`, `FormType`, `URL`, `rulebook_version`, `last_run`) to the AI schema. `pipeline.core.finalize()` stamps those after extraction.

- [ ] **Step 2: Add tests for stale/missing top-level shape**

Test that:

- schema requires `deal` and `events`;
- schema rejects extra top-level keys under strict output;
- schema includes every event field required by `prompts/extract.md` skeleton.

- [ ] **Step 3: Run schema tests**

Run:

```bash
python -m pytest tests/llm/test_response_format.py -q
```

Expected: schema tests pass.

- [ ] **Step 4: Commit schema**

Run:

```bash
git add pipeline/llm/response_format.py tests/llm/test_response_format.py
git commit -m "feat: add extraction JSON schema for SDK output"
```

Expected: schema commit.

## Task 12: Update Docs And Skill Contract

**Files:**
- Modify: `SKILL.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Possibly modify: `quality_reports/session_logs/2026-04-28_api-call-branch-brainstorm.md`

- [ ] **Step 1: Update architecture prose**

Replace subagent architecture language with:

```markdown
The live repo now uses code-orchestrated direct SDK calls: one Extractor LLM call, deterministic Python validation, and optional scoped Adjudicator LLM calls for soft flags. The provider interface is OpenAI-compatible and configured by `OPENAI_BASE_URL` / `OPENAI_API_KEY`.
```

- [ ] **Step 2: Update invocation contract**

State:

- `run.py --slug X --extract` runs one deal;
- `python -m pipeline.run_pool --filter reference --workers N` runs a batch;
- `--re-validate` uses cached `output/audit/{slug}/raw_response.json`;
- `--re-extract` forces a new LLM call.

- [ ] **Step 3: Remove stale claims**

Search and remove references to:

```bash
rg -n "subagent|--raw-extraction|--print-extractor-prompt|build_extractor_prompt|No model SDK calls|Python stays deterministic" SKILL.md AGENTS.md CLAUDE.md prompts pipeline tests
```

Keep historical mentions only inside `quality_reports/` docs.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add SKILL.md AGENTS.md CLAUDE.md quality_reports/session_logs/2026-04-28_api-call-branch-brainstorm.md
git commit -m "docs: update architecture for direct SDK orchestration"
```

Expected: docs commit.

## Task 13: Add Linkflow Smoke Script

**Files:**
- Create: `scripts/smoke_linkflow.py`

- [ ] **Step 1: Add opt-in smoke script**

Create:

```python
from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv

from pipeline.llm.client import OpenAICompatibleClient
from pipeline.llm.response_format import supports_json_schema


async def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("EXTRACT_MODEL", "gpt-5.5"))
    args = parser.parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://www.linkflow.run/v1"),
    )
    ok = await supports_json_schema(client, model=args.model)
    print(f"json_schema_supported={ok}")
    result = await client.complete(
        system="Reply with one short sentence.",
        user="Say API smoke test passed.",
        model=args.model,
        max_output_tokens=100,
    )
    print(result.text.strip())
    print(f"tokens input={result.input_tokens} output={result.output_tokens} reasoning={result.reasoning_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 2: Run without key**

Run:

```bash
env -u OPENAI_API_KEY python scripts/smoke_linkflow.py
```

Expected: exits with `OPENAI_API_KEY is required`.

- [ ] **Step 3: Commit smoke script**

Run:

```bash
git add scripts/smoke_linkflow.py
git commit -m "chore: add opt-in linkflow smoke test"
```

Expected: smoke script commit.

## Task 14: Full Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
python -m pytest -x
```

Expected: all tests pass.

- [ ] **Step 2: Run prompt rendering**

Run:

```bash
python run.py --slug medivation --print-prompt > /tmp/medivation_prompt.txt
head -n 20 /tmp/medivation_prompt.txt
rg -n "Read these files|Read tool|subagent|--raw-extraction" /tmp/medivation_prompt.txt
```

Expected: first command prints system/user sections; `rg` returns no hits.

- [ ] **Step 3: Run dry-run batch**

Run:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
```

Expected: prints selected reference deals and skip/run rationale; no API key needed; no output files written.

- [ ] **Step 4: Run real linkflow smoke only with rotated key**

Run after Austin rotates/sets a safe key:

```bash
python scripts/smoke_linkflow.py --model gpt-5.5
```

Expected: `json_schema_supported=True` and a short success response.

- [ ] **Step 5: Run one real reference extraction**

Run only after smoke succeeds:

```bash
python run.py --slug medivation --extract --extract-model gpt-5.5 --adjudicate-model gpt-5.5
python scoring/diff.py --slug medivation
```

Expected: Medivation writes `output/extractions/medivation.json`, audit files under `output/audit/medivation/`, and a human-review diff.

- [ ] **Step 6: Check for secrets and stale code**

Run:

```bash
rg -n "sk-[A-Za-z0-9]|OPENAI_API_KEY=.*[A-Za-z0-9]|--raw-extraction|--print-extractor-prompt|build_extractor_prompt|Claude Code subagent|No model SDK calls" .
```

Expected: no secret hits; stale API hits only in historical `quality_reports/` files or this implementation plan. Remove stale hits from operative files before finishing.

- [ ] **Step 7: Final commit**

Run:

```bash
git status --short
git add -A
git commit -m "feat: orchestrate extraction through direct SDK calls"
```

Expected: final cleanup commit only if there are remaining intentional changes.

## Completion Criteria

- `python -m pytest -x` passes.
- `python -m pipeline.run_pool --filter reference --workers 4 --dry-run` works without an API key.
- `scripts/smoke_linkflow.py` works with a rotated API key.
- `python run.py --slug medivation --extract --extract-model gpt-5.5 --adjudicate-model gpt-5.5` writes extraction and audit artifacts.
- `python scoring/diff.py --slug medivation` runs.
- No operative file mentions the old subagent orchestration or `--raw-extraction`.
- No API key appears in git-tracked files.
- Target-deal gate remains closed; no 392 target extraction has been run.
