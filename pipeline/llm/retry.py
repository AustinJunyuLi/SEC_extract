from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx
import openai


T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    backoff_base_seconds: float = 5.0
    backoff_factor: float = 3.0
    backoff_max_seconds: float = 60.0


class RetryExhaustedError(RuntimeError):
    def __init__(self, *, attempts: int, last_error: BaseException):
        super().__init__(f"retry exhausted after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def retry_delay(attempt: int, cfg: RetryConfig) -> float:
    delay = cfg.backoff_base_seconds * (cfg.backoff_factor ** max(0, attempt - 1))
    return min(delay, cfg.backoff_max_seconds)


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (
        openai.BadRequestError,
        openai.AuthenticationError,
        openai.PermissionDeniedError,
        openai.NotFoundError,
        openai.UnprocessableEntityError,
    )):
        return False
    if isinstance(exc, (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
    )):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {408, 409, 425, 429} or exc.response.status_code >= 500
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code in {408, 409, 425, 429} or status_code >= 500
    return False


async def _maybe_sleep(sleep: Callable[[float], Awaitable[None] | None], seconds: float) -> None:
    result = sleep(seconds)
    if result is not None:
        await result


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    cfg: RetryConfig,
    sleep: Callable[[float], Awaitable[None] | None] = asyncio.sleep,
) -> T:
    attempts = 0
    while True:
        attempts += 1
        try:
            return await operation()
        except BaseException as exc:
            if not is_retryable_exception(exc):
                raise
            if attempts >= cfg.max_attempts:
                raise RetryExhaustedError(attempts=attempts, last_error=exc) from exc
            await _maybe_sleep(sleep, retry_delay(attempts, cfg))
