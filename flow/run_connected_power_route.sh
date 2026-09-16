#!/usr/bin/env bash
# Add explicitly routed VDD/GND to a completed powered-access mixed-counter run.
# Run this from the LibreLane development nix-shell.
set -Eeuo pipefail

usage() {
    echo "Usage: $0 <completed-run-dir> [output-dir]" >&2
    exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$(realpath "$1")"
OUTPUT_DIR="${2:-$RUN_DIR/connected_power}"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"

TOP=tr1um_mixed_counter
PDK="$ROOT/flow/pdk_root/TR-1um"
TECH="$PDK/libs.tech/klayout/tech"
POWER_LIB="$PDK/libs.ref/TR-1um_stdcell_access_power"
INPUT_DEF="$RUN_DIR/final/def/$TOP.def"
TECH_LEF="$POWER_LIB/lef/TR-1um_tech.lef"
ROUTING_CELL_LEF="$POWER_LIB/lef/TR-1um_access_cells_signal_power.lef"
PHYSICAL_CELL_LEF="$POWER_LIB/lef/TR-1um_access_cells.lef"
ROUTING_MACRO_LEF="$ROOT/flow/align_macro/CMC_S_NMOS_B_X1_Y1.routing.lef"
PHYSICAL_MACRO_LEF="$ROOT/flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef"
CELL_GDS="$POWER_LIB/gds/TR-1um_stdcell_access_with_ties.gds"
MACRO_GDS="$ROOT/flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds"
ROUTE_TCL="$ROOT/flow/scripts/signoff/route_connected_power.tcl"

for command in openroad klayout python3; do
    command -v "$command" >/dev/null || {
        echo "ERROR: $command is unavailable; enter the LibreLane nix-shell first" >&2
        exit 3
    }
done
for required in \
    "$INPUT_DEF" "$TECH_LEF" "$ROUTING_CELL_LEF" "$PHYSICAL_CELL_LEF" \
    "$ROUTING_MACRO_LEF" "$PHYSICAL_MACRO_LEF" "$CELL_GDS" "$MACRO_GDS" \
    "$ROUTE_TCL"; do
    [[ -f "$required" ]] || { echo "ERROR: missing input $required" >&2; exit 4; }
done

export CONNECTED_POWER_TECH_LEF="$TECH_LEF"
export CONNECTED_POWER_CELL_LEF="$ROUTING_CELL_LEF"
export CONNECTED_POWER_MACRO_LEF="$ROUTING_MACRO_LEF"
export CONNECTED_POWER_INPUT_DEF="$INPUT_DEF"
export CONNECTED_POWER_OUTPUT_DEF="$OUTPUT_DIR/$TOP.connected_power.def"
export CONNECTED_POWER_OUTPUT_ODB="$OUTPUT_DIR/$TOP.connected_power.odb"
export CONNECTED_POWER_GUIDES="$OUTPUT_DIR/$TOP.connected_power.guide"
export CONNECTED_POWER_DRC="$OUTPUT_DIR/openroad_detailed_route.drc"
export CONNECTED_POWER_MACRO_INSTANCE="${CONNECTED_POWER_MACRO_INSTANCE:-u_ana}"

set -x
openroad -exit "$ROUTE_TCL" 2>&1 | tee "$OUTPUT_DIR/openroad.log"
if [[ ! -f "$CONNECTED_POWER_DRC" || -s "$CONNECTED_POWER_DRC" ]]; then
    echo "ERROR: OpenROAD detailed routing produced violations" >&2
    [[ -f "$CONNECTED_POWER_DRC" ]] && cat "$CONNECTED_POWER_DRC" >&2
    exit 5
fi

python3 "$ROOT/flow/librelane_override/librelane/scripts/klayout/stream_out.py" \
    "$CONNECTED_POWER_OUTPUT_DEF" \
    --output "$OUTPUT_DIR/$TOP.connected_power.gds" \
    --top "$TOP" \
    --conflict-resolution AddToCell \
    --lyt "$TECH/TR-1um.lyt" \
    --lyp "$TECH/TR-1um.lyp" \
    --lym "$TECH/def_layer_map.map" \
    --input-lef "$TECH_LEF" \
    --input-lef "$PHYSICAL_CELL_LEF" \
    --input-lef "$PHYSICAL_MACRO_LEF" \
    --with-gds-file "$CELL_GDS" \
    --with-gds-file "$MACRO_GDS"

klayout -b -zz -r "$TECH/drc/run.drc" \
    -rd "input=$OUTPUT_DIR/$TOP.connected_power.gds" \
    -rd "top_cell=$TOP" \
    -rd "report=$OUTPUT_DIR/drawing_drc.lyrdb" \
    2>&1 | tee "$OUTPUT_DIR/drawing_drc.log"
python3 "$ROOT/flow/scripts/signoff/check_klayout_report.py" \
    "$OUTPUT_DIR/drawing_drc.lyrdb"

python3 "$ROOT/flow/scripts/signoff/check_connected_power.py" \
    "$OUTPUT_DIR/$TOP.connected_power.gds" "$TOP" \
    2>&1 | tee "$OUTPUT_DIR/connected_power.log"

# Extraction is intentionally netlist-only here.  It provides an inspectable
# independent physical netlist without pretending that a framed LVS contract
# has passed.
klayout -b -zz -r "$TECH/lvs/run.lvs" \
    -rd "input=$OUTPUT_DIR/$TOP.connected_power.gds" \
    -rd "top_cell=$TOP" \
    -rd "report=$OUTPUT_DIR/extraction.lvsdb" \
    -rd "extracted=$OUTPUT_DIR/$TOP.connected_power.extracted" \
    -rd netlist_only \
    2>&1 | tee "$OUTPUT_DIR/extraction.log"
test -s "$OUTPUT_DIR/$TOP.connected_power.extracted"
set +x

echo "PASS: connected core GDS: $OUTPUT_DIR/$TOP.connected_power.gds"
echo "NOTE: this is a core-level result; direct connection to the MPW frame pads is not yet DRC-clean."
