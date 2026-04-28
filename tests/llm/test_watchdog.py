import asyncio

import pytest

from pipeline.llm.watchdog import APICallWatchdog, WatchdogConfig


def test_watchdog_records_activity_and_stale_warnings():
    async def run():
        cfg = WatchdogConfig(
            heartbeat_seconds=0.01,
            stale_warning_seconds=0.02,
            stream_idle_seconds=1.0,
            total_call_seconds=1.0,
        )
        async with APICallWatchdog(label="unit", cfg=cfg) as watchdog:
            await asyncio.sleep(0.03)
            watchdog.mark_activity(chars=7, phase="delta")
            await asyncio.sleep(0.02)
            return watchdog.stats

    stats = asyncio.run(run())

    assert stats.warnings >= 1
    assert stats.max_idle_seconds > 0
    assert any(event["phase"] == "delta" and event["chars"] == 7 for event in stats.events)


def test_watchdog_raises_stream_idle_timeout():
    async def run():
        cfg = WatchdogConfig(
            heartbeat_seconds=0.01,
            stale_warning_seconds=1.0,
            stream_idle_seconds=0.03,
            total_call_seconds=1.0,
        )
        async with APICallWatchdog(label="idle", cfg=cfg):
            await asyncio.sleep(0.2)

    with pytest.raises(asyncio.TimeoutError, match="stream idle"):
        asyncio.run(run())


def test_watchdog_raises_total_call_timeout_even_with_activity():
    async def run():
        cfg = WatchdogConfig(
            heartbeat_seconds=0.01,
            stale_warning_seconds=1.0,
            stream_idle_seconds=1.0,
            total_call_seconds=0.04,
        )
        async with APICallWatchdog(label="total", cfg=cfg) as watchdog:
            for _ in range(10):
                watchdog.mark_activity()
                await asyncio.sleep(0.01)

    with pytest.raises(asyncio.TimeoutError, match="total call"):
        asyncio.run(run())
