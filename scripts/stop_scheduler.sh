#!/bin/bash
# Stop the Gold/Silver Analysis Scheduler

echo "🛑 Stopping Gold/Silver Analysis Scheduler..."

# Find and kill the scheduler process
pkill -f "schedule_gold_silver_analysis.py"

if [ $? -eq 0 ]; then
    echo "✅ Scheduler stopped"
else
    echo "⚠️  No scheduler process found"
fi
