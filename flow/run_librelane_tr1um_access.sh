#!/usr/bin/env bash
# TR-1um LibreLane launcher for the signal-access standard-cell library.
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=flow/scripts/common/librelane.sh
source "$FLOW_DIR/scripts/common/librelane.sh"
tr1um_prepare_librelane "$FLOW_DIR"
tr1um_run_librelane "${1:?usage: run_librelane_tr1um_access.sh <config.yaml> [args...]}" "TR-1um_stdcell_access" "${@:2}"
