#!/usr/bin/env bash
# Run a Python command for high-signal-news inside the flake dev shell.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v nix >/dev/null 2>&1; then
    echo "[ERROR] nix is required but was not found in PATH" >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    cat <<'EOF' >&2
Usage: scripts/run-with-nix-python.sh <python-args...>

Examples:
  scripts/run-with-nix-python.sh scripts/run_daily_aggregation.py --help
  scripts/run-with-nix-python.sh -m scripts.scheduler.daily_briefing --help
EOF
    exit 1
fi

cd "$LAB_ROOT"
exec nix develop --command python3 "$@"
