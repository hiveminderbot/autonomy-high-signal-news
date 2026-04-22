#!/usr/bin/env bash
# Run the High-Signal News daily aggregation pipeline with a Nix-provided Python env.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON_SCRIPT="${LAB_ROOT}/scripts/run_daily_aggregation.py"

if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "[ERROR] Missing runner script: $PYTHON_SCRIPT" >&2
    exit 1
fi

if ! command -v nix-shell >/dev/null 2>&1; then
    echo "[ERROR] nix-shell is required but was not found in PATH" >&2
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
    --run "cd \"$LAB_ROOT\" && export PYTHONPATH=\"$PYTHONPATH_EXPORT\" && exec python3 \"$PYTHON_SCRIPT\"$ARGS_Q"
