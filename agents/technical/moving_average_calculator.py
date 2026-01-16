"""
Agent #13: Moving Average Calculator

Calculates Simple Moving Averages (SMA), Exponential Moving Averages (EMA),
detects crossovers, and identifies golden/death cross patterns.

Created: January 16, 2026
Checkpoint: CHECKPOINT-1
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import and_, select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import AgentCapability, AgentMetadata
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice


class MovingAverageCalculator(BaseAgent):
    """
    Agent #13: Moving Average Calculator
    
    Calculates moving averages for technical analysis.
    Optimized for long-term investing strategies.
    """
    
    def __init__(self):
        """Initialize the Moving Average Calculator agent."""
        super().__init__()
        self.db = get_database()
    
    async def initialize(self):
        """Initialize database connection."""
        await self.db.initialize()
        logger.info(f"{self.agent_id} initialized")
    
    async def shutdown(self):
        """Cleanup resources."""
        await self.db.close()
        logger.info(f"{self.agent_id} shutdown complete")
    
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="moving_average_calculator",
            name="Moving Average Calculator",
            description="Calculates moving averages and detects crossovers",
            category="technical",
            capabilities=[
                AgentCapability(
                    name="calculate_sma",
                    description="Calculate Simple Moving Average",
                    parameters={"symbol": "str", "period": "int", "lookback_days": "int"}
                ),
                AgentCapability(
                    name="calculate_ema",
                    description="Calculate Exponential Moving Average",
                    parameters={"symbol": "str", "period": "int", "lookback_days": "int"}
                ),
                AgentCapability(
                    name="detect_crossover",
                    description="Detect MA crossovers",
                    parameters={"symbol": "str", "fast_period": "int", "slow_period": "int"}
                ),
                AgentCapability(
                    name="calculate_all_mas",
                    description="Calculate all MAs at once",
                    parameters={"symbol": "str"}
                ),
            ],
            subscribes_to=[],
            publishes_to=["technical_analysis_updates"],
        )
    
    async def process_request(self, message) -> Dict[str, Any]:
        """Process incoming requests."""
        topic = message.topic
        params = message.data
        
        if topic == "calculate_sma":
            return await self._calculate_sma(params)
        elif topic == "calculate_ema":
            return await self._calculate_ema(params)
        elif topic == "detect_crossover":
            return await self._detect_crossover(params)
        elif topic == "calculate_all_mas":
            return await self._calculate_all_mas(params)
        else:
            return {"error": f"Unknown topic: {topic}"}
    
    async def _calculate_sma(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Simple Moving Average."""
        try:
            symbol = params.get('symbol')
            period = params.get('period', 200)
            lookback_days = params.get('lookback_days', 300)
            
            if not symbol:
                return {"error": "Symbol is required"}
            
            # Fetch historical data
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < period:
                return {"error": f"Insufficient data: need {period} days, got {len(df)}"}
            
            # Calculate SMA
            df['sma'] = df['close'].rolling(window=period).mean()
            
            current_price = float(df['close'].iloc[-1])
            current_sma = float(df['sma'].iloc[-1])
            
            return {
                'symbol': symbol,
                'period': period,
                'current_price': round(current_price, 2),
                'current_sma': round(current_sma, 2),
                'price_above_sma': current_price > current_sma,
                'distance_pct': round(((current_price - current_sma) / current_sma) * 100, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _calculate_ema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Exponential Moving Average."""
        try:
            symbol = params.get('symbol')
            period = params.get('period', 12)
            lookback_days = params.get('lookback_days', 200)
            
            if not symbol:
                return {"error": "Symbol is required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < period:
                return {"error": f"Insufficient data: need {period} days, got {len(df)}"}
            
            # Calculate EMA
            df['ema'] = df['close'].ewm(span=period, adjust=False).mean()
            
            current_price = float(df['close'].iloc[-1])
            current_ema = float(df['ema'].iloc[-1])
            
            return {
                'symbol': symbol,
                'period': period,
                'current_price': round(current_price, 2),
                'current_ema': round(current_ema, 2),
                'price_above_ema': current_price > current_ema,
                'distance_pct': round(((current_price - current_ema) / current_ema) * 100, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _detect_crossover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detect moving average crossovers."""
        try:
            symbol = params.get('symbol')
            fast_period = params.get('fast_period', 50)
            slow_period = params.get('slow_period', 200)
            ma_type = params.get('ma_type', 'sma')
            lookback_days = params.get('lookback_days', 400)
            
            if not symbol:
                return {"error": "Symbol is required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < slow_period:
                return {"error": f"Insufficient data: need {slow_period} days, got {len(df)}"}
            
            # Calculate MAs
            if ma_type == 'sma':
                df['fast_ma'] = df['close'].rolling(window=fast_period).mean()
                df['slow_ma'] = df['close'].rolling(window=slow_period).mean()
            else:
                df['fast_ma'] = df['close'].ewm(span=fast_period, adjust=False).mean()
                df['slow_ma'] = df['close'].ewm(span=slow_period, adjust=False).mean()
            
            # Detect crossover
            df['crossover'] = np.where(df['fast_ma'] > df['slow_ma'], 1, -1)
            df['crossover_change'] = df['crossover'].diff()
            
            recent_crossovers = df[df['crossover_change'] != 0].tail(1)
            
            crossover_detected = False
            crossover_type = 'none'
            crossover_date = None
            
            if not recent_crossovers.empty:
                crossover_row = recent_crossovers.iloc[0]
                crossover_date = crossover_row['date']
                days_since = (df['date'].iloc[-1] - crossover_date).days
                
                if days_since <= 10:
                    crossover_detected = True
                    crossover_type = 'bullish' if crossover_row['crossover_change'] > 0 else 'bearish'
            
            current_fast = float(df['fast_ma'].iloc[-1])
            current_slow = float(df['slow_ma'].iloc[-1])
            current_price = float(df['close'].iloc[-1])
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'fast_ma': round(current_fast, 2),
                'slow_ma': round(current_slow, 2),
                'fast_above_slow': current_fast > current_slow,
                'crossover_detected': crossover_detected,
                'crossover_type': crossover_type,
                'crossover_date': crossover_date.isoformat() if crossover_date else None,
                'golden_cross': crossover_detected and crossover_type == 'bullish' and fast_period == 50 and slow_period == 200,
                'death_cross': crossover_detected and crossover_type == 'bearish' and fast_period == 50 and slow_period == 200,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error detecting crossover: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _calculate_all_mas(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate all moving averages at once."""
        try:
            symbol = params.get('symbol')
            lookback_days = params.get('lookback_days', 400)
            
            if not symbol:
                return {"error": "Symbol is required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < 200:
                return {"error": f"Insufficient data: need 200 days, got {len(df)}"}
            
            # Calculate all standard MAs
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_100'] = df['close'].rolling(window=100).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
            
            current_price = float(df['close'].iloc[-1])
            
            # Detect golden/death cross
            df['50_above_200'] = df['sma_50'] > df['sma_200']
            crossover_change = df['50_above_200'].diff()
            recent_crossover = df[crossover_change != 0].tail(1)
            
            golden_cross = False
            death_cross = False
            
            if not recent_crossover.empty:
                crossover_row = recent_crossover.iloc[0]
                days_since = (df['date'].iloc[-1] - crossover_row['date']).days
                if days_since <= 10:
                    if crossover_row['50_above_200']:
                        golden_cross = True
                    else:
                        death_cross = True
            
            # Determine trend
            price_above_20 = current_price > df['sma_20'].iloc[-1]
            price_above_50 = current_price > df['sma_50'].iloc[-1]
            price_above_200 = current_price > df['sma_200'].iloc[-1]
            
            if price_above_20 and price_above_50 and price_above_200:
                trend = 'STRONG_BULLISH'
            elif price_above_50 and price_above_200:
                trend = 'BULLISH'
            elif not price_above_50 and not price_above_200:
                trend = 'BEARISH'
            elif not price_above_20 and not price_above_50:
                trend = 'STRONG_BEARISH'
            else:
                trend = 'NEUTRAL'
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'ma_values': {
                    'sma_20': round(float(df['sma_20'].iloc[-1]), 2),
                    'sma_50': round(float(df['sma_50'].iloc[-1]), 2),
                    'sma_100': round(float(df['sma_100'].iloc[-1]), 2),
                    'sma_200': round(float(df['sma_200'].iloc[-1]), 2),
                    'ema_12': round(float(df['ema_12'].iloc[-1]), 2),
                    'ema_26': round(float(df['ema_26'].iloc[-1]), 2)
                },
                'price_position': {
                    'above_20': price_above_20,
                    'above_50': price_above_50,
                    'above_200': price_above_200
                },
                'crossovers': {
                    'golden_cross': golden_cross,
                    'death_cross': death_cross
                },
                'trend_signal': trend,
                'distance_from_200_pct': round(
                    ((current_price - df['sma_200'].iloc[-1]) / df['sma_200'].iloc[-1]) * 100, 2
                ),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating all MAs: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _fetch_historical_data(self, symbol: str, lookback_days: int) -> pd.DataFrame:
        """
        Fetch historical price data from database.
        
        Note: lookback_days refers to trading days, not calendar days.
        We fetch more data than needed to account for weekends/holidays.
        """
        async with self.db.get_session() as session:
            # Get the latest available date for this symbol
            latest_stmt = select(HistoricalPrice.date).where(
                HistoricalPrice.symbol == symbol
            ).order_by(HistoricalPrice.date.desc()).limit(1)
            
            latest_result = await session.execute(latest_stmt)
            latest_row = latest_result.scalar_one_or_none()
            
            if not latest_row:
                return pd.DataFrame()  # No data available
            
            end_date = latest_row
            # Use generous calendar day buffer (250 trading days ≈ 365 calendar days)
            calendar_days_buffer = int(lookback_days * 1.5) + 100
            start_date = end_date - timedelta(days=calendar_days_buffer)
            
            stmt = select(HistoricalPrice).where(
                and_(
                    HistoricalPrice.symbol == symbol,
                    HistoricalPrice.date >= start_date,
                    HistoricalPrice.date <= end_date
                )
            ).order_by(HistoricalPrice.date)
            
            result = await session.execute(stmt)
            prices = result.scalars().all()
            
            if not prices:
                raise ValueError(f"No historical data found for {symbol}")
            
            return pd.DataFrame([
                {
                    'date': price.date,
                    'open': price.open,
                    'high': price.high,
                    'low': price.low,
                    'close': price.close,
                    'volume': price.volume
                }
                for price in prices
            ])


# Test function
async def test_agent():
    """Test the Moving Average Calculator"""
    print("=" * 80)
    print("Testing Moving Average Calculator (Agent #13)")
    print("=" * 80)
    
    agent = MovingAverageCalculator()
    await agent.initialize()
    await agent.start()
    
    try:
        # Test with AAPL
        print("\n1. Calculate All MAs for AAPL...")
        result = await agent._calculate_all_mas({'symbol': 'AAPL'})
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Symbol: {result['symbol']}")
            print(f"   ✅ Price: ${result['current_price']}")
            print(f"   ✅ SMA 200: ${result['ma_values']['sma_200']}")
            print(f"   ✅ Trend: {result['trend_signal']}")
            print(f"   ✅ Golden Cross: {result['crossovers']['golden_cross']}")
            print(f"   ✅ Death Cross: {result['crossovers']['death_cross']}")
        
        print("\n" + "=" * 80)
        print("✅ Test Complete!")
        print("=" * 80)
    
    finally:
        await agent.stop()
        await agent.shutdown()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_agent())
