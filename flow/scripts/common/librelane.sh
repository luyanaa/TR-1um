#!/usr/bin/env bash
# Shared launcher setup for the TR-1um LibreLane entry points.
set -euo pipefail
set -x

tr1um_prepare_librelane() {
    local flow_dir="$1"
    export PYTHONPATH="$flow_dir/librelane_override${PYTHONPATH:+:$PYTHONPATH}"
    export PDK_ROOT="${PDK_ROOT:-$flow_dir/pdk_root}"
    export PDK="${PDK:-TR-1um}"
}

tr1um_run_librelane() {
    local config="$1"
    local scl="${2:-}"
    shift 2

    local design_dir config_name
    design_dir="$(cd "$(dirname "$config")" && pwd)"
    config_name="$(basename "$config")"
    cd "$design_dir"

    local args=(--manual-pdk)
    if [[ -n "$scl" ]]; then
        args+=(--pdk-root "$PDK_ROOT" --pdk "$PDK" --scl "$scl")
    fi
    command -v librelane >/dev/null 2>&1 || {
        echo "ERROR: librelane is unavailable; enter the LibreLane development shell" >&2
        return 127
    }
    exec librelane "${args[@]}" "$config_name" "$@"
}
