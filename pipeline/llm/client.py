from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from pipeline.llm.retry import RetryConfig, with_retry
from pipeline.llm.watchdog import APICallWatchdog, WatchdogConfig, WatchdogStats


@dataclass
class CompletionResult:
    text: str
    model: str
    parsed_json: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
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
        model: str,
        system: str | None = None,
        user: str | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        stream: bool = True,
    ) -> CompletionResult:
        raise NotImplementedError


class OpenAICompatibleClient(LLMClient):
    supports_structured_output = True

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        openai_client: Any | None = None,
        watchdog_cfg: WatchdogConfig | None = None,
        retry_cfg: RetryConfig | None = None,
    ):
        self._client = openai_client or AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0)
        self.endpoint = "responses"
        self.supports_structured_output = True
        self.watchdog_cfg = watchdog_cfg or WatchdogConfig()
        self.retry_cfg = retry_cfg or RetryConfig()

    async def complete(
        self,
        *,
        model: str,
        system: str | None = None,
        user: str | None = None,
        input_items: list[dict[str, Any]] | None = None,
        text_format: dict | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        stream: bool = True,
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
                tools=tools,
                tool_choice=tool_choice,
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
                stream=stream,
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
        text_format: dict | None,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
        stream: bool,
        attempt: int,
    ) -> CompletionResult:
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
        }
        if text_format is not None:
            kwargs["text"] = {"format": text_format}
        if tools is not None:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        started = time.monotonic()
        if not stream:
            final_response = await self._client.responses.create(**kwargs)
            usage = getattr(final_response, "usage", None)
            text = getattr(final_response, "output_text", None) or _output_text_from_items(final_response)
            return CompletionResult(
                text=text,
                model=model,
                tool_calls=_tool_calls(final_response),
                output_items=_output_items(final_response),
                input_tokens=_usage_value(usage, "input_tokens"),
                output_tokens=_usage_value(usage, "output_tokens"),
                reasoning_tokens=_reasoning_tokens(usage),
                finish_reason=_finish_reason(final_response),
                latency_seconds=time.monotonic() - started,
                attempts=attempt,
                raw_response=final_response,
            )

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
            tool_calls=_tool_calls_from_items(output_items),
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


def _tool_calls(response: Any) -> list[dict[str, Any]]:
    return _tool_calls_from_items(_output_items(response))


def _tool_calls_from_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("type") == "function_call"]


def _output_text_from_items(response: Any) -> str:
    parts: list[str] = []
    for item in _output_items(response):
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") in {
                    "output_text",
                    "text",
                }:
                    parts.append(str(content.get("text") or ""))
    return "".join(parts)
