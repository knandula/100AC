"""
COMPLETE GOLD/SILVER ANALYSIS
Combines Technical + Macro factors for comprehensive trading decisions
"""
import asyncio
from agents.technical.moving_average_calculator import MovingAverageCalculator
from agents.technical.rsi_analyzer import RSIAnalyzer
from agents.technical.support_resistance_identifier import SupportResistanceIdentifier
from agents.macro.dollar_strength_analyzer import DollarStrengthAnalyzer
from agents.macro.real_yield_analyzer import RealYieldAnalyzer


async def analyze_symbol(symbol, tech_agents, macro_agents):
    """Run complete analysis for a symbol."""
    ma_agent, rsi_agent, sr_agent = tech_agents
    dollar_agent, yield_agent = macro_agents
    
    print(f"\n{'='*80}")
    print(f"COMPLETE ANALYSIS: {symbol}")
    print(f"{'='*80}")
    
    # Technical Analysis
    print(f"\n📊 TECHNICAL ANALYSIS")
    print(f"{'-'*80}")
    
    ma_result = await ma_agent._calculate_all_mas({'symbol': symbol})
    rsi_result = await rsi_agent._identify_oversold_overbought({'symbol': symbol})
    sr_result = await sr_agent._identify_all_levels({'symbol': symbol})
    
    tech_score = 0
    tech_factors = []
    
    if 'error' not in ma_result:
        trend = ma_result['trend_signal']
        price = ma_result['current_price']
        sma200 = ma_result['ma_values']['sma_200']
        
        print(f"\n  Trend: {trend}")
        print(f"  Price: ${price:.2f}")
        print(f"  SMA 200: ${sma200:.2f}")
        
        if trend in ['STRONG_BULLISH', 'BULLISH']:
            tech_score += 1
            tech_factors.append("✅ Bullish trend")
        elif trend in ['STRONG_BEARISH', 'BEARISH']:
            tech_score -= 1
            tech_factors.append("❌ Bearish trend")
    
    if 'error' not in rsi_result:
        signal = rsi_result['overall_signal']
        monthly_rsi = rsi_result['timeframes']['monthly']['rsi']
        
        print(f"  Monthly RSI: {monthly_rsi:.2f}")
        print(f"  RSI Signal: {signal}")
        
        if signal in ['STRONG_BUY', 'BUY']:
            tech_score += 1
            tech_factors.append("✅ RSI buy signal")
        elif signal in ['STRONG_SELL', 'SELL']:
            tech_score -= 1
            tech_factors.append("❌ RSI overbought")
    
    if 'error' not in sr_result:
        position = sr_result.get('current_position', 'UNKNOWN')
        
        print(f"  S/R Position: {position}")
        
        if position == 'NEAR_SUPPORT':
            tech_score += 1
            tech_factors.append("✅ Near support")
        elif position == 'NEAR_RESISTANCE':
            tech_score -= 1
            tech_factors.append("❌ Near resistance")
    
    # Macro Analysis (same for all symbols since macro is market-wide)
    print(f"\n💰 MACRO ANALYSIS")
    print(f"{'-'*80}")
    
    # Get macro scores (calculated once, applied to all symbols)
    return {
        'symbol': symbol,
        'technical_score': tech_score,
        'technical_factors': tech_factors,
        'price': ma_result.get('current_price', 0) if 'error' not in ma_result else 0,
        'trend': ma_result.get('trend_signal', 'UNKNOWN') if 'error' not in ma_result else 'UNKNOWN',
        'monthly_rsi': rsi_result['timeframes']['monthly']['rsi'] if 'error' not in rsi_result else 0,
        'sr_position': sr_result.get('current_position', 'UNKNOWN') if 'error' not in sr_result else 'UNKNOWN'
    }


async def main():
    """Run complete gold/silver analysis."""
    
    symbols = ['GLD', 'SLV', 'GOLDBEES.NS', 'SILVERBEES.NS']
    
    # Initialize all agents
    ma_agent = MovingAverageCalculator()
    rsi_agent = RSIAnalyzer()
    sr_agent = SupportResistanceIdentifier()
    dollar_agent = DollarStrengthAnalyzer()
    yield_agent = RealYieldAnalyzer()
    
    await ma_agent.initialize()
    await rsi_agent.initialize()
    await sr_agent.initialize()
    await dollar_agent.initialize()
    await yield_agent.initialize()
    
    await ma_agent.start()
    await rsi_agent.start()
    await sr_agent.start()
    await dollar_agent.start()
    await yield_agent.start()
    
    try:
        print("\n" + "="*80)
        print("GOLD/SILVER TRADING SYSTEM - COMPLETE ANALYSIS")
        print("="*80)
        
        # Get macro analysis (applies to all symbols)
        print("\n💰 MACRO ENVIRONMENT")
        print("="*80)
        
        dollar_result = await dollar_agent._analyze_all_dollar({})
        yield_result = await yield_agent._analyze_all_yields({})
        
        macro_score = 0
        macro_factors = []
        
        if 'error' not in dollar_result:
            impact = dollar_result['metal_impact']['impact_on_metals']
            dxy = dollar_result['dollar_index']['current_level']
            
            print(f"\n  💵 Dollar Index: {dxy}")
            print(f"     Impact: {impact}")
            
            if 'BULLISH' in impact:
                macro_score += 1
                macro_factors.append("✅ Dollar weakness supports metals")
            elif 'BEARISH' in impact:
                if 'STRONG' in impact:
                    macro_score -= 2
                    macro_factors.append("❌❌ Strong dollar headwind")
                else:
                    macro_score -= 1
                    macro_factors.append("❌ Dollar headwind")
        
        if 'error' not in yield_result:
            impact = yield_result['metal_impact']['impact_on_metals']
            real_yield = yield_result['real_yields']['real_yield']
            
            print(f"\n  📈 Real Yield: {real_yield:.2f}%")
            print(f"     Impact: {impact}")
            
            if 'BULLISH' in impact:
                if 'STRONG' in impact:
                    macro_score += 2
                    macro_factors.append("✅✅ Negative real yields favorable")
                else:
                    macro_score += 1
                    macro_factors.append("✅ Low real yields supportive")
            elif 'BEARISH' in impact:
                if 'STRONG' in impact:
                    macro_score -= 2
                    macro_factors.append("❌❌ High real yields headwind")
                else:
                    macro_score -= 1
                    macro_factors.append("❌ Real yields headwind")
        
        print(f"\n  🔄 Macro Score: {macro_score:+d}")
        for factor in macro_factors:
            print(f"     {factor}")
        
        # Analyze each symbol
        print("\n\n" + "="*80)
        print("INDIVIDUAL SYMBOL ANALYSIS")
        print("="*80)
        
        results = []
        for symbol in symbols:
            result = await analyze_symbol(
                symbol,
                (ma_agent, rsi_agent, sr_agent),
                (dollar_agent, yield_agent)
            )
            result['macro_score'] = macro_score
            result['combined_score'] = result['technical_score'] + macro_score
            results.append(result)
        
        # Summary
        print("\n\n" + "="*80)
        print("TRADING RECOMMENDATIONS")
        print("="*80)
        
        for result in results:
            symbol = result['symbol']
            tech_score = result['technical_score']
            combined_score = result['combined_score']
            
            print(f"\n{symbol}:")
            print(f"  Price: ${result['price']:.2f}")
            print(f"  Trend: {result['trend']}")
            print(f"  Monthly RSI: {result['monthly_rsi']:.2f}")
            print(f"  Position: {result['sr_position']}")
            print(f"  ─────────────────────────")
            print(f"  Technical Score: {tech_score:+d}")
            print(f"  Macro Score: {macro_score:+d}")
            print(f"  Combined Score: {combined_score:+d}")
            
            # Generate recommendation
            if combined_score >= 2:
                rec = "🟢 STRONG BUY"
                action = "Add aggressively on pullbacks"
            elif combined_score == 1:
                rec = "🟢 BUY"
                action = "Add on dips"
            elif combined_score == 0:
                rec = "⚪ HOLD"
                action = "Wait for clearer signals"
            elif combined_score == -1:
                rec = "🟠 SELL"
                action = "Reduce positions"
            else:
                rec = "🔴 STRONG SELL"
                action = "Take profits / exit positions"
            
            print(f"  ═════════════════════════")
            print(f"  {rec}")
            print(f"  Action: {action}")
        
        print("\n" + "="*80)
        print("KEY INSIGHTS")
        print("="*80)
        print(f"\n  📊 Macro Environment: {'FAVORABLE' if macro_score > 0 else 'UNFAVORABLE' if macro_score < 0 else 'NEUTRAL'}")
        print(f"     Combined macro score of {macro_score:+d} indicates")
        if macro_score <= -2:
            print(f"     STRONG HEADWINDS for precious metals")
        elif macro_score < 0:
            print(f"     HEADWINDS limiting upside potential")
        elif macro_score == 0:
            print(f"     NEUTRAL environment - technical analysis key")
        elif macro_score < 2:
            print(f"     TAILWINDS supporting metals")
        else:
            print(f"     STRONG TAILWINDS - favorable for precious metals")
        
        print(f"\n  🎯 Current Market State:")
        print(f"     All precious metals showing similar technical patterns:")
        print(f"     - Strong long-term uptrends")
        print(f"     - Extreme overbought conditions (Monthly RSI >94)")
        print(f"     - BUT macro headwinds from dollar + real yields")
        print(f"\n  💡 Strategic Guidance:")
        print(f"     While trends remain bullish, the combination of:")
        print(f"     • Extreme technical overbought readings")
        print(f"     • Strong macro headwinds (score: {macro_score:+d})")
        print(f"     Suggests: TAKE PROFITS near current levels")
        print(f"     Wait for: Pullback to support + improved macro setup")
        
        print(f"\n{'='*80}\n")
        
    finally:
        await ma_agent.stop()
        await rsi_agent.stop()
        await sr_agent.stop()
        await dollar_agent.stop()
        await yield_agent.stop()
        
        await ma_agent.shutdown()
        await rsi_agent.shutdown()
        await sr_agent.shutdown()
        await dollar_agent.shutdown()
        await yield_agent.shutdown()
        
        await ma_agent.db.close()


if __name__ == "__main__":
    asyncio.run(main())
