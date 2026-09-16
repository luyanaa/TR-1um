#!/usr/bin/env bash
# Generate and run strict transistor-level LVS for a digital core or hierarchy.
# Run this from the LibreLane development nix-shell.
set -Eeuo pipefail

usage() {
    echo "Usage: $0 <routed.gds> <routed.def> <powered-pnl.v> <top> <output-dir> [macro-contract.cir ...]" >&2
    exit 2
}

[[ $# -ge 5 ]] || usage
GDS="$(realpath "$1")"
DEF="$(realpath "$2")"
PNL="$(realpath "$3")"
TOP="$4"
OUTPUT_DIR="$5"
shift 5
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TECH="$ROOT/flow/pdk_root/TR-1um/libs.tech/klayout/tech"
CELL_CDL="${CORE_LVS_CELL_CDL:-$ROOT/flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access/cdl/TR-1um_stdcell_access.cdl}"
CELL_LIBERTY="${CORE_LVS_CELL_LIBERTY:-$ROOT/flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access/lib/TR-1um_stdcell_access_typ_5p0V_25C.lib}"
LABELER="$ROOT/flow/scripts/signoff/add_def_pin_labels.py"
BUILDER="$ROOT/flow/scripts/signoff/build_core_lvs_contract.py"
LABELED_GDS="$OUTPUT_DIR/$TOP.lvs.gds"
PHYSICAL="$OUTPUT_DIR/$TOP.physical.extracted"
CONTRACT="$OUTPUT_DIR/$TOP.strict.cir"

for command in klayout python3; do
    command -v "$command" >/dev/null || {
        echo "ERROR: $command is unavailable; enter the LibreLane nix-shell first" >&2
        exit 3
    }
done
for required in "$GDS" "$DEF" "$PNL" "$CELL_CDL" "$CELL_LIBERTY" "$LABELER" "$BUILDER"; do
    [[ -f "$required" ]] || { echo "ERROR: missing input $required" >&2; exit 4; }
done

builder_args=()
for macro_contract in "$@"; do
    macro_contract="$(realpath "$macro_contract")"
    [[ -f "$macro_contract" ]] || { echo "ERROR: missing macro contract $macro_contract" >&2; exit 4; }
    builder_args+=(--macro-contract "$macro_contract")
done

set -x
python3 "$LABELER" --input-gds "$GDS" --def "$DEF" --top "$TOP" \
    --output-gds "$LABELED_GDS"

klayout -b -zz -r "$TECH/lvs/run.lvs" \
    -rd "input=$LABELED_GDS" -rd "top_cell=$TOP" \
    -rd "report=$OUTPUT_DIR/physical-extraction.lvsdb" \
    -rd "extracted=$PHYSICAL" -rd netlist_only \
    2>&1 | tee "$OUTPUT_DIR/physical-extraction.log"
test -s "$PHYSICAL"

python3 "$BUILDER" \
    --physical-extracted "$PHYSICAL" \
    --powered-netlist "$PNL" \
    --cell-cdl "$CELL_CDL" \
    --cell-liberty "$CELL_LIBERTY" \
    --top "$TOP" --output "$CONTRACT" \
    "${builder_args[@]}"

klayout -b -zz -r "$TECH/lvs/run.lvs" \
    -rd "input=$LABELED_GDS" -rd "top_cell=$TOP" \
    -rd "circuit=$CONTRACT" \
    -rd "report=$OUTPUT_DIR/lvs.lvsdb" \
    -rd "extracted=$OUTPUT_DIR/$TOP.lvs.extracted" \
    2>&1 | tee "$OUTPUT_DIR/lvs.log"
grep -q "Congratulations! Netlists match" "$OUTPUT_DIR/lvs.log"
set +x

echo "PASS: strict transistor-level LVS: $TOP"
echo "LVS-labelled GDS: $LABELED_GDS"
echo "Reusable SPICE contract: $CONTRACT"
