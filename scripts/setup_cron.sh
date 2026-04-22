#!/usr/bin/env bash
#
# Cron Setup Script for High-Signal News Aggregation
#
# This script helps set up the daily cron job for running the aggregation pipeline.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(dirname "$SCRIPT_DIR")"
CRON_TAG="# high-signal-news-daily"

usage() {
    cat <<EOF
Usage: $0 [command]

Commands:
    install     Install the daily cron job (default: 6:00 AM daily)
    remove      Remove the daily cron job
    status      Show current cron job status
    test        Test run the aggregation without installing
    logs        Show recent aggregation logs

Options for install:
    --time HH:MM    Set cron time (default: 06:00)
    --domain DOMAIN Filter by domain (ai, software_development, investment)
    --limit N       Limit to N sources per run

Examples:
    $0 install                    # Install with defaults
    $0 install --time 07:00       # Run at 7 AM
    $0 install --domain ai        # Only aggregate AI sources
    $0 test --domain ai           # Test run for AI domain
    $0 logs                       # Show recent logs
EOF
}

# Default settings
CRON_HOUR="6"
CRON_MINUTE="0"
DOMAIN=""
LIMIT=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --time)
                CRON_HOUR="${2%%:*}"
                CRON_MINUTE="${2##*:}"
                shift 2
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --limit)
                LIMIT="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
}

cmd_install() {
    parse_args "$@"

    echo "Installing daily cron job for high-signal-news aggregation..."
    echo "  Time: $(printf "%02d:%02d" $CRON_HOUR $CRON_MINUTE)"
    echo "  Domain: ${DOMAIN:-all}"
    echo "  Limit: ${LIMIT:-unlimited}"
    echo ""

    # Build cron command
    CRON_CMD="$CRON_MINUTE $CRON_HOUR * * * cd $LAB_DIR && $SCRIPT_DIR/daily_cron.sh"

    if [[ -n "$DOMAIN" ]]; then
        CRON_CMD="$CRON_CMD --domain $DOMAIN"
    fi

    if [[ -n "$LIMIT" ]]; then
        CRON_CMD="$CRON_CMD --limit-feeds $LIMIT"
    fi

    CRON_CMD="$CRON_CMD >> $LAB_DIR/logs/cron.log 2>&1 $CRON_TAG"

    # Remove existing job if present
    cmd_remove --silent

    # Add new cron job
    (crontab -l 2>/dev/null || echo "") | { cat; echo "$CRON_CMD"; } | crontab -

    echo "✅ Cron job installed successfully"
    echo ""
    cmd_status
}

cmd_remove() {
    local silent="${1:-}"
    [[ -z "$silent" ]] && echo "Removing cron job..."

    (crontab -l 2>/dev/null || echo "") | grep -v "$CRON_TAG" | crontab -

    [[ -z "$silent" ]] && echo "✅ Cron job removed"
}

cmd_status() {
    echo "Current cron jobs for high-signal-news:"
    echo "========================================"

    local jobs
    jobs=$(crontab -l 2>/dev/null | grep "$CRON_TAG" || true)

    if [[ -z "$jobs" ]]; then
        echo "No cron jobs installed"
    else
        echo "$jobs" | while read -r line; do
            echo "  $line"
        done
    fi
    echo ""

    # Show recent log files
    echo "Recent aggregation runs:"
    echo "========================"
    if [[ -d "$LAB_DIR/logs" ]]; then
        ls -lt "$LAB_DIR/logs"/aggregation_*.log 2>/dev/null | head -5 | awk '{print "  " $6, $7, $8, $9}' || echo "  No logs found"
    else
        echo "  Log directory not found"
    fi
    echo ""

    # Show recent output files
    echo "Recent output files:"
    echo "===================="
    if [[ -d "$LAB_DIR/output" ]]; then
        ls -lt "$LAB_DIR/output"/aggregation_results_*.json 2>/dev/null | head -5 | awk '{print "  " $6, $7, $8, $9}' || echo "  No output files found"
    else
        echo "  Output directory not found"
    fi
}

cmd_test() {
    parse_args "$@"

    echo "Running test aggregation..."
    echo "  Domain: ${DOMAIN:-all}"
    echo "  Limit: ${LIMIT:-unlimited}"
    echo ""

    local args=()
    [[ -n "$DOMAIN" ]] && args+=("--domain" "$DOMAIN")
    [[ -n "$LIMIT" ]] && args+=("--limit-feeds" "$LIMIT")

    cd "$LAB_DIR"
    "$SCRIPT_DIR/daily_cron.sh" "${args[@]}"
}

cmd_logs() {
    echo "Recent aggregation logs:"
    echo "========================"

    if [[ -d "$LAB_DIR/logs" ]]; then
        local latest_log
        latest_log=$(ls -t "$LAB_DIR/logs"/aggregation_*.log 2>/dev/null | head -1)

        if [[ -n "$latest_log" ]]; then
            echo "Showing: $(basename "$latest_log")"
            echo "---"
            tail -50 "$latest_log"
        else
            echo "No logs found in $LAB_DIR/logs/"
        fi
    else
        echo "Log directory not found: $LAB_DIR/logs/"
    fi
}

# Main command dispatcher
case "${1:-install}" in
    install)
        shift || true
        cmd_install "$@"
        ;;
    remove)
        cmd_remove
        ;;
    status)
        cmd_status
        ;;
    test)
        shift || true
        cmd_test "$@"
        ;;
    logs)
        cmd_logs
        ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        echo "Unknown command: $1"
        usage
        exit 1
        ;;
esac
