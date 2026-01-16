"""
Agent #19: Real Yield Analyzer

Analyzes real yields (nominal yields minus inflation) and their impact on gold/silver.
Real yields represent the opportunity cost of holding non-yielding assets like gold.

Key Concept:
- High real yields (>2%) = Bearish for gold (investors prefer bonds)
- Low/negative real yields (<0%) = Bullish for gold (no opportunity cost)
- Real Yield = Nominal Yield - Inflation Expectations

Data Sources:
- 10-Year Treasury Yield (^TNX): Nominal yield
- TIPS ETF (TIP): Implied inflation expectations
- Alternative: Calculate from actual inflation data

Capabilities:
1. analyze_nominal_yields - Get current 10-year treasury yield levels
2. calculate_real_yields - Calculate real yields from nominal - inflation
3. assess_yield_impact - Assess real yields' impact on precious metals
4. analyze_all_yields - Comprehensive yield analysis
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


class RealYieldAnalyzer(BaseAgent):
    """
    Agent #19: Real Yield Analyzer
    
    Analyzes real yields (nominal yields - inflation) to assess opportunity
    cost of holding gold/silver. High real yields are bearish for metals,
    low/negative real yields are bullish.
    """
    
    TNX_SYMBOL = "^TNX"  # 10-Year Treasury Note Yield
    TIP_SYMBOL = "TIP"   # iShares TIPS Bond ETF (for inflation expectations)
    
    def __init__(self):
        """Initialize the Real Yield Analyzer agent."""
        self.db = get_database()
        super().__init__()
        
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="real_yield_analyzer",
            name="Real Yield Analyzer",
            description="Analyzes real yields and their impact on precious metals",
            category="macro",
            capabilities=[
                AgentCapability(
                    name="analyze_nominal_yields",
                    description="Get current 10-year treasury yield levels and trends",
                    parameters={"lookback_days": "int"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="calculate_real_yields",
                    description="Calculate real yields (nominal - inflation proxy)",
                    parameters={"lookback_days": "int"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="assess_yield_impact",
                    description="Assess real yields' impact on gold/silver",
                    parameters={"gold_symbol": "str", "silver_symbol": "str"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="analyze_all_yields",
                    description="Comprehensive real yield analysis",
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
        
        if capability == "analyze_nominal_yields":
            return await self._analyze_nominal_yields(data)
        elif capability == "calculate_real_yields":
            return await self._calculate_real_yields(data)
        elif capability == "assess_yield_impact":
            return await self._assess_yield_impact(data)
        elif capability == "analyze_all_yields":
            return await self._analyze_all_yields(data)
        else:
            return {"error": f"Unknown capability: {capability}"}
    
    async def _get_treasury_data(self, lookback_days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch 10-year treasury yield data from database."""
        try:
            async with self.db.get_session() as session:
                # Get date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days)
                
                # Query database
                query = select(HistoricalPrice).where(
                    and_(
                        HistoricalPrice.symbol == self.TNX_SYMBOL,
                        HistoricalPrice.date >= start_date,
                        HistoricalPrice.date <= end_date
                    )
                ).order_by(HistoricalPrice.date)
                
                result = await session.execute(query)
                rows = result.scalars().all()
                
                if not rows:
                    logger.warning(f"No data found for {self.TNX_SYMBOL}")
                    return None
                
                # Convert to DataFrame
                # Note: For ^TNX, the 'close' price IS the yield percentage
                # E.g., close=4.25 means 4.25% yield
                data = []
                for row in rows:
                    data.append({
                        'date': row.date,
                        'yield': row.close,  # close price = yield percentage
                    })
                
                df = pd.DataFrame(data)
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                
                logger.info(f"Loaded {len(df)} bars for {self.TNX_SYMBOL}")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching treasury data: {e}")
            return None
    
    async def _get_tips_data(self, lookback_days: int = 365) -> Optional[pd.DataFrame]:
        """Fetch TIPS ETF data to proxy inflation expectations."""
        try:
            async with self.db.get_session() as session:
                # Get date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days)
                
                # Query database
                query = select(HistoricalPrice).where(
                    and_(
                        HistoricalPrice.symbol == self.TIP_SYMBOL,
                        HistoricalPrice.date >= start_date,
                        HistoricalPrice.date <= end_date
                    )
                ).order_by(HistoricalPrice.date)
                
                result = await session.execute(query)
                rows = result.scalars().all()
                
                if not rows:
                    logger.warning(f"No data found for {self.TIP_SYMBOL}")
                    return None
                
                # Convert to DataFrame
                data = []
                for row in rows:
                    data.append({
                        'date': row.date,
                        'close': row.close,
                    })
                
                df = pd.DataFrame(data)
                df.set_index('date', inplace=True)
                df.sort_index(inplace=True)
                
                logger.info(f"Loaded {len(df)} bars for {self.TIP_SYMBOL}")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching TIPS data: {e}")
            return None
    
    async def _analyze_nominal_yields(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze current nominal 10-year treasury yields.
        
        Returns:
        - current_yield: Current 10Y yield in %
        - yield_ma_20/50/200: Moving averages of yields
        - yield_trend: Trend (RISING/FALLING/STABLE)
        - yield_change: Change over various periods
        """
        try:
            lookback_days = params.get('lookback_days', 365)
            
            df = await self._get_treasury_data(lookback_days)
            if df is None or len(df) < 200:
                return {"error": "Insufficient treasury yield data"}
            
            current_yield = float(df['yield'].iloc[-1])
            
            # Calculate moving averages of yields
            ma_20 = float(df['yield'].rolling(window=20).mean().iloc[-1])
            ma_50 = float(df['yield'].rolling(window=50).mean().iloc[-1])
            ma_200 = float(df['yield'].rolling(window=200).mean().iloc[-1])
            
            # Determine yield trend
            if current_yield > ma_20 > ma_50:
                trend = "RISING"
            elif current_yield < ma_20 < ma_50:
                trend = "FALLING"
            else:
                trend = "STABLE"
            
            # Calculate yield changes
            changes = {}
            if len(df) >= 5:
                changes['1_week'] = round(current_yield - float(df['yield'].iloc[-5]), 2)
            if len(df) >= 21:
                changes['1_month'] = round(current_yield - float(df['yield'].iloc[-21]), 2)
            if len(df) >= 63:
                changes['3_months'] = round(current_yield - float(df['yield'].iloc[-63]), 2)
            
            result = {
                "symbol": self.TNX_SYMBOL,
                "current_yield": round(current_yield, 2),
                "moving_averages": {
                    "ma_20": round(ma_20, 2),
                    "ma_50": round(ma_50, 2),
                    "ma_200": round(ma_200, 2)
                },
                "trend": trend,
                "yield_changes": changes,
                "interpretation": self._interpret_nominal_yields(current_yield, trend),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing nominal yields: {e}")
            return {"error": str(e)}
    
    async def _calculate_real_yields(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate real yields using TIPS as inflation proxy.
        
        Method: We'll use a simplified approach:
        - TIPS yield can be derived from TIP ETF performance
        - Real yield ≈ Nominal yield - Implied inflation
        - For simplicity, we'll estimate inflation from TIP price changes
        """
        try:
            lookback_days = params.get('lookback_days', 365)
            
            # Get nominal yields
            tnx_df = await self._get_treasury_data(lookback_days)
            if tnx_df is None or len(tnx_df) < 63:
                return {"error": "Insufficient treasury yield data"}
            
            # Get TIPS data
            tip_df = await self._get_tips_data(lookback_days)
            if tip_df is None or len(tip_df) < 63:
                return {"error": "Insufficient TIPS data"}
            
            # Align dates
            common_dates = tnx_df.index.intersection(tip_df.index)
            if len(common_dates) < 63:
                return {"error": "Insufficient overlapping data"}
            
            tnx_aligned = tnx_df.loc[common_dates]
            tip_aligned = tip_df.loc[common_dates]
            
            current_nominal_yield = float(tnx_aligned['yield'].iloc[-1])
            
            # Estimate implied inflation from TIP price momentum
            # TIPS prices rise when inflation expectations increase
            # Calculate 3-month annualized return of TIP as inflation proxy
            tip_price_current = float(tip_aligned['close'].iloc[-1])
            tip_price_3m_ago = float(tip_aligned['close'].iloc[-63]) if len(tip_aligned) >= 63 else tip_price_current
            
            tip_return_3m = ((tip_price_current - tip_price_3m_ago) / tip_price_3m_ago) * 100
            implied_inflation = tip_return_3m * 4  # Annualize (rough estimate)
            
            # Alternative: Use a baseline inflation estimate
            # For better accuracy, could integrate actual CPI data
            baseline_inflation = 2.5  # Fed's target
            
            # Use the higher of TIP-implied or baseline
            estimated_inflation = max(implied_inflation, baseline_inflation)
            
            # Calculate real yield
            real_yield = current_nominal_yield - estimated_inflation
            
            # Classify real yield level
            if real_yield > 2.0:
                level = "VERY_HIGH"
            elif real_yield > 1.0:
                level = "HIGH"
            elif real_yield > 0:
                level = "POSITIVE"
            elif real_yield > -1.0:
                level = "SLIGHTLY_NEGATIVE"
            else:
                level = "VERY_NEGATIVE"
            
            result = {
                "nominal_yield": round(current_nominal_yield, 2),
                "estimated_inflation": round(estimated_inflation, 2),
                "real_yield": round(real_yield, 2),
                "real_yield_level": level,
                "interpretation": self._interpret_real_yields(real_yield),
                "note": "Inflation estimated from TIPS ETF performance + baseline",
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating real yields: {e}")
            return {"error": str(e)}
    
    async def _assess_yield_impact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess real yields' impact on gold/silver prices.
        
        High real yields = Bearish for gold (opportunity cost of holding gold)
        Low/negative real yields = Bullish for gold (no opportunity cost)
        """
        try:
            gold_symbol = params.get('gold_symbol', 'GLD')
            silver_symbol = params.get('silver_symbol', 'SLV')
            
            # Get nominal yield analysis
            nominal_analysis = await self._analyze_nominal_yields({})
            if 'error' in nominal_analysis:
                return nominal_analysis
            
            # Get real yield calculation
            real_yield_analysis = await self._calculate_real_yields({})
            if 'error' in real_yield_analysis:
                return real_yield_analysis
            
            real_yield = real_yield_analysis['real_yield']
            real_yield_level = real_yield_analysis['real_yield_level']
            yield_trend = nominal_analysis['trend']
            
            # Assess impact based on real yield level
            if real_yield_level in ["VERY_HIGH", "HIGH"]:
                if yield_trend == "RISING":
                    impact = "STRONG_BEARISH_FOR_METALS"
                    guidance = "High and rising real yields - strong headwind for gold/silver. Consider reducing positions."
                else:
                    impact = "BEARISH_FOR_METALS"
                    guidance = "High real yields create opportunity cost for holding non-yielding metals."
            elif real_yield_level == "POSITIVE":
                impact = "NEUTRAL_TO_BEARISH_FOR_METALS"
                guidance = "Positive real yields provide moderate alternative to gold/silver."
            elif real_yield_level == "SLIGHTLY_NEGATIVE":
                impact = "NEUTRAL_TO_BULLISH_FOR_METALS"
                guidance = "Low real yields reduce opportunity cost of holding precious metals."
            else:  # VERY_NEGATIVE
                if yield_trend == "FALLING":
                    impact = "STRONG_BULLISH_FOR_METALS"
                    guidance = "Negative and falling real yields - strong tailwind for gold/silver. Favorable environment."
                else:
                    impact = "BULLISH_FOR_METALS"
                    guidance = "Negative real yields make gold/silver attractive vs bonds."
            
            result = {
                "nominal_yield": nominal_analysis['current_yield'],
                "real_yield": real_yield,
                "real_yield_level": real_yield_level,
                "yield_trend": yield_trend,
                "impact_on_metals": impact,
                "guidance": guidance,
                "context": "Real yields represent opportunity cost of holding gold/silver vs bonds",
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error assessing yield impact: {e}")
            return {"error": str(e)}
    
    async def _analyze_all_yields(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive real yield analysis combining all metrics."""
        try:
            gold_symbol = params.get('gold_symbol', 'GLD')
            silver_symbol = params.get('silver_symbol', 'SLV')
            
            # Get all analyses
            nominal_analysis = await self._analyze_nominal_yields({})
            real_yield_analysis = await self._calculate_real_yields({})
            impact_analysis = await self._assess_yield_impact({
                'gold_symbol': gold_symbol,
                'silver_symbol': silver_symbol
            })
            
            # Check for errors
            for analysis in [nominal_analysis, real_yield_analysis, impact_analysis]:
                if 'error' in analysis:
                    return analysis
            
            result = {
                "nominal_yields": nominal_analysis,
                "real_yields": real_yield_analysis,
                "metal_impact": impact_analysis,
                "summary": self._generate_summary(
                    nominal_analysis,
                    real_yield_analysis,
                    impact_analysis
                ),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in comprehensive yield analysis: {e}")
            return {"error": str(e)}
    
    def _interpret_nominal_yields(self, current_yield: float, trend: str) -> str:
        """Interpret nominal yield levels."""
        if current_yield > 5.0:
            base = "Very high nominal yields"
        elif current_yield > 4.0:
            base = "Elevated nominal yields"
        elif current_yield > 3.0:
            base = "Moderate nominal yields"
        elif current_yield > 2.0:
            base = "Low nominal yields"
        else:
            base = "Very low nominal yields"
        
        trend_text = {
            "RISING": "and rising",
            "FALLING": "and falling",
            "STABLE": "and stable"
        }
        
        return f"{base} {trend_text.get(trend, '')}"
    
    def _interpret_real_yields(self, real_yield: float) -> str:
        """Interpret what real yield levels mean for gold/silver."""
        if real_yield > 2.0:
            return "Very high real yields - strong bearish for gold/silver (bonds attractive)"
        elif real_yield > 1.0:
            return "High real yields - bearish for gold/silver (opportunity cost significant)"
        elif real_yield > 0:
            return "Positive real yields - mild bearish for precious metals"
        elif real_yield > -1.0:
            return "Slightly negative real yields - mild bullish for gold/silver"
        else:
            return "Very negative real yields - strong bullish for gold/silver (no opportunity cost)"
    
    def _generate_summary(
        self,
        nominal: Dict[str, Any],
        real: Dict[str, Any],
        impact: Dict[str, Any]
    ) -> str:
        """Generate human-readable summary of yield analysis."""
        nom_yield = nominal['current_yield']
        real_yield = real['real_yield']
        inflation = real['estimated_inflation']
        impact_signal = impact['impact_on_metals']
        
        summary = (
            f"10-Year Treasury yield at {nom_yield}%, estimated inflation {inflation}%, "
            f"resulting in real yield of {real_yield}%. "
            f"Overall impact: {impact_signal.replace('_', ' ').lower()}. "
            f"{impact['guidance']}"
        )
        
        return summary


if __name__ == "__main__":
    import asyncio
    
    async def test_yield_analyzer():
        """Test the Real Yield Analyzer."""
        print("=" * 80)
        print("Real Yield Analyzer Test")
        print("=" * 80)
        print()
        
        # Create and initialize agent
        analyzer = RealYieldAnalyzer()
        await analyzer.initialize()
        await analyzer.start()
        
        try:
            # Test comprehensive analysis
            print("Running comprehensive yield analysis...")
            result = await analyzer._analyze_all_yields({
                'gold_symbol': 'GLD',
                'silver_symbol': 'SLV'
            })
            
            if 'error' in result:
                print(f"❌ Error: {result['error']}")
            else:
                print("\n📊 Nominal Yields:")
                nom = result['nominal_yields']
                print(f"  10Y Treasury: {nom['current_yield']}%")
                print(f"  MA 20: {nom['moving_averages']['ma_20']}%")
                print(f"  MA 50: {nom['moving_averages']['ma_50']}%")
                print(f"  MA 200: {nom['moving_averages']['ma_200']}%")
                print(f"  Trend: {nom['trend']}")
                if 'yield_changes' in nom:
                    changes = nom['yield_changes']
                    if '1_week' in changes:
                        print(f"  1-Week Change: {changes['1_week']:+.2f}%")
                    if '1_month' in changes:
                        print(f"  1-Month Change: {changes['1_month']:+.2f}%")
                    if '3_months' in changes:
                        print(f"  3-Month Change: {changes['3_months']:+.2f}%")
                
                print("\n📈 Real Yields:")
                real = result['real_yields']
                print(f"  Nominal Yield: {real['nominal_yield']}%")
                print(f"  Est. Inflation: {real['estimated_inflation']}%")
                print(f"  Real Yield: {real['real_yield']}%")
                print(f"  Level: {real['real_yield_level']}")
                
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
    
    asyncio.run(test_yield_analyzer())
