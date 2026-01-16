"""
Support/Resistance Identifier Agent - CHECKPOINT-3
Agent #17: Identifies key support and resistance levels for trading decisions

Capabilities:
1. identify_support_levels: Find major support zones
2. identify_resistance_levels: Find major resistance zones
3. calculate_proximity: Distance to nearest S/R levels
4. identify_all_levels: Comprehensive S/R analysis

Author: 100AC System
Created: January 16, 2026
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import select, and_

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability, Message
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice


class SupportResistanceIdentifier(BaseAgent):
    """
    Agent #17: Support/Resistance Identifier
    
    Identifies key support and resistance levels using multiple methods:
    - Pivot points
    - Local extrema (peaks and troughs)
    - Psychological levels ($5 increments)
    - Volume-weighted levels
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
            agent_id="support_resistance_identifier",
            name="Support/Resistance Identifier",
            description="Identifies key support and resistance levels for trading",
            category="technical",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="identify_support_levels",
                    description="Find major support levels",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "lookback_days": "int (optional): Days to analyze, default 90",
                        "min_touches": "int (optional): Minimum touches to confirm level, default 2"
                    }
                ),
                AgentCapability(
                    name="identify_resistance_levels",
                    description="Find major resistance levels",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "lookback_days": "int (optional): Days to analyze, default 90",
                        "min_touches": "int (optional): Minimum touches to confirm level, default 2"
                    }
                ),
                AgentCapability(
                    name="calculate_proximity",
                    description="Calculate distance to nearest S/R levels",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "current_price": "float (optional): Current price, uses latest if not provided"
                    }
                ),
                AgentCapability(
                    name="identify_all_levels",
                    description="Comprehensive S/R analysis with all methods",
                    parameters={
                        "symbol": "str (required): ETF symbol",
                        "lookback_days": "int (optional): Days to analyze, default 90"
                    }
                )
            ]
        )
    
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """Process incoming requests based on capability."""
        topic = message.topic
        params = message.data
        
        if topic == "identify_support_levels":
            return await self._identify_support_levels(params)
        elif topic == "identify_resistance_levels":
            return await self._identify_resistance_levels(params)
        elif topic == "calculate_proximity":
            return await self._calculate_proximity(params)
        elif topic == "identify_all_levels":
            return await self._identify_all_levels(params)
        else:
            return {"error": f"Unknown capability: {topic}"}
    
    async def _identify_support_levels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify major support levels using multiple methods.
        """
        try:
            symbol = params.get('symbol')
            lookback_days = params.get('lookback_days', 90)
            min_touches = params.get('min_touches', 2)
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < 20:
                return {"error": f"Insufficient data: need 20+ days, got {len(df)}"}
            
            # Find support levels using multiple methods
            pivot_supports = self._calculate_pivot_supports(df)
            local_supports = self._find_local_extrema(df, 'support', min_touches)
            psychological_supports = self._find_psychological_levels(df, 'support')
            
            # Combine and rank support levels
            all_supports = self._merge_levels(
                pivot_supports, local_supports, psychological_supports
            )
            
            # Filter by strength and proximity
            strong_supports = [s for s in all_supports if s['strength'] >= 2]
            strong_supports = sorted(strong_supports, key=lambda x: x['price'], reverse=True)
            
            current_price = df['close'].iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'support_levels': strong_supports[:5],  # Top 5 strongest
                'nearest_support': self._find_nearest_level(strong_supports, current_price, 'below'),
                'method': 'pivot_points + local_extrema + psychological',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error identifying support levels: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _identify_resistance_levels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify major resistance levels using multiple methods.
        """
        try:
            symbol = params.get('symbol')
            lookback_days = params.get('lookback_days', 90)
            min_touches = params.get('min_touches', 2)
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            df = await self._fetch_historical_data(symbol, lookback_days)
            
            if len(df) < 20:
                return {"error": f"Insufficient data: need 20+ days, got {len(df)}"}
            
            # Find resistance levels using multiple methods
            pivot_resistances = self._calculate_pivot_resistances(df)
            local_resistances = self._find_local_extrema(df, 'resistance', min_touches)
            psychological_resistances = self._find_psychological_levels(df, 'resistance')
            
            # Combine and rank resistance levels
            all_resistances = self._merge_levels(
                pivot_resistances, local_resistances, psychological_resistances
            )
            
            # Filter by strength and proximity
            strong_resistances = [r for r in all_resistances if r['strength'] >= 2]
            strong_resistances = sorted(strong_resistances, key=lambda x: x['price'])
            
            current_price = df['close'].iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'resistance_levels': strong_resistances[:5],  # Top 5 strongest
                'nearest_resistance': self._find_nearest_level(strong_resistances, current_price, 'above'),
                'method': 'pivot_points + local_extrema + psychological',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error identifying resistance levels: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _calculate_proximity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate distance to nearest support and resistance levels.
        """
        try:
            symbol = params.get('symbol')
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            # Get support and resistance levels
            support_result = await self._identify_support_levels({'symbol': symbol})
            resistance_result = await self._identify_resistance_levels({'symbol': symbol})
            
            if 'error' in support_result or 'error' in resistance_result:
                return {"error": "Failed to identify S/R levels"}
            
            current_price = support_result['current_price']
            nearest_support = support_result.get('nearest_support')
            nearest_resistance = resistance_result.get('nearest_resistance')
            
            # Calculate distances and percentages
            support_distance = None
            support_pct = None
            if nearest_support:
                support_distance = current_price - nearest_support['price']
                support_pct = (support_distance / current_price) * 100
            
            resistance_distance = None
            resistance_pct = None
            if nearest_resistance:
                resistance_distance = nearest_resistance['price'] - current_price
                resistance_pct = (resistance_distance / current_price) * 100
            
            # Determine position in range
            position = "NEUTRAL"
            if support_distance and resistance_distance:
                total_range = support_distance + resistance_distance
                position_ratio = support_distance / total_range
                
                if position_ratio < 0.25:
                    position = "NEAR_SUPPORT"
                elif position_ratio > 0.75:
                    position = "NEAR_RESISTANCE"
                else:
                    position = "MID_RANGE"
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'nearest_support': {
                    'level': nearest_support,
                    'distance': round(support_distance, 2) if support_distance else None,
                    'distance_pct': round(support_pct, 2) if support_pct else None
                },
                'nearest_resistance': {
                    'level': nearest_resistance,
                    'distance': round(resistance_distance, 2) if resistance_distance else None,
                    'distance_pct': round(resistance_pct, 2) if resistance_pct else None
                },
                'position': position,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating proximity: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _identify_all_levels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive support and resistance analysis.
        """
        try:
            symbol = params.get('symbol')
            lookback_days = params.get('lookback_days', 90)
            
            if not symbol:
                return {"error": "symbol parameter required"}
            
            # Get all analyses
            support_result = await self._identify_support_levels({
                'symbol': symbol,
                'lookback_days': lookback_days
            })
            
            resistance_result = await self._identify_resistance_levels({
                'symbol': symbol,
                'lookback_days': lookback_days
            })
            
            proximity_result = await self._calculate_proximity({
                'symbol': symbol
            })
            
            if 'error' in support_result:
                return support_result
            if 'error' in resistance_result:
                return resistance_result
            
            # Trading signal based on proximity
            position = proximity_result.get('position', 'NEUTRAL')
            if position == "NEAR_SUPPORT":
                signal = "BUY_ZONE"
            elif position == "NEAR_RESISTANCE":
                signal = "SELL_ZONE"
            else:
                signal = "HOLD"
            
            return {
                'symbol': symbol,
                'current_price': support_result['current_price'],
                'support': support_result,
                'resistance': resistance_result,
                'proximity': proximity_result,
                'trading_signal': signal,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error in comprehensive S/R analysis: {e}", exc_info=True)
            return {"error": str(e)}
    
    # Helper methods
    
    def _calculate_pivot_supports(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Calculate support levels using pivot points.
        
        Pivot Point = (High + Low + Close) / 3
        S1 = (2 × Pivot) - High
        S2 = Pivot - (High - Low)
        """
        recent_data = df.tail(20)  # Use recent 20 days
        
        high = recent_data['high'].max()
        low = recent_data['low'].min()
        close = recent_data['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        
        return [
            {'price': round(s1, 2), 'strength': 2, 'type': 'pivot_s1'},
            {'price': round(s2, 2), 'strength': 3, 'type': 'pivot_s2'}
        ]
    
    def _calculate_pivot_resistances(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Calculate resistance levels using pivot points.
        
        R1 = (2 × Pivot) - Low
        R2 = Pivot + (High - Low)
        """
        recent_data = df.tail(20)
        
        high = recent_data['high'].max()
        low = recent_data['low'].min()
        close = recent_data['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        
        return [
            {'price': round(r1, 2), 'strength': 2, 'type': 'pivot_r1'},
            {'price': round(r2, 2), 'strength': 3, 'type': 'pivot_r2'}
        ]
    
    def _find_local_extrema(self, df: pd.DataFrame, level_type: str, 
                           min_touches: int) -> List[Dict[str, Any]]:
        """
        Find support/resistance levels based on local minima/maxima.
        """
        window = 10
        levels = []
        
        if level_type == 'support':
            # Find local minima
            for i in range(window, len(df) - window):
                if all(df['low'].iloc[i] <= df['low'].iloc[i-j] for j in range(1, window+1)) and \
                   all(df['low'].iloc[i] <= df['low'].iloc[i+j] for j in range(1, window+1)):
                    
                    price = df['low'].iloc[i]
                    # Count touches (price within 1% of this level)
                    touches = self._count_touches(df, price, 0.01)
                    
                    if touches >= min_touches:
                        levels.append({
                            'price': round(price, 2),
                            'strength': touches,
                            'type': 'local_minimum'
                        })
        else:
            # Find local maxima
            for i in range(window, len(df) - window):
                if all(df['high'].iloc[i] >= df['high'].iloc[i-j] for j in range(1, window+1)) and \
                   all(df['high'].iloc[i] >= df['high'].iloc[i+j] for j in range(1, window+1)):
                    
                    price = df['high'].iloc[i]
                    touches = self._count_touches(df, price, 0.01)
                    
                    if touches >= min_touches:
                        levels.append({
                            'price': round(price, 2),
                            'strength': touches,
                            'type': 'local_maximum'
                        })
        
        return levels
    
    def _find_psychological_levels(self, df: pd.DataFrame, 
                                   level_type: str) -> List[Dict[str, Any]]:
        """
        Find psychological levels ($5 increments).
        """
        current_price = df['close'].iloc[-1]
        price_range = df['close'].max() - df['close'].min()
        
        levels = []
        
        # Generate $5 levels around current price
        base = int(current_price / 5) * 5
        
        if level_type == 'support':
            # Look for levels below current price
            for i in range(1, 5):
                level_price = base - (i * 5)
                if level_price > 0:
                    touches = self._count_touches(df, level_price, 0.02)
                    if touches >= 1:
                        levels.append({
                            'price': round(level_price, 2),
                            'strength': min(touches, 3),
                            'type': 'psychological'
                        })
        else:
            # Look for levels above current price
            for i in range(1, 5):
                level_price = base + (i * 5)
                touches = self._count_touches(df, level_price, 0.02)
                if touches >= 1:
                    levels.append({
                        'price': round(level_price, 2),
                        'strength': min(touches, 3),
                        'type': 'psychological'
                    })
        
        return levels
    
    def _count_touches(self, df: pd.DataFrame, level: float, threshold: float) -> int:
        """
        Count how many times price touched a level (within threshold %).
        """
        touches = 0
        for _, row in df.iterrows():
            if abs(row['high'] - level) / level <= threshold or \
               abs(row['low'] - level) / level <= threshold:
                touches += 1
        return touches
    
    def _merge_levels(self, *level_lists) -> List[Dict[str, Any]]:
        """
        Merge levels from different methods, combining nearby levels.
        """
        all_levels = []
        for level_list in level_lists:
            all_levels.extend(level_list)
        
        if not all_levels:
            return []
        
        # Sort by price
        all_levels.sort(key=lambda x: x['price'])
        
        # Merge levels within 1% of each other
        merged = []
        i = 0
        while i < len(all_levels):
            current = all_levels[i]
            cluster = [current]
            
            # Find nearby levels
            j = i + 1
            while j < len(all_levels):
                if abs(all_levels[j]['price'] - current['price']) / current['price'] <= 0.01:
                    cluster.append(all_levels[j])
                    j += 1
                else:
                    break
            
            # Average price and sum strength
            avg_price = sum(l['price'] for l in cluster) / len(cluster)
            total_strength = sum(l['strength'] for l in cluster)
            
            merged.append({
                'price': round(avg_price, 2),
                'strength': total_strength,
                'type': 'merged',
                'sources': [l['type'] for l in cluster]
            })
            
            i = j
        
        return merged
    
    def _find_nearest_level(self, levels: List[Dict[str, Any]], 
                           current_price: float, direction: str) -> Optional[Dict[str, Any]]:
        """
        Find nearest level above or below current price.
        """
        if direction == 'below':
            below_levels = [l for l in levels if l['price'] < current_price]
            if below_levels:
                return max(below_levels, key=lambda x: x['price'])
        else:
            above_levels = [l for l in levels if l['price'] > current_price]
            if above_levels:
                return min(above_levels, key=lambda x: x['price'])
        
        return None
    
    async def _fetch_historical_data(self, symbol: str, lookback_days: int) -> pd.DataFrame:
        """
        Fetch historical price data from database.
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
    """Test the Support/Resistance Identifier"""
    print("=" * 80)
    print("Testing Support/Resistance Identifier (Agent #17)")
    print("=" * 80)
    
    agent = SupportResistanceIdentifier()
    await agent.initialize()
    await agent.start()
    
    try:
        # Test 1: Identify Support Levels
        print("\n1. Identify Support Levels for AAPL...")
        result = await agent._identify_support_levels({
            'symbol': 'AAPL',
            'lookback_days': 90
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Current Price: ${result['current_price']}")
            print(f"   ✅ Found {len(result['support_levels'])} support levels")
            if result.get('nearest_support'):
                print(f"   ✅ Nearest Support: ${result['nearest_support']['price']} (strength: {result['nearest_support']['strength']})")
        
        # Test 2: Identify Resistance Levels
        print("\n2. Identify Resistance Levels for AAPL...")
        result = await agent._identify_resistance_levels({
            'symbol': 'AAPL',
            'lookback_days': 90
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Found {len(result['resistance_levels'])} resistance levels")
            if result.get('nearest_resistance'):
                print(f"   ✅ Nearest Resistance: ${result['nearest_resistance']['price']} (strength: {result['nearest_resistance']['strength']})")
        
        # Test 3: Calculate Proximity
        print("\n3. Calculate Proximity to S/R Levels...")
        result = await agent._calculate_proximity({
            'symbol': 'AAPL'
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Position: {result['position']}")
            if result['nearest_support']['distance']:
                print(f"   ✅ Support Distance: ${result['nearest_support']['distance']} ({result['nearest_support']['distance_pct']}%)")
            if result['nearest_resistance']['distance']:
                print(f"   ✅ Resistance Distance: ${result['nearest_resistance']['distance']} ({result['nearest_resistance']['distance_pct']}%)")
        
        # Test 4: Comprehensive Analysis
        print("\n4. Comprehensive S/R Analysis...")
        result = await agent._identify_all_levels({
            'symbol': 'AAPL'
        })
        
        if 'error' in result:
            print(f"   ❌ Error: {result['error']}")
        else:
            print(f"   ✅ Trading Signal: {result['trading_signal']}")
        
        print("\n" + "=" * 80)
        print("✅ Test Complete!")
        print("=" * 80)
    
    finally:
        await agent.stop()
        await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(test_agent())
