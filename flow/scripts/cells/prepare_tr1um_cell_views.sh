#!/usr/bin/env bash
# Prepare origin-normalized compatibility GDS from immutable TR-1um STDLIB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export TR1UM_STDLIB_SOURCE_GDS="${TR1UM_STDLIB_SOURCE_GDS:-$ROOT/STDLIB/LogicCells/gds}"
export TR1UM_FLOW_CELL_GDS_DIR="${TR1UM_FLOW_CELL_GDS_DIR:-$ROOT/flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/flow_gds}"
exec klayout -b -r "$ROOT/flow/scripts/cells/prepare_tr1um_cell_views.py"
