"""
RSI Analyzer Agent - CHECKPOINT-2
Agent #14: Relative Strength Index analysis for long-term trading signals

Capabilities:
1. calculate_rsi: Calculate RSI for given period (14, 21, 28 days)
2. detect_divergence: Identify bullish/bearish divergences
3. identify_oversold_overbought: Determine extreme conditions
4. calculate_weekly_monthly_rsi: Long-term RSI for strategic positioning

Author: 100AC System
Created: January 16, 2026
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import select, and_

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability, Message
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice


class RSIAnalyzer(BaseAgent):
    """
    Agent #14: RSI Analyzer
    
    Analyzes Relative Strength Index for long-term gold/silver ETF trading.
    Focuses on weekly/monthly timeframes for strategic positioning.
    """
    
    def __init__(self):
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
        """Return agent metadata with capabilities."""
        return AgentMetadata(
            agent_id="rsi_analyzer",
            name="RSI Analyzer",
            description="Calculates RSI and identifies divergences for long-term trading",
            category="technical",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="calculate_rsi",
                    description="Calculate RSI for specified period",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "period": "int (optional): RSI period, default 14",
                        "timeframe": "str (optional): 'daily', 'weekly', 'monthly', default 'daily'"
                    }
                ),
                AgentCapability(
                    name="detect_divergence",
                    description="Detect bullish/bearish RSI divergences",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "lookback_days": "int (optional): Days to analyze, default 60"
                    }
                ),
                AgentCapability(
                    name="identify_oversold_overbought",
                    description="Identify extreme RSI conditions",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "oversold_threshold": "int (optional): Default 30",
                        "overbought_threshold": "int (optional): Default 70"
                    }
                ),
                AgentCapability(
                    name="calculate_all_rsi",
                    description="Comprehensive RSI analysis with all timeframes",
                    parameters={
                        "symbol": "str (required): ETF symbol"
                    }
                )
            ]
        )
    
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """Process incoming requests based on capability."""
        topic = message.topic
        params = message.data
        
        if topic == "calculate_rsi":
            return await self._calculate_rsi(params)
        elif topic == "detect_divergence":
            return await self._detect_divergence(params)
        elif topic == "identify_oversold_overbought":
            return await self._identify_oversold_overbought(params)
        elif topic == "calculate_all_rsi":
            return await self._calculate_all_rsi(params)
        else:
            return {"error": f"Unknown capability: {topic}"}
    
    async def _calculate_rsi(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate RSI for specified period and timeframe.
        
        RSI Formula:
        RS = Average Gain / Average Loss
        RSI = 100 - (100 / (1 + RS))
        """
        try:
            symbol = params.get('symbol')
            period = params.get('period', 14)
            timeframe = params.get('timeframe', 'daily')
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            # Fetch sufficient historical data
            lookback = period * 3  # Need extra data for accurate calculation
            df = await self._fetch_historical_data(symbol, lookback, timeframe)
            
            if len(df) < period + 1:
                return {"error": f"Insufficient data: need {period + 1} periods, got {len(df)}"}
            
            # Calculate RSI
            rsi_values = self._compute_rsi(df['close'], period)
            df['rsi'] = rsi_values
            
            current_rsi = rsi_values.iloc[-1]
            previous_rsi = rsi_values.iloc[-2] if len(rsi_values) > 1 else None
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'period': period,
                'current_rsi': round(current_rsi, 2),
                'previous_rsi': round(previous_rsi, 2) if previous_rsi else None,
                'rsi_change': round(current_rsi - previous_rsi, 2) if previous_rsi else None,
                'current_price': round(df['close'].iloc[-1], 2),
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _detect_divergence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect bullish and bearish divergences.
        
        Bullish Divergence: Price makes lower low, RSI makes higher low
        Bearish Divergence: Price makes higher high, RSI makes lower high
        """
        try:
            symbol = params.get('symbol')
            lookback_days = params.get('lookback_days', 60)
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days, 'daily')
            
            if len(df) < 30:  # Minimum for divergence detection
                return {"error": f"Insufficient data: need 30+ days, got {len(df)}"}
            
            # Calculate RSI
            df['rsi'] = self._compute_rsi(df['close'], 14)
            
            # Find peaks and troughs in both price and RSI
            price_peaks = self._find_peaks(df['close'])
            price_troughs = self._find_troughs(df['close'])
            rsi_peaks = self._find_peaks(df['rsi'])
            rsi_troughs = self._find_troughs(df['rsi'])
            
            # Detect divergences
            bullish_divergence = self._check_bullish_divergence(
                df, price_troughs, rsi_troughs
            )
            bearish_divergence = self._check_bearish_divergence(
                df, price_peaks, rsi_peaks
            )
            
            return {
                'symbol': symbol,
                'lookback_days': lookback_days,
                'bullish_divergence': bullish_divergence,
                'bearish_divergence': bearish_divergence,
                'current_rsi': round(df['rsi'].iloc[-1], 2),
                'current_price': round(df['close'].iloc[-1], 2),
                'signal': 'BULLISH' if bullish_divergence else 'BEARISH' if bearish_divergence else 'NEUTRAL',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error detecting divergence: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _identify_oversold_overbought(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify oversold/overbought conditions across multiple timeframes.
        """
        try:
            symbol = params.get('symbol')
            oversold_threshold = params.get('oversold_threshold', 30)
            overbought_threshold = params.get('overbought_threshold', 70)
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            # Analyze multiple timeframes
            timeframes = ['daily', 'weekly', 'monthly']
            results = {}
            
            for tf in timeframes:
                df = await self._fetch_historical_data(symbol, 50, tf)
                if len(df) >= 15:
                    rsi = self._compute_rsi(df['close'], 14)
                    current_rsi = rsi.iloc[-1]
                    
                    condition = 'NEUTRAL'
                    if current_rsi < oversold_threshold:
                        condition = 'OVERSOLD'
                    elif current_rsi > overbought_threshold:
                        condition = 'OVERBOUGHT'
                    
                    results[tf] = {
                        'rsi': round(current_rsi, 2),
                        'condition': condition
                    }
            
            # Determine overall signal
            conditions = [r['condition'] for r in results.values()]
            if conditions.count('OVERSOLD') >= 2:
                overall_signal = 'STRONG_BUY'
            elif 'OVERSOLD' in conditions:
                overall_signal = 'BUY'
            elif conditions.count('OVERBOUGHT') >= 2:
                overall_signal = 'STRONG_SELL'
            elif 'OVERBOUGHT' in conditions:
                overall_signal = 'SELL'
            else:
                overall_signal = 'HOLD'
            
            return {
                'symbol': symbol,
                'thresholds': {
                    'oversold': oversold_threshold,
                    'overbought': overbought_threshold
                },
                'timeframes': results,
                'overall_signal': overall_signal,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error identifying oversold/overbought: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _calculate_all_rsi(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive RSI analysis with all capabilities.
        """
        try:
            symbol = params.get('symbol')
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            # Daily RSI
            daily_rsi = await self._calculate_rsi({
                'symbol': symbol,
                'period': 14,
                'timeframe': 'daily'
            })
            
            # Weekly RSI
            weekly_rsi = await self._calculate_rsi({
                'symbol': symbol,
                'period': 14,
                'timeframe': 'weekly'
            })
            
            # Monthly RSI
            monthly_rsi = await self._calculate_rsi({
                'symbol': symbol,
                'period': 14,
                'timeframe': 'monthly'
            })
            
            # Divergence detection
            divergence = await self._detect_divergence({
                'symbol': symbol,
                'lookback_days': 60
            })
            
            # Oversold/Overbought
            extremes = await self._identify_oversold_overbought({
                'symbol': symbol
            })
            
            return {
                'symbol': symbol,
                'daily': daily_rsi,
                'weekly': weekly_rsi,
                'monthly': monthly_rsi,
                'divergence': divergence,
                'extremes': extremes,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error in comprehensive RSI analysis: {e}", exc_info=True)
            return {"error": str(e)}
    
    # Helper methods
    
    def _compute_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Compute RSI using the Wilder smoothing method.
        """
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Use Wilder's smoothing (exponential moving average with alpha = 1/period)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _find_peaks(self, series: pd.Series, window: int = 5) -> List[int]:
        """Find local peaks in a series."""
        peaks = []
        for i in range(window, len(series) - window):
            if all(series.iloc[i] > series.iloc[i-j] for j in range(1, window+1)) and \
               all(series.iloc[i] > series.iloc[i+j] for j in range(1, window+1)):
                peaks.append(i)
        return peaks
    
    def _find_troughs(self, series: pd.Series, window: int = 5) -> List[int]:
        """Find local troughs in a series."""
        troughs = []
        for i in range(window, len(series) - window):
            if all(series.iloc[i] < series.iloc[i-j] for j in range(1, window+1)) and \
               all(series.iloc[i] < series.iloc[i+j] for j in range(1, window+1)):
                troughs.append(i)
        return troughs
    
    def _check_bullish_divergence(self, df: pd.DataFrame, 
                                   price_troughs: List[int], 
                                   rsi_troughs: List[int]) -> bool:
        """
        Check for bullish divergence: price lower low, RSI higher low.
        """
        if len(price_troughs) < 2 or len(rsi_troughs) < 2:
            return False
        
        # Get last two troughs
        recent_price_troughs = sorted(price_troughs)[-2:]
        recent_rsi_troughs = sorted(rsi_troughs)[-2:]
        
        # Check if price made lower low but RSI made higher low
        price_lower = df['close'].iloc[recent_price_troughs[-1]] < df['close'].iloc[recent_price_troughs[-2]]
        rsi_higher = df['rsi'].iloc[recent_rsi_troughs[-1]] > df['rsi'].iloc[recent_rsi_troughs[-2]]
        
        return price_lower and rsi_higher
    
    def _check_bearish_divergence(self, df: pd.DataFrame,
                                   price_peaks: List[int],
                                   rsi_peaks: List[int]) -> bool:
        """
        Check for bearish divergence: price higher high, RSI lower high.
        """
        if len(price_peaks) < 2 or len(rsi_peaks) < 2:
            return False
        
        # Get last two peaks
        recent_price_peaks = sorted(price_peaks)[-2:]
        recent_rsi_peaks = sorted(rsi_peaks)[-2:]
        
        # Check if price made higher high but RSI made lower high
        price_higher = df['close'].iloc[recent_price_peaks[-1]] > df['close'].iloc[recent_price_peaks[-2]]
        rsi_lower = df['rsi'].iloc[recent_rsi_peaks[-1]] < df['rsi'].iloc[recent_rsi_peaks[-2]]
        
        return price_higher and rsi_lower
    
    async def _fetch_historical_data(self, symbol: str, lookback_days: int, 
                                     timeframe: str = 'daily') -> pd.DataFrame:
        """
        Fetch historical price data and resample if needed.
        
        Note: lookback_days refers to periods in the requested timeframe.
        For weekly/monthly, we fetch more daily data and resample.
        """
        async with self.db.get_session() as session:
            # Get latest available date
            latest_stmt = select(HistoricalPrice.date).where(
                HistoricalPrice.symbol == symbol
            ).order_by(HistoricalPrice.date.desc()).limit(1)
            
            latest_result = await session.execute(latest_stmt)
            latest_row = latest_result.scalar_one_or_none()
            
            if not latest_row:
                return pd.DataFrame()
            
            end_date = latest_row
            
            # Calculate start date based on timeframe
            if timeframe == 'monthly':
                calendar_days = lookback_days * 30 * 2  # 2x buffer for monthly
            elif timeframe == 'weekly':
                calendar_days = lookback_days * 7 * 2  # 2x buffer for weekly
            else:
                calendar_days = int(lookback_days * 1.5) + 50
            
            start_date = end_date - timedelta(days=calendar_days)
            
            # Fetch daily data
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
            
            # Convert to DataFrame
            df = pd.DataFrame([
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
            
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Resample if needed
            if timeframe == 'weekly':
                df = df.resample('W').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            elif timeframe == 'monthly':
                df = df.resample('ME').agg({  # ME = Month End
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            
            return df.reset_index()


# Test function
async def test_agent():
    """Test the RSI Analyzer"""
    print("=" * 80)
    print("Testing RSI Analyzer (Agent #14)")
    print("=" * 80)
    
    agent = RSIAnalyzer()
    await agent.initialize()
    await agent.start()
    
    try:
        # Test 1: Daily RSI
        print("\n1. Calculate Daily RSI for AAPL...")
        result = await agent._calculate_rsi({
            'symbol': 'AAPL',
            'period': 14,
            'timeframe': 'daily'
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Current RSI: {result['current_rsi']}")
            print(f"   ✅ RSI Change: {result['rsi_change']}")
            print(f"   ✅ Price: ${result['current_price']}")
        
        # Test 2: Weekly RSI
        print("\n2. Calculate Weekly RSI for AAPL...")
        result = await agent._calculate_rsi({
            'symbol': 'AAPL',
            'period': 14,
            'timeframe': 'weekly'
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Weekly RSI: {result['current_rsi']}")
        
        # Test 3: Oversold/Overbought
        print("\n3. Check Oversold/Overbought Conditions...")
        result = await agent._identify_oversold_overbought({
            'symbol': 'AAPL'
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Overall Signal: {result['overall_signal']}")
            for tf, data in result['timeframes'].items():
                print(f"   ✅ {tf.capitalize()}: RSI={data['rsi']}, {data['condition']}")
        
        print("\n" + "=" * 80)
        print("✅ Test Complete!")
        print("=" * 80)
    
    finally:
        await agent.stop()
        await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(test_agent())
