import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import get_settings
from app.database import create_database_tables
from app.logging_config import configure_logging
from app.services.calendar_scheduler import get_calendar_scheduler
from app.services.market_scheduler import get_scheduler
from app.routers.alerts import router as alerts_router
from app.routers.analysis import router as analysis_router
from app.routers.backtest import router as backtest_router
from app.routers.calendar import router as calendar_router
from app.routers.delivery_quality import router as delivery_quality_router
from app.routers.delivery_states import router as delivery_states_router
from app.routers.dol import router as dol_router
from app.routers.execution import router as execution_router
from app.routers.health import router as health_router
from app.routers.irl_erl import router as irl_erl_router
from app.routers.journal import router as journal_router
from app.routers.liquidity import router as liquidity_router
from app.routers.market import router as market_router
from app.routers.market_ingest import router as market_ingest_router
from app.routers.mmxm import router as mmxm_router
from app.routers.narrative import router as narrative_router
from app.routers.narrative_ledger import router as narrative_ledger_router
from app.routers.news import router as news_router
from app.routers.quarter_readiness import router as quarter_readiness_router
from app.routers.replay import router as replay_router
from app.routers.ssmt import router as ssmt_router
from app.routers.sweep import router as sweep_router
from app.routers.time import router as time_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    log = logging.getLogger(__name__)
    log.info("Starting %s", settings.app_name)
    table_status = create_database_tables()
    log.info("Database table status: %s", table_status["status"])

    scheduler = get_scheduler()
    if settings.market_ingest_autostart and settings.market_data_provider:
        try:
            await scheduler.start()
            log.info("Market scheduler autostarted: %s", scheduler.status())
        except Exception as exc:
            log.warning("Market scheduler autostart skipped: %s", exc)

    calendar_scheduler = get_calendar_scheduler()
    if settings.calendar_autostart and settings.calendar_provider:
        try:
            await calendar_scheduler.start()
            log.info("Calendar scheduler autostarted: %s", calendar_scheduler.status())
        except Exception as exc:
            log.warning("Calendar scheduler autostart skipped: %s", exc)

    try:
        yield
    finally:
        try:
            await scheduler.stop()
        except Exception:
            log.exception("Failed to stop market scheduler cleanly")
        try:
            await calendar_scheduler.stop()
        except Exception:
            log.exception("Failed to stop calendar scheduler cleanly")
        log.info("Stopping %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(market_router)
    app.include_router(market_ingest_router)
    app.include_router(liquidity_router)
    app.include_router(sweep_router)
    app.include_router(dol_router)
    app.include_router(irl_erl_router)
    app.include_router(quarter_readiness_router)
    app.include_router(time_router)
    app.include_router(ssmt_router)
    app.include_router(narrative_ledger_router)
    app.include_router(mmxm_router)
    app.include_router(delivery_quality_router)
    app.include_router(delivery_states_router)
    app.include_router(news_router)
    app.include_router(calendar_router)
    app.include_router(execution_router)
    app.include_router(narrative_router)
    app.include_router(alerts_router)
    app.include_router(journal_router)
    app.include_router(backtest_router)
    app.include_router(replay_router)
    app.include_router(analysis_router)
    return app


app = create_app()
