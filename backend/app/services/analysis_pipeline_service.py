import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.schemas.analysis import AnalysisRunRequest, AnalysisRunResponse, AnalysisStepResponse
from app.schemas.execution import ExecutionEvaluateRequest
from app.schemas.liquidity import LiquidityRefreshRequest
from app.schemas.narrative import NarrativeGenerateRequest
from app.schemas.ssmt import SsmtEvaluateRequest
from app.schemas.sweep import SweepScanRequest
from app.services.delivery_quality_service import DeliveryQualityService
from app.services.dol_service import DolService
from app.services.execution_service import ExecutionService
from app.services.irl_erl_service import IrlErlService
from app.services.liquidity_service import LiquidityService
from app.services.mmxm_service import MmxmService
from app.services.narrative_ledger_service import NarrativeLedgerService
from app.services.narrative_service import NarrativeService
from app.services.quarter_readiness_service import QuarterReadinessService
from app.services.ssmt_service import SsmtService
from app.services.sweep_service import SweepService


@dataclass
class PipelineTrace:
    steps: list[dict[str, str | int | None]]
    missing_inputs: list[str]

    def add(
        self, stage: str, status: str, detail: str, record_id: int | None = None
    ) -> None:
        self.steps.append(
            {"stage": stage, "status": status, "detail": detail, "record_id": record_id}
        )

    def missing(self, detail: str) -> None:
        if detail not in self.missing_inputs:
            self.missing_inputs.append(detail)


class AnalysisPipelineService:
    @staticmethod
    def run(db: Session, request: AnalysisRunRequest) -> AnalysisRun:
        market = (
            db.query(MarketSnapshot)
            .filter(
                MarketSnapshot.symbol == request.symbol,
                MarketSnapshot.timeframe == request.execution_timeframe,
            )
            .order_by(MarketSnapshot.timestamp_utc.desc(), MarketSnapshot.id.desc())
            .first()
        )
        if market is None:
            raise ValueError(
                f"No {request.execution_timeframe} market snapshots found for {request.symbol}."
            )
        cutoff = market.timestamp_utc
        trace = PipelineTrace([], [])
        run = AnalysisRun(
            symbol=request.symbol,
            as_of_utc=cutoff,
            sweep_timeframe=request.sweep_timeframe,
            execution_timeframe=request.execution_timeframe,
            minimum_rr=request.minimum_rr,
            provider=request.provider.value,
            sweep_narrative_alignment=request.sweep_narrative_alignment.value,
            ssmt_poi_touched=request.ssmt_poi_touched,
            ssmt_poi_reference=request.ssmt_poi_reference,
            run_status="running",
            decision_status="No Trade",
            no_trade_reason="Analysis run in progress.",
            step_trace="[]",
            missing_inputs="[]",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        _, levels, missing_levels = LiquidityService.refresh_levels(
            db, LiquidityRefreshRequest(symbol=request.symbol, as_of_utc=cutoff)
        )
        detail = f"{len(levels)} liquidity levels refreshed through the decision cutoff."
        if missing_levels:
            detail += f" Missing references: {', '.join(missing_levels)}."
            trace.missing("Missing liquidity references: " + ", ".join(missing_levels))
        trace.add("liquidity_map", "completed" if levels else "waiting", detail)

        try:
            _, sweeps, waiting_reasons = SweepService.scan(
                db,
                SweepScanRequest(
                    symbol=request.symbol,
                    timeframe=request.sweep_timeframe,
                    as_of_utc=cutoff,
                    narrative_alignment=request.sweep_narrative_alignment,
                ),
            )
            sweep_status = "completed" if sweeps else "waiting"
            detail = f"{len(sweeps)} liquidity interactions evaluated."
            if waiting_reasons:
                detail += " Confirmation is still pending for at least one interaction."
            if not sweeps:
                trace.missing("No sweep interaction is available for DOL confirmation.")
            trace.add("sweep_classification", sweep_status, detail)
        except ValueError as exc:
            trace.add("sweep_classification", "waiting", str(exc))
            trace.missing(str(exc))

        dol = DolService.evaluate(db, request.symbol, cutoff)
        run.dol_assessment_id = dol.id
        dol_ready = dol.lifecycle_status in {"Active", "Shift Confirmed"}
        trace.add(
            "dol",
            "completed" if dol_ready else "waiting",
            f"DOL lifecycle is {dol.lifecycle_status}: {dol.status_reason}",
            dol.id,
        )
        if not dol_ready:
            trace.missing(f"DOL must become Active or Shift Confirmed; current status is {dol.lifecycle_status}.")

        mapping_result = IrlErlService.evaluate(db, request.symbol)
        mapping = mapping_result.mapping
        run.irl_erl_mapping_id = mapping.id
        mapping_ready = mapping.mapping_status == "aligned"
        trace.add(
            "direction_liquidity",
            "completed" if mapping_ready else "waiting",
            f"IRL/ERL mapping is {mapping.mapping_status}: {mapping.status_reason}",
            mapping.id,
        )
        if not mapping_ready:
            trace.missing("IRL/ERL direction liquidity mapping is not aligned.")

        quarter = QuarterReadinessService.evaluate(db, request.symbol, cutoff)
        run.quarter_readiness_id = quarter.id
        trace.add(
            "quarter_readiness",
            "completed" if quarter.quarter_execution_allowed else "waiting",
            f"{quarter.quarter_status}: {quarter.status_reason}",
            quarter.id,
        )
        if not quarter.quarter_execution_allowed:
            trace.missing("Active Daye quarter is not ready for execution confirmation.")

        ssmt = SsmtService.evaluate(
            db,
            SsmtEvaluateRequest(
                trade_asset="XAUUSD",
                confirmation_symbol="XAGUSD",
                timeframe="H4",
                poi_touched=request.ssmt_poi_touched,
                poi_reference=request.ssmt_poi_reference,
                as_of_utc=cutoff,
            ),
        )
        run.ssmt_event_id = ssmt.id
        ssmt_ready = ssmt.ssmt_status in {"valid_bullish", "valid_bearish"}
        trace.add(
            "ssmt",
            "completed" if ssmt_ready else "waiting",
            f"SSMT status is {ssmt.ssmt_status}: {ssmt.status_reason}",
            ssmt.id,
        )
        if not ssmt_ready:
            trace.missing("Valid aligned XAU/XAG SSMT confirmation is not available.")

        primary = db.get(LiquidityLevel, dol.primary_level_id) if dol.primary_level_id else None
        engineered = (
            db.get(LiquidityLevel, dol.engineered_level_id)
            if dol.engineered_level_id
            else None
        )
        invalidation = engineered or NarrativeLedgerService.resolve_invalidation(db, dol, market)
        ledger = NarrativeLedgerService.ensure_active(
            db, dol, market, primary, invalidation, quarter, ssmt
        )
        if ledger is None:
            trace.add(
                "narrative_ledger",
                "waiting",
                "A target and invalidation boundary are required before a delivery ledger can be opened.",
            )
            trace.missing("Narrative ledger lacks a defined target and invalidation boundary.")
        else:
            ledger = NarrativeLedgerService.evaluate(
                db, request.symbol, request.execution_timeframe, cutoff
            )
            ledger = NarrativeLedgerService.apply_context_failure(db, ledger, dol, quarter, ssmt)
            run.narrative_ledger_id = ledger.id
            ledger_ready = (
                ledger.continuation_status in {"active", "continuing"} and not ledger.reset_required
            )
            trace.add(
                "narrative_ledger",
                "completed" if ledger_ready else "blocked",
                f"Narrative ledger is {ledger.continuation_status}: {ledger.status_reason}",
                ledger.id,
            )
            if not ledger_ready:
                trace.missing("Active narrative has failed or requires reset.")

        if ledger is not None:
            mmxm = MmxmService.evaluate(db, request.symbol, "H4", cutoff)
            run.mmxm_assessment_id = mmxm.id
            trace.add(
                "mmxm_timing",
                "completed" if not mmxm.timing_conflict.startswith("Timing conflict") else "waiting",
                f"{mmxm.active_model}: {mmxm.timing_conflict}",
                mmxm.id,
            )
            quality = DeliveryQualityService.evaluate(
                db, request.symbol, request.execution_timeframe, cutoff
            )
            run.delivery_quality_assessment_id = quality.id
            trace.add(
                "delivery_quality",
                "completed" if quality.expansion_status == "valid" else "waiting",
                f"{quality.expansion_quality}: {quality.status_reason}",
                quality.id,
            )
            execution = ExecutionService.evaluate(
                db,
                ExecutionEvaluateRequest(
                    symbol=request.symbol,
                    timeframe=request.execution_timeframe,
                    as_of_utc=cutoff,
                    minimum_rr=request.minimum_rr,
                ),
            )
            run.execution_assessment_id = execution.id
            trace.add(
                "execution_confirmation",
                "completed" if execution.execution_status == "Valid Setup" else "waiting",
                execution.no_trade_reason,
                execution.id,
            )
            if execution.execution_status != "Valid Setup":
                trace.missing("CISD/MSS, POI, and risk confirmation gates have not all passed.")
        else:
            trace.add(
                "execution_confirmation",
                "skipped",
                "Execution confirmation remains blocked until a narrative ledger exists.",
            )

        snapshot = NarrativeService.generate(
            db,
            NarrativeGenerateRequest(
                symbol=request.symbol,
                provider=request.provider,
                as_of_utc=cutoff,
            ),
        )
        run.narrative_snapshot_id = snapshot.id
        run.decision_status = snapshot.execution_status
        run.no_trade_reason = snapshot.no_trade_reason
        run.run_status = "ready" if snapshot.execution_status == "Valid Setup" else "blocked"
        trace.add(
            "narrative_output",
            "completed",
            f"Decision output recorded as {snapshot.execution_status}.",
            snapshot.id,
        )
        run.step_trace = json.dumps(trace.steps)
        run.missing_inputs = json.dumps(trace.missing_inputs)
        run.completed_at_utc = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get(db: Session, run_id: int) -> AnalysisRun | None:
        return db.get(AnalysisRun, run_id)

    @staticmethod
    def get_latest(db: Session, symbol: str) -> AnalysisRun | None:
        return (
            db.query(AnalysisRun)
            .filter(AnalysisRun.symbol == symbol)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .first()
        )

    @staticmethod
    def response(run: AnalysisRun) -> AnalysisRunResponse:
        return AnalysisRunResponse(
            id=run.id,
            symbol=run.symbol,
            as_of_utc=run.as_of_utc,
            sweep_timeframe=run.sweep_timeframe,
            execution_timeframe=run.execution_timeframe,
            minimum_rr=run.minimum_rr,
            provider=run.provider,
            run_status=run.run_status,
            decision_status=run.decision_status,
            no_trade_reason=run.no_trade_reason,
            steps=[AnalysisStepResponse(**step) for step in json.loads(run.step_trace)],
            missing_inputs=json.loads(run.missing_inputs),
            dol_assessment_id=run.dol_assessment_id,
            irl_erl_mapping_id=run.irl_erl_mapping_id,
            quarter_readiness_id=run.quarter_readiness_id,
            ssmt_event_id=run.ssmt_event_id,
            narrative_ledger_id=run.narrative_ledger_id,
            mmxm_assessment_id=run.mmxm_assessment_id,
            delivery_quality_assessment_id=run.delivery_quality_assessment_id,
            execution_assessment_id=run.execution_assessment_id,
            narrative_snapshot_id=run.narrative_snapshot_id,
            created_at=run.created_at,
            completed_at_utc=run.completed_at_utc,
        )
