"""Async scheduler for periodic economic-calendar refresh + catalyst sync."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.services.calendar_providers import get_calendar_provider
from app.services.calendar_providers.base import (
    CalendarProvider,
    CalendarProviderError,
)
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)


class CalendarScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._provider: CalendarProvider | None = None
        self._provider_name: str | None = None
        self._interval_seconds: int | None = None
        self._sync_symbol: str = "XAUUSD"
        self._last_tick_utc: datetime | None = None
        self._next_tick_utc: datetime | None = None
        self._last_error: str | None = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict:
        return {
            "running": self.running,
            "provider": self._provider_name,
            "symbols": [self._sync_symbol] if self._sync_symbol else [],
            "timeframes": [],
            "interval_seconds": self._interval_seconds,
            "last_tick_utc": self._last_tick_utc,
            "last_error": self._last_error,
            "next_tick_utc": self._next_tick_utc,
        }

    async def start(
        self,
        provider_name: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        sync_symbol: Optional[str] = None,
    ) -> dict:
        async with self._lock:
            if self.running:
                return self.status()

            settings = get_settings()
            self._provider_name = (provider_name or settings.calendar_provider or "").strip() or None
            if not self._provider_name:
                raise RuntimeError("CALENDAR_PROVIDER not configured")

            self._interval_seconds = int(interval_seconds or settings.calendar_refresh_interval_seconds)
            self._sync_symbol = (sync_symbol or "XAUUSD").upper()
            self._provider = get_calendar_provider(self._provider_name)

            self._task = asyncio.create_task(self._loop(), name="calendar-scheduler")
            return self.status()

    async def stop(self) -> dict:
        async with self._lock:
            if self._task is None or self._task.done():
                self._task = None
                return self.status()
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
            return self.status()

    async def _loop(self) -> None:
        assert self._provider is not None
        assert self._interval_seconds is not None
        try:
            while True:
                self._last_tick_utc = datetime.now(tz=UTC)
                self._next_tick_utc = self._last_tick_utc + timedelta(seconds=self._interval_seconds)
                await self._tick_once()
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.info("Calendar scheduler cancelled")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Calendar scheduler crashed: %s", exc)
            self._last_error = str(exc)

    async def _tick_once(self) -> None:
        if SessionLocal is None:
            self._last_error = "DATABASE_URL is not configured"
            return
        try:
            await asyncio.to_thread(self._refresh_and_sync_blocking)
            self._last_error = None
        except CalendarProviderError as exc:
            self._last_error = f"provider: {exc}"
            logger.warning("Calendar scheduler provider error: %s", exc)
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Calendar scheduler tick failed: %s", exc)

    def _refresh_and_sync_blocking(self) -> None:
        assert self._provider is not None
        assert SessionLocal is not None
        session = SessionLocal()
        try:
            CalendarService.refresh(session, self._provider)
            CalendarService.sync_to_catalyst(session, self._sync_symbol)
        finally:
            session.close()


_scheduler: CalendarScheduler | None = None


def get_calendar_scheduler() -> CalendarScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = CalendarScheduler()
    return _scheduler
