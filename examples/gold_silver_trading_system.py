"""
GOLD/SILVER TRADING SYSTEM - COMPLETE INTEGRATION
Uses all 6 agents to generate actionable trading signals
"""
import asyncio
from agents.technical.moving_average_calculator import MovingAverageCalculator
from agents.technical.rsi_analyzer import RSIAnalyzer
from agents.technical.support_resistance_identifier import SupportResistanceIdentifier
from agents.macro.dollar_strength_analyzer import DollarStrengthAnalyzer
from agents.macro.real_yield_analyzer import RealYieldAnalyzer
from agents.signals.entry_exit_signal_generator import EntryExitSignalGenerator


async def analyze_complete(symbol, agents):
    """Run complete 6-agent analysis for a symbol."""
    ma_agent, rsi_agent, sr_agent, dollar_agent, yield_agent, signal_agent = agents
    
    print(f"\n{'='*80}")
    print(f"ANALYZING: {symbol}")
    print(f"{'='*80}\n")
    
    # Gather all data
    ma_result = await ma_agent._calculate_all_mas({'symbol': symbol})
    rsi_result = await rsi_agent._identify_oversold_overbought({'symbol': symbol})
    sr_result = await sr_agent._identify_all_levels({'symbol': symbol})
    dollar_result = await dollar_agent._analyze_all_dollar({})
    yield_result = await yield_agent._analyze_all_yields({})
    
    # Check for errors
    for name, result in [
        ('MA', ma_result), ('RSI', rsi_result), ('S/R', sr_result),
        ('Dollar', dollar_result), ('Yields', yield_result)
    ]:
        if 'error' in result:
            print(f"❌ Error in {name}: {result['error']}")
            return None
    
    # Prepare data for signal generator
    technical_data = {
        'ma_data': ma_result,
        'rsi_data': rsi_result,
        'sr_data': sr_result
    }
    
    macro_data = {
        'dollar_data': dollar_result['metal_impact'],
        'yield_data': yield_result['metal_impact']
    }
    
    # Generate signal
    signal = await signal_agent._generate_signal({
        'symbol': symbol,
        'technical_data': technical_data,
        'macro_data': macro_data
    })
    
    return signal


async def main():
    """Main trading system."""
    
    symbols = ['GLD', 'SLV', 'GOLDBEES.NS', 'SILVERBEES.NS']
    
    # Initialize all 6 agents
    print("\n" + "="*80)
    print("INITIALIZING GOLD/SILVER TRADING SYSTEM")
    print("="*80)
    print("\n🔧 Loading 6 specialized agents:")
    print("   1. Moving Average Calculator")
    print("   2. RSI Analyzer")
    print("   3. Support/Resistance Identifier")
    print("   4. Dollar Strength Analyzer")
    print("   5. Real Yield Analyzer")
    print("   6. Entry/Exit Signal Generator")
    print()
    
    ma_agent = MovingAverageCalculator()
    rsi_agent = RSIAnalyzer()
    sr_agent = SupportResistanceIdentifier()
    dollar_agent = DollarStrengthAnalyzer()
    yield_agent = RealYieldAnalyzer()
    signal_agent = EntryExitSignalGenerator()
    
    await ma_agent.initialize()
    await rsi_agent.initialize()
    await sr_agent.initialize()
    await dollar_agent.initialize()
    await yield_agent.initialize()
    await signal_agent.initialize()
    
    await ma_agent.start()
    await rsi_agent.start()
    await sr_agent.start()
    await dollar_agent.start()
    await yield_agent.start()
    await signal_agent.start()
    
    try:
        print("✅ All agents initialized and ready\n")
        
        # Analyze each symbol
        results = []
        for symbol in symbols:
            signal = await analyze_complete(
                symbol,
                (ma_agent, rsi_agent, sr_agent, dollar_agent, yield_agent, signal_agent)
            )
            if signal:
                results.append(signal)
        
        # Display results
        print("\n" + "="*80)
        print("TRADING RECOMMENDATIONS")
        print("="*80)
        
        for result in results:
            symbol = result['symbol']
            action = result['action']
            confidence = result['confidence']
            tech_score = result['technical_score']
            macro_score = result['macro_score']
            position_pct = result['position_size_pct']
            
            # Color code action
            if action == 'STRONG_BUY':
                color = '🟢🟢'
            elif action == 'BUY':
                color = '🟢'
            elif action == 'HOLD':
                color = '⚪'
            elif action == 'SELL':
                color = '🟠'
            else:  # STRONG_SELL
                color = '🔴'
            
            print(f"\n{color} {symbol}: {action} (Confidence: {confidence}/100)")
            print(f"{'─'*80}")
            print(f"  Technical: {tech_score}/50 | Macro: {macro_score}/50")
            
            if position_pct > 0:
                print(f"  📈 Action: BUY {position_pct}% position")
            elif position_pct == 0:
                print(f"  ⏸️  Action: HOLD current positions")
            elif position_pct == -50:
                print(f"  📉 Action: REDUCE 50% of position")
            elif position_pct == -100:
                print(f"  🚪 Action: EXIT all positions")
            
            print(f"\n  💡 Key Reasons:")
            for reason in result['reasoning'][:5]:  # Top 5 reasons
                print(f"     {reason}")
            
            if result.get('trade_plan'):
                plan = result['trade_plan']
                if 'exit_optimal' in plan:
                    print(f"\n  📋 Exit Plan:")
                    print(f"     Sell at: ${plan['exit_optimal']:.2f}")
                    print(f"     Re-entry: ${plan['reentry_target']:.2f}")
                elif 'entry_optimal' in plan:
                    print(f"\n  📋 Entry Plan:")
                    print(f"     Buy at: ${plan['entry_optimal']:.2f}")
                    print(f"     Stop Loss: ${plan['stop_loss']:.2f}")
                    print(f"     Target: ${plan['take_profit_1']:.2f}")
                    print(f"     Risk/Reward: {plan['risk_reward_ratio']}")
        
        # Summary
        print(f"\n{'='*80}")
        print("SYSTEM SUMMARY")
        print(f"{'='*80}")
        
        avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0
        
        actions = {}
        for r in results:
            actions[r['action']] = actions.get(r['action'], 0) + 1
        
        print(f"\n  📊 Analysis Complete:")
        print(f"     Symbols Analyzed: {len(results)}")
        print(f"     Average Confidence: {avg_confidence:.1f}/100")
        print(f"\n  🎯 Action Distribution:")
        for action, count in sorted(actions.items()):
            print(f"     {action}: {count} symbol(s)")
        
        print(f"\n  💰 Market Environment:")
        if results:
            macro_score = results[0]['macro_score']  # Same for all
            if macro_score >= 30:
                env = "FAVORABLE"
                emoji = "✅"
            elif macro_score >= 20:
                env = "NEUTRAL"
                emoji = "⚪"
            else:
                env = "UNFAVORABLE"
                emoji = "❌"
            
            print(f"     {emoji} {env} (Macro Score: {macro_score}/50)")
            print(f"     Dollar + Real Yields creating {'headwinds' if macro_score < 25 else 'tailwinds'}")
        
        print(f"\n{'='*80}\n")
        
    finally:
        # Cleanup
        await ma_agent.stop()
        await rsi_agent.stop()
        await sr_agent.stop()
        await dollar_agent.stop()
        await yield_agent.stop()
        await signal_agent.stop()
        
        await ma_agent.shutdown()
        await rsi_agent.shutdown()
        await sr_agent.shutdown()
        await dollar_agent.shutdown()
        await yield_agent.shutdown()
        await signal_agent.shutdown()
        
        await ma_agent.db.close()


if __name__ == "__main__":
    asyncio.run(main())
