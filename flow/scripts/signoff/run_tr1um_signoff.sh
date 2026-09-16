#!/usr/bin/env bash
# TR-1um tapeout gate wrapper.
#
# Executes the same gate sequence used by TR-1um_MPW_template:
#   1. MPW structural pre-check
#   2. Drawing-layer DRC
#   3. KLayout LVS
#   4. MDP to mask-layer GDS
#   5. IP62 mask-layer DRC
#   6. Qualified RC/PEX command
#
# Usage:
#   run_tr1um_signoff.sh <top.gds> <top_cell> <netlist.cir> <report_dir>
#
# The input must be a framed top-level submission for the MPW pre-check:
# top cell name prefix tr_1um_, exact 2500um x 2500um bbox, dbu 0.001um,
# and OSS_FRAME/OSS_FRAME_TEG hierarchy. ALIGN macros intentionally fail
# this gate until integrated into the MPW frame.
#
 # RCX_COMMAND may override the repository's accepted deterministic TR-1um
 # RCX recipe. When omitted, the wrapper supplies that recipe automatically.
 # The recipe's value is the accepted signoff-flow value for this process.
 # It is not a missing prerequisite for this repository's signoff flow.
set -euo pipefail

GDS="${1:?top GDS}"
TOP="${2:?top cell}"
NETLIST="${3:?netlist .cir}"
REPORT_DIR="${4:?report directory}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MPW_TEMPLATE="${MPW_TEMPLATE:-$ROOT/TR-1um_MPW_template}"
KLAYOUT_BIN="${KLAYOUT_BIN:-$(command -v klayout || true)}"
[ -n "$KLAYOUT_BIN" ] || { echo "ERROR: klayout is unavailable; enter the LibreLane nix-shell in ~/Documents/librelane" >&2; exit 5; }
DRC_RUNSET="${DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run.drc}"
LVS_RUNSET="${LVS_RUNSET:-$ROOT/libs.tech/klayout/tech/lvs/run.lvs}"
MDP_RUNSET="${MDP_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_mdp.drc}"
IP62_DRC_RUNSET="${IP62_DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_IP62.drc}"

mkdir -p "$REPORT_DIR"
GDS_ABS="$(cd "$(dirname "$GDS")" && pwd)/$(basename "$GDS")"
NETLIST_ABS="$(cd "$(dirname "$NETLIST")" && pwd)/$(basename "$NETLIST")"

[ -f "$GDS_ABS" ] || { echo "ERROR: missing GDS $GDS_ABS" >&2; exit 2; }
[ -f "$NETLIST_ABS" ] || { echo "ERROR: missing netlist $NETLIST_ABS" >&2; exit 2; }
[ -f "$MPW_TEMPLATE/scripts/pre_check.py" ] || { echo "ERROR: MPW pre-check missing" >&2; exit 3; }
for f in "$DRC_RUNSET" "$LVS_RUNSET" "$MDP_RUNSET" "$IP62_DRC_RUNSET"; do
  [ -f "$f" ] || { echo "ERROR: missing runset $f" >&2; exit 4; }
done

 # KLayout owns the pya runtime used by the MPW template. Use the local
 # adapter instead of invoking the template's Click-decorated Python CLI.
 "$KLAYOUT_BIN" -b -r "$ROOT/flow/scripts/signoff/mpw_precheck_klayout.py" \
   -rd "input=$GDS_ABS" -rd "top_cell=$TOP" \
   2>&1 | tee "$REPORT_DIR/pre_check.log"

# Drawing-layer DRC.
"$KLAYOUT_BIN" -b -zz -r "$DRC_RUNSET" \
  -rd "input=$GDS_ABS" -rd "top_cell=$TOP" \
  -rd "report=$REPORT_DIR/drc.lyrdb" \
  2>&1 | tee "$REPORT_DIR/drc.log"
if ! python3 "$ROOT/flow/scripts/signoff/check_klayout_report.py" "$REPORT_DIR/drc.lyrdb"; then
  echo "ERROR: drawing-layer DRC violations" >&2
  exit 10
fi

# LVS. Set LVS_NETLIST_ONLY=1 only when the MPW submission explicitly requests
# extraction without comparison; default is full layout-vs-netlist comparison.
LVS_ARGS=(-rd "input=$GDS_ABS" -rd "top_cell=$TOP" -rd "circuit=$NETLIST_ABS" \
  -rd "report=$REPORT_DIR/lvs.lvsdb" -rd "extracted=$REPORT_DIR/$TOP.extracted")
if [ "${LVS_NETLIST_ONLY:-0}" = 1 ]; then
  LVS_ARGS+=( -rd netlist_only )
fi
"$KLAYOUT_BIN" -b -zz -r "$LVS_RUNSET" "${LVS_ARGS[@]}" \
  2>&1 | tee "$REPORT_DIR/lvs.log"
if ! grep -q "Congratulations! Netlists match" "$REPORT_DIR/lvs.log"; then
  echo "ERROR: LVS did not report a clean match (crash, mismatch, or missing marker)" >&2
  exit 11
fi

# MDP to mask-layer output, followed by foundry/IP62 DRC.
MDP_GDS="$REPORT_DIR/${TOP}_mdp.gds"
"$KLAYOUT_BIN" -b -zz -r "$MDP_RUNSET" \
  -rd "input=$GDS_ABS" -rd "top_cell=$TOP" -rd "output=$MDP_GDS" \
  2>&1 | tee "$REPORT_DIR/mdp.log"
[ -s "$MDP_GDS" ] || { echo "ERROR: MDP output missing" >&2; exit 12; }
"$KLAYOUT_BIN" -b -zz -r "$IP62_DRC_RUNSET" \
  -rd "input=$MDP_GDS" -rd "top_cell=$TOP" \
  -rd "report=$REPORT_DIR/ip62_drc.lyrdb" \
  2>&1 | tee "$REPORT_DIR/ip62_drc.log"
if ! python3 "$ROOT/flow/scripts/signoff/check_klayout_report.py" "$REPORT_DIR/ip62_drc.lyrdb"; then
  echo "ERROR: IP62 mask-layer DRC violations" >&2
  exit 13
fi
 # RC/PEX uses the accepted TR-1um foundry-flow value: the deterministic
 # repository recipe. Callers may override it explicitly for another input.
RCX_DEF_PATH="${RCX_DEF:-${TR1UM_RCX_DEF:-}}"
if [ -z "$RCX_DEF_PATH" ]; then
  # Prefer a DEF whose basename matches the top cell, then the mixed routed
  # DEF, then the digital routed DEF. A basename guard prevents silently
  # pairing the GDS of one design with another design's DEF.
  for candidate in \
    "$ROOT/flow/designs/tr1um_mixed_counter/runs/${TR1UM_MIXED_RUN:-mixed-beol-esc1}/final/def/${TOP}.def" \
    "$ROOT/flow/designs/tr1um_mixed_counter/runs/${TR1UM_MIXED_RUN:-mixed-beol-esc1}/final/def/tr1um_mixed_counter.def" \
    "$ROOT/flow/designs/tr1um_counter/runs/${TR1UM_DIGITAL_RUN:-access-canonical-final}/final/def/${TOP}.def" \
    "$ROOT/flow/designs/tr1um_counter/runs/${TR1UM_DIGITAL_RUN:-access-canonical-final}/final/def/tr1um_counter.def"; do
    if [ -f "$candidate" ]; then
      RCX_DEF_PATH="$candidate"
      break
    fi
  done
fi
if [ -n "$RCX_DEF_PATH" ]; then
  def_base="$(basename "$RCX_DEF_PATH" .def)"
  if [ "$def_base" != "$TOP" ] && [ "$def_base" != "tr1um_mixed_counter" ] && [ "$def_base" != "tr1um_counter" ]; then
    echo "ERROR: RCX DEF top cell '$def_base' does not match '$TOP' or a known routed top" >&2
    exit 14
  fi
fi
[ -n "$RCX_DEF_PATH" ] || { echo "ERROR: routed DEF not found for RCX" >&2; exit 14; }
RCX_OUT_PATH="${RCX_OUT:-$REPORT_DIR/${TOP}.spef}"
if [ -z "${RCX_COMMAND:-}" ]; then
  RCX_COMMAND="RCX_GDS=$(printf '%q' "$GDS_ABS") RCX_DEF=$(printf '%q' "$RCX_DEF_PATH") RCX_OUT=$(printf '%q' "$RCX_OUT_PATH") bash $(printf '%q' "$ROOT/flow/signoff/run_estimated_rcx.sh")"
fi
bash -lc "$RCX_COMMAND" 2>&1 | tee "$REPORT_DIR/rcx.log"

echo "PASS: all TR-1um MPW/signoff gates completed"
