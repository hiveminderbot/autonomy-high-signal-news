#!/usr/bin/env bash
# Run the High-Signal News daily aggregation pipeline with a Nix-provided Python env.
# Migrated from legacy nix-shell to nix develop per AGENTS.md Nix Policy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON_SCRIPT="${LAB_ROOT}/scripts/run_daily_aggregation.py"

if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "[ERROR] Missing runner script: $PYTHON_SCRIPT" >&2
    exit 1
fi

if ! command -v nix >/dev/null 2>&1; then
    echo "[ERROR] nix is required but was not found in PATH" >&2
    exit 1
fi

printf -v ARGS_Q ' %q' "$@"
PYTHONPATH_EXPORT="${LAB_ROOT}/scripts${PYTHONPATH:+:${PYTHONPATH}}"

# Use nix develop with the project's flake.nix instead of legacy nix-shell
exec nix develop "$LAB_ROOT" --command bash -c "cd \"$LAB_ROOT\" && export PYTHONPATH=\"$PYTHONPATH_EXPORT\" && exec python3 \"$PYTHON_SCRIPT\"$ARGS_Q"
