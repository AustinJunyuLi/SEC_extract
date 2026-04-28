import asyncio

import httpx
import pytest

from pipeline.llm.retry import RetryConfig, RetryExhaustedError, retry_delay, with_retry


def test_retry_delay_uses_bounded_exponential_backoff():
    cfg = RetryConfig(max_attempts=4, backoff_base_seconds=2.0, backoff_factor=3.0, backoff_max_seconds=20.0)

    assert retry_delay(1, cfg) == 2.0
    assert retry_delay(2, cfg) == 6.0
    assert retry_delay(3, cfg) == 18.0
    assert retry_delay(4, cfg) == 20.0


def test_with_retry_retries_transient_httpx_errors_without_real_sleep():
    attempts = 0
    sleeps = []

    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.TimeoutException("temporary")
        return "ok"

    async def sleep(seconds):
        sleeps.append(seconds)

    result = asyncio.run(with_retry(flaky, cfg=RetryConfig(max_attempts=3, backoff_base_seconds=1), sleep=sleep))

    assert result == "ok"
    assert attempts == 3
    assert sleeps == [1.0, 3.0]


def test_with_retry_does_not_retry_non_retryable_http_status():
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.test"))
    attempts = 0

    async def bad_request():
        nonlocal attempts
        attempts += 1
        raise httpx.HTTPStatusError("bad", request=response.request, response=response)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(with_retry(bad_request, cfg=RetryConfig(max_attempts=3), sleep=lambda _: None))

    assert attempts == 1


def test_with_retry_raises_exhausted_with_last_error():
    async def always_timeout():
        raise httpx.TimeoutException("temporary")

    with pytest.raises(RetryExhaustedError) as excinfo:
        asyncio.run(with_retry(always_timeout, cfg=RetryConfig(max_attempts=2), sleep=lambda _: None))

    assert isinstance(excinfo.value.last_error, httpx.TimeoutException)
    assert excinfo.value.attempts == 2
