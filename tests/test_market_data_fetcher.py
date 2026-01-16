"""
Tests for Agent #1: Market Data Fetcher
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from agents.data.market_data_fetcher import MarketDataFetcher
from shared.database.connection import init_database
from shared.data_models import Message, MessageType
from shared.message_bus import init_message_bus
from shared.validators import DataValidator, ValidationError


@pytest.mark.asyncio
async def test_market_data_fetcher_metadata():
    """Test agent metadata."""
    agent = MarketDataFetcher()
    metadata = agent.get_metadata()
    
    assert metadata.agent_id == "market_data_fetcher"
    assert metadata.category == "data"
    assert len(metadata.capabilities) == 4
    assert "fetch_price" in [c.name for c in metadata.capabilities]


@pytest.mark.asyncio
async def test_fetch_price_valid_symbol():
    """Test fetching price for a valid symbol."""
    # Initialize dependencies
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")  # Use in-memory database for testing
    await db.initialize()
    
    # Create agent
    agent = MarketDataFetcher()
    await agent.start()
    
    # Test with AAPL
    request = Message(
        from_agent="tester",
        to_agent="market_data_fetcher",
        message_type=MessageType.REQUEST,
        topic="fetch_price",
        data={"symbol": "AAPL"},
        correlation_id="test_001",
    )
    
    result = await agent.process_request(request)
    
    assert "error" not in result
    assert result["symbol"] == "AAPL"
    assert "price" in result
    assert isinstance(result["price"], (int, float))
    assert result["price"] > 0
    assert result["source"] == "yfinance"
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_fetch_price_invalid_symbol():
    """Test fetching price for an invalid symbol."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = MarketDataFetcher()
    await agent.start()
    
    # Test with invalid symbol
    request = Message(
        from_agent="tester",
        to_agent="market_data_fetcher",
        message_type=MessageType.REQUEST,
        topic="fetch_price",
        data={"symbol": "INVALID123XYZ"},
        correlation_id="test_002",
    )
    
    result = await agent.process_request(request)
    
    assert "error" in result
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_validate_symbol():
    """Test symbol validation."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = MarketDataFetcher()
    await agent.start()
    
    # Test valid symbol
    request = Message(
        from_agent="tester",
        to_agent="market_data_fetcher",
        message_type=MessageType.REQUEST,
        topic="validate_symbol",
        data={"symbol": "GOOGL"},
        correlation_id="test_003",
    )
    
    result = await agent.process_request(request)
    
    assert result["symbol"] == "GOOGL"
    assert result["valid"] is True
    assert "company_name" in result
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_data_validator():
    """Test data validation utilities."""
    # Valid symbol
    assert DataValidator.validate_symbol("AAPL")
    assert DataValidator.validate_symbol("BRK.A")
    
    # Invalid symbols
    with pytest.raises(ValidationError):
        DataValidator.validate_symbol("")
    
    with pytest.raises(ValidationError):
        DataValidator.validate_symbol("123")
    
    with pytest.raises(ValidationError):
        DataValidator.validate_symbol("TOOLONG")
    
    # Valid prices
    assert DataValidator.validate_price(150.50)
    assert DataValidator.validate_price(0.01)
    assert DataValidator.validate_price(1000.0)
    
    # Invalid prices
    with pytest.raises(ValidationError):
        DataValidator.validate_price(-10.0)
    
    with pytest.raises(ValidationError):
        DataValidator.validate_price(0.0)  # Zero not allowed by default
    
    with pytest.raises(ValidationError):
        DataValidator.validate_price(10_000_000.0)  # Too high
    
    # Valid OHLC
    assert DataValidator.validate_ohlc(100.0, 105.0, 99.0, 103.0)
    
    # Invalid OHLC
    with pytest.raises(ValidationError):
        DataValidator.validate_ohlc(100.0, 90.0, 99.0, 95.0)  # High < Low


@pytest.mark.asyncio
async def test_fetch_batch():
    """Test batch fetching multiple symbols."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = MarketDataFetcher()
    await agent.start()
    
    # Test batch fetch
    request = Message(
        from_agent="tester",
        to_agent="market_data_fetcher",
        message_type=MessageType.REQUEST,
        topic="fetch_batch",
        data={"symbols": ["AAPL", "GOOGL", "MSFT"], "use_cache": False},
        correlation_id="test_004",
    )
    
    result = await agent.process_request(request)
    
    assert "quotes" in result
    assert "errors" in result
    assert result["total"] == 3
    assert result["successful"] >= 1  # At least some should succeed
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_symbol_sanitization():
    """Test symbol sanitization."""
    assert DataValidator.sanitize_symbol("  aapl  ") == "AAPL"
    assert DataValidator.sanitize_symbol("brk.a") == "BRK.A"
    assert DataValidator.sanitize_symbol("MSFT123") == "MSFT"  # Removes numbers
