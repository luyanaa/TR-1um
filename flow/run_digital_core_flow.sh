#!/usr/bin/env bash
# Finish any sparse TR-1um digital design with ordinary M1 supply buses,
# then run DRC, supply-connectivity checks, extraction, and strict LVS.
# Run this from the LibreLane development nix-shell.
set -Eeuo pipefail

usage() {
    echo "Usage: $0 <completed-run-dir> <top-module> [output-dir]" >&2
    exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$(realpath "$1")"
TOP="$2"
OUTPUT_DIR="${3:-$RUN_DIR/connected_power}"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"
DESIGN_DIR="$(dirname "$(dirname "$RUN_DIR")")"
GDS_POSTPROCESS="$DESIGN_DIR/postprocess_gds.py"
POWER_CONFIG="$DESIGN_DIR/power_channels.json"
ROUTE_CONFIG="$DESIGN_DIR/route_options.json"

PDK="$ROOT/flow/pdk_root/TR-1um"
TECH="$PDK/libs.tech/klayout/tech"
ACCESS_LIB="$PDK/libs.ref/TR-1um_stdcell_access"
POWER_LIB="$PDK/libs.ref/TR-1um_stdcell_access_power"
INPUT_DEF="$RUN_DIR/31-openroad-detailedplacement/$TOP.def"
BASE_GDS="$RUN_DIR/final/gds/$TOP.gds"
TECH_LEF="$ACCESS_LIB/lef/TR-1um_tech.lef"
PHYSICAL_CELL_LEF="$ACCESS_LIB/lef/TR-1um_access_cells.lef"
ROUTING_SOURCE_LEF="$POWER_LIB/lef/TR-1um_access_cells_signal_power.lef"
CELL_CDL="$ACCESS_LIB/cdl/TR-1um_stdcell_access.cdl"
CELL_LIBERTY="$ACCESS_LIB/lib/TR-1um_stdcell_access_typ_5p0V_25C.lib"
POWERED_PNL="$RUN_DIR/final/pnl/$TOP.pnl.v"
ADD_POWER="$ROOT/flow/scripts/signoff/add_channel_power.py"
ADD_LABELS="$ROOT/flow/scripts/signoff/add_def_pin_labels.py"
NORMALIZE_TIES="$ROOT/flow/scripts/signoff/normalize_tie_cells.py"
BUILD_CONTRACT="$ROOT/flow/scripts/signoff/build_core_lvs_contract.py"
MAKE_ROUTING_LEF="$ROOT/flow/scripts/signoff/make_routing_obstructions.py"
MAKE_TECH_LEF="$ROOT/flow/scripts/signoff/make_conservative_tech_lef.py"
EXTRACT_CELLS="$ROOT/flow/scripts/signoff/extract_child_library.py"
CHECK_EXTRACTION="$ROOT/flow/scripts/signoff/check_extracted_instance_supplies.py"
ROUTE_TCL="$ROOT/flow/scripts/signoff/route_digital_core.tcl"
OFFICIAL_IP62="$ROOT/flow/run_official_ip62_drc.sh"

for command in openroad klayout python3; do
    command -v "$command" >/dev/null || {
        echo "ERROR: $command is unavailable; enter the LibreLane nix-shell first" >&2
        exit 3
    }
done
for required in \
    "$INPUT_DEF" "$BASE_GDS" "$POWERED_PNL" "$CELL_CDL" "$CELL_LIBERTY" "$TECH_LEF" "$PHYSICAL_CELL_LEF" \
    "$ROUTING_SOURCE_LEF" "$ADD_POWER" "$MAKE_ROUTING_LEF" "$MAKE_TECH_LEF" \
    "$ADD_LABELS" "$NORMALIZE_TIES" "$BUILD_CONTRACT" "$EXTRACT_CELLS" \
    "$CHECK_EXTRACTION" "$ROUTE_TCL" "$OFFICIAL_IP62"; do
    [[ -f "$required" ]] || { echo "ERROR: missing input $required" >&2; exit 4; }
done

ROUTING_CELL_LEF="$OUTPUT_DIR/TR-1um_core_routing.lef"
ROUTING_TECH_LEF="$OUTPUT_DIR/TR-1um_core_tech.lef"
CHILD_GDS="$OUTPUT_DIR/TR-1um_known_good_cells.gds"
POWER_DEF="$OUTPUT_DIR/$TOP.placed_power.def"
OUTPUT_DEF="$OUTPUT_DIR/$TOP.connected_power.def"
OUTPUT_GDS="$OUTPUT_DIR/$TOP.connected_power.gds"
UNLABELED_GDS="$OUTPUT_DIR/$TOP.unlabeled.gds"
CONTRACT="$OUTPUT_DIR/$TOP.strict.cir"

set -x
# Take physical child views from the already DRC-clean LibreLane result.  This
# isolates this derivation from any later regeneration of the aggregate library.
python3 "$EXTRACT_CELLS" "$BASE_GDS" "$TOP" "$CHILD_GDS"
python3 "$MAKE_TECH_LEF" "$TECH_LEF" "$ROUTING_TECH_LEF"
python3 "$MAKE_ROUTING_LEF" "$ROUTING_SOURCE_LEF" "$ROUTING_CELL_LEF"
POWER_ARGS=()
if [[ -f "$POWER_CONFIG" ]]; then
    POWER_ARGS+=(--config "$POWER_CONFIG")
fi
python3 "$ADD_POWER" "$INPUT_DEF" "$POWER_DEF" "$PHYSICAL_CELL_LEF" "${POWER_ARGS[@]}"

export CORE_TECH_LEF="$ROUTING_TECH_LEF"
export CORE_CELL_LEF="$ROUTING_CELL_LEF"
export CORE_INPUT_DEF="$POWER_DEF"
export CORE_OUTPUT_DEF="$OUTPUT_DEF"
export CORE_OUTPUT_ODB="$OUTPUT_DIR/$TOP.connected_power.odb"
export CORE_OUTPUT_LEF="$OUTPUT_DIR/$TOP.macro.lef"
export CORE_GUIDES="$OUTPUT_DIR/$TOP.connected_power.guide"
export CORE_DRC="$OUTPUT_DIR/openroad_detailed_route.drc"
if [[ -z "${CORE_DRT_SEED:-}" && -f "$ROUTE_CONFIG" ]]; then
    CORE_DRT_SEED="$(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1])).get("drt_seed", 42)))' "$ROUTE_CONFIG")"
    export CORE_DRT_SEED
fi

openroad -exit "$ROUTE_TCL" 2>&1 | tee "$OUTPUT_DIR/openroad.log"
if [[ ! -f "$CORE_DRC" || -s "$CORE_DRC" ]]; then
    echo "ERROR: OpenROAD detailed routing produced violations" >&2
    [[ -f "$CORE_DRC" ]] && cat "$CORE_DRC" >&2
    exit 5
fi

python3 "$ROOT/flow/librelane_override/librelane/scripts/klayout/stream_out.py" \
    "$OUTPUT_DEF" \
    --output "$UNLABELED_GDS" \
    --top "$TOP" \
    --conflict-resolution AddToCell \
    --lyt "$TECH/TR-1um.lyt" \
    --lyp "$TECH/TR-1um.lyp" \
    --lym "$TECH/def_layer_map.map" \
    --input-lef "$TECH_LEF" \
    --input-lef "$PHYSICAL_CELL_LEF" \
    --with-gds-file "$CHILD_GDS"

python3 "$ADD_LABELS" --input-gds "$UNLABELED_GDS" --def "$OUTPUT_DEF" \
    --top "$TOP" --output-gds "$OUTPUT_GDS"

TIE_NORMALIZED_GDS="$OUTPUT_DIR/$TOP.tie_normalized.gds"
python3 "$NORMALIZE_TIES" --input "$OUTPUT_GDS" --output "$TIE_NORMALIZED_GDS"
mv -f -- "$TIE_NORMALIZED_GDS" "$OUTPUT_GDS"

if [[ -f "$GDS_POSTPROCESS" ]]; then
    POSTPROCESSED_GDS="$OUTPUT_DIR/$TOP.postprocessed.gds"
    python3 "$GDS_POSTPROCESS" --input "$OUTPUT_GDS" \
        --output "$POSTPROCESSED_GDS" --top "$TOP"
    mv -f -- "$POSTPROCESSED_GDS" "$OUTPUT_GDS"
fi

klayout -b -zz -r "$TECH/drc/run.drc" \
    -rd "input=$OUTPUT_GDS" \
    -rd "top_cell=$TOP" \
    -rd "report=$OUTPUT_DIR/drawing_drc.lyrdb" \
    2>&1 | tee "$OUTPUT_DIR/drawing_drc.log"
python3 "$ROOT/flow/scripts/signoff/check_klayout_report.py" \
    "$OUTPUT_DIR/drawing_drc.lyrdb"

python3 "$ROOT/flow/scripts/signoff/check_connected_power.py" \
    "$OUTPUT_GDS" "$TOP" \
    2>&1 | tee "$OUTPUT_DIR/connected_power.log"

# Extract first, then build the independent intent contract and compare it.
klayout -b -zz -r "$TECH/lvs/run.lvs" \
    -rd "input=$OUTPUT_GDS" \
    -rd "top_cell=$TOP" \
    -rd "report=$OUTPUT_DIR/extraction.lvsdb" \
    -rd "extracted=$OUTPUT_DIR/$TOP.connected_power.extracted" \
    -rd netlist_only \
    2>&1 | tee "$OUTPUT_DIR/extraction.log"
test -s "$OUTPUT_DIR/$TOP.connected_power.extracted"
python3 "$CHECK_EXTRACTION" \
    "$POWER_DEF" "$OUTPUT_DIR/$TOP.connected_power.extracted" "$TOP"

python3 "$BUILD_CONTRACT" \
    --physical-extracted "$OUTPUT_DIR/$TOP.connected_power.extracted" \
    --powered-netlist "$POWERED_PNL" --cell-cdl "$CELL_CDL" \
    --cell-liberty "$CELL_LIBERTY" \
    --top "$TOP" --output "$CONTRACT"
klayout -b -zz -r "$TECH/lvs/run.lvs" \
    -rd "input=$OUTPUT_GDS" -rd "top_cell=$TOP" \
    -rd "circuit=$CONTRACT" \
    -rd "report=$OUTPUT_DIR/lvs.lvsdb" \
    -rd "extracted=$OUTPUT_DIR/$TOP.lvs.extracted" \
    2>&1 | tee "$OUTPUT_DIR/lvs.log"
grep -q "Congratulations! Netlists match" "$OUTPUT_DIR/lvs.log"

# The in-shell drawing deck remains useful for fast geometry feedback, but the
# official image/deck is the final authority and also reports electrical
# warnings such as WAR06 Floating SG.  Set RUN_OFFICIAL_IP62_DRC=0 only for an
# explicitly non-signoff development iteration.
if [[ "${RUN_OFFICIAL_IP62_DRC:-1}" == 1 ]]; then
    "$OFFICIAL_IP62" "$OUTPUT_GDS" "$TOP" \
        "$OUTPUT_DIR/official_ip62_drc.lyrdb" \
        2>&1 | tee "$OUTPUT_DIR/official_ip62_drc.log"
fi
set +x

echo "PASS: connected, DRC-clean, LVS-clean digital core GDS: $OUTPUT_GDS"
echo "Macro LEF: $CORE_OUTPUT_LEF"
echo "Reusable LVS contract: $CONTRACT"
if [[ "${RUN_OFFICIAL_IP62_DRC:-1}" == 1 ]]; then
    echo "Official IP62 report: $OUTPUT_DIR/official_ip62_drc.lyrdb"
fi
echo "NOTE: this is a core-level result; the MPW frame/pad transition is not included."
