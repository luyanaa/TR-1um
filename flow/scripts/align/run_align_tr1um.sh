#!/usr/bin/env bash
# TR-1um ALIGN flow driver.
#
# Runs ALIGN (analog layout automation) with the TR-1um PDK abstraction, then
# post-processes the GDS into TR-1um drawing layers (AP/AN/WN) via KLayout.
#
# Usage:
#   run_align_tr1um.sh <netlist_dir> <top_subckt> <netlist_file> <work_dir>
#
# `netlist_file` may be either a basename inside `netlist_dir` or an absolute
# path. All paths are normalized before invoking ALIGN because ALIGN resolves
# `--netlist_file` against the process CWD rather than `netlist_dir`.
#
# Optional environment controls:
#   ALIGN_FLOW_START, ALIGN_FLOW_STOP, ALIGN_EXTERNAL_PLACEMENT
#   ALIGN_EFFORT, ALIGN_ROUTER_MODE, ALIGN_ROUTER, ALIGN_SEED
#   ALIGN_REQUIRE_CLEAN, ALIGN_DRC_RUNSET
#
# Prereqs:
#   - conda env "spice" with ALIGN installed
#     (import needs DYLD_LIBRARY_PATH=$CONDA_PREFIX/lib for liblpsolve55)
#   - klayout (from the LibreLane nix devshell) for post-processing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

NETLIST_DIR_ARG="${1:?usage: run_align_tr1um.sh <netlist dir> <top subckt> <netlist file> <work dir>}"
TOP="${2:?top subckt}"
NETLIST_ARG="${3:?netlist file}"
WORK_ARG="${4:?work dir}"

NETLIST_DIR="$(cd "$NETLIST_DIR_ARG" && pwd)"
if [[ "$NETLIST_ARG" = /* ]]; then
  NETLIST_PATH="$NETLIST_ARG"
else
  NETLIST_PATH="$NETLIST_DIR/$NETLIST_ARG"
fi
NETLIST_PATH="$(cd "$(dirname "$NETLIST_PATH")" && pwd)/$(basename "$NETLIST_PATH")"
[[ -f "$NETLIST_PATH" ]] || { echo "ERROR: netlist not found: $NETLIST_PATH" >&2; exit 2; }

mkdir -p "$WORK_ARG"
WORK="$(cd "$WORK_ARG" && pwd)"

CONDA_PY="${CONDA_PY:-$HOME/miniforge3/envs/spice/bin/python}"
TR1UM_PDK="${TR1UM_PDK:-$HOME/Documents/ALIGN-public/pdks/TR1um}"
POSTPROC="${TR1UM_ALIGN_POSTPROCESS:-$ROOT/flow/scripts/align/align_postprocess.py}"
KLAYOUT_BIN="${KLAYOUT_BIN:-$(command -v klayout || true)}"
[[ -x "$CONDA_PY" ]] || { echo "ERROR: ALIGN Python not executable: $CONDA_PY" >&2; exit 3; }
[[ -d "$TR1UM_PDK" ]] || { echo "ERROR: ALIGN PDK not found: $TR1UM_PDK" >&2; exit 3; }
[[ -f "$POSTPROC" ]] || { echo "ERROR: postprocessor not found: $POSTPROC" >&2; exit 3; }
[[ -n "$KLAYOUT_BIN" ]] || { echo "ERROR: klayout not found; set KLAYOUT_BIN or enter the LibreLane shell" >&2; exit 3; }
[[ -x "$KLAYOUT_BIN" ]] || { echo "ERROR: klayout not executable: $KLAYOUT_BIN" >&2; exit 3; }

ALIGN_EXTERNAL_PLACEMENT="${ALIGN_EXTERNAL_PLACEMENT:-}"
TOP_UPPER="$(printf '%s' "$TOP" | tr '[:lower:]' '[:upper:]')"
if [[ -z "$ALIGN_EXTERNAL_PLACEMENT" && "$TOP_UPPER" == "TELESCOPIC_OTA" ]]; then
  ALIGN_EXTERNAL_PLACEMENT="$ROOT/flow/align_test/input/TELESCOPIC_OTA.placement_verilog.json"
fi
if [[ -n "$ALIGN_EXTERNAL_PLACEMENT" ]]; then
  [[ -f "$ALIGN_EXTERNAL_PLACEMENT" ]] || { echo "ERROR: external placement file not found: $ALIGN_EXTERNAL_PLACEMENT" >&2; exit 3; }
else
  ALIGN_EXTERNAL_PLACEMENT="-"
fi

echo "==> Stage 1/2: ALIGN (topology -> primitives -> PnR)"
ALIGN_LIB="$(dirname "$CONDA_PY")/../lib"
PYTHONPATH="$ROOT/flow/scripts/align${PYTHONPATH:+:$PYTHONPATH}" \
DYLD_LIBRARY_PATH="$ALIGN_LIB${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" \
  "$CONDA_PY" - "$NETLIST_DIR" "$TR1UM_PDK" "$WORK" "$TOP" "$NETLIST_PATH" "$ALIGN_EXTERNAL_PLACEMENT" <<'PY'
import os
import sys
from pathlib import Path

from align.main import schematic2layout
import align.pnr.main as pnr_main
from align_external_placement import make_placer_driver

netlist_dir, pdk_dir, working_dir = map(Path, sys.argv[1:4])
top = sys.argv[4]
netlist = Path(sys.argv[5])
external_placement = None if sys.argv[6] == "-" else Path(sys.argv[6])

def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}

if external_placement is not None:
    pnr_main.placer_driver = make_placer_driver(external_placement, top)

result = schematic2layout(
    str(netlist_dir),
    str(pdk_dir),
    netlist_file=str(netlist),
    subckt=top,
    working_dir=str(working_dir),
    nvariants=1,
    effort=int(os.environ.get("ALIGN_EFFORT", "0")),
    flow_start=os.environ.get("ALIGN_FLOW_START"),
    flow_stop=os.environ.get("ALIGN_FLOW_STOP"),
    router_mode=os.environ.get("ALIGN_ROUTER_MODE", "bottom_up"),
    router=os.environ.get("ALIGN_ROUTER", "astar"),
    seed=int(os.environ.get("ALIGN_SEED", "0")),
    use_analytical_placer=env_bool("ALIGN_USE_ANALYTICAL_PLACER"),
    ilp_solver=os.environ.get("ALIGN_ILP_SOLVER", "symphony"),
)
if result is None:
    raise RuntimeError("ALIGN returned no result")
PY
if [[ "${ALIGN_FLOW_STOP:-}" == "3_pnr:place" ]]; then
  echo "Done. Placement stage completed in $WORK/3_pnr"
  exit 0
fi
TOP_UPPER="$(printf '%s' "$TOP" | tr '[:lower:]' '[:upper:]')"
GDS_IN="$WORK/${TOP_UPPER}_0.gds"
LEF_IN="$WORK/${TOP_UPPER}_0.lef"
GDS_CANONICAL="$WORK/${TOP_UPPER}.gds"
LEF_CANONICAL="$WORK/${TOP_UPPER}.lef"
GDS_OUT="$WORK/${TOP_UPPER}_drawing.gds"
if [ -f "$GDS_IN" ] && [ -f "$LEF_IN" ]; then
  TR1UM_GDS_IN="$GDS_IN" TR1UM_GDS_OUT="$GDS_CANONICAL" \
  TR1UM_LEF_IN="$LEF_IN" TR1UM_LEF_OUT="$LEF_CANONICAL" \
  TR1UM_MACRO_NAME="$TOP_UPPER" \
    "$KLAYOUT_BIN" -b -r "$ROOT/flow/scripts/align/normalize_macro.py"
  TR1UM_GDS_IN="$GDS_CANONICAL" TR1UM_GDS_OUT="$GDS_OUT" \
    "$KLAYOUT_BIN" -b -r "$POSTPROC"
  echo "Wrote: $GDS_CANONICAL"
  echo "Wrote: $LEF_CANONICAL"
  echo "Wrote: $GDS_OUT"
else
  echo "ERROR: ALIGN completed without expected GDS/LEF: $GDS_IN $LEF_IN" >&2
  exit 4
fi
if [[ "${ALIGN_REQUIRE_CLEAN:-0}" == 1 ]]; then
  [[ ! -s "$WORK/3_pnr/${TOP_UPPER}_0.errors" ]] || { echo "ERROR: ALIGN reported layout errors" >&2; exit 5; }
  DRC_REPORT="$WORK/${TOP_UPPER}.drc.lyrdb"
  "$KLAYOUT_BIN" -b -zz -r "${ALIGN_DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run.drc}" \
    -rd "input=$GDS_OUT" -rd "top_cell=$TOP_UPPER" -rd "report=$DRC_REPORT"
  python3 - "$DRC_REPORT" <<'PY'
import re
import sys
report = open(sys.argv[1], encoding="utf-8").read()
items = len(re.findall(r"<item>", report))
if items:
    raise SystemExit(f"ERROR: ALIGN drawing DRC reported {items} items: {sys.argv[1]}")
print("ALIGN drawing DRC: 0 items")
PY
fi
echo "Done. Results in $WORK (3_pnr/Results, and canonical *.gds/*.lef)"
