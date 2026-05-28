"""Replay policy interface — emits hypothetical decisions point-in-time."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models.market_snapshot import MarketSnapshot


@dataclass(frozen=True)
class ReplayContext:
    """Information available to a policy at decision time.

    Only candles up to and including `as_of_utc` may be inspected. The replay
    engine builds this strictly to avoid look-ahead.
    """

    symbol: str
    timeframe: str
    as_of_utc: datetime
    primary_candles: list[MarketSnapshot]
    secondary_candles: list[MarketSnapshot]
    time_context: dict


@dataclass(frozen=True)
class ReplayDecision:
    """Hypothetical decision emitted by a policy."""

    decision: str  # "Valid Setup" | "No Trade"
    direction: str  # "delivery_up" | "delivery_down" | "none"
    target_price: Decimal | None
    invalidation_price: Decimal | None
    entry_reference: Decimal | None
    expected_rr: Decimal | None
    reason: str


class ReplayPolicy(ABC):
    name: str = "base"

    @abstractmethod
    def decide(self, ctx: ReplayContext) -> ReplayDecision:
        """Return a decision based only on context up to `as_of_utc`."""
