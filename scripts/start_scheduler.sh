#!/bin/bash
# Start the Gold/Silver Analysis Scheduler in the background

cd "$(dirname "$0")/.."

echo "🚀 Starting Gold/Silver Post-Market Analysis Scheduler..."
echo "📊 Runs daily after market close:"
echo "   • India Market: 4:00 PM IST"
echo "   • US Market:    5:00 PM ET"
echo "📧 Email alerts enabled"
echo "📅 Monday-Friday only"
echo ""

# Run in background with nohup
nohup python scripts/schedule_gold_silver_analysis.py > logs/scheduler.log 2>&1 &

SCHEDULER_PID=$!
echo "✅ Scheduler started with PID: $SCHEDULER_PID"
echo "📝 Logs: logs/scheduler.log"
echo ""
echo "To stop: ./scripts/stop_scheduler.sh"
echo "To view logs: tail -f logs/scheduler.log"
