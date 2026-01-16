#!/usr/bin/env python3
"""
Schedule Gold/Silver Analysis Workflow

Runs the gold/silver trading analysis post-market hours:
- After US market close: 5:00 PM ET (2:30 AM IST next day)
- After India market close: 4:00 PM IST (5:30 AM ET)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# Import the analysis agents
from agents.technical.moving_average_calculator import MovingAverageCalculator
from agents.technical.rsi_analyzer import RSIAnalyzer
from agents.technical.support_resistance_identifier import SupportResistanceIdentifier
from agents.macro.dollar_strength_analyzer import DollarStrengthAnalyzer
from agents.macro.real_yield_analyzer import RealYieldAnalyzer
from agents.signals.entry_exit_signal_generator import EntryExitSignalGenerator
from agents.alerts.alert_manager import AlertManager

# Market close times
US_MARKET_CLOSE_TIME = time(17, 0)  # 5:00 PM ET
INDIA_MARKET_CLOSE_TIME = time(16, 0)  # 4:00 PM IST

ET_TIMEZONE = ZoneInfo("America/New_York")
IST_TIMEZONE = ZoneInfo("Asia/Kolkata")


async def run_analysis():
    """Run the complete gold/silver analysis."""
    now = datetime.now()
    logger.info("=" * 80)
    logger.info(f"SCHEDULED GOLD/SILVER ANALYSIS - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Import and run the analysis script
    from scripts.analyze_gold_silver import main as analyze_main
    
    try:
        await analyze_main()
        logger.info("✅ Scheduled analysis completed successfully")
    except Exception as e:
        logger.error(f"❌ Scheduled analysis failed: {e}")
        import traceback
        traceback.print_exc()


def is_weekday():
    """Check if today is a weekday (Monday-Friday)."""
    return datetime.now().weekday() < 5  # 0=Monday, 4=Friday


def seconds_until_next_run():
    """Calculate seconds until next scheduled run."""
    now_et = datetime.now(ET_TIMEZONE)
    now_ist = datetime.now(IST_TIMEZONE)
    
    # Check if it's a weekday
    if not is_weekday():
        # If weekend, wait until Monday
        days_until_monday = (7 - now_et.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 1
        next_run = now_et.replace(hour=US_MARKET_CLOSE_TIME.hour, 
                                   minute=US_MARKET_CLOSE_TIME.minute, 
                                   second=0, microsecond=0)
        next_run = next_run + timedelta(days=days_until_monday)
        return int((next_run - now_et).total_seconds())
    
    # Check if we should run after US market close (5 PM ET)
    us_close_today = now_et.replace(hour=US_MARKET_CLOSE_TIME.hour,
                                     minute=US_MARKET_CLOSE_TIME.minute,
                                     second=0, microsecond=0)
    
    # Check if we should run after India market close (4 PM IST)
    india_close_today = now_ist.replace(hour=INDIA_MARKET_CLOSE_TIME.hour,
                                         minute=INDIA_MARKET_CLOSE_TIME.minute,
                                         second=0, microsecond=0)
    
    # Convert India time to ET for comparison
    india_close_et = india_close_today.astimezone(ET_TIMEZONE)
    
    # Determine next run time
    next_runs = []
    
    if now_et < us_close_today:
        next_runs.append(us_close_today)
    
    if now_et < india_close_et:
        next_runs.append(india_close_et)
    
    # If both times have passed today, schedule for tomorrow
    if not next_runs:
        from datetime import timedelta
        tomorrow_et = now_et + timedelta(days=1)
        us_close_tomorrow = tomorrow_et.replace(hour=US_MARKET_CLOSE_TIME.hour,
                                                 minute=US_MARKET_CLOSE_TIME.minute,
                                                 second=0, microsecond=0)
        next_runs.append(us_close_tomorrow)
    
    # Get the nearest run time
    next_run = min(next_runs)
    seconds = int((next_run - now_et).total_seconds())
    
    return seconds, next_run


async def main():
    """Main entry point."""
    from datetime import timedelta
    
    logger.info("🚀 Gold/Silver Post-Market Analysis Scheduler")
    logger.info("=" * 80)
    logger.info("📊 Runs after market close:")
    logger.info("   • US Market: 5:00 PM ET (after NYSE close)")
    logger.info("   • India Market: 4:00 PM IST (after NSE close)")
    logger.info("📧 Email alerts sent for high-confidence signals")
    logger.info("📅 Runs Monday-Friday only")
    logger.info("=" * 80)
    logger.info("")
    
    # Calculate next run
    try:
        seconds, next_run = seconds_until_next_run()
        next_run_str = next_run.strftime("%Y-%m-%d %I:%M %p %Z")
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        logger.info(f"⏰ Next run: {next_run_str}")
        logger.info(f"⏱️  Time until next run: {hours}h {minutes}m")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
    except Exception as e:
        logger.error(f"Error calculating next run: {e}")
        # Default to running immediately if calculation fails
        seconds = 0
    
    try:
        while True:
            # Wait until next scheduled time
            if seconds > 0:
                logger.info(f"💤 Waiting {seconds // 60} minutes until next run...")
                await asyncio.sleep(seconds)
            
            # Check if it's a weekday
            if not is_weekday():
                logger.info("📅 Weekend - skipping run")
                seconds, next_run = seconds_until_next_run()
                continue
            
            # Run the analysis
            now = datetime.now(ET_TIMEZONE)
            market = "US" if now.hour >= 17 else "India"
            logger.info(f"\n🔔 POST-{market}-MARKET ANALYSIS STARTING")
            await run_analysis()
            
            # Calculate next run time
            seconds, next_run = seconds_until_next_run()
            next_run_str = next_run.strftime("%Y-%m-%d %I:%M %p %Z")
            logger.info(f"\n⏰ Next scheduled run: {next_run_str}")
            logger.info("")
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping scheduler...")
    finally:
        logger.info("✅ Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
