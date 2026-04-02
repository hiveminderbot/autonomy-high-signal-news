#!/bin/bash
#
# Install systemd service and timer for High-Signal News aggregation
#
# Usage:
#   ./install.sh                    # Install for current user
#   ./install.sh --system           # Install system-wide (requires sudo)
#   ./install.sh --uninstall        # Remove service and timer
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
USER_MODE=true
UNINSTALL=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --system)
            USER_MODE=false
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --system      Install system-wide (requires sudo)"
            echo "  --uninstall   Remove service and timer"
            echo "  --help, -h    Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Install for current user"
            echo "  sudo $0 --system      # Install system-wide"
            echo "  $0 --uninstall        # Remove user installation"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine systemd directory
if [[ "$USER_MODE" == true ]]; then
    SYSTEMD_DIR="$HOME/.config/systemd/user"
    SERVICE_NAME="high-signal-news"
else
    SYSTEMD_DIR="/etc/systemd/system"
    SERVICE_NAME="high-signal-news"
fi

# Service and timer file paths
SERVICE_FILE="${SYSTEMD_DIR}/${SERVICE_NAME}.service"
TIMER_FILE="${SYSTEMD_DIR}/${SERVICE_NAME}.timer"
ENV_FILE="${LAB_ROOT}/.env.briefing"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

uninstall_service() {
    log_info "Uninstalling High-Signal News service..."

    # Stop and disable timer
    if [[ "$USER_MODE" == true ]]; then
        systemctl --user stop "${SERVICE_NAME}.timer" 2>/dev/null || true
        systemctl --user disable "${SERVICE_NAME}.timer" 2>/dev/null || true
        systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null || true
    else
        sudo systemctl stop "${SERVICE_NAME}.timer" 2>/dev/null || true
        sudo systemctl disable "${SERVICE_NAME}.timer" 2>/dev/null || true
        sudo systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
    fi

    # Remove files
    rm -f "$SERVICE_FILE" "$TIMER_FILE"

    # Reload systemd
    if [[ "$USER_MODE" == true ]]; then
        systemctl --user daemon-reload
    else
        sudo systemctl daemon-reload
    fi

    log_success "Service uninstalled successfully"
}

install_service() {
    log_info "Installing High-Signal News aggregation service..."
    log_info "Lab root: $LAB_ROOT"
    log_info "Mode: $([[ "$USER_MODE" == true ]] && echo 'user' || echo 'system')"

    # Check if lab directory exists
    if [[ ! -d "$LAB_ROOT" ]]; then
        log_error "Lab directory not found: $LAB_ROOT"
        exit 1
    fi

    # Create systemd directory if needed
    mkdir -p "$SYSTEMD_DIR"

    # Get current user info
    local current_user
    current_user="${USER:-$(whoami)}"

    # Determine Python path
    local python_path
    if [[ -f "${LAB_ROOT}/.venv/bin/python" ]]; then
        python_path="${LAB_ROOT}/.venv/bin/python"
    elif command -v python3 &>/dev/null; then
        python_path="$(command -v python3)"
    else
        log_error "Python not found"
        exit 1
    fi

    log_info "Using Python: $python_path"

    # Create service file
    log_info "Creating service file..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=High-Signal News Daily Aggregation
Documentation=https://forgejo.internal/autonomy/high-signal-news
After=network.target

[Service]
Type=oneshot
User=${current_user}
Group=${current_user}
WorkingDirectory=${LAB_ROOT}
Environment="PATH=${LAB_ROOT}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=${LAB_ROOT}/scripts"
EnvironmentFile=-${ENV_FILE}

# Run the daily aggregation
ExecStart=${python_path} \\
    ${LAB_ROOT}/scripts/aggregator/daily_pipeline.py \\
    --db ${LAB_ROOT}/data/news.db \\
    --catalog ${LAB_ROOT}/sources/sources-ai.json \\
    --output-dir ${LAB_ROOT}/output \\
    -v

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${LAB_ROOT}/data \\
               ${LAB_ROOT}/output \\
               ${LAB_ROOT}/logs \\
               ${LAB_ROOT}/state

[Install]
WantedBy=multi-user.target
EOF

    log_success "Created ${SERVICE_FILE}"

    # Create timer file
    log_info "Creating timer file..."
    cat > "$TIMER_FILE" << EOF
[Unit]
Description=Run High-Signal News aggregation daily at 9:00 AM
Documentation=https://forgejo.internal/autonomy/high-signal-news

[Timer]
# Run daily at 9:00 AM (perfect for morning briefing)
OnCalendar=*-*-* 09:00:00

# Randomize start time by up to 10 minutes to avoid thundering herd
RandomizedDelaySec=10m

# Ensure timer runs if system was off during scheduled time
Persistent=true

[Install]
WantedBy=timers.target
EOF

    log_success "Created ${TIMER_FILE}"

    # Create environment file template if it doesn't exist
    if [[ ! -f "$ENV_FILE" ]]; then
        log_info "Creating environment file template..."
        cat > "$ENV_FILE" << EOF
# High-Signal News Environment Configuration
# Copy this file to .env.briefing and fill in your values

# Telegram Bot Configuration (optional)
# Get token from @BotFather
HN_BRIEFING_BOT_TOKEN=your_bot_token_here
# Get chat ID from @userinfobot or group chat
HN_BRIEFING_CHAT_ID=your_chat_id_here

# Email Configuration (optional)
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_app_password
# BRIEFING_EMAIL_TO=recipient@example.com

# Beads Integration (optional)
# BEADS_DIR=/path/to/.beads
EOF
        log_warn "Created ${ENV_FILE} - please edit with your configuration"
    fi

    # Create required directories
    mkdir -p "${LAB_ROOT}/data" "${LAB_ROOT}/output" "${LAB_ROOT}/logs" "${LAB_ROOT}/state"

    # Reload systemd
    log_info "Reloading systemd..."
    if [[ "$USER_MODE" == true ]]; then
        systemctl --user daemon-reload
    else
        sudo systemctl daemon-reload
    fi

    log_success "Systemd configuration reloaded"

    # Enable timer
    log_info "Enabling timer..."
    if [[ "$USER_MODE" == true ]]; then
        systemctl --user enable "${SERVICE_NAME}.timer"
    else
        sudo systemctl enable "${SERVICE_NAME}.timer"
    fi

    log_success "Timer enabled"

    # Show status
    echo ""
    echo "========================================"
    echo "Installation Complete!"
    echo "========================================"
    echo ""
    echo "Service: ${SERVICE_NAME}"
    echo "Timer: Daily at 9:00 AM (+ up to 10 min random delay)"
    echo ""
    echo "Commands:"
    if [[ "$USER_MODE" == true ]]; then
        echo "  Start timer:    systemctl --user start ${SERVICE_NAME}.timer"
        echo "  Check status:   systemctl --user status ${SERVICE_NAME}.timer"
        echo "  View logs:      journalctl --user -u ${SERVICE_NAME}.service"
        echo "  Run now:        systemctl --user start ${SERVICE_NAME}.service"
    else
        echo "  Start timer:    sudo systemctl start ${SERVICE_NAME}.timer"
        echo "  Check status:   sudo systemctl status ${SERVICE_NAME}.timer"
        echo "  View logs:      sudo journalctl -u ${SERVICE_NAME}.service"
        echo "  Run now:        sudo systemctl start ${SERVICE_NAME}.service"
    fi
    echo ""

    if [[ ! -f "$ENV_FILE" ]] || grep -q "your_bot_token_here" "$ENV_FILE" 2>/dev/null; then
        log_warn "Telegram not configured - edit ${ENV_FILE} to enable delivery"
    fi
}

# Main
main() {
    echo "========================================"
    echo "High-Signal News Systemd Installer"
    echo "========================================"
    echo ""

    if [[ "$UNINSTALL" == true ]]; then
        uninstall_service
    else
        install_service
    fi
}

main "$@"
