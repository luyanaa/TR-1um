#!/usr/bin/env bash
# One-command generic TR-1um RTL -> placed/routed GDS -> connected-power
# KLayout DRC -> extraction -> strict LVS flow. Run inside the LibreLane shell.
set -Eeuo pipefail

if [[ $# != 3 ]]; then
    echo "Usage: $0 <design-config.yaml> <top-module> <run-tag>" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$(realpath "$1")"
TOP="$2"
TAG="$3"
DESIGN_DIR="$(dirname "$CONFIG")"

set -x
"$ROOT/flow/run_librelane_tr1um_access.sh" "$CONFIG" --run-tag "$TAG"
"$ROOT/flow/run_digital_core_flow.sh" "$DESIGN_DIR/runs/$TAG" "$TOP"
set +x

echo "PASS: RTL-to-GDS-to-LVS completed for $TOP ($TAG)"
