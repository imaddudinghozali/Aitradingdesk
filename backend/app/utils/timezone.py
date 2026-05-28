"""Timezone utilities for NY time handling."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


NY_TZ = ZoneInfo("America/New_York")


def to_ny_time(dt_utc: datetime) -> datetime:
    """Convert UTC datetime to NY time.
    
    Args:
        dt_utc: Datetime in UTC (can be naive or aware)
        
    Returns:
        Datetime in NY timezone (timezone-aware)
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC)
    
    return dt_utc.astimezone(NY_TZ)


def to_utc_time(dt_ny: datetime) -> datetime:
    """Convert NY datetime to UTC.
    
    Args:
        dt_ny: Datetime in NY timezone (can be naive or aware)
        
    Returns:
        Datetime in UTC (timezone-aware)
    """
    if dt_ny.tzinfo is None:
        dt_ny = dt_ny.replace(tzinfo=NY_TZ)
    
    return dt_ny.astimezone(UTC)


def now_ny() -> datetime:
    """Get current time in NY timezone.
    
    Returns:
        Current datetime in NY timezone (timezone-aware)
    """
    return datetime.now(NY_TZ)


def now_utc() -> datetime:
    """Get current time in UTC.
    
    Returns:
        Current datetime in UTC (timezone-aware)
    """
    return datetime.now(UTC)


def get_ny_offset() -> str:
    """Get current NY timezone offset as string.
    
    Returns:
        Timezone offset (e.g., "-04:00" or "-05:00")
    """
    return now_ny().strftime("%z")
