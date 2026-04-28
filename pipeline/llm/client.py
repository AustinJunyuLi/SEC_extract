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
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    latency_seconds: float = 0.0
    attempts: int = 1
    finish_reason: str | None = None
    watchdog: WatchdogStats = field(default_factory=WatchdogStats)
    raw_response: Any | None = None


class LLMClient(ABC):
    supports_structured_output = False

    @abstractmethod
    async def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        text_format: dict | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
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
        self.supports_structured_output = not _is_newapi_base_url(base_url)
        self.watchdog_cfg = watchdog_cfg or WatchdogConfig()
        self.retry_cfg = retry_cfg or RetryConfig()

    async def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        text_format: dict | None = None,
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
        system: str,
        user: str,
        text_format: dict | None,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
        attempt: int,
    ) -> CompletionResult:
        kwargs: dict[str, Any] = {
            "model": model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if text_format is not None:
            kwargs["text"] = {"format": text_format}
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        started = time.monotonic()
        text_parts: list[str] = []
        final_response = None
        async with APICallWatchdog(label=f"responses:{model}:attempt-{attempt}", cfg=self.watchdog_cfg) as watchdog:
            async with self._client.responses.stream(**kwargs) as stream:
                async for event in stream:
                    delta = _event_delta(event)
                    watchdog.mark_activity(chars=len(delta), phase=getattr(event, "type", "event"))
                    if delta:
                        text_parts.append(delta)
                if hasattr(stream, "get_final_response"):
                    final_response = await stream.get_final_response()
        if not text_parts and final_response is not None:
            output_text = getattr(final_response, "output_text", None)
            if output_text:
                text_parts.append(output_text)

        usage = getattr(final_response, "usage", None)
        return CompletionResult(
            text="".join(text_parts),
            model=model,
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            reasoning_tokens=_reasoning_tokens(usage),
            finish_reason=_finish_reason(final_response),
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


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(name) or 0)
    return int(getattr(usage, name, 0) or 0)


def _is_newapi_base_url(base_url: str | None) -> bool:
    if base_url and any(marker in base_url.lower() for marker in ("linkflow.run", "newapi")):
        return True
    return False


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
