from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field


LOGGER = logging.getLogger(__name__)


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
    """Async watchdog for long streaming Responses API calls."""

    def __init__(self, *, label: str, cfg: WatchdogConfig):
        self.label = label
        self.cfg = cfg
        self.owner_task: asyncio.Task | None = None
        self.timeout_error: asyncio.TimeoutError | None = None
        self.started_at = time.monotonic()
        self.last_activity_at = self.started_at
        self.stats = WatchdogStats()
        self._task: asyncio.Task | None = None
        self._stopped: asyncio.Event | None = None
        self._last_warning_at = self.started_at

    async def __aenter__(self) -> APICallWatchdog:
        self.owner_task = asyncio.current_task()
        self.started_at = time.monotonic()
        self.last_activity_at = self.started_at
        self._last_warning_at = self.started_at
        self._stopped = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name=f"llm-watchdog:{self.label}")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stopped is not None:
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
        assert self._stopped is not None
        while not self._stopped.is_set():
            await asyncio.sleep(self.cfg.heartbeat_seconds)
            now = time.monotonic()
            elapsed = now - self.started_at
            idle = now - self.last_activity_at
            self.stats.max_idle_seconds = max(self.stats.max_idle_seconds, idle)
            LOGGER.info("llm heartbeat label=%s elapsed=%.1fs idle=%.1fs", self.label, elapsed, idle)
            if elapsed >= self.cfg.total_call_seconds:
                self._timeout(f"total call timeout after {elapsed:.1f}s")
                return
            if idle >= self.cfg.stream_idle_seconds:
                self._timeout(f"stream idle timeout after {idle:.1f}s")
                return
            if idle >= self.cfg.stale_warning_seconds and now - self._last_warning_at >= self.cfg.stale_warning_seconds:
                self.stats.warnings += 1
                self._last_warning_at = now
                LOGGER.warning("llm stream stale label=%s elapsed=%.1fs idle=%.1fs", self.label, elapsed, idle)

    def _timeout(self, message: str) -> None:
        self.timeout_error = asyncio.TimeoutError(f"{self.label}: {message}")
        if self.owner_task is not None:
            self.owner_task.cancel()
