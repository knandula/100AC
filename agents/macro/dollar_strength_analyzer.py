"""
Agent #18: Dollar Strength Analyzer

Analyzes US Dollar Index (DXY) strength and its impact on gold/silver prices.
The dollar has an inverse correlation with precious metals - when the dollar
strengthens, gold/silver typically weaken (and vice versa).

Key Metrics:
- Dollar Index (DX-Y.NYB) current level and trend
- Dollar momentum and rate of change
- Correlation analysis with gold/silver
- Dollar position relative to moving averages

Capabilities:
1. analyze_dollar_index - Get current DXY level and trend analysis
2. calculate_dollar_momentum - Calculate dollar rate of change
3. assess_dollar_impact - Assess dollar's impact on precious metals
4. analyze_all_dollar - Comprehensive dollar analysis
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
from loguru import logger
from sqlalchemy import select, and_

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability, Message
from shared.database.connection import get_database
from shared.database.models import HistoricalPrice


class DollarStrengthAnalyzer(BaseAgent):
    """
    Agent #18: Dollar Strength Analyzer
    
    Analyzes US Dollar Index to assess macro impact on gold/silver.
    Dollar and precious metals typically have inverse correlation.
    """
    
    DOLLAR_SYMBOL = "DX-Y.NYB"  # ICE US Dollar Index
    
    def __init__(self):
        """Initialize the Dollar Strength Analyzer agent."""
        self.db = get_database()
        super().__init__()
        
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="dollar_strength_analyzer",
            name="Dollar Strength Analyzer",
            description="Analyzes US Dollar Index strength and impact on precious metals",
            category="macro",
            capabilities=[
                AgentCapability(
                    name="analyze_dollar_index",
                    description="Get current DXY level and trend analysis",
                    parameters={"lookback_days": "int"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="calculate_dollar_momentum",
                    description="Calculate dollar rate of change over multiple timeframes",
                    parameters={"lookback_days": "int"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="assess_dollar_impact",
                    description="Assess dollar's impact on gold/silver given current levels",
                    parameters={"gold_symbol": "str", "silver_symbol": "str"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="analyze_all_dollar",
                    description="Comprehensive dollar strength analysis",
                    parameters={"gold_symbol": "str", "silver_symbol": "str"},
                    returns="Dict[str, Any]",
                ),
            ],
            dependencies=[],
        )
    
    async def initialize(self):
        """Initialize database connection."""
        await self.db.initialize()
        logger.info(f"{self.agent_id} initialized")
    
    async def shutdown(self):
        """Cleanup resources."""
        logger.info(f"{self.agent_id} shutdown complete")
    
    async def process_request(self, message: Message) -> Dict[str, Any]:
        """Process incoming requests based on capability."""
        capability = message.topic
        data = message.data or {}
        
        if capability == "analyze_dollar_index":
            return await self._analyze_dollar_index(data)
        elif capability == "calculate_dollar_momentum":
            return await self._calculate_dollar_momentum(data)
        elif capability == "assess_dollar_impact":
            return await self._assess_dollar_impact(data)
        elif capability == "analyze_all_dollar":
            return await self._analyze_all_dollar(data)
        else:
            return {"error": f"Unknown capability: {capability}"}
    
    async def _get_dollar_data(self, lookback_days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch dollar index historical data from database."""
        try:
            async with self.db.get_session() as session:
                # Get date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days)
                
                # Query database
                query = select(HistoricalPrice).where(
                    and_(
                        HistoricalPrice.symbol == self.DOLLAR_SYMBOL,
                        HistoricalPrice.date >= start_date,
                        HistoricalPrice.date <= end_date
                    )
                ).order_by(HistoricalPrice.date)
                
                result = await session.execute(query)
                rows = result.scalars().all()
                
                if not rows:
                    logger.warning(f"No data found for {self.DOLLAR_SYMBOL}")
                    return None
                
                # Convert to DataFrame
                data = []
                for row in rows:
                    data.append({
                        'date': row.date,
                        'open': row.open,
                        'high': row.high,
                        'low': row.low,
                        'close': row.close,
                        'volume': row.volume
                    })
                
                df = pd.DataFrame(data)
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                
                logger.info(f"Loaded {len(df)} bars for {self.DOLLAR_SYMBOL}")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching dollar data: {e}")
            return None
    
    async def _analyze_dollar_index(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze current dollar index level and trend.
        
        Returns:
        - current_level: Current DXY value
        - sma_20/50/200: Moving averages
        - trend: Dollar trend (BULLISH/BEARISH/NEUTRAL)
        - position: Position relative to MAs
        """
        try:
            lookback_days = params.get('lookback_days', 365)
            
            df = await self._get_dollar_data(lookback_days)
            if df is None or len(df) < 200:
                return {"error": "Insufficient dollar index data"}
            
            current_price = float(df['close'].iloc[-1])
            
            # Calculate moving averages
            sma_20 = float(df['close'].rolling(window=20).mean().iloc[-1])
            sma_50 = float(df['close'].rolling(window=50).mean().iloc[-1])
            sma_200 = float(df['close'].rolling(window=200).mean().iloc[-1])
            
            # Determine trend
            if current_price > sma_20 > sma_50 > sma_200:
                trend = "STRONG_BULLISH"
            elif current_price > sma_200:
                trend = "BULLISH"
            elif current_price < sma_20 < sma_50 < sma_200:
                trend = "STRONG_BEARISH"
            elif current_price < sma_200:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
            
            # Position relative to 200-day MA
            pct_from_200ma = ((current_price - sma_200) / sma_200) * 100
            
            result = {
                "symbol": self.DOLLAR_SYMBOL,
                "current_level": round(current_price, 2),
                "moving_averages": {
                    "sma_20": round(sma_20, 2),
                    "sma_50": round(sma_50, 2),
                    "sma_200": round(sma_200, 2)
                },
                "trend": trend,
                "pct_from_200ma": round(pct_from_200ma, 2),
                "interpretation": self._interpret_dollar_trend(trend),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing dollar index: {e}")
            return {"error": str(e)}
    
    async def _calculate_dollar_momentum(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate dollar momentum using rate of change across multiple timeframes.
        
        Returns:
        - roc_1w/1m/3m: Rate of change over 1 week, 1 month, 3 months
        - momentum_signal: Overall momentum signal
        """
        try:
            lookback_days = params.get('lookback_days', 365)
            
            df = await self._get_dollar_data(lookback_days)
            if df is None or len(df) < 63:  # ~3 months trading days
                return {"error": "Insufficient dollar index data"}
            
            current_price = float(df['close'].iloc[-1])
            
            # Calculate rate of change for different periods
            # 1 week ago (5 trading days)
            if len(df) >= 5:
                price_1w_ago = float(df['close'].iloc[-5])
                roc_1w = ((current_price - price_1w_ago) / price_1w_ago) * 100
            else:
                roc_1w = 0.0
            
            # 1 month ago (~21 trading days)
            if len(df) >= 21:
                price_1m_ago = float(df['close'].iloc[-21])
                roc_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100
            else:
                roc_1m = 0.0
            
            # 3 months ago (~63 trading days)
            if len(df) >= 63:
                price_3m_ago = float(df['close'].iloc[-63])
                roc_3m = ((current_price - price_3m_ago) / price_3m_ago) * 100
            else:
                roc_3m = 0.0
            
            # Determine overall momentum
            momentum_scores = []
            if roc_1w > 0.5:
                momentum_scores.append(1)
            elif roc_1w < -0.5:
                momentum_scores.append(-1)
            else:
                momentum_scores.append(0)
            
            if roc_1m > 2.0:
                momentum_scores.append(1)
            elif roc_1m < -2.0:
                momentum_scores.append(-1)
            else:
                momentum_scores.append(0)
            
            if roc_3m > 5.0:
                momentum_scores.append(1)
            elif roc_3m < -5.0:
                momentum_scores.append(-1)
            else:
                momentum_scores.append(0)
            
            avg_momentum = sum(momentum_scores) / len(momentum_scores)
            
            if avg_momentum > 0.5:
                momentum_signal = "STRONG_STRENGTHENING"
            elif avg_momentum > 0:
                momentum_signal = "STRENGTHENING"
            elif avg_momentum < -0.5:
                momentum_signal = "STRONG_WEAKENING"
            elif avg_momentum < 0:
                momentum_signal = "WEAKENING"
            else:
                momentum_signal = "STABLE"
            
            result = {
                "current_level": round(current_price, 2),
                "rate_of_change": {
                    "1_week": round(roc_1w, 2),
                    "1_month": round(roc_1m, 2),
                    "3_months": round(roc_3m, 2)
                },
                "momentum_signal": momentum_signal,
                "interpretation": self._interpret_dollar_momentum(momentum_signal),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating dollar momentum: {e}")
            return {"error": str(e)}
    
    async def _assess_dollar_impact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess dollar's impact on gold/silver prices.
        
        Analyzes correlation and provides trading guidance based on dollar strength.
        """
        try:
            gold_symbol = params.get('gold_symbol', 'GLD')
            silver_symbol = params.get('silver_symbol', 'SLV')
            
            # Get dollar analysis
            dollar_analysis = await self._analyze_dollar_index({})
            if 'error' in dollar_analysis:
                return dollar_analysis
            
            dollar_momentum = await self._calculate_dollar_momentum({})
            if 'error' in dollar_momentum:
                return dollar_momentum
            
            dollar_trend = dollar_analysis['trend']
            momentum_signal = dollar_momentum['momentum_signal']
            
            # Assess impact (inverse correlation)
            if dollar_trend in ["STRONG_BULLISH", "BULLISH"]:
                if momentum_signal in ["STRONG_STRENGTHENING", "STRENGTHENING"]:
                    impact = "STRONG_BEARISH_FOR_METALS"
                    guidance = "Strong dollar headwind - Consider taking profits on gold/silver longs"
                else:
                    impact = "BEARISH_FOR_METALS"
                    guidance = "Dollar strength may limit upside in precious metals"
            elif dollar_trend in ["STRONG_BEARISH", "BEARISH"]:
                if momentum_signal in ["STRONG_WEAKENING", "WEAKENING"]:
                    impact = "STRONG_BULLISH_FOR_METALS"
                    guidance = "Weak dollar tailwind - Favorable for gold/silver positions"
                else:
                    impact = "BULLISH_FOR_METALS"
                    guidance = "Dollar weakness supports precious metals"
            else:
                impact = "NEUTRAL_FOR_METALS"
                guidance = "Dollar neutral - Focus on other factors for gold/silver"
            
            result = {
                "dollar_level": dollar_analysis['current_level'],
                "dollar_trend": dollar_trend,
                "dollar_momentum": momentum_signal,
                "impact_on_metals": impact,
                "guidance": guidance,
                "correlation_note": "Dollar and precious metals typically have inverse correlation",
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error assessing dollar impact: {e}")
            return {"error": str(e)}
    
    async def _analyze_all_dollar(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive dollar strength analysis combining all metrics."""
        try:
            gold_symbol = params.get('gold_symbol', 'GLD')
            silver_symbol = params.get('silver_symbol', 'SLV')
            
            # Get all analyses
            index_analysis = await self._analyze_dollar_index({})
            momentum_analysis = await self._calculate_dollar_momentum({})
            impact_analysis = await self._assess_dollar_impact({
                'gold_symbol': gold_symbol,
                'silver_symbol': silver_symbol
            })
            
            # Check for errors
            for analysis in [index_analysis, momentum_analysis, impact_analysis]:
                if 'error' in analysis:
                    return analysis
            
            result = {
                "dollar_index": index_analysis,
                "dollar_momentum": momentum_analysis,
                "metal_impact": impact_analysis,
                "summary": self._generate_summary(
                    index_analysis, 
                    momentum_analysis, 
                    impact_analysis
                ),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive dollar analysis: {e}")
            return {"error": str(e)}
    
    def _interpret_dollar_trend(self, trend: str) -> str:
        """Interpret what the dollar trend means for traders."""
        interpretations = {
            "STRONG_BULLISH": "Dollar in strong uptrend - significant headwind for gold/silver",
            "BULLISH": "Dollar trending higher - moderate headwind for precious metals",
            "NEUTRAL": "Dollar range-bound - not a major factor for metals",
            "BEARISH": "Dollar trending lower - moderate tailwind for gold/silver",
            "STRONG_BEARISH": "Dollar in strong downtrend - significant tailwind for precious metals"
        }
        return interpretations.get(trend, "Unknown trend")
    
    def _interpret_dollar_momentum(self, momentum: str) -> str:
        """Interpret dollar momentum signals."""
        interpretations = {
            "STRONG_STRENGTHENING": "Dollar gaining strength rapidly - bearish for metals",
            "STRENGTHENING": "Dollar showing upward momentum - mild bearish for metals",
            "STABLE": "Dollar momentum neutral",
            "WEAKENING": "Dollar losing momentum - mild bullish for metals",
            "STRONG_WEAKENING": "Dollar weakening rapidly - bullish for metals"
        }
        return interpretations.get(momentum, "Unknown momentum")
    
    def _generate_summary(
        self, 
        index: Dict[str, Any], 
        momentum: Dict[str, Any], 
        impact: Dict[str, Any]
    ) -> str:
        """Generate human-readable summary of dollar analysis."""
        dollar_level = index['current_level']
        trend = index['trend']
        mom_signal = momentum['momentum_signal']
        impact_signal = impact['impact_on_metals']
        
        summary = (
            f"US Dollar Index at {dollar_level}, {trend.replace('_', ' ').lower()} trend. "
            f"Momentum is {mom_signal.replace('_', ' ').lower()}. "
            f"Overall impact: {impact_signal.replace('_', ' ').lower()}. "
            f"{impact['guidance']}"
        )
        
        return summary


if __name__ == "__main__":
    import asyncio
    
    async def test_dollar_analyzer():
        """Test the Dollar Strength Analyzer."""
        print("=" * 80)
        print("Dollar Strength Analyzer Test")
        print("=" * 80)
        print()
        
        # Create and initialize agent
        analyzer = DollarStrengthAnalyzer()
        await analyzer.initialize()
        await analyzer.start()
        
        try:
            # Test comprehensive analysis
            print("Running comprehensive dollar analysis...")
            result = await analyzer._analyze_all_dollar({
                'gold_symbol': 'GLD',
                'silver_symbol': 'SLV'
            })
            
            if 'error' in result:
                print(f"❌ Error: {result['error']}")
            else:
                print("\n📊 Dollar Index Analysis:")
                idx = result['dollar_index']
                print(f"  Level: {idx['current_level']}")
                print(f"  SMA 20: {idx['moving_averages']['sma_20']}")
                print(f"  SMA 50: {idx['moving_averages']['sma_50']}")
                print(f"  SMA 200: {idx['moving_averages']['sma_200']}")
                print(f"  Trend: {idx['trend']}")
                print(f"  % from 200-MA: {idx['pct_from_200ma']}%")
                
                print("\n📈 Dollar Momentum:")
                mom = result['dollar_momentum']
                print(f"  1-Week ROC: {mom['rate_of_change']['1_week']}%")
                print(f"  1-Month ROC: {mom['rate_of_change']['1_month']}%")
                print(f"  3-Month ROC: {mom['rate_of_change']['3_months']}%")
                print(f"  Signal: {mom['momentum_signal']}")
                
                print("\n🎯 Impact on Precious Metals:")
                impact = result['metal_impact']
                print(f"  Impact: {impact['impact_on_metals']}")
                print(f"  Guidance: {impact['guidance']}")
                
                print("\n💡 Summary:")
                print(f"  {result['summary']}")
            
        finally:
            await analyzer.stop()
            await analyzer.shutdown()
            await analyzer.db.close()
    
    asyncio.run(test_dollar_analyzer())
