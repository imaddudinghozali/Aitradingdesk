"""Daye Quarterly Theory time-ladder builder.

Produces the nested fractal grid (90 Minute / Day / Week), each row split into
its consecutive quarters across a shared trailing window so the rows align on a
common time axis. The cell containing `as_of` is flagged `is_current`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from app.engines.time_engine import TimeEngine
from app.utils.timezone import now_utc, to_ny_time, to_utc_time

_QUARTER_START_HOUR = {"Q1": 18, "Q2": 0, "Q3": 6, "Q4": 12}
_QUARTER_INDEX = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
_WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Trailing span of the shared time axis.
_WINDOW = timedelta(days=4)


@dataclass(frozen=True)
class LadderCell:
    label: str
    sub_label: str
    quarter_index: int
    start_utc: datetime
    end_utc: datetime
    is_current: bool


@dataclass(frozen=True)
class LadderRow:
    cycle: str
    cells: list[LadderCell]


@dataclass(frozen=True)
class QuarterLadder:
    as_of_utc: datetime
    window_start_utc: datetime
    window_end_utc: datetime
    now_ratio: float
    rows: list[LadderRow]


def _day_quarter_start_ny(dt_ny: datetime) -> datetime:
    quarter = TimeEngine.get_daily_quarter(dt_ny).value
    return dt_ny.replace(
        hour=_QUARTER_START_HOUR[quarter], minute=0, second=0, microsecond=0
    )


def _micro_start_ny(dt_ny: datetime) -> datetime:
    day_start = _day_quarter_start_ny(dt_ny)
    elapsed = int((dt_ny - day_start).total_seconds() // 60)
    bucket = (elapsed // 90) * 90
    return day_start + timedelta(minutes=bucket)


def _calendar_day_start_ny(dt_ny: datetime) -> datetime:
    return dt_ny.replace(hour=0, minute=0, second=0, microsecond=0)


def _build_row(
    cycle: str,
    cell_start_fn: Callable[[datetime], datetime],
    length: timedelta,
    label_fn: Callable[[datetime], tuple[str, str, int]],
    window_start_ny: datetime,
    window_end_ny: datetime,
    now_ny: datetime,
) -> LadderRow:
    cells: list[LadderCell] = []
    cursor = cell_start_fn(window_start_ny)
    guard = 0
    while cursor < window_end_ny and guard < 4000:
        guard += 1
        end = cursor + length
        label, sub_label, index = label_fn(cursor)
        cells.append(
            LadderCell(
                label=label,
                sub_label=sub_label,
                quarter_index=index,
                start_utc=to_utc_time(cursor),
                end_utc=to_utc_time(end),
                is_current=cursor <= now_ny < end,
            )
        )
        cursor = end
    return LadderRow(cycle=cycle, cells=cells)


def _day_label(start_ny: datetime) -> tuple[str, str, int]:
    quarter = TimeEngine.get_daily_quarter(start_ny).value
    return quarter, TimeEngine.get_session(start_ny).value, _QUARTER_INDEX[quarter]


def _micro_label(start_ny: datetime) -> tuple[str, str, int]:
    label = TimeEngine.get_micro_quarter(start_ny)  # e.g. "Q3.2"
    micro_index = int(label.split(".")[1])
    return label, start_ny.strftime("%H:%M"), micro_index


def _week_label(start_ny: datetime) -> tuple[str, str, int]:
    quarter = TimeEngine.get_weekly_quarter(start_ny)
    return quarter, _WEEKDAY_SHORT[start_ny.weekday()], _QUARTER_INDEX[quarter]


def build_ladder(as_of_utc: datetime | None = None) -> QuarterLadder:
    as_of = as_of_utc or now_utc()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=now_utc().tzinfo)
    now_ny = to_ny_time(as_of)

    # End the axis at the close of the in-progress 6h session so a little future
    # is visible to the right of the "now" marker.
    window_end_ny = _day_quarter_start_ny(now_ny) + timedelta(hours=6)
    window_start_ny = window_end_ny - _WINDOW

    window_start_utc = to_utc_time(window_start_ny)
    window_end_utc = to_utc_time(window_end_ny)
    span = (window_end_utc - window_start_utc).total_seconds()
    now_ratio = (as_of - window_start_utc).total_seconds() / span if span else 1.0
    now_ratio = max(0.0, min(1.0, now_ratio))

    rows = [
        _build_row(
            "90 Minute", _micro_start_ny, timedelta(minutes=90), _micro_label,
            window_start_ny, window_end_ny, now_ny,
        ),
        _build_row(
            "Day", _day_quarter_start_ny, timedelta(hours=6), _day_label,
            window_start_ny, window_end_ny, now_ny,
        ),
        _build_row(
            "Week", _calendar_day_start_ny, timedelta(days=1), _week_label,
            window_start_ny, window_end_ny, now_ny,
        ),
    ]

    return QuarterLadder(
        as_of_utc=as_of,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        now_ratio=now_ratio,
        rows=rows,
    )
