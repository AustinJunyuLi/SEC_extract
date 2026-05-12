from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from pipeline.llm.retry import RetryConfig, with_retry
from pipeline.llm.watchdog import APICallWatchdog, WatchdogConfig, WatchdogStats


@dataclass
class CompletionResult:
    text: str
    model: str
    parsed_json: dict[str, Any] | None = None
    output_items: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    latency_seconds: float = 0.0
    attempts: int = 1
    finish_reason: str | None = None
    watchdog: WatchdogStats = field(default_factory=WatchdogStats)
    raw_response: Any | None = None


class LLMClient(ABC):
    supports_structured_output = True

    @abstractmethod
    async def complete(
        self,
        *,
        model: str | None,
        system: str | None = None,
        user: str | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> CompletionResult:
        raise NotImplementedError


class OpenAIResponsesClient(LLMClient):
    supports_structured_output = True

    def __init__(
        self,
        *,
        api_key: str,
        openai_client: Any | None = None,
        watchdog_cfg: WatchdogConfig | None = None,
        retry_cfg: RetryConfig | None = None,
    ):
        self._client = openai_client or AsyncOpenAI(api_key=api_key, max_retries=0)
        self.endpoint = "openai_responses"
        self.supports_structured_output = True
        self.watchdog_cfg = watchdog_cfg or WatchdogConfig()
        self.retry_cfg = retry_cfg or RetryConfig()

    async def complete(
        self,
        *,
        model: str | None,
        system: str | None = None,
        user: str | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> CompletionResult:
        attempts = 0

        async def attempt_once() -> CompletionResult:
            nonlocal attempts
            attempts += 1
            return await self._complete_once(
                model=model,
                system=system,
                user=user,
                input_items=input_items,
                text_format=text_format,
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
                attempt=attempts,
            )

        result = await with_retry(attempt_once, cfg=self.retry_cfg)
        result.attempts = attempts
        return result

    async def _complete_once(
        self,
        *,
        model: str,
        system: str | None,
        user: str | None,
        input_items: list[dict[str, Any]] | None,
        text_format: dict,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
        attempt: int,
    ) -> CompletionResult:
        if not model:
            raise ValueError("OpenAI Responses backend requires an explicit model")
        if not text_format:
            raise ValueError("strict Responses text_format is required")
        if input_items is None:
            if system is None or user is None:
                raise ValueError("system and user are required when input_items is not provided")
            input_payload = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        else:
            input_payload = input_items
        kwargs: dict[str, Any] = {
            "model": model,
            "input": input_payload,
            "text": {"format": text_format},
        }
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        started = time.monotonic()
        text_parts: list[str] = []
        stream_output_items: list[dict[str, Any]] = []
        final_response = None
        missing_completed_event = False
        async with APICallWatchdog(label=f"responses:{model}:attempt-{attempt}", cfg=self.watchdog_cfg) as watchdog:
            try:
                async with self._client.responses.stream(**kwargs) as stream:
                    async for event in stream:
                        delta = _event_delta(event)
                        watchdog.mark_activity(chars=len(delta), phase=getattr(event, "type", "event"))
                        if delta:
                            text_parts.append(delta)
                        item = _event_output_item(event)
                        if item is not None:
                            stream_output_items.append(item)
                    if hasattr(stream, "get_final_response"):
                        final_response = await stream.get_final_response()
            except RuntimeError as exc:
                if not _is_missing_completed_event(exc) or not (text_parts or stream_output_items):
                    raise
                missing_completed_event = True
        if not text_parts and final_response is not None:
            output_text = getattr(final_response, "output_text", None)
            if output_text:
                text_parts.append(output_text)

        usage = getattr(final_response, "usage", None)
        output_items = _output_items(final_response) or stream_output_items
        return CompletionResult(
            text="".join(text_parts),
            model=model,
            output_items=output_items,
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            reasoning_tokens=_reasoning_tokens(usage),
            finish_reason="missing_response_completed" if missing_completed_event else _finish_reason(final_response),
            latency_seconds=time.monotonic() - started,
            attempts=attempt,
            watchdog=watchdog.stats,
            raw_response=final_response,
        )


BridgeRunner = Any


class ClaudeAgentSDKClient(LLMClient):
    supports_structured_output = True

    def __init__(
        self,
        *,
        bridge_path: Path | None = None,
        node_executable: str = "node",
        bridge_runner: BridgeRunner | None = None,
        watchdog_cfg: WatchdogConfig | None = None,
        retry_cfg: RetryConfig | None = None,
    ):
        self.bridge_path = bridge_path or Path(__file__).with_name("claude_agent_bridge.mjs")
        self.node_executable = node_executable
        self._bridge_runner = bridge_runner
        self.endpoint = "claude_agent_sdk"
        self.supports_structured_output = True
        self.watchdog_cfg = watchdog_cfg or WatchdogConfig()
        self.retry_cfg = retry_cfg or RetryConfig()

    async def complete(
        self,
        *,
        model: str | None,
        system: str | None = None,
        user: str | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> CompletionResult:
        attempts = 0

        async def attempt_once() -> CompletionResult:
            nonlocal attempts
            attempts += 1
            return await self._complete_once(
                model=model,
                system=system,
                user=user,
                input_items=input_items,
                text_format=text_format,
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
                attempt=attempts,
            )

        result = await with_retry(attempt_once, cfg=self.retry_cfg)
        result.attempts = attempts
        return result

    async def _complete_once(
        self,
        *,
        model: str | None,
        system: str | None,
        user: str | None,
        input_items: list[dict[str, Any]] | None,
        text_format: dict,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
        attempt: int,
    ) -> CompletionResult:
        if not text_format:
            raise ValueError("strict json_schema text_format is required")
        if text_format.get("type") != "json_schema" or text_format.get("strict") is not True:
            raise ValueError("Claude Agent SDK backend requires strict json_schema text_format")
        system_prompt, user_prompt = _system_user_from_inputs(
            system=system,
            user=user,
            input_items=input_items,
        )
        request: dict[str, Any] = {
            "model": model,
            "system": system_prompt,
            "user": user_prompt,
            "text_format": text_format,
            "max_output_tokens": max_output_tokens,
            "reasoning_effort": reasoning_effort,
            "thinking": _claude_thinking(reasoning_effort),
        }
        started = time.monotonic()
        async with APICallWatchdog(label=f"claude-agent-sdk:{model or 'default'}:attempt-{attempt}", cfg=self.watchdog_cfg) as watchdog:
            response = await self._run_bridge(request)
            watchdog.mark_activity(chars=len(str(response.get("text") or "")), phase="bridge_result")
        text = str(response.get("text") or "")
        if not text:
            structured = response.get("structured_output")
            if structured is not None:
                text = json.dumps(structured, separators=(",", ":"))
        if not text:
            raise RuntimeError("Claude Agent SDK bridge returned no structured text")
        return CompletionResult(
            text=text,
            model=str(response.get("model") or model or "claude_agent_sdk_default"),
            output_items=list(response.get("output_items") or []),
            input_tokens=int(response.get("input_tokens") or 0),
            output_tokens=int(response.get("output_tokens") or 0),
            reasoning_tokens=int(response.get("reasoning_tokens") or 0),
            finish_reason=response.get("finish_reason"),
            latency_seconds=time.monotonic() - started,
            attempts=attempt,
            watchdog=watchdog.stats,
            raw_response=response.get("raw_response"),
        )

    async def _run_bridge(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._bridge_runner is not None:
            return await self._bridge_runner(request)
        env = dict(os.environ)
        env["NODE_NO_WARNINGS"] = env.get("NODE_NO_WARNINGS", "1")
        proc = await asyncio.create_subprocess_exec(
            self.node_executable,
            str(self.bridge_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
        )
        stdout, stderr = await proc.communicate(
            json.dumps(request, separators=(",", ":"), default=str).encode("utf-8")
        )
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Claude Agent SDK bridge failed with exit {proc.returncode}: {detail}")
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            preview = stdout.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Claude Agent SDK bridge returned non-JSON stdout: {preview}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Claude Agent SDK bridge returned non-object payload")
        return payload


def _system_user_from_inputs(
    *,
    system: str | None,
    user: str | None,
    input_items: list[dict[str, Any]] | None,
) -> tuple[str, str]:
    if input_items is None:
        if system is None or user is None:
            raise ValueError("system and user are required when input_items is not provided")
        return system, user
    system_parts: list[str] = []
    user_parts: list[str] = []
    for item in input_items:
        role = item.get("role")
        content = item.get("content")
        text = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
        if role == "system":
            system_parts.append(text)
        elif role == "user":
            user_parts.append(text)
        else:
            raise ValueError(f"unsupported Claude Agent SDK input role: {role!r}")
    if not system_parts or not user_parts:
        raise ValueError("Claude Agent SDK backend requires system and user input items")
    return "\n\n".join(system_parts), "\n\n".join(user_parts)


def _claude_thinking(reasoning_effort: str | None) -> dict[str, Any] | None:
    if reasoning_effort in (None, "none"):
        return None
    budgets = {
        "low": 4_000,
        "medium": 8_000,
        "high": 16_000,
        "xhigh": 32_000,
    }
    if reasoning_effort not in budgets:
        raise ValueError(f"Claude Agent SDK backend does not support reasoning effort {reasoning_effort!r}")
    return {"type": "enabled", "budgetTokens": budgets[reasoning_effort]}


def _event_delta(event: Any) -> str:
    event_type = getattr(event, "type", "")
    if event_type in {"response.output_text.delta", "response.output_text.annotation.added"}:
        return getattr(event, "delta", "") or ""
    if isinstance(event, dict) and event.get("type") == "response.output_text.delta":
        return event.get("delta") or ""
    return ""


def _is_missing_completed_event(exc: RuntimeError) -> bool:
    return "response.completed" in str(exc)


def _event_output_item(event: Any) -> dict[str, Any] | None:
    event_type = getattr(event, "type", "")
    if isinstance(event, dict):
        event_type = event.get("type", "")
        if event_type == "response.output_item.done" and isinstance(event.get("item"), dict):
            return dict(event["item"])
        return None
    if event_type != "response.output_item.done":
        return None
    item = getattr(event, "item", None)
    if item is None:
        return None
    return _model_dump(item)


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(name) or 0)
    return int(getattr(usage, name, 0) or 0)


def _response_value(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _reasoning_tokens(usage: Any) -> int:
    if usage is None:
        return 0
    details = _response_value(usage, "output_tokens_details")
    if isinstance(details, dict):
        return int(details.get("reasoning_tokens") or 0)
    return int(getattr(details, "reasoning_tokens", 0) or 0)


def _finish_reason(response: Any) -> str | None:
    if response is None:
        return None
    for name in ("finish_reason", "status"):
        value = _response_value(response, name)
        if value:
            return str(value)
    return None


def _model_dump(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    data: dict[str, Any] = {}
    for name in ("type", "name", "call_id", "arguments", "id", "status"):
        value = getattr(obj, name, None)
        if value is not None:
            data[name] = value
    return data


def _output_items(response: Any) -> list[dict[str, Any]]:
    output = _response_value(response, "output") or []
    return [_model_dump(item) for item in output]
