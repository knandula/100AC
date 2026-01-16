#!/usr/bin/env python3
"""
Gold/Silver Trading Analysis Script

Runs complete analysis using 100AC agents and displays results.
Usage: python scripts/analyze_gold_silver.py
"""
import sys
from pathlib import Path
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.technical.moving_average_calculator import MovingAverageCalculator
from agents.technical.rsi_analyzer import RSIAnalyzer
from agents.technical.support_resistance_identifier import SupportResistanceIdentifier
from agents.macro.dollar_strength_analyzer import DollarStrengthAnalyzer
from agents.macro.real_yield_analyzer import RealYieldAnalyzer
from agents.signals.entry_exit_signal_generator import EntryExitSignalGenerator
from agents.alerts.alert_manager import AlertManager


async def analyze_symbol(symbol: str, agents: dict) -> dict:
    """Analyze a single symbol."""
    # Gather technical data
    ma_result = await agents['ma']._calculate_all_mas({'symbol': symbol})
    rsi_result = await agents['rsi']._identify_oversold_overbought({'symbol': symbol})
    sr_result = await agents['sr']._identify_all_levels({'symbol': symbol})
    
    # Check for errors
    for name, result in [('MA', ma_result), ('RSI', rsi_result), ('S/R', sr_result)]:
        if 'error' in result:
            return {'error': f'{name} analysis failed: {result["error"]}'}
    
    # Gather macro data (same for all symbols)
    dollar_result = await agents['dollar']._analyze_all_dollar({})
    yield_result = await agents['yield']._analyze_all_yields({})
    
    if 'error' in dollar_result or 'error' in yield_result:
        return {'error': 'Macro analysis failed'}
    
    # Generate signal
    signal = await agents['signal']._generate_signal({
        'symbol': symbol,
        'technical_data': {
            'ma_data': ma_result,
            'rsi_data': rsi_result,
            'sr_data': sr_result
        },
        'macro_data': {
            'dollar_data': dollar_result['metal_impact'],
            'yield_data': yield_result['metal_impact']
        }
    })
    
    return signal


def format_results(results: list) -> str:
    """Format results for display."""
    lines = []
    lines.append("=" * 80)
    lines.append("GOLD/SILVER TRADING SIGNALS")
    lines.append("=" * 80)
    lines.append("")
    
    for result in results:
        emoji = {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'HOLD': '⚪', 'SELL': '🟠', 'STRONG_SELL': '🔴'}.get(result['action'], '⚪')
        lines.append(f"{emoji} {result['symbol']}: {result['action']} (Confidence: {result['confidence']}/100)")
        lines.append("─" * 80)
        lines.append(f"  Technical: {result['technical_score']}/50 | Macro: {result['macro_score']}/50")
        
        if result['position_size_pct'] > 0:
            lines.append(f"  📈 Action: BUY {result['position_size_pct']}% position")
        elif result['position_size_pct'] == 0:
            lines.append(f"  ⏸️  Action: HOLD current positions")
        elif result['position_size_pct'] == -50:
            lines.append(f"  📉 Action: REDUCE 50% of position")
        else:
            lines.append(f"  🚪 Action: EXIT all positions")
        
        lines.append("")
        lines.append("  💡 Key Reasons:")
        for reason in result['reasoning'][:5]:
            lines.append(f"     {reason}")
        
        if result.get('trade_plan'):
            plan = result['trade_plan']
            lines.append("")
            if 'exit_optimal' in plan:
                lines.append("  📋 Exit Plan:")
                lines.append(f"     Sell at: ${plan['exit_optimal']:.2f}")
                lines.append(f"     Re-entry: ${plan['reentry_target']:.2f}")
            else:
                lines.append("  📋 Entry Plan:")
                lines.append(f"     Buy at: ${plan['entry_optimal']:.2f}")
                lines.append(f"     Stop: ${plan['stop_loss']:.2f}")
                lines.append(f"     Target: ${plan['take_profit_1']:.2f}")
        lines.append("")
    
    lines.append("=" * 80)
    lines.append("SUMMARY")
    lines.append("=" * 80)
    avg_conf = sum(r['confidence'] for r in results) / len(results) if results else 0
    lines.append(f"Symbols Analyzed: {len(results)}")
    lines.append(f"Average Confidence: {avg_conf:.1f}/100")
    if results:
        macro = results[0]['macro_score']
        env = "FAVORABLE ✅" if macro >= 30 else "NEUTRAL ⚪" if macro >= 20 else "UNFAVORABLE ❌"
        lines.append(f"Macro Environment: {env} ({macro}/50)")
    lines.append("=" * 80)
    
    return "\n".join(lines)


async def main():
    """Main entry point."""
    symbols = ['GLD', 'SLV', 'GOLDBEES.NS', 'SILVERBEES.NS']
    
    # Initialize agents
    agents = {
        'ma': MovingAverageCalculator(),
        'rsi': RSIAnalyzer(),
        'sr': SupportResistanceIdentifier(),
        'dollar': DollarStrengthAnalyzer(),
        'yield': RealYieldAnalyzer(),
        'signal': EntryExitSignalGenerator(),
        'alert': AlertManager()
    }
    
    # Initialize and start all agents
    for agent in agents.values():
        await agent.initialize()
        await agent.start()
    
    try:
        # Analyze each symbol
        results = []
        for symbol in symbols:
            signal = await analyze_symbol(symbol, agents)
            if 'error' not in signal:
                results.append(signal)
        
        # Display results
        print("\n" + format_results(results))
        
        # Check thresholds and send alerts
        print("\n" + "=" * 80)
        print("CHECKING ALERT THRESHOLDS")
        print("=" * 80)
        alert_result = await agents['alert']._check_thresholds({'signals': results})
        print(f"\n✅ {alert_result['alerts_triggered']} alert(s) triggered\n")
        
        # Send email alerts for high-confidence signals (>= 70 or <= 30)
        print("=" * 80)
        print("SENDING EMAIL ALERTS")
        print("=" * 80)
        
        # Collect all signals that meet the threshold
        signals_to_email = []
        for signal in results:
            confidence = signal.get('confidence', 0)
            # Include signals with high confidence BUY or low confidence SELL
            if confidence >= 70 or confidence <= 30:
                signals_to_email.append(signal)
        
        # Send a single combined email with all signals
        if signals_to_email:
            email_params = {
                "signals": signals_to_email
            }
            email_result = await agents['alert']._send_combined_email_alert(email_params)
            if email_result.get('success'):
                print(f"✅ Combined email sent with {len(signals_to_email)} signal(s)")
                print(f"📧 Email sent to: {email_result.get('to_email')}")
            elif 'error' in email_result:
                print(f"⚠️ Email failed: {email_result['error']}")
        else:
            print("ℹ️  No signals met the threshold for email alerts")
        print()
        
    finally:
        # Cleanup
        for agent in agents.values():
            await agent.stop()
            await agent.shutdown()
        await agents['ma'].db.close()


if __name__ == "__main__":
    asyncio.run(main())
