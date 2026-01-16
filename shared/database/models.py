"""
Database models for market data storage.

Uses SQLAlchemy ORM with async support via aiosqlite.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class MarketQuote(Base):
    """
    Real-time market quote data.
    
    Stores the latest price, bid/ask, and volume information for symbols.
    """
    
    __tablename__ = "market_quotes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Price data
    price: Mapped[float] = mapped_column(Float, nullable=False)
    bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bid_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ask_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Volume data
    volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    __table_args__ = (
        Index("idx_symbol_timestamp", "symbol", "timestamp"),
    )


class HistoricalPrice(Base):
    """
    Historical OHLCV price data.
    
    Stores daily (or intraday) historical price bars.
    """
    
    __tablename__ = "historical_prices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # OHLCV data
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Adjusted prices
    adj_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Metadata
    interval: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    __table_args__ = (
        Index("idx_symbol_date_interval", "symbol", "date", "interval", unique=True),
    )


class AgentCache(Base):
    """
    Generic cache for agent data.
    
    Allows agents to store arbitrary cached data with TTL.
    """
    
    __tablename__ = "agent_cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(255), nullable=False)
    cache_value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # TTL
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Additional info (renamed from metadata)
    extra_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_agent_cache_key", "agent_id", "cache_key", unique=True),
    )


class DataQualityLog(Base):
    """
    Log of data quality issues and validation errors.
    
    Tracks when data fails validation or quality checks.
    """
    
    __tablename__ = "data_quality_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    
    # Source information
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Issue details
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low, medium, high
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Additional data
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_timestamp_severity", "timestamp", "severity"),
    )
