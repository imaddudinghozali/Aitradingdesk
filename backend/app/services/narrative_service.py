from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.delivery_quality_assessment import DeliveryQualityAssessment
from app.models.dol_assessment import DolAssessment
from app.models.execution_assessment import ExecutionAssessment
from app.models.irl_erl_mapping import IrlErlMapping
from app.models.liquidity_level import LiquidityLevel
from app.models.market_snapshot import MarketSnapshot
from app.models.mmxm_assessment import MmxmAssessment
from app.models.narrative_ledger import NarrativeLedger
from app.models.narrative_snapshot import NarrativeSnapshot
from app.models.news_catalyst_event import NewsCatalystEvent
from app.models.quarter_readiness import QuarterReadinessAssessment
from app.models.ssmt_event import SsmtEvent
from app.models.sweep_event import SweepEvent
from app.schemas.narrative import NarrativeGenerateRequest, NarrativeProvider
from app.services.alert_service import AlertService
from app.services.claude_service import ClaudeNarrativeClient
from app.services.delivery_quality_service import DeliveryQualityService
from app.services.delivery_state_service import DeliveryStateService
from app.services.narrative_ledger_service import NarrativeLedgerService
from app.services.news_service import NewsCatalystService
from app.services.mmxm_service import MmxmService
from app.services.quarter_readiness_service import QuarterReadinessService
from app.services.ssmt_service import SsmtService
from app.services.telegram_service import TelegramService


class NarrativeService:
    READY_DOL = {"Active", "Shift Confirmed"}

    @staticmethod
    def generate(
        db: Session,
        request: NarrativeGenerateRequest,
        claude_client: ClaudeNarrativeClient | None = None,
    ) -> NarrativeSnapshot:
        dol = (
            db.query(DolAssessment)
            .filter(DolAssessment.symbol == request.symbol)
            .order_by(DolAssessment.as_of_utc.desc())
            .first()
        )
        if dol is None:
            raise ValueError("DOL assessment not found. Evaluate DOL before generating narrative.")
        mapping = (
            db.query(IrlErlMapping)
            .filter(IrlErlMapping.symbol == request.symbol)
            .order_by(IrlErlMapping.as_of_utc.desc())
            .first()
        )
        if mapping is None:
            raise ValueError(
                "Direction liquidity mapping not found. Evaluate IRL/ERL before generating narrative."
            )
        market_query = db.query(MarketSnapshot).filter(MarketSnapshot.symbol == request.symbol)
        if request.as_of_utc is not None:
            market_query = market_query.filter(
                MarketSnapshot.timestamp_utc <= NarrativeService._utc(request.as_of_utc)
            )
        market = market_query.order_by(
            MarketSnapshot.timestamp_utc.desc(), MarketSnapshot.id.desc()
        ).first()
        if market is None:
            raise ValueError("Market snapshot not found. Ingest market data before generating narrative.")

        primary = db.get(LiquidityLevel, dol.primary_level_id) if dol.primary_level_id else None
        engineered = (
            db.get(LiquidityLevel, dol.engineered_level_id)
            if dol.engineered_level_id
            else None
        )
        retracement = NarrativeService._retracement_reference(db, dol, market)
        invalidation = engineered or NarrativeLedgerService.resolve_invalidation(db, dol, market)
        sweep = (
            db.get(SweepEvent, dol.source_sweep_event_id)
            if dol.source_sweep_event_id
            else None
        )
        quarter = QuarterReadinessService.evaluate(db, request.symbol, market.timestamp_utc)
        ssmt = SsmtService.get_current(db) if request.symbol == "XAUUSD" else None
        ledger = NarrativeLedgerService.ensure_active(
            db, dol, market, primary, invalidation, quarter, ssmt
        )
        if ledger is not None:
            ledger = NarrativeLedgerService.evaluate(
                db, request.symbol, "M15", market.timestamp_utc
            )
            if ledger.reset_required:
                db.refresh(dol)
                quarter = QuarterReadinessService.evaluate(
                    db, request.symbol, market.timestamp_utc
                )
            ledger = NarrativeLedgerService.apply_context_failure(
                db, ledger, dol, quarter, ssmt
            )
        mmxm = (
            MmxmService.evaluate(db, request.symbol, "H4", market.timestamp_utc)
            if ledger is not None
            else None
        )
        delivery_quality = (
            DeliveryQualityService.evaluate(db, request.symbol, "M15", market.timestamp_utc)
            if ledger is not None
            else None
        )
        news = NewsCatalystService.get_current(db, request.symbol)
        execution = NarrativeService._current_execution(db, request.symbol, ledger, market)
        state = NarrativeService._state_context(
            dol, mapping, quarter, sweep, delivery_quality, market
        )
        locked = NarrativeService._locked_fields(
            dol,
            mapping,
            market,
            primary,
            engineered,
            sweep,
            quarter,
            ssmt,
            ledger,
            mmxm,
            delivery_quality,
            state,
            news,
            execution,
        )
        narrative = NarrativeService._rule_narrative(dol, mapping, market, primary, quarter, state)
        ai_enhanced = False
        model: str | None = None
        if request.provider == NarrativeProvider.CLAUDE:
            settings = get_settings()
            client = claude_client or ClaudeNarrativeClient(settings)
            narrative.update(client.generate({**locked, **narrative}))
            ai_enhanced = True
            model = settings.anthropic_model

        snapshot = NarrativeSnapshot(
            symbol=request.symbol,
            provider=request.provider.value,
            model=model,
            ai_enhanced=ai_enhanced,
            dol_assessment_id=dol.id,
            irl_erl_mapping_id=mapping.id,
            quarter_readiness_id=quarter.id,
            ssmt_event_id=ssmt.id if ssmt else None,
            narrative_ledger_id=ledger.id if ledger else None,
            mmxm_assessment_id=mmxm.id if mmxm else None,
            delivery_quality_assessment_id=delivery_quality.id if delivery_quality else None,
            news_catalyst_event_id=news.id if news else None,
            execution_assessment_id=execution.id if execution else None,
            source_sweep_event_id=sweep.id if sweep else None,
            session=market.session,
            session_anchor=market.session_anchor,
            daily_quarter=market.daily_quarter,
            quarter_status=quarter.quarter_status,
            next_valid_window=quarter.next_valid_window,
            htf_dol=locked["htf_dol"],
            dol_status=dol.lifecycle_status,
            direction_liquidity=mapping.direction_flow,
            active_model=locked["active_model"],
            macro_state=locked["macro_state"],
            quarterly_state=locked["quarterly_state"],
            session_state=locked["session_state"],
            intraday_state=locked["intraday_state"],
            conflict_resolution=locked["conflict_resolution"],
            news_catalyst_status=locked["news_catalyst_status"],
            delivery_tempo=locked["delivery_tempo"],
            delivery_state=narrative["delivery_state"],
            session_narrative=narrative["session_narrative"],
            judas_manipulation_status=locked["judas_manipulation_status"],
            opr_status=locked["opr_status"],
            mmxm_timing_context=locked["mmxm_timing_context"],
            ssmt_status=locked["ssmt_status"],
            expansion_quality=locked["expansion_quality"],
            setup_context=locked["setup_context"],
            trigger_confirmation=locked["trigger_confirmation"],
            risk_context=locked["risk_context"],
            execution_status=locked["execution_status"],
            no_trade_reason=locked["no_trade_reason"],
            validation_required=locked["validation_required"],
            continuation_status=locked["continuation_status"],
            reset_required=locked["reset_required"],
            next_decision_if_invalidated=locked["next_decision_if_invalidated"],
            invalidation=locked["invalidation"],
            target_liquidity=locked["target_liquidity"],
            retracement_reference=retracement,
            rendered_snapshot="",
            as_of_utc=market.timestamp_utc,
        )
        snapshot.rendered_snapshot = NarrativeService.render(snapshot)
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        DeliveryStateService.record_snapshot(db, snapshot)
        alert = AlertService.record_narrative(db, snapshot)
        NarrativeService._auto_send_telegram(db, snapshot)
        return snapshot

    @staticmethod
    def get_latest(db: Session, symbol: str) -> NarrativeSnapshot | None:
        return (
            db.query(NarrativeSnapshot)
            .filter(NarrativeSnapshot.symbol == symbol)
            .order_by(NarrativeSnapshot.created_at.desc(), NarrativeSnapshot.id.desc())
            .first()
        )

    @staticmethod
    def render(snapshot: NarrativeSnapshot) -> str:
        return "\n".join(
            [
                "MARKET DELIVERY SNAPSHOT",
                f"Pair: {snapshot.symbol}",
                f"Session: {snapshot.session}",
                f"Session Anchor: {snapshot.session_anchor}",
                f"Quarter (QT): {snapshot.daily_quarter}",
                f"Quarter Status: {snapshot.quarter_status}",
                f"HTF DOL: {snapshot.htf_dol}",
                f"DOL Status: {snapshot.dol_status}",
                f"Direction Liquidity: {snapshot.direction_liquidity}",
                f"Active Model: {snapshot.active_model}",
                f"Macro State: {snapshot.macro_state}",
                f"Quarterly State: {snapshot.quarterly_state}",
                f"Session State: {snapshot.session_state}",
                f"Intraday State: {snapshot.intraday_state}",
                f"Conflict Resolution: {snapshot.conflict_resolution}",
                f"News Catalyst: {snapshot.news_catalyst_status}",
                f"Delivery Tempo: {snapshot.delivery_tempo}",
                f"Delivery State: {snapshot.delivery_state}",
                f"Session Narrative: {snapshot.session_narrative}",
                f"Judas/Manipulation Status: {snapshot.judas_manipulation_status}",
                f"OPR Status: {snapshot.opr_status}",
                f"MMXM Timing Context: {snapshot.mmxm_timing_context}",
                f"SSMT XAU-XAG: {snapshot.ssmt_status}",
                f"Expansion Quality: {snapshot.expansion_quality}",
                f"Setup Context: {snapshot.setup_context}",
                f"Trigger Confirmation: {snapshot.trigger_confirmation}",
                f"Risk Context: {snapshot.risk_context}",
                f"Execution Status: {snapshot.execution_status}",
                f"No Trade Reason: {snapshot.no_trade_reason}",
                f"Validation Required: {snapshot.validation_required}",
                f"Narrative Status: {snapshot.continuation_status}",
                f"Reset Required: {snapshot.reset_required}",
                f"Next Decision If Invalidated: {snapshot.next_decision_if_invalidated}",
                f"Next Valid Window: {snapshot.next_valid_window}",
                f"Invalidation: {snapshot.invalidation}",
                f"Target Liquidity: {snapshot.target_liquidity}",
                f"Retracement Reference: {snapshot.retracement_reference or 'None - no untaken opposing liquidity nearby.'}",
            ]
        )

    @staticmethod
    def render_telegram(snapshot: NarrativeSnapshot) -> str:
        return "\n".join(
            [
                "SNAPSHOT MARKET DELIVERY",
                f"Pair: {snapshot.symbol}",
                f"Sesi: {NarrativeService._id_text(snapshot.session)}",
                f"Anchor Sesi: {snapshot.session_anchor}",
                f"Quarter (QT): {snapshot.daily_quarter}",
                f"Status Quarter: {NarrativeService._id_text(snapshot.quarter_status)}",
                f"DOL HTF: {NarrativeService._id_text(snapshot.htf_dol)}",
                f"Status DOL: {NarrativeService._id_text(snapshot.dol_status)}",
                f"Arah Likuiditas: {NarrativeService._id_text(snapshot.direction_liquidity)}",
                f"Model Aktif: {NarrativeService._id_text(snapshot.active_model)}",
                f"State Makro: {NarrativeService._id_text(snapshot.macro_state)}",
                f"State Quarterly: {NarrativeService._id_text(snapshot.quarterly_state)}",
                f"State Sesi: {NarrativeService._id_text(snapshot.session_state)}",
                f"State Intraday: {NarrativeService._id_text(snapshot.intraday_state)}",
                f"Resolusi Konflik: {NarrativeService._id_text(snapshot.conflict_resolution)}",
                f"Katalis News: {NarrativeService._id_text(snapshot.news_catalyst_status)}",
                f"Tempo Delivery: {NarrativeService._id_text(snapshot.delivery_tempo)}",
                f"State Delivery: {NarrativeService._id_text(snapshot.delivery_state)}",
                f"Narrative Sesi: {NarrativeService._id_text(snapshot.session_narrative)}",
                f"Status Judas/Manipulasi: {NarrativeService._id_text(snapshot.judas_manipulation_status)}",
                f"Status OPR: {NarrativeService._id_text(snapshot.opr_status)}",
                f"Konteks Timing MMXM: {NarrativeService._id_text(snapshot.mmxm_timing_context)}",
                f"SSMT XAU-XAG: {NarrativeService._id_text(snapshot.ssmt_status)}",
                f"Kualitas Ekspansi: {NarrativeService._id_text(snapshot.expansion_quality)}",
                f"Konteks Setup: {NarrativeService._id_text(snapshot.setup_context)}",
                f"Konfirmasi Trigger: {NarrativeService._id_text(snapshot.trigger_confirmation)}",
                f"Konteks Risiko: {NarrativeService._id_text(snapshot.risk_context)}",
                f"Status Eksekusi: {NarrativeService._id_text(snapshot.execution_status)}",
                f"Alasan Tidak Ada Trade: {NarrativeService._id_text(snapshot.no_trade_reason)}",
                f"Validasi Wajib: {NarrativeService._id_text(snapshot.validation_required)}",
                f"Status Narrative: {NarrativeService._id_text(snapshot.continuation_status)}",
                f"Perlu Reset: {NarrativeService._id_text(snapshot.reset_required)}",
                f"Keputusan Jika Invalidated: {NarrativeService._id_text(snapshot.next_decision_if_invalidated)}",
                f"Window Valid Berikutnya: {NarrativeService._id_text(snapshot.next_valid_window)}",
                f"Invalidation: {NarrativeService._id_text(snapshot.invalidation)}",
                f"Target Likuiditas: {NarrativeService._id_text(snapshot.target_liquidity)}",
                "Referensi Retracement: "
                + NarrativeService._id_text(
                    snapshot.retracement_reference
                    or "None - no untaken opposing liquidity nearby."
                ),
            ]
        )

    @staticmethod
    def _id_text(value: object) -> str:
        if isinstance(value, bool):
            return "Ya" if value else "Tidak"
        text = str(value)
        replacements = [
            ("No Trade", "Tidak Ada Trade"),
            ("Valid Setup", "Setup Valid"),
            ("Waiting", "Menunggu"),
            ("waiting", "menunggu"),
            ("None", "Tidak ada"),
            ("not configured", "belum dikonfigurasi"),
            ("not defined", "belum didefinisikan"),
            ("not available", "belum tersedia"),
            ("not evaluated", "belum dievaluasi"),
            ("not confirmed", "belum terkonfirmasi"),
            ("not aligned", "belum selaras"),
            ("No aligned", "Tidak ada yang selaras"),
            ("No valid", "Tidak ada yang valid"),
            ("Narrative incomplete", "Narrative belum lengkap"),
            ("Narrative status", "Status narrative"),
            ("Narrative failed", "Narrative gagal"),
            ("DOL status", "Status DOL"),
            ("Direction liquidity status", "Status likuiditas arah"),
            ("Quarter readiness", "Kesiapan quarter"),
            ("Delivery quality", "Kualitas delivery"),
            ("CISD/MSS execution confirmation", "Konfirmasi eksekusi CISD/MSS"),
            ("execution confirmation", "konfirmasi eksekusi"),
            ("execution setup", "setup eksekusi"),
            ("execution POI", "POI eksekusi"),
            ("confirmation gate", "gate konfirmasi"),
            ("target liquidity", "target likuiditas"),
            ("Target Liquidity", "Target Likuiditas"),
            ("invalidation level", "level invalidation"),
            ("next decision", "keputusan berikutnya"),
            ("Reset DOL identification", "Reset identifikasi DOL"),
            ("fresh DOL identification", "identifikasi DOL baru"),
            ("Active objective is suspended", "Objective aktif ditangguhkan"),
            ("Current status", "Status saat ini"),
            ("Current session state", "State sesi saat ini"),
            ("Session inheritance", "Warisan sesi"),
            ("market snapshot", "snapshot market"),
            ("high-impact", "impact tinggi"),
            ("post-news", "setelah news"),
            ("news catalyst", "katalis news"),
            ("discretionary trader review is required", "review trader discretionary wajib"),
            ("this output never emits an order", "output ini tidak pernah mengirim order"),
            ("no order is emitted", "tidak ada order yang dikirim"),
            ("before any execution setup can be considered", "sebelum setup eksekusi boleh dipertimbangkan"),
            ("before any new setup", "sebelum setup baru"),
            ("before considering delivery", "sebelum mempertimbangkan delivery"),
            ("remains", "tetap"),
            ("requires", "membutuhkan"),
            ("required", "wajib"),
            ("available", "tersedia"),
            ("defined", "didefinisikan"),
            ("aligned", "selaras"),
            ("valid", "valid"),
            ("active", "aktif"),
            ("continuing", "berlanjut"),
            ("weakening", "melemah"),
            ("failed", "gagal"),
            ("blocked", "terblokir"),
            ("delayed expansion", "ekspansi tertunda"),
            ("compressed delivery", "delivery terkompresi"),
            ("slow delivery", "delivery lambat"),
            ("exhausted expansion", "ekspansi exhausted"),
            ("healthy expansion", "ekspansi sehat"),
            ("weak expansion", "ekspansi lemah"),
            ("terminal expansion", "ekspansi terminal"),
            ("manipulation", "manipulasi"),
            ("accumulation", "akumulasi"),
            ("expansion", "ekspansi"),
            ("repricing", "repricing"),
            ("redistribution", "redistribusi"),
            ("exhaustion", "exhaustion"),
            ("continuation", "kontinuasi"),
            ("Unconfirmed", "Belum terkonfirmasi"),
            ("Close", "Close"),
        ]
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    @staticmethod
    def _locked_fields(
        dol: DolAssessment,
        mapping: IrlErlMapping,
        market: MarketSnapshot,
        primary: LiquidityLevel | None,
        engineered: LiquidityLevel | None,
        sweep: SweepEvent | None,
        quarter: QuarterReadinessAssessment,
        ssmt: SsmtEvent | None,
        ledger: NarrativeLedger | None,
        mmxm: MmxmAssessment | None,
        delivery_quality: DeliveryQualityAssessment | None,
        state: dict[str, str],
        news: NewsCatalystEvent | None,
        execution: ExecutionAssessment | None,
    ) -> dict[str, object]:
        reasons: list[str] = []
        if dol.lifecycle_status not in NarrativeService.READY_DOL:
            reasons.append(f"DOL status is {dol.lifecycle_status}.")
        if mapping.mapping_status != "aligned":
            reasons.append(f"Direction liquidity status is {mapping.mapping_status}.")
        if primary is None:
            reasons.append("Target liquidity is not defined.")
        if ledger is None:
            reasons.append("Narrative incomplete - invalidation level and next decision are not defined.")
        if not quarter.quarter_execution_allowed:
            reasons.append(
                f"Quarter readiness is {quarter.quarter_status}: {quarter.status_reason}"
            )
        if ssmt is None or ssmt.ssmt_status not in {"valid_bullish", "valid_bearish"}:
            reasons.append(
                "SSMT is not valid for confluence."
                if ssmt is None
                else f"SSMT status is {ssmt.ssmt_status}: {ssmt.status_reason}"
            )
        if ledger is not None and ledger.continuation_status in {"weakening", "failed", "reversed"}:
            reasons.append(
                f"Narrative status is {ledger.continuation_status}: {ledger.status_reason}"
            )
        if delivery_quality is None:
            reasons.append("Delivery quality cannot be assessed without a complete narrative ledger.")
        elif delivery_quality.expansion_status != "valid":
            reasons.append(
                f"Delivery quality is {delivery_quality.expansion_quality}: "
                f"{delivery_quality.status_reason}"
            )
        if state["conflict_resolution"] != "Aligned - no cross-layer delivery conflict detected.":
            reasons.append(state["conflict_resolution"])
        if news is not None:
            reasons.append(news.no_trade_reason)
        if execution is None:
            reasons.append("CISD/MSS execution confirmation has not been evaluated for the current market snapshot.")
        elif execution.execution_status != "Valid Setup":
            reasons.append(execution.no_trade_reason)
        valid_execution = not reasons and execution is not None and execution.execution_status == "Valid Setup"
        return {
            "session": market.session,
            "session_anchor": market.session_anchor,
            "daily_quarter": market.daily_quarter,
            "quarter_status": quarter.quarter_status,
            "next_valid_window": quarter.next_valid_window,
            "htf_dol": NarrativeService._level_text(primary, "Unconfirmed"),
            "active_model": MmxmService.display_model(mmxm),
            "macro_state": state["macro_state"],
            "quarterly_state": state["quarterly_state"],
            "session_state": state["session_state"],
            "intraday_state": state["intraday_state"],
            "conflict_resolution": state["conflict_resolution"],
            "news_catalyst_status": (
                f"{news.event_name} - {news.news_phase} / {news.catalyst_status}: {news.status_reason}"
                if news
                else "None scheduled or evaluated."
            ),
            "delivery_tempo": (
                delivery_quality.delivery_tempo if delivery_quality else "delayed expansion"
            ),
            "expansion_quality": DeliveryQualityService.display_quality(delivery_quality),
            "judas_manipulation_status": MmxmService.display_judas(mmxm),
            "opr_status": (
                mmxm.opr_status
                if mmxm
                else "Waiting - OPR context has not been evaluated."
            ),
            "mmxm_timing_context": (
                f"{mmxm.timing_probability}: {mmxm.timing_conflict}"
                if mmxm
                else "Waiting - MMXM timing context has not been evaluated."
            ),
            "ssmt_status": SsmtService.display_status(ssmt),
            "setup_context": (
                execution.setup_context
                if execution
                else "Waiting for execution POI and confirmation evaluation."
            ),
            "trigger_confirmation": (
                execution.trigger_confirmation
                if execution
                else "Waiting - execute the confirmation gate on M5/M15/H1."
            ),
            "risk_context": (
                NarrativeService._risk_text(execution)
                if execution
                else "Waiting - invalidation, target, and minimum RR must be checked by execution gate."
            ),
            "execution_status": "Valid Setup" if valid_execution else "No Trade",
            "no_trade_reason": (
                "None - backend confirmation gates passed; setup context only, no order is emitted."
                if valid_execution
                else " ".join(reasons)
            ),
            "validation_required": (
                "Discretionary trader review is required; this output never emits an order."
                if valid_execution
                else "Define POI and validate CISD/MSS before any execution setup can be considered."
            ),
            "continuation_status": ledger.continuation_status if ledger else "weakening",
            "reset_required": ledger.reset_required if ledger else True,
            "next_decision_if_invalidated": (
                ledger.next_decision_if_invalidated
                if ledger
                else "Define invalidation and restart top-down analysis before considering delivery."
            ),
            "invalidation": NarrativeLedgerService.invalidation_text(ledger),
            "target_liquidity": NarrativeService._level_text(primary, "Unconfirmed"),
            "sweep_status": sweep.sweep_status if sweep else "none",
        }

    @staticmethod
    def _auto_send_telegram(db: Session, snapshot: NarrativeSnapshot) -> None:
        settings = get_settings()
        if not settings.telegram_auto_send_narrative:
            return
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            snapshot.telegram_status = "not_configured"
            db.commit()
            db.refresh(snapshot)
            return
        try:
            message_id = TelegramService.send_message(
                settings,
                NarrativeService.render_telegram(snapshot),
            )
        except Exception:
            snapshot.telegram_status = "failed"
            db.commit()
            db.refresh(snapshot)
            return
        snapshot.telegram_status = "sent"
        snapshot.telegram_message_id = message_id
        AlertService.mark_telegram_sent(db, snapshot.id, message_id)
        db.commit()
        db.refresh(snapshot)

    @staticmethod
    def _current_execution(
        db: Session,
        symbol: str,
        ledger: NarrativeLedger | None,
        market: MarketSnapshot,
    ) -> ExecutionAssessment | None:
        if ledger is None:
            return None
        execution = (
            db.query(ExecutionAssessment)
            .filter(
                ExecutionAssessment.symbol == symbol,
                ExecutionAssessment.narrative_ledger_id == ledger.id,
                ExecutionAssessment.as_of_utc == market.timestamp_utc,
            )
            .order_by(ExecutionAssessment.id.desc())
            .first()
        )
        if execution is None:
            return None
        return execution

    @staticmethod
    def _risk_text(execution: ExecutionAssessment) -> str:
        rr = NarrativeService._price(execution.rr_ratio) if execution.rr_ratio is not None else "unavailable"
        entry = NarrativeService._price(execution.entry_reference) if execution.entry_reference is not None else "unavailable"
        target = NarrativeService._price(execution.target_price) if execution.target_price is not None else "unavailable"
        return (
            f"Entry reference {entry}; invalidation {NarrativeService._price(execution.invalidation_price)}; "
            f"target {target}; RR {rr} versus minimum {NarrativeService._price(execution.minimum_rr)} "
            f"({execution.risk_status})."
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _rule_narrative(
        dol: DolAssessment,
        mapping: IrlErlMapping,
        market: MarketSnapshot,
        primary: LiquidityLevel | None,
        quarter: QuarterReadinessAssessment,
        state: dict[str, str],
    ) -> dict[str, str]:
        target = NarrativeService._level_text(primary, "unconfirmed target liquidity")
        return {
            "delivery_state": (
                f"{state['macro_state']} / {state['quarterly_state']} / "
                f"{state['intraday_state']}: {mapping.direction_flow} toward {target}."
            ),
            "session_narrative": NarrativeService._session_inheritance(
                market, quarter, state["session_state"], mapping.direction_flow
            ),
        }

    @staticmethod
    def _state_context(
        dol: DolAssessment,
        mapping: IrlErlMapping,
        quarter: QuarterReadinessAssessment,
        sweep: SweepEvent | None,
        delivery_quality: DeliveryQualityAssessment | None,
        market: MarketSnapshot,
    ) -> dict[str, str]:
        macro = {
            "Active": "continuation",
            "Shift Confirmed": "repricing",
            "Weakening": "exhaustion",
            "Shift Pending": "redistribution",
            "Invalidated": "redistribution",
        }.get(dol.lifecycle_status, "accumulation")
        quarterly = {
            "Forming": "accumulation",
            "Manipulation Phase": "manipulation",
            "Expansion Ready": "repricing",
            "Expansion Active": "expansion",
            "Failure Risk": "exhaustion",
            "Closed / Late Entry": "redistribution",
        }.get(quarter.quarter_status, "accumulation")
        if sweep and sweep.sweep_status == "Manipulation Sweep":
            session = "manipulation"
        elif sweep and sweep.displacement_detected:
            session = "expansion"
        elif market.session in {"Asia", "London"}:
            session = "accumulation"
        else:
            session = "repricing"
        if delivery_quality is None:
            intraday = "accumulation"
        elif delivery_quality.terminal_expansion:
            intraday = "exhaustion"
        elif delivery_quality.engineered_expansion:
            intraday = "manipulation"
        elif delivery_quality.expansion_status == "valid":
            intraday = "expansion"
        else:
            intraday = "repricing"
        conflict = "Aligned - no cross-layer delivery conflict detected."
        if mapping.mapping_status != "aligned":
            conflict = "Conflict resolution - direction liquidity is not aligned; suspend delivery narrative and remain No Trade."
        elif macro in {"exhaustion", "redistribution"} and intraday == "expansion":
            conflict = "Conflict resolution - intraday expansion opposes weakened macro delivery; reset DOL before continuation."
        elif quarter.quarter_status in {"Failure Risk", "Closed / Late Entry"} and intraday == "expansion":
            conflict = "Conflict resolution - intraday expansion occurs in a blocked quarter; do not promote it to execution."
        return {
            "macro_state": macro,
            "quarterly_state": quarterly,
            "session_state": session,
            "intraday_state": intraday,
            "conflict_resolution": conflict,
        }

    @staticmethod
    def _session_inheritance(
        market: MarketSnapshot,
        quarter: QuarterReadinessAssessment,
        session_state: str,
        direction_flow: str,
    ) -> str:
        inheritance = {
            "Asia": "Asia is forming range/liquidity build-up for later sessions.",
            "London": "London inherits Asia liquidity and may form manipulation or early continuation.",
            "NY AM": "NY inherits London liquidity and must confirm expansion, repricing, or reversal.",
            "NY PM": "NY PM inherits the morning delivery and monitors continuation versus exhaustion.",
            "London Close": "London Close inherits completed intraday delivery and monitors failure or reversal.",
        }.get(market.session, "Session inheritance is waiting for recognized session context.")
        return (
            f"{inheritance} Current session state is {session_state}; {market.daily_quarter} "
            f"is {quarter.quarter_status} for {direction_flow}."
        )

    @staticmethod
    def _retracement_reference(
        db: Session,
        dol: DolAssessment,
        market: MarketSnapshot,
    ) -> str:
        """Nearest untaken liquidity on the side OPPOSITE the DOL direction.

        When DOL delivery is down, the realistic near-term draw before a far HTF
        target is a retracement UP into the nearest untaken BSL (swing high /
        session high). This is a context reference only, never a trade target.
        """
        direction = dol.delivery_direction
        if direction not in {"delivery_up", "delivery_down"}:
            return ""
        opposing_side = "SSL" if direction == "delivery_up" else "BSL"
        price = market.close
        levels = (
            db.query(LiquidityLevel)
            .filter(
                LiquidityLevel.symbol == dol.symbol,
                LiquidityLevel.liquidity_side == opposing_side,
                LiquidityLevel.status.in_(["active", "touched"]),
            )
            .all()
        )
        if opposing_side == "BSL":
            candidates = [lv for lv in levels if lv.price > price]
        else:
            candidates = [lv for lv in levels if lv.price < price]
        if not candidates:
            return ""
        nearest = min(candidates, key=lambda lv: abs(lv.price - price))
        side_word = "above" if opposing_side == "BSL" else "below"
        return (
            f"{nearest.level_type} {opposing_side} at {NarrativeService._price(nearest.price)} "
            f"({side_word} price) - nearest opposing liquidity if delivery retraces before "
            f"the {direction.replace('delivery_', '')} HTF objective."
        )

    @staticmethod
    def _level_text(level: LiquidityLevel | None, fallback: str) -> str:
        if level is None:
            return fallback
        return f"{level.level_type} {level.liquidity_side} at {NarrativeService._price(level.price)}"

    @staticmethod
    def _price(value: Decimal) -> str:
        return format(value.normalize(), "f")
