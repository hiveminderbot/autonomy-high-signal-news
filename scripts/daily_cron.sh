#!/usr/bin/env bash
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

RUN_WITH_NIX_PYTHON="$SCRIPT_DIR/run-with-nix-python.sh"

if [[ ! -x "$RUN_WITH_NIX_PYTHON" ]]; then
    echo "[ERROR] Missing executable Nix Python wrapper: $RUN_WITH_NIX_PYTHON" >&2
    exit 1
fi

# Log startup
echo "[$(date -Iseconds)] Starting daily aggregation cron job"
echo "[$(date -Iseconds)] Working directory: $LAB_DIR"
echo "[$(date -Iseconds)] Python wrapper: $RUN_WITH_NIX_PYTHON"

# Run the aggregation
if "$RUN_WITH_NIX_PYTHON" scripts/run_daily_aggregation.py "$@"; then
    echo "[$(date -Iseconds)] Daily aggregation completed successfully"
    exit 0
else
    echo "[$(date -Iseconds)] Daily aggregation failed with exit code $?"
    exit 1
fi
