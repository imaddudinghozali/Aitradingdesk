"""Basic replay policy — minimal Shadow-style shadow decisions.

Implements a conservative point-in-time rule set that respects PRD guardrails
without re-running the full reasoning chain:

1. Daye Quarter Gate — only Q2 (London) and Q3 (NY AM) qualify as expansion windows.
2. Sweep Detection — last completed candle must wick past the recent N-bar high (bearish setup)
   or low (bullish setup) with rejection (close back inside).
3. Direction Bias — recent close vs. 20-bar SMA decides bullish/bearish bias; sweep
   direction must oppose the bias (manipulation -> reversal toward DOL).
4. DOL / Target — next untaken N-bar extreme in the bias direction.
5. Invalidation — outside the swept wick by a small buffer (1 pip in price units).
6. RR gate — minimum RR ratio must be met.

This is a *shadow* heuristic, not a re-implementation of every backend gate. It
emits `No Trade` aggressively, matching PRD philosophy ("more No Trade than
setups"). Use it for raw-candle replay validation only.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.replay_policies.base import (
    ReplayContext,
    ReplayDecision,
    ReplayPolicy,
)


class BasicReplayPolicy(ReplayPolicy):
    name = "basic"

    def __init__(
        self,
        lookback_bars: int = 20,
        min_rr: Decimal = Decimal("2.0"),
        sweep_buffer_ticks: Decimal = Decimal("0.5"),
    ) -> None:
        self.lookback_bars = lookback_bars
        self.min_rr = min_rr
        self.sweep_buffer = sweep_buffer_ticks

    def decide(self, ctx: ReplayContext) -> ReplayDecision:
        candles = ctx.primary_candles
        if len(candles) < self.lookback_bars + 2:
            return _no_trade("Insufficient history for replay decision")

        quarter = ctx.time_context.get("daily_quarter")
        if quarter not in {"Q2", "Q3"}:
            return _no_trade(f"Quarter {quarter} is not an expansion window (need Q2 or Q3)")

        recent = candles[-self.lookback_bars : -1]
        last_completed = candles[-1]
        sma_close = sum((c.close for c in recent), Decimal(0)) / Decimal(len(recent))
        bias = "bullish" if last_completed.close >= sma_close else "bearish"

        recent_high = max(c.high for c in recent)
        recent_low = min(c.low for c in recent)

        if bias == "bullish":
            swept_low = last_completed.low < recent_low
            rejected = last_completed.close > recent_low
            if not (swept_low and rejected):
                return _no_trade("No bullish sweep + rejection of recent low")
            entry = last_completed.close
            target = recent_high
            invalidation = last_completed.low - self.sweep_buffer
            direction = "delivery_up"
        else:
            swept_high = last_completed.high > recent_high
            rejected = last_completed.close < recent_high
            if not (swept_high and rejected):
                return _no_trade("No bearish sweep + rejection of recent high")
            entry = last_completed.close
            target = recent_low
            invalidation = last_completed.high + self.sweep_buffer
            direction = "delivery_down"

        risk = abs(entry - invalidation)
        if risk <= 0:
            return _no_trade("Risk distance is zero or negative")
        reward = abs(target - entry)
        rr = reward / risk
        if rr < self.min_rr:
            return _no_trade(
                f"RR {rr:.2f} below minimum {self.min_rr} after sweep at quarter {quarter}"
            )

        return ReplayDecision(
            decision="Valid Setup",
            direction=direction,
            target_price=target,
            invalidation_price=invalidation,
            entry_reference=entry,
            expected_rr=rr,
            reason=(
                f"Daye {quarter} {bias} bias sweep of {self.lookback_bars}-bar "
                f"{'low' if bias == 'bullish' else 'high'} with rejection close; "
                f"target {target} / RR {rr:.2f}"
            ),
        )


def _no_trade(reason: str) -> ReplayDecision:
    return ReplayDecision(
        decision="No Trade",
        direction="none",
        target_price=None,
        invalidation_price=None,
        entry_reference=None,
        expected_rr=None,
        reason=reason,
    )
