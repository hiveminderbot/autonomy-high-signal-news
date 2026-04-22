#!/usr/bin/env bash
# Run a Python command for high-signal-news inside a Nix-provided environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v nix-shell >/dev/null 2>&1; then
    echo "[ERROR] nix-shell is required but was not found in PATH" >&2
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

printf -v ARGS_Q ' %q' "$@"
PYTHONPATH_EXPORT="${LAB_ROOT}/scripts\${PYTHONPATH:+:\$PYTHONPATH}"

exec nix-shell \
    -p \
    python312 \
    python312Packages.feedparser \
    python312Packages.requests \
    python312Packages.beautifulsoup4 \
    python312Packages.pyyaml \
    python312Packages.sgmllib3k \
    python312Packages.markdown \
    python312Packages.pytest \
    --run "cd \"$LAB_ROOT\" && export PYTHONPATH=\"$PYTHONPATH_EXPORT\" && exec python3$ARGS_Q"
