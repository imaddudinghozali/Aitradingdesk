"""Live market data ingestion orchestrator.

Pulls candles from a configured `MarketDataProvider`, de-duplicates against
stored snapshots, persists new ones through `MarketService`, and records each
attempt in `ingestion_runs` for audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ingestion_run import IngestionRun
from app.models.market_snapshot import MarketSnapshot
from app.schemas.analysis import AnalysisRunRequest
from app.schemas.market import MarketDataInput
from app.schemas.narrative import NarrativeProvider
from app.services.analysis_pipeline_service import AnalysisPipelineService
from app.services.market_providers.base import (
    CandleData,
    MarketDataProvider,
    ProviderError,
)
from app.services.market_service import MarketService

logger = logging.getLogger(__name__)


@dataclass
class IngestionOutcome:
    provider: str
    symbol: str
    timeframe: str
    status: str
    candles_fetched: int
    candles_inserted: int
    candles_skipped: int
    first_candle_utc: datetime | None
    last_candle_utc: datetime | None
    started_at_utc: datetime
    finished_at_utc: datetime
    error_message: str | None


class MarketIngestionService:
    @staticmethod
    def run_once(
        db: Session,
        provider: MarketDataProvider,
        symbol: str,
        timeframe: str,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> IngestionOutcome:
        symbol_up = symbol.upper()
        timeframe_up = timeframe.upper()
        started = datetime.now(tz=UTC)

        candles: list[CandleData] = []
        error: str | None = None
        status = "ok"

        try:
            candles = provider.fetch_ohlc(
                symbol_up,
                timeframe_up,
                start_utc=start_utc,
                end_utc=end_utc,
                limit=limit,
            )
        except ProviderError as exc:
            error = str(exc)
            status = "provider_error"
        except Exception as exc:  # pragma: no cover - defensive
            error = f"unexpected: {exc}"
            status = "error"
            logger.exception("Unexpected provider failure for %s %s", symbol_up, timeframe_up)

        inserted = 0
        skipped = 0
        first_ts: datetime | None = None
        last_ts: datetime | None = None

        for candle in candles:
            if MarketIngestionService._exists(db, candle):
                skipped += 1
                continue
            if not _is_valid_ohlc(candle):
                skipped += 1
                continue
            try:
                MarketService.create_snapshot(
                    db,
                    MarketDataInput(
                        symbol=candle.symbol,
                        timeframe=candle.timeframe,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        timestamp_utc=candle.timestamp_utc,
                    ),
                )
                inserted += 1
                if first_ts is None or candle.timestamp_utc < first_ts:
                    first_ts = candle.timestamp_utc
                if last_ts is None or candle.timestamp_utc > last_ts:
                    last_ts = candle.timestamp_utc
            except Exception as exc:
                logger.warning(
                    "Failed to insert candle %s %s %s: %s",
                    candle.symbol,
                    candle.timeframe,
                    candle.timestamp_utc.isoformat(),
                    exc,
                )
                skipped += 1
                status = "partial"
                error = error or str(exc)

        finished = datetime.now(tz=UTC)

        run = IngestionRun(
            provider=provider.name,
            symbol=symbol_up,
            timeframe=timeframe_up,
            status=status,
            candles_fetched=len(candles),
            candles_inserted=inserted,
            candles_skipped=skipped,
            first_candle_utc=first_ts,
            last_candle_utc=last_ts,
            started_at_utc=started,
            finished_at_utc=finished,
            error_message=error,
        )
        db.add(run)
        db.commit()

        return IngestionOutcome(
            provider=provider.name,
            symbol=symbol_up,
            timeframe=timeframe_up,
            status=status,
            candles_fetched=len(candles),
            candles_inserted=inserted,
            candles_skipped=skipped,
            first_candle_utc=first_ts,
            last_candle_utc=last_ts,
            started_at_utc=started,
            finished_at_utc=finished,
            error_message=error,
        )

    @staticmethod
    def run_batch(
        db: Session,
        provider: MarketDataProvider,
        symbols: list[str],
        timeframes: list[str],
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> list[IngestionOutcome]:
        outcomes: list[IngestionOutcome] = []
        for symbol in symbols:
            for timeframe in timeframes:
                outcomes.append(
                    MarketIngestionService.run_once(
                        db,
                        provider,
                        symbol,
                        timeframe,
                        start_utc=start_utc,
                        end_utc=end_utc,
                        limit=limit,
                    )
                )
        MarketIngestionService._maybe_run_auto_analysis(db, outcomes)
        return outcomes

    @staticmethod
    def latest_run(db: Session, symbol: str, timeframe: str) -> IngestionRun | None:
        return (
            db.query(IngestionRun)
            .filter(
                IngestionRun.symbol == symbol.upper(),
                IngestionRun.timeframe == timeframe.upper(),
            )
            .order_by(IngestionRun.started_at_utc.desc(), IngestionRun.id.desc())
            .first()
        )

    @staticmethod
    def recent_runs(db: Session, limit: int = 50) -> list[IngestionRun]:
        return (
            db.query(IngestionRun)
            .order_by(IngestionRun.started_at_utc.desc(), IngestionRun.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _exists(db: Session, candle: CandleData) -> bool:
        return (
            db.query(MarketSnapshot.id)
            .filter(
                MarketSnapshot.symbol == candle.symbol,
                MarketSnapshot.timeframe == candle.timeframe,
                MarketSnapshot.timestamp_utc == candle.timestamp_utc,
            )
            .first()
            is not None
        )

    @staticmethod
    def _maybe_run_auto_analysis(db: Session, outcomes: list[IngestionOutcome]) -> None:
        settings = get_settings()
        if not settings.market_ingest_auto_analysis:
            return

        trigger_timeframe = settings.market_ingest_auto_analysis_timeframe.upper()
        changed = any(
            outcome.symbol == "XAUUSD"
            and outcome.timeframe == trigger_timeframe
            and outcome.candles_inserted > 0
            for outcome in outcomes
        )
        if not changed:
            return

        provider_raw = settings.market_ingest_auto_analysis_provider.strip().lower()
        provider = (
            NarrativeProvider.CLAUDE
            if provider_raw == NarrativeProvider.CLAUDE.value
            else NarrativeProvider.RULES
        )
        try:
            AnalysisPipelineService.run(
                db,
                AnalysisRunRequest(
                    symbol="XAUUSD",
                    sweep_timeframe=trigger_timeframe,
                    execution_timeframe=trigger_timeframe,
                    provider=provider,
                ),
            )
        except Exception as exc:
            logger.warning("Auto-analysis after market ingest failed: %s", exc)


def _is_valid_ohlc(candle: CandleData) -> bool:
    prices = [candle.open, candle.high, candle.low, candle.close]
    if any(p is None or not isinstance(p, Decimal) for p in prices):
        return False
    if candle.high < candle.low:
        return False
    if candle.open < candle.low or candle.open > candle.high:
        return False
    if candle.close < candle.low or candle.close > candle.high:
        return False
    return True
