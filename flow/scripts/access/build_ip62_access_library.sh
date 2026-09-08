#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export TR1UM_IP62_SOURCE_GDS="${TR1UM_IP62_SOURCE_GDS:-$ROOT/STDLIB/LogicCells/gds}"
export TR1UM_IP62_ACCESS_ROOT="${TR1UM_IP62_ACCESS_ROOT:-$ROOT/flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access}"
exec klayout -b -r "$ROOT/flow/scripts/access/gen_ip62_beol_access_strict.py"
