"""Async scheduler for periodic live market data ingestion.

A single in-process asyncio task ticks every `interval_seconds`, opens a DB
session via `SessionLocal`, and invokes `MarketIngestionService.run_batch`.
The scheduler is controllable via the `/market/ingest/scheduler/*` endpoints
and lifecycle-managed in `app.main.lifespan`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.services.market_ingestion_service import MarketIngestionService
from app.services.market_providers import get_provider
from app.services.market_providers.base import MarketDataProvider, ProviderError

logger = logging.getLogger(__name__)


class MarketScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._provider: MarketDataProvider | None = None
        self._provider_name: str | None = None
        self._symbols: list[str] = []
        self._timeframes: list[str] = []
        self._interval_seconds: int | None = None
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
            "symbols": list(self._symbols),
            "timeframes": list(self._timeframes),
            "interval_seconds": self._interval_seconds,
            "last_tick_utc": self._last_tick_utc,
            "last_error": self._last_error,
            "next_tick_utc": self._next_tick_utc,
        }

    async def start(
        self,
        provider_name: Optional[str] = None,
        symbols: Optional[list[str]] = None,
        timeframes: Optional[list[str]] = None,
        interval_seconds: Optional[int] = None,
    ) -> dict:
        async with self._lock:
            if self.running:
                return self.status()

            settings = get_settings()
            self._provider_name = (provider_name or settings.market_data_provider or "").strip() or None
            if not self._provider_name:
                raise RuntimeError("MARKET_DATA_PROVIDER not configured")

            self._symbols = list(symbols) if symbols else _csv(settings.market_ingest_symbols)
            self._timeframes = list(timeframes) if timeframes else _csv(settings.market_ingest_timeframes)
            self._interval_seconds = int(interval_seconds or settings.market_ingest_interval_seconds)

            if not self._symbols or not self._timeframes:
                raise RuntimeError("MARKET_INGEST_SYMBOLS and MARKET_INGEST_TIMEFRAMES must be set")

            self._provider = get_provider(self._provider_name)
            self._task = asyncio.create_task(self._loop(), name="market-scheduler")
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
            logger.info("Market scheduler cancelled")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Market scheduler crashed: %s", exc)
            self._last_error = str(exc)

    async def _tick_once(self) -> None:
        if SessionLocal is None:
            self._last_error = "DATABASE_URL is not configured"
            return
        try:
            await asyncio.to_thread(self._run_batch_blocking)
            self._last_error = None
        except ProviderError as exc:
            self._last_error = f"provider: {exc}"
            logger.warning("Scheduler provider error: %s", exc)
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Scheduler tick failed: %s", exc)

    def _run_batch_blocking(self) -> None:
        assert self._provider is not None
        assert SessionLocal is not None
        session = SessionLocal()
        try:
            MarketIngestionService.run_batch(
                session,
                self._provider,
                self._symbols,
                self._timeframes,
            )
        finally:
            session.close()


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


_scheduler: MarketScheduler | None = None


def get_scheduler() -> MarketScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = MarketScheduler()
    return _scheduler
