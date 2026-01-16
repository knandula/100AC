"""
Agent #20: Entry/Exit Signal Generator

Aggregates technical + macro analysis into actionable BUY/SELL signals with:
- Confidence scoring (0-100)
- Position sizing recommendations  
- Entry/exit price ranges
- Stop loss / take profit levels
- Detailed reasoning

Signal Weighting (50/50 balanced):
- Technical Analysis: 50 points (MA trend, RSI, S/R)
- Macro Analysis: 50 points (Dollar strength, Real yields)

For aggressive trading profile:
- Strong Buy: 75-100 confidence
- Buy: 60-74 confidence
- Hold: 40-59 confidence
- Sell: 25-39 confidence
- Strong Sell: 0-24 confidence
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.data_models import AgentMetadata, AgentCapability, Message
from shared.database.connection import get_database


class EntryExitSignalGenerator(BaseAgent):
    """
    Agent #20: Entry/Exit Signal Generator
    
    Combines technical + macro signals into actionable trading recommendations.
    Provides confidence scores, position sizing, and trade planning.
    """
    
    def __init__(self):
        """Initialize the Entry/Exit Signal Generator agent."""
        self.db = get_database()
        super().__init__()
        
    def get_metadata(self) -> AgentMetadata:
        """Return agent metadata."""
        return AgentMetadata(
            agent_id="entry_exit_signal_generator",
            name="Entry/Exit Signal Generator",
            description="Generates BUY/SELL signals by combining technical + macro analysis",
            category="signals",
            capabilities=[
                AgentCapability(
                    name="generate_signal",
                    description="Generate comprehensive trading signal with confidence score",
                    parameters={
                        "symbol": "str",
                        "technical_data": "Dict[str, Any]",
                        "macro_data": "Dict[str, Any]"
                    },
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="calculate_position_size",
                    description="Calculate position size based on confidence and risk profile",
                    parameters={"confidence": "int", "risk_profile": "str"},
                    returns="Dict[str, Any]",
                ),
                AgentCapability(
                    name="generate_trade_plan",
                    description="Generate complete trade plan with entry/exit/stops",
                    parameters={
                        "symbol": "str",
                        "signal": "str",
                        "current_price": "float",
                        "support": "float",
                        "resistance": "float"
                    },
                    returns="Dict[str, Any]",
                ),
            ],
            dependencies=[
                "moving_average_calculator",
                "rsi_analyzer",
                "support_resistance_identifier",
                "dollar_strength_analyzer",
                "real_yield_analyzer"
            ],
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
        
        if capability == "generate_signal":
            return await self._generate_signal(data)
        elif capability == "calculate_position_size":
            return await self._calculate_position_size(data)
        elif capability == "generate_trade_plan":
            return await self._generate_trade_plan(data)
        else:
            return {"error": f"Unknown capability: {capability}"}
    
    async def _generate_signal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive trading signal.
        
        Combines technical + macro analysis with equal weighting (50/50).
        """
        try:
            symbol = params.get('symbol')
            technical_data = params.get('technical_data', {})
            macro_data = params.get('macro_data', {})
            
            if not symbol:
                return {"error": "Symbol required"}
            
            # Score technical signals (max 50 points)
            tech_score, tech_breakdown = self._score_technical(technical_data)
            
            # Score macro signals (max 50 points)
            macro_score, macro_breakdown = self._score_macro(macro_data)
            
            # Combined confidence (0-100)
            confidence = tech_score + macro_score
            
            # Determine action
            action = self._determine_action(confidence)
            
            # Get position size recommendation
            position_size = await self._calculate_position_size({
                'confidence': confidence,
                'risk_profile': 'aggressive'
            })
            
            # Extract price info for trade plan
            current_price = technical_data.get('ma_data', {}).get('current_price', 0)
            support = technical_data.get('sr_data', {}).get('nearest_support', 0)
            resistance = technical_data.get('sr_data', {}).get('nearest_resistance', 0)
            
            # Generate trade plan
            trade_plan = None
            if action in ['STRONG_BUY', 'BUY', 'STRONG_SELL', 'SELL']:
                trade_plan = await self._generate_trade_plan({
                    'symbol': symbol,
                    'signal': action,
                    'current_price': current_price,
                    'support': support,
                    'resistance': resistance
                })
            
            # Compile reasoning
            reasoning = []
            reasoning.extend(tech_breakdown['reasons'])
            reasoning.extend(macro_breakdown['reasons'])
            
            result = {
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "technical_score": tech_score,
                "macro_score": macro_score,
                "position_size_pct": position_size.get('position_size_pct', 0),
                "breakdown": {
                    "technical": tech_breakdown,
                    "macro": macro_breakdown
                },
                "trade_plan": trade_plan,
                "reasoning": reasoning,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return {"error": str(e)}
    
    def _score_technical(self, technical_data: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        """
        Score technical analysis signals (max 50 points).
        
        Breakdown:
        - Moving Averages: 15 points
        - RSI: 15 points
        - Support/Resistance: 20 points
        """
        score = 0
        reasons = []
        details = {}
        
        # Moving Averages (15 points max)
        ma_data = technical_data.get('ma_data', {})
        trend = ma_data.get('trend_signal', 'UNKNOWN')
        
        if trend == 'STRONG_BULLISH':
            score += 15
            reasons.append("✅ Strong bullish trend (price >> 200-MA)")
            details['ma_score'] = 15
        elif trend == 'BULLISH':
            score += 10
            reasons.append("✅ Bullish trend (price > 200-MA)")
            details['ma_score'] = 10
        elif trend == 'NEUTRAL':
            score += 7
            details['ma_score'] = 7
        elif trend == 'BEARISH':
            score += 3
            reasons.append("⚠️ Bearish trend (price < 200-MA)")
            details['ma_score'] = 3
        elif trend == 'STRONG_BEARISH':
            score += 0
            reasons.append("❌ Strong bearish trend (price << 200-MA)")
            details['ma_score'] = 0
        
        # Check for golden/death cross
        crossovers = ma_data.get('crossovers', {})
        if crossovers.get('golden_cross'):
            score += 5
            reasons.append("✅ Golden cross detected (50/200 MA)")
        elif crossovers.get('death_cross'):
            score -= 5
            reasons.append("❌ Death cross detected (50/200 MA)")
            score = max(0, score)  # Don't go negative
        
        # RSI (15 points max)
        rsi_data = technical_data.get('rsi_data', {})
        rsi_signal = rsi_data.get('overall_signal', 'NEUTRAL')
        monthly_rsi = rsi_data.get('timeframes', {}).get('monthly', {}).get('rsi', 50)
        
        if rsi_signal == 'STRONG_BUY':
            score += 15
            reasons.append(f"✅ Extremely oversold (Monthly RSI: {monthly_rsi:.1f})")
            details['rsi_score'] = 15
        elif rsi_signal == 'BUY':
            score += 12
            reasons.append(f"✅ Oversold conditions (Monthly RSI: {monthly_rsi:.1f})")
            details['rsi_score'] = 12
        elif rsi_signal == 'NEUTRAL':
            score += 7
            details['rsi_score'] = 7
        elif rsi_signal == 'SELL':
            score += 3
            reasons.append(f"⚠️ Overbought conditions (Monthly RSI: {monthly_rsi:.1f})")
            details['rsi_score'] = 3
        elif rsi_signal == 'STRONG_SELL':
            score += 0
            reasons.append(f"❌ Extremely overbought (Monthly RSI: {monthly_rsi:.1f})")
            details['rsi_score'] = 0
        
        # Support/Resistance (20 points max)
        sr_data = technical_data.get('sr_data', {})
        position = sr_data.get('current_position', 'UNKNOWN')
        
        if position == 'NEAR_SUPPORT':
            score += 20
            reasons.append("✅ Near strong support - high probability bounce")
            details['sr_score'] = 20
        elif position == 'MID_RANGE':
            score += 10
            details['sr_score'] = 10
        elif position == 'NEAR_RESISTANCE':
            score += 0
            reasons.append("❌ Near resistance - potential pullback zone")
            details['sr_score'] = 0
        else:
            score += 10
            details['sr_score'] = 10
        
        # Cap at 50
        score = min(50, score)
        
        breakdown = {
            "score": score,
            "max_score": 50,
            "details": details,
            "reasons": reasons
        }
        
        return score, breakdown
    
    def _score_macro(self, macro_data: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        """
        Score macro analysis signals (max 50 points).
        
        Breakdown:
        - Dollar Strength: 25 points
        - Real Yields: 25 points
        """
        score = 0
        reasons = []
        details = {}
        
        # Dollar Strength (25 points max)
        dollar_data = macro_data.get('dollar_data', {})
        dollar_impact = dollar_data.get('impact_on_metals', 'NEUTRAL_FOR_METALS')
        
        impact_scores = {
            'STRONG_BULLISH_FOR_METALS': 25,
            'BULLISH_FOR_METALS': 20,
            'NEUTRAL_FOR_METALS': 12,
            'BEARISH_FOR_METALS': 5,
            'STRONG_BEARISH_FOR_METALS': 0
        }
        
        dollar_score = impact_scores.get(dollar_impact, 12)
        score += dollar_score
        details['dollar_score'] = dollar_score
        
        if dollar_score >= 20:
            reasons.append(f"✅ Weak dollar supporting metals")
        elif dollar_score <= 5:
            reasons.append(f"❌ Strong dollar headwind")
        
        # Real Yields (25 points max)
        yield_data = macro_data.get('yield_data', {})
        yield_impact = yield_data.get('impact_on_metals', 'NEUTRAL_FOR_METALS')
        
        yield_score = impact_scores.get(yield_impact, 12)
        score += yield_score
        details['yield_score'] = yield_score
        
        if yield_score >= 20:
            reasons.append(f"✅ Negative/low real yields favorable")
        elif yield_score <= 5:
            reasons.append(f"❌ High real yields headwind")
        
        # Cap at 50
        score = min(50, score)
        
        breakdown = {
            "score": score,
            "max_score": 50,
            "details": details,
            "reasons": reasons
        }
        
        return score, breakdown
    
    def _determine_action(self, confidence: int) -> str:
        """Determine action based on confidence score."""
        if confidence >= 75:
            return "STRONG_BUY"
        elif confidence >= 60:
            return "BUY"
        elif confidence >= 40:
            return "HOLD"
        elif confidence >= 25:
            return "SELL"
        else:
            return "STRONG_SELL"
    
    async def _calculate_position_size(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate recommended position size based on confidence and risk profile."""
        try:
            confidence = params.get('confidence', 50)
            risk_profile = params.get('risk_profile', 'moderate')
            
            # Aggressive profile (user's preference)
            if risk_profile == 'aggressive':
                if confidence >= 75:
                    position_pct = 25  # 25-30%
                    sizing = "MAX_POSITION"
                elif confidence >= 60:
                    position_pct = 18  # 15-20%
                    sizing = "LARGE_POSITION"
                elif confidence >= 40:
                    position_pct = 0  # Hold existing
                    sizing = "MAINTAIN"
                elif confidence >= 25:
                    position_pct = -50  # Reduce by 50%
                    sizing = "REDUCE_HALF"
                else:
                    position_pct = -100  # Exit completely
                    sizing = "EXIT_ALL"
            else:
                # Conservative/Moderate (not used, but here for reference)
                if confidence >= 75:
                    position_pct = 15
                    sizing = "MODERATE_POSITION"
                elif confidence >= 60:
                    position_pct = 10
                    sizing = "SMALL_POSITION"
                else:
                    position_pct = 0
                    sizing = "HOLD"
            
            result = {
                "confidence": confidence,
                "risk_profile": risk_profile,
                "position_size_pct": position_pct,
                "sizing": sizing,
                "explanation": self._explain_sizing(sizing, confidence)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return {"error": str(e)}
    
    def _explain_sizing(self, sizing: str, confidence: int) -> str:
        """Explain position sizing recommendation."""
        explanations = {
            "MAX_POSITION": f"High confidence ({confidence}%) - Aggressive entry with 25-30% of capital",
            "LARGE_POSITION": f"Good confidence ({confidence}%) - Enter with 15-20% of capital",
            "MAINTAIN": f"Neutral zone ({confidence}%) - Hold existing positions, no new action",
            "REDUCE_HALF": f"Weak signal ({confidence}%) - Reduce exposure by 50%",
            "EXIT_ALL": f"Strong sell signal ({confidence}%) - Exit all positions"
        }
        return explanations.get(sizing, "Unknown sizing")
    
    async def _generate_trade_plan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed trade plan with entry/exit/stops."""
        try:
            symbol = params.get('symbol')
            signal = params.get('signal')
            current_price = params.get('current_price', 0)
            support = params.get('support', 0)
            resistance = params.get('resistance', 0)
            
            if not all([symbol, signal, current_price]):
                return {"error": "Missing required parameters"}
            
            plan = {}
            
            if signal in ['STRONG_BUY', 'BUY']:
                # Entry range: current to slight pullback
                plan['entry_optimal'] = round(current_price * 0.98, 2)  # 2% below current
                plan['entry_range_low'] = round(current_price * 0.95, 2)  # 5% below
                plan['entry_range_high'] = round(current_price * 1.01, 2)  # 1% above
                
                # Stop loss: below support with buffer
                if support > 0:
                    plan['stop_loss'] = round(support * 0.97, 2)  # 3% below support
                else:
                    plan['stop_loss'] = round(current_price * 0.90, 2)  # 10% below current
                
                # Take profit: resistance with buffer
                if resistance > 0:
                    plan['take_profit_1'] = round(resistance * 0.98, 2)  # Just before resistance
                    plan['take_profit_2'] = round(resistance * 1.05, 2)  # Breakout target
                else:
                    plan['take_profit_1'] = round(current_price * 1.10, 2)  # 10% gain
                    plan['take_profit_2'] = round(current_price * 1.20, 2)  # 20% gain
                
                # Risk/Reward
                risk = current_price - plan['stop_loss']
                reward = plan['take_profit_1'] - current_price
                plan['risk_reward_ratio'] = round(reward / risk if risk > 0 else 0, 2)
                
                plan['strategy'] = "Enter on dips, scale out at targets"
                
            elif signal in ['STRONG_SELL', 'SELL']:
                # Exit range
                plan['exit_optimal'] = round(current_price * 0.99, 2)  # Sell now or slight bounce
                plan['exit_range_low'] = round(current_price * 0.95, 2)
                plan['exit_range_high'] = round(current_price * 1.02, 2)
                
                # Re-entry targets (if user wants to buy back later)
                if support > 0:
                    plan['reentry_target'] = round(support * 1.02, 2)  # Near support
                else:
                    plan['reentry_target'] = round(current_price * 0.85, 2)  # 15% pullback
                
                plan['strategy'] = "Take profits, wait for pullback to re-enter"
            
            return plan
            
        except Exception as e:
            logger.error(f"Error generating trade plan: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    import asyncio
    
    async def test_signal_generator():
        """Test the Entry/Exit Signal Generator."""
        print("=" * 80)
        print("Entry/Exit Signal Generator Test")
        print("=" * 80)
        print()
        
        # Create and initialize agent
        generator = EntryExitSignalGenerator()
        await generator.initialize()
        await generator.start()
        
        try:
            # Test with sample data (simulating GLD strong sell scenario)
            print("Testing STRONG SELL scenario (current market conditions)...")
            
            technical_data = {
                'ma_data': {
                    'current_price': 423.33,
                    'trend_signal': 'STRONG_BULLISH',  # +1 point (trend is up)
                    'crossovers': {'golden_cross': False, 'death_cross': False}
                },
                'rsi_data': {
                    'overall_signal': 'STRONG_SELL',  # 0 points (extremely overbought)
                    'timeframes': {
                        'monthly': {'rsi': 96.39}
                    }
                },
                'sr_data': {
                    'current_position': 'NEAR_RESISTANCE',  # 0 points
                    'nearest_support': 415.00,
                    'nearest_resistance': 425.00
                }
            }
            
            macro_data = {
                'dollar_data': {
                    'impact_on_metals': 'BEARISH_FOR_METALS'  # 5 points (dollar headwind)
                },
                'yield_data': {
                    'impact_on_metals': 'STRONG_BEARISH_FOR_METALS'  # 0 points (high yields)
                }
            }
            
            result = await generator._generate_signal({
                'symbol': 'GLD',
                'technical_data': technical_data,
                'macro_data': macro_data
            })
            
            if 'error' in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"\n{'='*80}")
                print(f"SIGNAL GENERATED: {result['action']}")
                print(f"{'='*80}")
                print(f"\nSymbol: {result['symbol']}")
                print(f"Confidence: {result['confidence']}/100")
                print(f"Position Size: {result['position_size_pct']}%")
                
                print(f"\n📊 Score Breakdown:")
                print(f"  Technical: {result['technical_score']}/50")
                tech_details = result['breakdown']['technical']['details']
                print(f"    - MA Score: {tech_details.get('ma_score', 0)}")
                print(f"    - RSI Score: {tech_details.get('rsi_score', 0)}")
                print(f"    - S/R Score: {tech_details.get('sr_score', 0)}")
                
                print(f"  Macro: {result['macro_score']}/50")
                macro_details = result['breakdown']['macro']['details']
                print(f"    - Dollar Score: {macro_details.get('dollar_score', 0)}")
                print(f"    - Yield Score: {macro_details.get('yield_score', 0)}")
                
                print(f"\n💡 Reasoning:")
                for reason in result['reasoning']:
                    print(f"  {reason}")
                
                if result.get('trade_plan'):
                    print(f"\n📋 Trade Plan:")
                    plan = result['trade_plan']
                    if 'exit_optimal' in plan:
                        print(f"  Exit Price: ${plan['exit_optimal']:.2f}")
                        print(f"  Exit Range: ${plan['exit_range_low']:.2f} - ${plan['exit_range_high']:.2f}")
                        print(f"  Re-entry Target: ${plan['reentry_target']:.2f}")
                        print(f"  Strategy: {plan['strategy']}")
            
        finally:
            await generator.stop()
            await generator.shutdown()
            await generator.db.close()
    
    asyncio.run(test_signal_generator())
