"""
Tests for Agent #2: Historical Data Loader

Tests all capabilities:
1. load_history - Single symbol historical data
2. load_batch_history - Multiple symbols
3. get_available_dates - Check cached dates
4. update_incremental - Fetch only new bars
"""

import pytest
from datetime import datetime, timedelta
from agents.data.historical_data_loader import HistoricalDataLoader
from shared.message_bus import MessageBus
from shared.database.connection import Database


def init_message_bus():
    """Initialize message bus for testing."""
    bus = MessageBus()
    return bus


def init_database(db_url: str = "sqlite+aiosqlite:///:memory:"):
    """Initialize database for testing."""
    db = Database(db_url)
    return db


@pytest.mark.asyncio
async def test_historical_data_loader_metadata():
    """Test agent metadata and capabilities."""
    agent = HistoricalDataLoader()
    
    assert agent.agent_id == "historical_data_loader"
    assert agent.metadata.category == "data"
    assert len(agent.metadata.capabilities) == 4
    
    capability_names = [cap.name for cap in agent.metadata.capabilities]
    assert "load_history" in capability_names
    assert "load_batch_history" in capability_names
    assert "get_available_dates" in capability_names
    assert "update_incremental" in capability_names


@pytest.mark.asyncio
async def test_load_history_valid_symbol():
    """Test loading historical data for a valid symbol."""
    # Initialize dependencies
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    # Test parameters: AAPL for last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    params = {
        "symbol": "AAPL",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "interval": "1d"
    }
    
    # Create message
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=params
    )
    
    # Process message
    result = await agent.process_request(message)
    
    # Assertions
    assert result["success"] is True
    assert "data" in result
    assert result["count"] > 0
    assert len(result["data"]) == result["count"]
    
    # Check first bar structure
    first_bar = result["data"][0]
    assert "symbol" in first_bar
    assert "date" in first_bar
    assert "open" in first_bar
    assert "high" in first_bar
    assert "low" in first_bar
    assert "close" in first_bar
    assert "volume" in first_bar
    assert first_bar["symbol"] == "AAPL"
    
    # Validate OHLC relationships
    assert first_bar["high"] >= first_bar["low"]
    assert first_bar["high"] >= first_bar["open"]
    assert first_bar["high"] >= first_bar["close"]
    assert first_bar["low"] <= first_bar["open"]
    assert first_bar["low"] <= first_bar["close"]
    
    # Cleanup
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_load_history_invalid_symbol():
    """Test loading history for an invalid symbol."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    params = {
        "symbol": "INVALIDSYMBOL123",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=params
    )
    
    result = await agent.process_request(message)
    
    # Should fail - no data for invalid symbol
    assert result["success"] is False
    assert "error" in result
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_load_history_invalid_interval():
    """Test with invalid interval parameter."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    params = {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "interval": "invalid_interval"
    }
    
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=params
    )
    
    result = await agent.process_request(message)
    
    assert result["success"] is False
    assert "Invalid interval" in result["error"]
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_load_batch_history():
    """Test loading history for multiple symbols."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    params = {
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "interval": "1d"
    }
    
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_batch_history",
        data=params
    )
    
    result = await agent.process_request(message)
    
    assert result["success"] is True
    assert "results" in result
    assert "summary" in result
    
    # Check all symbols processed
    assert "AAPL" in result["results"]
    assert "MSFT" in result["results"]
    assert "GOOGL" in result["results"]
    
    # Check summary
    summary = result["summary"]
    assert summary["total"] == 3
    assert summary["success_count"] > 0
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_get_available_dates():
    """Test getting available cached dates for a symbol."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    # First load some data
    load_params = {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    from shared.data_models import Message, MessageType
    load_msg = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=load_params
    )
    
    load_result = await agent.process_request(load_msg)
    assert load_result["success"] is True
    
    # Now check available dates
    dates_params = {"symbol": "AAPL"}
    dates_msg = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="get_available_dates",
        data=dates_params
    )
    
    result = await agent.process_request(dates_msg)
    
    assert result["success"] is True
    assert "dates" in result
    assert result["count"] > 0
    assert "earliest" in result
    assert "latest" in result
    assert result["earliest"] == "2024-01-01" or result["earliest"] > "2024-01-01"  # Market may be closed on Jan 1
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_update_incremental():
    """Test incremental update fetching only new bars."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    # First load: January 2024
    load_params = {
        "symbol": "MSFT",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    from shared.data_models import Message, MessageType
    load_msg = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=load_params
    )
    
    initial_result = await agent.process_request(load_msg)
    assert initial_result["success"] is True
    initial_count = initial_result["count"]
    
    # Now do incremental update (should fetch Feb onwards)
    update_params = {"symbol": "MSFT"}
    update_msg = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="update_incremental",
        data=update_params
    )
    
    update_result = await agent.process_request(update_msg)
    
    assert update_result["success"] is True
    assert "new_bars" in update_result
    assert "latest_date" in update_result
    # Should have fetched data after Jan 31
    assert update_result["latest_date"] > "2024-01-31"
    
    await agent.stop()
    await bus.stop()
    await db.close()


@pytest.mark.asyncio
async def test_cache_functionality():
    """Test that caching works correctly."""
    bus = init_message_bus()
    await bus.start()
    
    db = init_database("sqlite+aiosqlite:///:memory:")
    await db.initialize()
    
    agent = HistoricalDataLoader()
    await agent.initialize()
    await agent.start()
    
    params = {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-01-10"
    }
    
    from shared.data_models import Message, MessageType
    message = Message(
        from_agent="test",
        to_agent=agent.agent_id,
        message_type=MessageType.REQUEST,
        topic="load_history",
        data=params
    )
    
    # First call - should fetch from API
    result1 = await agent.process_request(message)
    assert result1["success"] is True
    assert result1["cached"] is False
    
    # Second call - should hit cache
    result2 = await agent.process_request(message)
    assert result2["success"] is True
    assert result2["cached"] is True
    assert result2["count"] == result1["count"]
    
    await agent.stop()
    await bus.stop()
    await db.close()
