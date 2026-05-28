"""Time engine for Shadow Quarterly market timing."""

from datetime import UTC, datetime
from enum import Enum

from app.utils.timezone import to_ny_time


class Session(str, Enum):
    """Market sessions based on NY time."""
    ASIA = "Asia"
    LONDON = "London"
    NY_AM = "NY AM"
    NY_PM = "NY PM"
    LONDON_CLOSE = "London Close"


class Quarter(str, Enum):
    """Daily quarters (Daye QT) - 4 quarters × 6 hours."""
    Q1 = "Q1"  # 18:00–00:00 NY (Asia)
    Q2 = "Q2"  # 00:00–06:00 NY (London)
    Q3 = "Q3"  # 06:00–12:00 NY (NY AM)
    Q4 = "Q4"  # 12:00–18:00 NY (NY PM)


class DayOfWeek(str, Enum):
    """Days of week."""
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


class TimeEngine:
    """Engine for detecting market session and quarter context."""
    
    # Session Anchors (NY hour marks)
    SESSION_ANCHORS = {1, 5, 9, 13, 17, 21}
    
    # Session time ranges (hour in NY timezone)
    SESSION_RANGES = {
        Session.ASIA: (21, 5),  # 21:00 NY to 05:00 NY (wraps to next day)
        Session.LONDON: (5, 12),  # 05:00 to 12:00
        Session.NY_AM: (9, 13),  # 09:00 to 13:00 (overlaps with London)
        Session.NY_PM: (13, 17),  # 13:00 to 17:00
        Session.LONDON_CLOSE: (17, 21),  # 17:00 to 21:00
    }
    
    # Daily Quarter ranges (hour in NY timezone)
    QUARTER_RANGES = {
        Quarter.Q1: (18, 0),  # 18:00 to 00:00 (wraps to next day)
        Quarter.Q2: (0, 6),   # 00:00 to 06:00
        Quarter.Q3: (6, 12),  # 06:00 to 12:00
        Quarter.Q4: (12, 18),  # 12:00 to 18:00
    }
    
    # Micro-quarter time ranges (in minutes from start of quarter)
    # Each quarter is 360 minutes (6 hours), divided into 4 × 90 min
    MICRO_QUARTER_RANGES = {
        "1": (0, 90),
        "2": (90, 180),
        "3": (180, 270),
        "4": (270, 360),
    }
    
    @staticmethod
    def get_session(dt_ny: datetime) -> Session:
        """Determine session for NY time.
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            Session enum value
        """
        hour = dt_ny.hour
        
        # Asia session: 21:00 to 04:59 (wraps across midnight)
        if hour >= 21 or hour < 5:
            return Session.ASIA
        
        # NY AM takes priority over the London overlap.
        if 9 <= hour < 13:
            return Session.NY_AM

        # London session before NY open.
        if 5 <= hour < 9:
            return Session.LONDON
        
        # NY PM: 13:00 to 16:59
        if 13 <= hour < 17:
            return Session.NY_PM
        
        # London Close: 17:00 to 20:59
        if 17 <= hour < 21:
            return Session.LONDON_CLOSE
        
        # Fallback (shouldn't reach here)
        return Session.ASIA
    
    @staticmethod
    def get_session_anchor(dt_ny: datetime) -> str:
        """Get session anchor (01, 05, 09, 13, 17, 21 NY).
        
        Anchors mark important session transition times.
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            Active session anchor label, such as "09 NY".
        """
        hour = dt_ny.hour
        anchors = sorted(TimeEngine.SESSION_ANCHORS)

        active_anchor = 21
        for anchor in anchors:
            if hour >= anchor:
                active_anchor = anchor
            else:
                break

        return f"{active_anchor:02d} NY"
    
    @staticmethod
    def get_daily_quarter(dt_ny: datetime) -> Quarter:
        """Determine Daye Quarter (Q1-Q4) for NY time.
        
        Q1: 18:00–00:00 NY (Asia)
        Q2: 00:00–06:00 NY (London pre)
        Q3: 06:00–12:00 NY (NY AM)
        Q4: 12:00–18:00 NY (NY PM)
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            Quarter enum value
        """
        hour = dt_ny.hour
        
        if 18 <= hour < 24:  # 18:00 to 23:59
            return Quarter.Q1
        elif 0 <= hour < 6:  # 00:00 to 05:59
            return Quarter.Q2
        elif 6 <= hour < 12:  # 06:00 to 11:59
            return Quarter.Q3
        else:  # 12:00 to 17:59
            return Quarter.Q4

    @staticmethod
    def get_yearly_quarter(dt_ny: datetime) -> str:
        return f"Q{((dt_ny.month - 1) // 3) + 1}"

    @staticmethod
    def get_monthly_quarter(dt_ny: datetime) -> str:
        return f"Q{min(((dt_ny.day - 1) // 7) + 1, 4)}"

    @staticmethod
    def get_weekly_quarter(dt_ny: datetime) -> str:
        return f"Q{min(dt_ny.weekday() + 1, 4)}"
    
    @staticmethod
    def get_micro_quarter(dt_ny: datetime) -> str:
        """Get 90-minute micro-quarter within Daye Quarter.
        
        Each 6-hour quarter is divided into 4 × 90-minute micro-quarters.
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            Micro-quarter as string (e.g., "Q1.1", "Q1.2", etc.)
        """
        quarter = TimeEngine.get_daily_quarter(dt_ny)
        
        # Get hour and minute
        hour = dt_ny.hour
        minute = dt_ny.minute
        
        # Get quarter start hour
        quarter_starts = {
            Quarter.Q1: 18,
            Quarter.Q2: 0,
            Quarter.Q3: 6,
            Quarter.Q4: 12,
        }
        
        start_hour = quarter_starts[quarter]
        
        # Calculate minutes from quarter start
        minutes_in_quarter = (hour - start_hour) * 60 + minute
        
        # Ensure positive (handle day wrapping for Q1/Q2)
        if minutes_in_quarter < 0:
            minutes_in_quarter += 24 * 60
        
        # Determine which 90-min micro-quarter
        micro = 1
        for i in range(1, 5):
            if minutes_in_quarter < i * 90:
                micro = i
                break
        
        return f"{quarter.value}.{micro}"
    
    @staticmethod
    def is_killzone(dt_ny: datetime) -> bool:
        """Check if time is in killzone (09:00-10:00 NY).
        
        Killzone is high-volume session transition time.
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            True if in killzone, False otherwise
        """
        return 9 <= dt_ny.hour < 10
    
    @staticmethod
    def get_day_of_week(dt_ny: datetime) -> DayOfWeek:
        """Get day of week from NY datetime.
        
        Args:
            dt_ny: Datetime in NY timezone
            
        Returns:
            DayOfWeek enum value
        """
        days = [
            DayOfWeek.MONDAY,
            DayOfWeek.TUESDAY,
            DayOfWeek.WEDNESDAY,
            DayOfWeek.THURSDAY,
            DayOfWeek.FRIDAY,
            DayOfWeek.SATURDAY,
            DayOfWeek.SUNDAY,
        ]
        return days[dt_ny.weekday()]
    
    @staticmethod
    def get_time_context(dt_utc: datetime | None = None) -> dict:
        """Get complete time context for a datetime.
        
        Args:
            dt_utc: UTC datetime (None = current time)
            
        Returns:
            Dictionary with full time context
        """
        if dt_utc is None:
            dt_utc = datetime.now(tz=UTC)
        
        # Convert to NY time
        dt_ny = to_ny_time(dt_utc)
        
        return {
            "timestamp_utc": dt_utc,
            "timestamp_ny": dt_ny,
            "session": TimeEngine.get_session(dt_ny).value,
            "session_anchor": TimeEngine.get_session_anchor(dt_ny),
            "yearly_quarter": TimeEngine.get_yearly_quarter(dt_ny),
            "monthly_quarter": TimeEngine.get_monthly_quarter(dt_ny),
            "weekly_quarter": TimeEngine.get_weekly_quarter(dt_ny),
            "daily_quarter": TimeEngine.get_daily_quarter(dt_ny).value,
            "micro_quarter_90m": TimeEngine.get_micro_quarter(dt_ny),
            "is_killzone": TimeEngine.is_killzone(dt_ny),
            "day_of_week": TimeEngine.get_day_of_week(dt_ny).value,
        }
