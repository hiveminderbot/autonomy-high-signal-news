#!/usr/bin/env bash
#
# Daily Briefing Orchestration Script
#
# This script orchestrates the complete daily briefing workflow:
# 1. Runs aggregation pipeline (if not skipped)
# 2. Generates briefing from aggregated content
# 3. Renders briefing in configured formats
# 4. Delivers via configured channels (email, Telegram, file)
#
# Intended to be run via cron:
#   0 7 * * * cd /home/exedev/autonomy/labs/high-signal-news && ./scripts/run-daily.sh >> logs/cron.log 2>&1
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${LAB_DIR}/logs"
OUTPUT_DIR="${LAB_DIR}/output"
CONFIG_DIR="${LAB_DIR}/config"
RUN_WITH_NIX_PYTHON="${SCRIPT_DIR}/run-with-nix-python.sh"

# Create directories
mkdir -p "$LOG_DIR" "$OUTPUT_DIR" "$CONFIG_DIR"

# Logging
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/daily_run_$TIMESTAMP.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Parse arguments
SKIP_AGGREGATION=false
FORCE_REGENERATE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-aggregation)
            SKIP_AGGREGATION=true
            shift
            ;;
        --force)
            FORCE_REGENERATE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-aggregation    Skip aggregation pipeline, use cached stories"
            echo "  --force               Force regeneration even if briefing already exists"
            echo "  --help                Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  SMTP_HOST            SMTP server hostname"
            echo "  SMTP_PORT            SMTP server port (default: 587)"
            echo "  SMTP_USERNAME        SMTP username"
            echo "  SMTP_PASSWORD        SMTP password"
            echo "  EMAIL_FROM           From address for emails"
            echo "  EMAIL_TO             Comma-separated recipient addresses"
            echo "  TELEGRAM_BOT_TOKEN   Telegram bot token"
            echo "  TELEGRAM_CHAT_ID     Telegram chat ID"
            exit 0
            ;;
        *)
            log "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if already run today (unless --force)
TODAY=$(date +%Y-%m-%d)
TODAY_BRIEFING="$OUTPUT_DIR/briefing_${TODAY}.md"

if [[ "$FORCE_REGENERATE" == false && -f "$TODAY_BRIEFING" ]]; then
    log "Briefing for today ($TODAY) already exists: $TODAY_BRIEFING"
    log "Use --force to regenerate"
    exit 0
fi

if [[ ! -x "$RUN_WITH_NIX_PYTHON" ]]; then
    log "Missing executable Nix Python wrapper: $RUN_WITH_NIX_PYTHON"
    exit 1
fi

log "=================================================="
log "Daily Briefing Run - $TIMESTAMP"
log "=================================================="
log "Skip aggregation: $SKIP_AGGREGATION"
log "Force regenerate: $FORCE_REGENERATE"
log "Working directory: $LAB_DIR"
log "Log file: $LOG_FILE"
log ""

cd "$LAB_DIR"

# Build Python command
PYTHON_CMD=("$RUN_WITH_NIX_PYTHON" -m scripts.scheduler.daily_briefing)

if [[ "$SKIP_AGGREGATION" == true ]]; then
    PYTHON_CMD+=(--skip-aggregation)
fi

PYTHON_CMD+=(--output "$OUTPUT_DIR" --log-dir "$LOG_DIR")

# Run the scheduler
printf -v PYTHON_CMD_LOG '%q ' "${PYTHON_CMD[@]}"
log "Running: ${PYTHON_CMD_LOG% }"
log ""

if "${PYTHON_CMD[@]}" 2>&1 | tee -a "$LOG_FILE"; then
    log ""
    log "=================================================="
    log "Daily briefing completed successfully"
    log "=================================================="

    # Show output files
    if [[ -f "$OUTPUT_DIR/latest.md" ]]; then
        log "Latest briefing: $OUTPUT_DIR/latest.md"
    fi

    if [[ -f "$OUTPUT_DIR/latest_run_report.json" ]]; then
        log "Run report: $OUTPUT_DIR/latest_run_report.json"
    fi

    exit 0
else
    EXIT_CODE=$?
    log ""
    log "=================================================="
    log "Daily briefing failed with exit code: $EXIT_CODE"
    log "=================================================="
    exit $EXIT_CODE
fi
