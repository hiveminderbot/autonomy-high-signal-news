#!/usr/bin/env bash
# Run the high-signal-news pytest suite inside the lab's Nix-backed Python environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_WITH_NIX_PYTHON="${SCRIPT_DIR}/run-with-nix-python.sh"

if [[ ! -x "$RUN_WITH_NIX_PYTHON" ]]; then
    echo "[ERROR] Missing Nix Python wrapper: $RUN_WITH_NIX_PYTHON" >&2
    exit 1
fi

cd "$LAB_ROOT"
exec "$RUN_WITH_NIX_PYTHON" -m pytest tests/ "$@"
