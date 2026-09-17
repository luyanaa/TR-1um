#!/usr/bin/env bash
# Run SPEF-backed gate-level simulations for completed TR-1um digital runs.
# Invoke from the LibreLane development shell.
set -Euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec python3 "$ROOT/flow/scripts/signoff/run_post_layout_digital.py" \
    --manifest "$ROOT/flow/qualification/post_layout_digital_manifest.json" \
    "$@"
