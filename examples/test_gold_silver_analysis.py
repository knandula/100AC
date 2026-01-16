"""Test all technical agents with Gold/Silver ETFs."""
import asyncio
from agents.technical.moving_average_calculator import MovingAverageCalculator
from agents.technical.rsi_analyzer import RSIAnalyzer
from agents.technical.support_resistance_identifier import SupportResistanceIdentifier

async def test_gold_silver_analysis():
    """Run comprehensive technical analysis on GLD and SLV."""
    
    symbols = ['GLD', 'SLV', 'GOLDBEES.NS', 'SILVERBEES.NS']
    
    # Initialize all agents
    ma_agent = MovingAverageCalculator()
    rsi_agent = RSIAnalyzer()
    sr_agent = SupportResistanceIdentifier()
    
    await ma_agent.initialize()
    await rsi_agent.initialize()
    await sr_agent.initialize()
    
    await ma_agent.start()
    await rsi_agent.start()
    await sr_agent.start()
    
    try:
        for symbol in symbols:
            print("\n" + "=" * 80)
            print(f"Technical Analysis: {symbol}")
            print("=" * 80)
            
            # Moving Averages
            print(f"\n📊 Moving Averages:")
            ma_result = await ma_agent._calculate_all_mas({'symbol': symbol})
            if 'error' not in ma_result:
                print(f"  Current Price: ${ma_result['current_price']}")
                print(f"  SMA 20:  ${ma_result['ma_values']['sma_20']}")
                print(f"  SMA 50:  ${ma_result['ma_values']['sma_50']}")
                print(f"  SMA 200: ${ma_result['ma_values']['sma_200']}")
                print(f"  Trend: {ma_result['trend_signal']}")
                print(f"  Golden Cross: {ma_result['crossovers']['golden_cross']}")
                print(f"  Death Cross: {ma_result['crossovers']['death_cross']}")
            else:
                print(f"  ❌ Error: {ma_result['error']}")
            
            # RSI Analysis
            print(f"\n📈 RSI Analysis:")
            rsi_result = await rsi_agent._identify_oversold_overbought({'symbol': symbol})
            if 'error' not in rsi_result:
                print(f"  Overall Signal: {rsi_result['overall_signal']}")
                for tf, data in rsi_result['timeframes'].items():
                    print(f"  {tf.capitalize():8} RSI={data['rsi']:5.2f}  {data['condition']}")
            else:
                print(f"  ❌ Error: {rsi_result['error']}")
            
            # Support/Resistance
            print(f"\n🎯 Support/Resistance:")
            sr_result = await sr_agent._calculate_proximity({'symbol': symbol})
            if 'error' not in sr_result:
                print(f"  Position: {sr_result['position']}")
                if sr_result['nearest_support']['distance']:
                    print(f"  Support:    ${sr_result['nearest_support']['level']['price']:7.2f} (distance: {sr_result['nearest_support']['distance_pct']:5.2f}%)")
                if sr_result['nearest_resistance']['distance']:
                    print(f"  Resistance: ${sr_result['nearest_resistance']['level']['price']:7.2f} (distance: {sr_result['nearest_resistance']['distance_pct']:5.2f}%)")
            else:
                print(f"  ❌ Error: {sr_result['error']}")
            
            # Overall Assessment
            print(f"\n💡 Combined Signal:")
            
            trend_score = 0
            if 'error' not in ma_result:
                if ma_result['trend_signal'] in ['BULLISH', 'STRONG_BULLISH']:
                    trend_score += 1
                    print(f"  ✅ Bullish trend (price above 200-day MA)")
                elif ma_result['trend_signal'] in ['BEARISH', 'STRONG_BEARISH']:
                    trend_score -= 1
                    print(f"  ⚠️  Bearish trend (price below 200-day MA)")
            
            if 'error' not in rsi_result:
                if rsi_result['overall_signal'] in ['STRONG_BUY', 'BUY']:
                    trend_score += 1
                    print(f"  ✅ RSI suggests buying opportunity")
                elif rsi_result['overall_signal'] in ['STRONG_SELL', 'SELL']:
                    trend_score -= 1
                    print(f"  ⚠️  RSI suggests selling pressure")
            
            if 'error' not in sr_result:
                if sr_result['position'] == 'NEAR_SUPPORT':
                    trend_score += 1
                    print(f"  ✅ Near support - potential bounce zone")
                elif sr_result['position'] == 'NEAR_RESISTANCE':
                    trend_score -= 1
                    print(f"  ⚠️  Near resistance - potential pullback zone")
            
            if trend_score >= 2:
                print(f"\n  🟢 OVERALL: STRONG BUY")
            elif trend_score == 1:
                print(f"\n  🟡 OVERALL: BUY")
            elif trend_score == -1:
                print(f"\n  🟡 OVERALL: SELL")
            elif trend_score <= -2:
                print(f"\n  🔴 OVERALL: STRONG SELL")
            else:
                print(f"\n  ⚪ OVERALL: NEUTRAL/HOLD")
    
    finally:
        await ma_agent.stop()
        await rsi_agent.stop()
        await sr_agent.stop()
        
        await ma_agent.shutdown()
        await rsi_agent.shutdown()
        await sr_agent.shutdown()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    asyncio.run(test_gold_silver_analysis())
