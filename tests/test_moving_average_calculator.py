"""
Tests for Moving Average Calculator Agent (Agent #13)

Tests all four capabilities:
    1. calculate_sma
    2. calculate_ema
    3. detect_crossover
    4. calculate_golden_death_cross
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from agents.technical.moving_average_calculator import MovingAverageCalculator
from shared.data_models import Message
from shared.database.connection import get_async_session
from shared.database.models import HistoricalPrice


@pytest.fixture
async def agent():
    """Create and start agent for testing"""
    agent = MovingAverageCalculator()
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def sample_data(db_session):
    """Create sample historical data for testing"""
    symbol = "TEST_MA"
    base_price = 100.0
    
    # Generate 400 days of sample data with a trend
    prices = []
    for i in range(400):
        date = datetime.utcnow() - timedelta(days=400-i)
        # Create uptrend: price increases gradually
        price = base_price + (i * 0.1)
        
        prices.append(HistoricalPrice(
            symbol=symbol,
            date=date,
            open=price - 0.5,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1000000
        ))
    
    db_session.add_all(prices)
    await db_session.commit()
    
    return symbol


@pytest.mark.asyncio
async def test_agent_initialization(agent):
    """Test agent initializes correctly"""
    assert agent.agent_id == "moving_average_calculator"
    assert agent.name == "Moving Average Calculator"
    assert len(agent.capabilities) >= 4
    assert "calculate_sma" in agent.capabilities
    assert "calculate_ema" in agent.capabilities
    assert "detect_crossover" in agent.capabilities
    assert "calculate_golden_death_cross" in agent.capabilities


@pytest.mark.asyncio
async def test_calculate_sma(agent, sample_data):
    """Test SMA calculation"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_sma',
            'symbol': sample_data,
            'period': 50,
            'lookback_days': 200
        }
    )
    
    response = await agent.process_message(message)
    
    assert response.payload['status'] == 'success'
    data = response.payload['data']
    
    assert data['symbol'] == sample_data
    assert 'current_price' in data
    assert 'current_sma' in data
    assert 'price_above_sma' in data
    assert 'distance_from_sma_pct' in data
    assert len(data['sma_values']) > 0
    
    # In uptrend, current price should be above older SMA
    assert data['current_price'] > data['current_sma']


@pytest.mark.asyncio
async def test_calculate_sma_insufficient_data(agent):
    """Test SMA with insufficient data"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_sma',
            'symbol': 'NONEXISTENT',
            'period': 200
        }
    )
    
    response = await agent.process_message(message)
    assert response.payload['status'] == 'error'


@pytest.mark.asyncio
async def test_calculate_ema(agent, sample_data):
    """Test EMA calculation"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_ema',
            'symbol': sample_data,
            'period': 12,
            'lookback_days': 100
        }
    )
    
    response = await agent.process_message(message)
    
    assert response.payload['status'] == 'success'
    data = response.payload['data']
    
    assert data['symbol'] == sample_data
    assert 'current_ema' in data
    assert 'price_above_ema' in data
    assert len(data['ema_values']) > 0


@pytest.mark.asyncio
async def test_detect_crossover(agent, sample_data):
    """Test MA crossover detection"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'detect_crossover',
            'symbol': sample_data,
            'fast_period': 50,
            'slow_period': 200,
            'ma_type': 'sma'
        }
    )
    
    response = await agent.process_message(message)
    
    assert response.payload['status'] == 'success'
    data = response.payload['data']
    
    assert 'fast_ma' in data
    assert 'slow_ma' in data
    assert 'fast_above_slow' in data
    assert 'crossover_detected' in data
    assert 'crossover_type' in data
    
    # In uptrend, fast should be above slow
    assert data['fast_above_slow'] == True


@pytest.mark.asyncio
async def test_detect_crossover_ema(agent, sample_data):
    """Test EMA crossover detection"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'detect_crossover',
            'symbol': sample_data,
            'fast_period': 12,
            'slow_period': 26,
            'ma_type': 'ema'
        }
    )
    
    response = await agent.process_message(message)
    assert response.payload['status'] == 'success'


@pytest.mark.asyncio
async def test_golden_death_cross(agent, sample_data):
    """Test golden/death cross detection"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_golden_death_cross',
            'symbol': sample_data
        }
    )
    
    response = await agent.process_message(message)
    
    assert response.payload['status'] == 'success'
    data = response.payload['data']
    
    assert 'ma_50' in data
    assert 'ma_200' in data
    assert 'golden_cross' in data
    assert 'death_cross' in data
    assert 'trend_signal' in data
    assert data['trend_signal'] in ['BULLISH', 'BEARISH', 'NEUTRAL']


@pytest.mark.asyncio
async def test_calculate_all_mas(agent, sample_data):
    """Test calculate all MAs at once"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_all_mas',
            'symbol': sample_data
        }
    )
    
    response = await agent.process_message(message)
    
    assert response.payload['status'] == 'success'
    data = response.payload['data']
    
    assert 'current_price' in data
    assert 'ma_values' in data
    
    ma_values = data['ma_values']
    assert '20_day' in ma_values
    assert '50_day' in ma_values
    assert '100_day' in ma_values
    assert '200_day' in ma_values
    assert 'ema_12' in ma_values
    assert 'ema_26' in ma_values
    
    assert 'price_position' in data
    assert 'crossovers' in data
    assert 'trend_signal' in data
    assert 'distance_from_200_pct' in data


@pytest.mark.asyncio
async def test_invalid_capability(agent, sample_data):
    """Test handling of invalid capability"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'invalid_capability',
            'symbol': sample_data
        }
    )
    
    response = await agent.process_message(message)
    assert response.payload['status'] == 'error'


@pytest.mark.asyncio
async def test_missing_symbol(agent):
    """Test error handling when symbol is missing"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_sma',
            'period': 200
        }
    )
    
    response = await agent.process_message(message)
    assert response.payload['status'] == 'error'
    assert 'required' in response.payload['error'].lower()


@pytest.mark.asyncio
async def test_real_data_aapl(agent):
    """Test with real AAPL data if available"""
    message = Message(
        sender_id="test",
        receiver_id=agent.agent_id,
        message_type='request',
        payload={
            'capability': 'calculate_all_mas',
            'symbol': 'AAPL'
        }
    )
    
    response = await agent.process_message(message)
    
    # This might fail if AAPL data not loaded yet, which is okay
    if response.payload['status'] == 'success':
        data = response.payload['data']
        assert data['current_price'] > 0
        assert all(v > 0 for v in data['ma_values'].values())
