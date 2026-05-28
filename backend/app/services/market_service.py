"""Market data service for CRUD operations."""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.engines.time_engine import TimeEngine
from app.models.market_snapshot import MarketSnapshot
from app.schemas.market import MarketDataInput

logger = logging.getLogger(__name__)


class MarketService:
    """Service for market data operations."""
    
    @staticmethod
    def create_snapshot(db: Session, data: MarketDataInput) -> MarketSnapshot:
        """Create a new market snapshot.
        
        Args:
            db: Database session
            data: Market data input
            
        Returns:
            Created MarketSnapshot instance
        """
        time_context = TimeEngine.get_time_context(data.timestamp_utc)
        
        snapshot = MarketSnapshot(
            symbol=data.symbol,
            timeframe=data.timeframe,
            open=data.open,
            high=data.high,
            low=data.low,
            close=data.close,
            volume=data.volume,
            timestamp_utc=data.timestamp_utc,
            timestamp_ny=time_context["timestamp_ny"],
            session=time_context["session"],
            session_anchor=time_context["session_anchor"],
            yearly_quarter=time_context["yearly_quarter"],
            monthly_quarter=time_context["monthly_quarter"],
            weekly_quarter=time_context["weekly_quarter"],
            daily_quarter=time_context["daily_quarter"],
            micro_quarter_90m=time_context["micro_quarter_90m"],
            day_of_week=time_context["day_of_week"],
            is_killzone=time_context["is_killzone"],
        )
        
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        
        logger.info(
            f"Created market snapshot: {snapshot.symbol} {snapshot.timeframe} "
            f"@ {snapshot.timestamp_ny.isoformat()}"
        )
        
        return snapshot
    
    @staticmethod
    def get_latest(
        db: Session,
        symbol: str,
        timeframe: str,
    ) -> MarketSnapshot | None:
        """Get latest snapshot for a symbol/timeframe.
        
        Args:
            db: Database session
            symbol: Symbol (XAUUSD, XAGUSD)
            timeframe: Timeframe (M5, H1, etc.)
            
        Returns:
            Latest MarketSnapshot or None
        """
        return db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timeframe == timeframe,
        ).order_by(desc(MarketSnapshot.timestamp_utc)).first()
    
    @staticmethod
    def get_snapshots(
        db: Session,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[MarketSnapshot]:
        """Get recent snapshots for a symbol/timeframe.
        
        Args:
            db: Database session
            symbol: Symbol (XAUUSD, XAGUSD)
            timeframe: Timeframe (M5, H1, etc.)
            limit: Max number of snapshots
            
        Returns:
            List of MarketSnapshot instances
        """
        return db.query(MarketSnapshot).filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timeframe == timeframe,
        ).order_by(desc(MarketSnapshot.timestamp_utc)).limit(limit).all()
    
    @staticmethod
    def get_all_symbols(db: Session) -> list[str]:
        """Get all available symbols in database.
        
        Args:
            db: Database session
            
        Returns:
            List of unique symbols
        """
        symbols = db.query(MarketSnapshot.symbol).distinct().all()
        return [s[0] for s in symbols]
    
    @staticmethod
    def get_all_timeframes(db: Session, symbol: str) -> list[str]:
        """Get all available timeframes for a symbol.
        
        Args:
            db: Database session
            symbol: Symbol
            
        Returns:
            List of unique timeframes
        """
        timeframes = db.query(MarketSnapshot.timeframe).filter(
            MarketSnapshot.symbol == symbol
        ).distinct().all()
        return [t[0] for t in timeframes]
