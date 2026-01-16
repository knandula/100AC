"""Comprehensive macro analysis for Gold/Silver trading."""
import asyncio
from agents.macro.dollar_strength_analyzer import DollarStrengthAnalyzer
from agents.macro.real_yield_analyzer import RealYieldAnalyzer


async def test_macro_analysis():
    """Run comprehensive macro analysis."""
    
    symbols = ['GLD', 'SLV', 'GOLDBEES.NS', 'SILVERBEES.NS']
    
    # Initialize agents
    dollar_agent = DollarStrengthAnalyzer()
    yield_agent = RealYieldAnalyzer()
    
    await dollar_agent.initialize()
    await yield_agent.initialize()
    
    await dollar_agent.start()
    await yield_agent.start()
    
    try:
        print("\n" + "=" * 80)
        print("MACRO ANALYSIS: Dollar Strength & Real Yields")
        print("=" * 80)
        
        # Dollar Analysis
        print("\n💵 US DOLLAR STRENGTH")
        print("-" * 80)
        dollar_result = await dollar_agent._analyze_all_dollar({
            'gold_symbol': 'GLD',
            'silver_symbol': 'SLV'
        })
        
        if 'error' not in dollar_result:
            idx = dollar_result['dollar_index']
            mom = dollar_result['dollar_momentum']
            impact = dollar_result['metal_impact']
            
            print(f"\n📊 Dollar Index (DXY): {idx['current_level']}")
            print(f"   Trend: {idx['trend']}")
            print(f"   SMA 200: {idx['moving_averages']['sma_200']}")
            print(f"   % from 200-MA: {idx['pct_from_200ma']:+.2f}%")
            
            print(f"\n📈 Dollar Momentum: {mom['momentum_signal']}")
            print(f"   1-Week ROC: {mom['rate_of_change']['1_week']:+.2f}%")
            print(f"   1-Month ROC: {mom['rate_of_change']['1_month']:+.2f}%")
            print(f"   3-Month ROC: {mom['rate_of_change']['3_months']:+.2f}%")
            
            print(f"\n🎯 Impact: {impact['impact_on_metals']}")
            print(f"   {impact['guidance']}")
        
        # Yield Analysis
        print("\n\n💰 REAL YIELDS ANALYSIS")
        print("-" * 80)
        yield_result = await yield_agent._analyze_all_yields({
            'gold_symbol': 'GLD',
            'silver_symbol': 'SLV'
        })
        
        if 'error' not in yield_result:
            nom = yield_result['nominal_yields']
            real = yield_result['real_yields']
            impact = yield_result['metal_impact']
            
            print(f"\n📊 10-Year Treasury Yield: {nom['current_yield']}%")
            print(f"   Trend: {nom['trend']}")
            print(f"   MA 200: {nom['moving_averages']['ma_200']}%")
            if 'yield_changes' in nom and '3_months' in nom['yield_changes']:
                print(f"   3-Month Change: {nom['yield_changes']['3_months']:+.2f}%")
            
            print(f"\n📈 Real Yield Calculation:")
            print(f"   Nominal Yield: {real['nominal_yield']}%")
            print(f"   Est. Inflation: {real['estimated_inflation']}%")
            print(f"   Real Yield: {real['real_yield']}%")
            print(f"   Level: {real['real_yield_level']}")
            
            print(f"\n🎯 Impact: {impact['impact_on_metals']}")
            print(f"   {impact['guidance']}")
        
        # Combined Macro Signal
        print("\n\n🔄 COMBINED MACRO SIGNAL")
        print("=" * 80)
        
        if 'error' not in dollar_result and 'error' not in yield_result:
            dollar_impact = dollar_result['metal_impact']['impact_on_metals']
            yield_impact = yield_result['metal_impact']['impact_on_metals']
            
            # Score the impacts
            impact_scores = {
                'STRONG_BEARISH_FOR_METALS': -2,
                'BEARISH_FOR_METALS': -1,
                'NEUTRAL_TO_BEARISH_FOR_METALS': -0.5,
                'NEUTRAL_FOR_METALS': 0,
                'NEUTRAL_TO_BULLISH_FOR_METALS': 0.5,
                'BULLISH_FOR_METALS': 1,
                'STRONG_BULLISH_FOR_METALS': 2
            }
            
            dollar_score = impact_scores.get(dollar_impact, 0)
            yield_score = impact_scores.get(yield_impact, 0)
            combined_score = dollar_score + yield_score
            
            print(f"\n📊 Macro Factor Breakdown:")
            print(f"   Dollar Strength: {dollar_impact} (Score: {dollar_score:+.1f})")
            print(f"   Real Yields: {yield_impact} (Score: {yield_score:+.1f})")
            print(f"   ─────────────────────────────────────────")
            print(f"   Combined Score: {combined_score:+.1f}")
            
            if combined_score <= -2:
                macro_signal = "STRONG BEARISH"
                color = "🔴"
            elif combined_score < 0:
                macro_signal = "BEARISH"
                color = "🟠"
            elif combined_score == 0:
                macro_signal = "NEUTRAL"
                color = "⚪"
            elif combined_score < 2:
                macro_signal = "BULLISH"
                color = "🟢"
            else:
                macro_signal = "STRONG BULLISH"
                color = "🟢🟢"
            
            print(f"\n{color} OVERALL MACRO SIGNAL: {macro_signal}")
            
            # Interpretation
            print(f"\n💡 Interpretation:")
            if combined_score < -1:
                print(f"   Strong macro headwinds for gold/silver. Both dollar strength")
                print(f"   and real yields creating unfavorable environment.")
                print(f"   → Recommendation: REDUCE POSITIONS / TAKE PROFITS")
            elif combined_score < 0:
                print(f"   Moderate macro headwinds. Consider the technical picture")
                print(f"   carefully before adding to positions.")
                print(f"   → Recommendation: HOLD / SELECTIVE PROFIT TAKING")
            elif combined_score == 0:
                print(f"   Macro factors balanced. Technical analysis will be key.")
                print(f"   → Recommendation: FOLLOW TECHNICAL SIGNALS")
            elif combined_score < 1:
                print(f"   Moderate macro tailwinds supporting gold/silver.")
                print(f"   → Recommendation: HOLD / SELECTIVE ADDITIONS")
            else:
                print(f"   Strong macro tailwinds! Favorable environment for metals.")
                print(f"   → Recommendation: ADD ON PULLBACKS")
        
        print("\n" + "=" * 80)
        
    finally:
        await dollar_agent.stop()
        await yield_agent.stop()
        await dollar_agent.shutdown()
        await yield_agent.shutdown()
        await dollar_agent.db.close()


if __name__ == "__main__":
    asyncio.run(test_macro_analysis())
