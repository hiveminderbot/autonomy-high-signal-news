#!/usr/bin/env bash
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
DRY_RUN=false
DRY_RUN_OUTPUT_DIR=""

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
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output-dir)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}[ERROR]${NC} --output-dir requires a directory path" >&2
                exit 1
            fi
            DRY_RUN=true
            DRY_RUN_OUTPUT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --system              Install system-wide (requires sudo)"
            echo "  --uninstall           Remove service and timer"
            echo "  --dry-run             Render service/timer files without calling systemctl"
            echo "  --output-dir <dir>    Write dry-run artifacts under <dir> instead of a temp dir"
            echo "  --help, -h            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                 # Install for current user"
            echo "  sudo $0 --system                   # Install system-wide"
            echo "  $0 --dry-run                       # Preview generated files"
            echo "  $0 --output-dir /tmp/hsn-systemd   # Write dry-run artifacts to a known path"
            echo "  $0 --uninstall                     # Remove user installation"
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

render_service_file() {
    local target_file="$1"
    local current_user="$2"
    local runner_path="$3"

    cat > "$target_file" << EOF
[Unit]
Description=High-Signal News Daily Aggregation
Documentation=https://forgejo.internal/autonomy/high-signal-news
After=network.target

[Service]
Type=oneshot
User=${current_user}
Group=${current_user}
WorkingDirectory=${LAB_ROOT}
Environment="PATH=$HOME/.nix-profile/bin:/nix/var/nix/profiles/default/bin:/run/current-system/sw/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=-${ENV_FILE}

# Run the daily aggregation through the Nix-backed wrapper
ExecStart=${runner_path} \
    --db ${LAB_ROOT}/state/aggregation.db \
    --newsletter-db ${LAB_ROOT}/state/newsletters.db \
    --catalog ${LAB_ROOT}/sources/sources-ai.json \
    --newsletter-catalog ${LAB_ROOT}/sources/newsletter_catalog.json \
    --output-dir ${LAB_ROOT}/output \
    --log-dir ${LAB_ROOT}/logs

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
}

render_timer_file() {
    local target_file="$1"

    cat > "$target_file" << EOF
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
}

render_env_template() {
    local target_file="$1"

    cat > "$target_file" << EOF
# High-Signal News Environment Configuration
# Copy this file to .env.briefing and fill in your values

# Telegram Bot Configuration (optional)
# Get token from @BotFather
HN_BRIEFING_BOT_TOKEN=your_b...here
# Get chat ID from @userinfobot or group chat
HN_BRIEFING_CHAT_ID=your_chat_id_here

# Email Configuration (optional)
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=***
# BRIEFING_EMAIL_TO=recipient@example.com

# Beads Integration (optional)
# BEADS_DIR=/path/to/.beads
EOF
}

print_completion_banner() {
    local mode_label="$1"
    local service_target="$2"
    local timer_target="$3"
    local env_target="$4"

    echo ""
    echo "========================================"
    echo "$mode_label"
    echo "========================================"
    echo ""
    echo "Service: ${SERVICE_NAME}"
    echo "Timer: Daily at 9:00 AM (+ up to 10 min random delay)"
    echo "Service file: ${service_target}"
    echo "Timer file:   ${timer_target}"
    echo "Env file:     ${env_target}"
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
}

dry_run_install() {
    local current_user="$1"
    local runner_path="$2"
    local dry_run_dir

    if [[ -n "$DRY_RUN_OUTPUT_DIR" ]]; then
        dry_run_dir="$DRY_RUN_OUTPUT_DIR"
        mkdir -p "$dry_run_dir"
    else
        dry_run_dir="$(mktemp -d /tmp/high-signal-news-systemd.XXXXXX)"
    fi

    local service_target="${dry_run_dir}/${SERVICE_NAME}.service"
    local timer_target="${dry_run_dir}/${SERVICE_NAME}.timer"
    local env_target="${dry_run_dir}/.env.briefing.template"

    log_info "Dry-run mode: rendering artifacts under ${dry_run_dir}"
    render_service_file "$service_target" "$current_user" "$runner_path"
    render_timer_file "$timer_target"
    render_env_template "$env_target"

    log_success "Rendered ${service_target}"
    log_success "Rendered ${timer_target}"
    log_success "Rendered ${env_target}"
    print_completion_banner "Dry Run Complete!" "$service_target" "$timer_target" "$env_target"
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

    # Get current user info
    local current_user
    current_user="${USER:-$(whoami)}"

    # Determine Nix-backed runner path
    local runner_path
    runner_path="${LAB_ROOT}/scripts/aggregator/systemd/run-daily-aggregation-nix.sh"
    if [[ ! -x "$runner_path" ]]; then
        log_error "Nix runner not found or not executable: $runner_path"
        exit 1
    fi

    log_info "Using Nix runner: $runner_path"

    if [[ "$DRY_RUN" == true ]]; then
        dry_run_install "$current_user" "$runner_path"
        return
    fi

    # Create systemd directory if needed
    mkdir -p "$SYSTEMD_DIR"

    # Create service file
    log_info "Creating service file..."
    render_service_file "$SERVICE_FILE" "$current_user" "$runner_path"

    log_success "Created ${SERVICE_FILE}"

    # Create timer file
    log_info "Creating timer file..."
    render_timer_file "$TIMER_FILE"

    log_success "Created ${TIMER_FILE}"

    # Create environment file template if it doesn't exist
    if [[ ! -f "$ENV_FILE" ]]; then
        log_info "Creating environment file template..."
        render_env_template "$ENV_FILE"
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
    print_completion_banner "Installation Complete!" "$SERVICE_FILE" "$TIMER_FILE" "$ENV_FILE"

    if [[ ! -f "$ENV_FILE" ]] || grep -q "HN_BRIEFING_CHAT_ID=your_chat_id_here" "$ENV_FILE" 2>/dev/null; then
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
