import json
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import AlertRecord, DeliveryStateRecord, DolAssessment, IrlErlMapping, LiquidityLevel, NarrativeSnapshot, SsmtEvent  # noqa: F401
from app.routers.narrative import send_narrative_to_telegram
from app.schemas.market import MarketDataInput
from app.schemas.narrative import NarrativeGenerateRequest, NarrativeProvider, TelegramSendRequest
from app.services.claude_service import ClaudeNarrativeClient
from app.services.market_service import MarketService
from app.services.narrative_service import NarrativeService
from app.utils.timezone import NY_TZ


class FakeClaudeClient:
    def generate(self, context: dict[str, object]) -> dict[str, str]:
        return {
            "delivery_state": "Refined observation toward external liquidity.",
            "session_narrative": "Session remains under observation; confirmation is absent.",
            "judas_manipulation_status": "Waiting for later model validation.",
            "expansion_quality": "Quality is not validated.",
            "execution_status": "Valid Setup",
        }


class FakeHTTPResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class NarrativeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings_patcher = patch(
            "app.services.narrative_service.get_settings",
            return_value=Settings(telegram_auto_send_narrative=False),
        )
        self.settings_patcher.start()
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.db = Session(bind=engine)
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
                open=2450,
                high=2455,
                low=2445,
                close=2450,
            ),
        )
        primary = self.level("PWH", "BSL", 2500)
        engineered = self.level("PWL", "SSL", 2400, "taken")
        dol = DolAssessment(
            symbol="XAUUSD",
            lifecycle_status="Active",
            delivery_direction="delivery_up",
            primary_level_id=primary.id,
            engineered_level_id=engineered.id,
            objective_quality="true_objective",
            status_reason="test active DOL",
            old_objective_resolved=False,
            displacement_confirmed=True,
            timing_confirmed=True,
            prior_narrative_resolved=False,
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
        )
        self.db.add(dol)
        self.db.commit()
        self.db.refresh(dol)
        mapping = IrlErlMapping(
            symbol="XAUUSD",
            dol_assessment_id=dol.id,
            direction_flow="ERL -> IRL -> ERL",
            mapping_status="aligned",
            status_reason="test alignment",
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
        )
        self.db.add(mapping)
        self.db.commit()

    def tearDown(self) -> None:
        self.settings_patcher.stop()
        self.db.close()

    def level(self, level_type: str, side: str, price: int, status: str = "active") -> LiquidityLevel:
        level = LiquidityLevel(
            symbol="XAUUSD",
            level_type=level_type,
            liquidity_side=side,
            price=Decimal(price),
            status=status,
            source_timeframe="D",
            source_period_start_ny=datetime(2026, 5, 19, 0, tzinfo=NY_TZ),
            source_period_end_ny=datetime(2026, 5, 20, 5, tzinfo=NY_TZ),
            as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            status_reason="test level",
        )
        self.db.add(level)
        self.db.commit()
        self.db.refresh(level)
        return level

    def test_rules_snapshot_is_consistent_and_locked_to_no_trade(self) -> None:
        snapshot = NarrativeService.generate(
            self.db,
            NarrativeGenerateRequest(provider=NarrativeProvider.RULES),
        )

        self.assertFalse(snapshot.ai_enhanced)
        self.assertEqual("No Trade", snapshot.execution_status)
        self.assertIn("CISD/MSS", snapshot.no_trade_reason)
        self.assertIn("MARKET DELIVERY SNAPSHOT", snapshot.rendered_snapshot)
        self.assertIn("Quarter Status: Closed / Late Entry", snapshot.rendered_snapshot)
        self.assertIn("Next Valid Window: Next Q4", snapshot.rendered_snapshot)
        self.assertIn("Narrative Status: active", snapshot.rendered_snapshot)
        self.assertIn("Target Liquidity: PWH BSL at 2500", snapshot.rendered_snapshot)
        self.assertIn("SSMT XAU-XAG: Waiting", snapshot.rendered_snapshot)
        self.assertIn("Delivery Tempo: delayed expansion", snapshot.rendered_snapshot)
        self.assertIn("weak expansion", snapshot.expansion_quality)
        self.assertIn("Macro State:", snapshot.rendered_snapshot)
        self.assertIn("Conflict Resolution:", snapshot.rendered_snapshot)
        self.assertIn("News Catalyst: None scheduled or evaluated.", snapshot.rendered_snapshot)
        self.assertIn("OPR Status:", snapshot.rendered_snapshot)
        self.assertIn("MMXM Timing Context:", snapshot.rendered_snapshot)
        alert = self.db.query(AlertRecord).filter(AlertRecord.narrative_snapshot_id == snapshot.id).one()
        self.assertEqual("narrative_snapshot", alert.event_type)
        self.assertFalse(alert.sent_to_telegram)
        states = self.db.query(DeliveryStateRecord).filter(DeliveryStateRecord.narrative_snapshot_id == snapshot.id).all()
        self.assertEqual({"macro", "quarterly", "session", "intraday"}, {state.timeframe_layer for state in states})

    def test_claude_text_cannot_replace_backend_execution_status(self) -> None:
        snapshot = NarrativeService.generate(
            self.db,
            NarrativeGenerateRequest(provider=NarrativeProvider.CLAUDE),
            claude_client=FakeClaudeClient(),
        )

        self.assertTrue(snapshot.ai_enhanced)
        self.assertEqual("No Trade", snapshot.execution_status)
        self.assertNotIn("Valid Setup", snapshot.rendered_snapshot)
        self.assertIn("Refined observation", snapshot.delivery_state)
        self.assertNotIn("Waiting for later model validation", snapshot.judas_manipulation_status)
        self.assertNotEqual("Quality is not validated.", snapshot.expansion_quality)

    @patch("app.routers.narrative.TelegramService.send_message", return_value="901")
    def test_telegram_endpoint_marks_snapshot_sent(self, send_message) -> None:
        snapshot = NarrativeService.generate(self.db, NarrativeGenerateRequest())

        response = send_narrative_to_telegram(
            snapshot.id,
            TelegramSendRequest(chat_id="test-chat"),
            self.db,
        )

        self.assertEqual("sent", response.telegram_status)
        self.assertEqual("901", response.telegram_message_id)
        alert = self.db.query(AlertRecord).filter(AlertRecord.narrative_snapshot_id == snapshot.id).one()
        self.assertTrue(alert.sent_to_telegram)
        self.assertEqual("901", alert.telegram_message_id)
        send_message.assert_called_once()
        sent_text = send_message.call_args.args[1]
        self.assertIn("SNAPSHOT MARKET DELIVERY", sent_text)
        self.assertIn("Status Eksekusi: Tidak Ada Trade", sent_text)
        self.assertIn("Alasan Tidak Ada Trade:", sent_text)
        self.assertNotIn("MARKET DELIVERY SNAPSHOT", sent_text)
        self.assertNotIn("Execution Status:", sent_text)

    @patch("app.services.narrative_service.TelegramService.send_message", return_value="902")
    @patch(
        "app.services.narrative_service.get_settings",
        return_value=Settings(
            telegram_bot_token="bot-token",
            telegram_chat_id="chat-id",
            telegram_auto_send_narrative=True,
        ),
    )
    def test_generate_auto_sends_telegram_when_enabled(self, _settings, send_message) -> None:
        snapshot = NarrativeService.generate(self.db, NarrativeGenerateRequest())

        self.assertEqual("sent", snapshot.telegram_status)
        self.assertEqual("902", snapshot.telegram_message_id)
        alert = self.db.query(AlertRecord).filter(AlertRecord.narrative_snapshot_id == snapshot.id).one()
        self.assertTrue(alert.sent_to_telegram)
        self.assertEqual("902", alert.telegram_message_id)
        sent_text = send_message.call_args.args[1]
        self.assertIn("SNAPSHOT MARKET DELIVERY", sent_text)
        self.assertIn("Status Eksekusi: Tidak Ada Trade", sent_text)

    def test_latest_valid_ssmt_is_included_in_snapshot(self) -> None:
        self.db.add(
            SsmtEvent(
                trade_asset="XAUUSD",
                confirmation_symbol="XAGUSD",
                timeframe="H4",
                ssmt_status="valid_bullish",
                direction="bullish",
                cic_detected=True,
                quarter_sequence_valid=True,
                magneto_status="clear",
                poi_touched=True,
                ssmt_dol_alignment="aligned",
                ssmt_noise_status="clear",
                xau_relative_state="relative_strength",
                confirmation_pair_state="XAU Higher Low; XAG Lower Low.",
                liquidity_context="SSL swept before SSMT formation.",
                status_reason="Valid bullish SSMT fixture.",
                as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC),
            )
        )
        self.db.commit()

        snapshot = NarrativeService.generate(self.db, NarrativeGenerateRequest())

        self.assertIn("VALID BULLISH", snapshot.ssmt_status)
        self.assertIn("trade asset XAUUSD only", snapshot.rendered_snapshot)

    def test_decision_cutoff_does_not_read_future_market_snapshot(self) -> None:
        MarketService.create_snapshot(
            self.db,
            MarketDataInput(
                symbol="XAUUSD",
                timeframe="M15",
                timestamp_utc=datetime(2026, 5, 20, 16, tzinfo=UTC),
                open=2500,
                high=2510,
                low=2490,
                close=2505,
            ),
        )

        snapshot = NarrativeService.generate(
            self.db,
            NarrativeGenerateRequest(as_of_utc=datetime(2026, 5, 20, 15, tzinfo=UTC)),
        )

        self.assertEqual(datetime(2026, 5, 20, 15), snapshot.as_of_utc)


class ClaudeNarrativeClientTest(unittest.TestCase):
    @patch("app.services.claude_service.urlopen")
    def test_raw_trade_instruction_is_rejected(self, urlopen) -> None:
        content = {
            "delivery_state": "Buy immediately.",
            "session_narrative": "Observation.",
            "judas_manipulation_status": "Waiting.",
            "expansion_quality": "Waiting.",
        }
        urlopen.return_value = FakeHTTPResponse(
            {"content": [{"type": "text", "text": json.dumps(content)}]}
        )
        client = ClaudeNarrativeClient(
            Settings(
                anthropic_api_key="test-key",
                anthropic_api_format="anthropic",
                anthropic_auth_scheme="x-api-key",
            )
        )

        with self.assertRaisesRegex(RuntimeError, "disallowed execution instruction"):
            client.generate({"symbol": "XAUUSD"})

    @patch("app.services.claude_service.urlopen")
    def test_openai_compatible_router_response_is_supported(self, urlopen) -> None:
        content = {
            "delivery_state": "Delivery remains observational.",
            "session_narrative": "Session context is waiting for confirmation.",
        }
        urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": json.dumps(content)}}]}
        )
        client = ClaudeNarrativeClient(
            Settings(
                anthropic_api_key="router-key",
                anthropic_base_url="https://agentrouter.org/v1",
                anthropic_api_format="openai",
                anthropic_auth_scheme="bearer",
            )
        )

        narrative = client.generate({"symbol": "XAUUSD"})
        request = urlopen.call_args.args[0]

        self.assertEqual(content, narrative)
        self.assertEqual("https://agentrouter.org/v1/chat/completions", request.full_url)
        self.assertEqual("Bearer router-key", request.headers["Authorization"])


if __name__ == "__main__":
    unittest.main()
