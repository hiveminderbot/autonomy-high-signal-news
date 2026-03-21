#!/bin/bash
#
# Daily Aggregation Cron Script
#
# This script runs the daily aggregation pipeline.
# Designed to be called from crontab.
#
# Usage:
#   ./daily_cron.sh                    # Run with defaults
#   ./daily_cron.sh --domain ai        # Run for AI domain only
#   ./daily_cron.sh --limit-feeds 10   # Limit to 10 feed sources
#

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"

# Change to lab directory
cd "$LAB_DIR"

# Set up Python path
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Default Python interpreter
PYTHON="${PYTHON:-python3}"

# Log startup
echo "[$(date -Iseconds)] Starting daily aggregation cron job"
echo "[$(date -Iseconds)] Working directory: $LAB_DIR"
echo "[$(date -Iseconds)] Python: $PYTHON"

# Run the aggregation
if $PYTHON scripts/run_daily_aggregation.py "$@"; then
    echo "[$(date -Iseconds)] Daily aggregation completed successfully"
    exit 0
else
    echo "[$(date -Iseconds)] Daily aggregation failed with exit code $?"
    exit 1
fi
