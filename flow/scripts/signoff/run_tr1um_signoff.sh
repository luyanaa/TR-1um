#!/usr/bin/env bash
# TR-1um tapeout gate wrapper.
#
#   1. Drawing-DRC and LVS source/manual/runset parity
#   2. MPW structural pre-check
#   3. Drawing-layer DRC
#   4. Netlist-label and (manifest-backed) ERC electrical gates
#   5. KLayout LVS
#   6. MDP to mask-layer GDS
#   7. IP62 mask-layer DRC
#   8. Engineering RC/PEX command (or explicit qualified override)
#
# The parity gates fail closed for malformed manifests, unreadable inputs, or
# active source/runset structure mismatches.
# Manufacturer-rule gaps are emitted as TODOs/warnings and do not stop
# the physical flow.
# The default RCX recipe is transparent and not foundry-qualified.
#
# Usage:
#   run_tr1um_signoff.sh <top.gds> <top_cell> <netlist.cir> <report_dir> [signoff_manifest]
#
# When a signoff manifest is supplied, its fail-closed analog release gate is
# evaluated after the physical evidence stages. Without one, this wrapper
# retains its structural-evidence mode for reproducible intermediate runs.
# `ERC_CONTRACT` (or `ANALOG_ERC_CONTRACT`) is required for manifest-backed
# signoff; the physical electrical DRC and label gate are always run.
# `ELECTRICAL_LIMITS_CONTRACT` can override the default central contract.
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
SIGNOFF_MANIFEST="${5:-${ANALOG_SIGNOFF_MANIFEST:-}}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
ANALOG_MANIFEST_CHECKER="$ROOT/flow/scripts/signoff/check_analog_signoff_manifest.py"
DRC_RULE_PARITY_CHECKER="$ROOT/flow/scripts/signoff/check_drc_rule_parity.py"
LVS_SOURCE_PARITY_CHECKER="$ROOT/flow/scripts/signoff/check_lvs_source_parity.py"
NETLIST_LABEL_CHECKER="$ROOT/flow/scripts/signoff/check_netlist_labels.py"
ANALOG_ERC_CHECKER="$ROOT/flow/scripts/signoff/check_analog_erc.py"
ERC_CONTRACT="${ERC_CONTRACT:-${ANALOG_ERC_CONTRACT:-}}"
ELECTRICAL_LIMITS_CONTRACT="${ELECTRICAL_LIMITS_CONTRACT:-$ROOT/flow/qualification/tr1um_electrical_limits.json}"
MPW_TEMPLATE="${MPW_TEMPLATE:-$ROOT/TR-1um_MPW_template}"
KLAYOUT_BIN="${KLAYOUT_BIN:-$(command -v klayout || true)}"
[ -n "$KLAYOUT_BIN" ] || { echo "ERROR: klayout is unavailable; enter the LibreLane nix-shell in ~/Documents/librelane" >&2; exit 5; }
DRC_RUNSET="${DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run.drc}"
DRC_RULE_PARITY_MANIFEST="${DRC_RULE_PARITY_MANIFEST:-$ROOT/flow/qualification/drc_rule_parity.json}"
LVS_SOURCE_PARITY_MANIFEST="${LVS_SOURCE_PARITY_MANIFEST:-$ROOT/flow/qualification/lvs_source_parity.json}"
LVS_RUNSET="${LVS_RUNSET:-$ROOT/libs.tech/klayout/tech/lvs/run.lvs}"
MDP_RUNSET="${MDP_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_mdp.drc}"
IP62_DRC_RUNSET="${IP62_DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_IP62.drc}"

mkdir -p "$REPORT_DIR"
GDS_ABS="$(cd "$(dirname "$GDS")" && pwd)/$(basename "$GDS")"
SIGNOFF_MANIFEST_ABS=""
if [ -n "$SIGNOFF_MANIFEST" ]; then
  [ -f "$SIGNOFF_MANIFEST" ] || { echo "ERROR: missing signoff manifest $SIGNOFF_MANIFEST" >&2; exit 3; }
  SIGNOFF_MANIFEST_ABS="$(cd "$(dirname "$SIGNOFF_MANIFEST")" && pwd)/$(basename "$SIGNOFF_MANIFEST")"
  [ -f "$ANALOG_MANIFEST_CHECKER" ] || { echo "ERROR: analog manifest checker missing" >&2; exit 3; }
fi
if [ -n "$SIGNOFF_MANIFEST" ] && [ -z "$ERC_CONTRACT" ]; then
  echo "ERROR: manifest-backed signoff requires ERC_CONTRACT or ANALOG_ERC_CONTRACT" >&2
  exit 11
fi
NETLIST_ABS="$(cd "$(dirname "$NETLIST")" && pwd)/$(basename "$NETLIST")"

[ -f "$GDS_ABS" ] || { echo "ERROR: missing GDS $GDS_ABS" >&2; exit 2; }
[ -f "$NETLIST_ABS" ] || { echo "ERROR: missing netlist $NETLIST_ABS" >&2; exit 2; }
[ -f "$MPW_TEMPLATE/scripts/pre_check.py" ] || { echo "ERROR: MPW pre-check missing" >&2; exit 3; }
for f in "$DRC_RUNSET" "$LVS_RUNSET" "$MDP_RUNSET" "$IP62_DRC_RUNSET"; do
  [ -f "$f" ] || { echo "ERROR: missing runset $f" >&2; exit 4; }
done
[ -f "$DRC_RULE_PARITY_CHECKER" ] || { echo "ERROR: DRC rule parity checker missing" >&2; exit 3; }
[ -f "$DRC_RULE_PARITY_MANIFEST" ] || { echo "ERROR: DRC rule parity manifest missing $DRC_RULE_PARITY_MANIFEST" >&2; exit 3; }
[ -f "$LVS_SOURCE_PARITY_CHECKER" ] || { echo "ERROR: LVS source parity checker missing" >&2; exit 3; }
[ -f "$LVS_SOURCE_PARITY_MANIFEST" ] || { echo "ERROR: LVS source parity manifest missing $LVS_SOURCE_PARITY_MANIFEST" >&2; exit 3; }
if ! python3 "$LVS_SOURCE_PARITY_CHECKER" \
  --manifest "$LVS_SOURCE_PARITY_MANIFEST" --runset "$LVS_RUNSET" \
  --output "$REPORT_DIR/lvs_source_parity.json"; then
  echo "ERROR: LVS source/manual/runset parity manifest is invalid" >&2
  exit 9
fi
if ! python3 "$DRC_RULE_PARITY_CHECKER" \
  --manifest "$DRC_RULE_PARITY_MANIFEST" --runset "$DRC_RUNSET" \
  --output "$REPORT_DIR/drc_rule_parity.json"; then
  echo "ERROR: drawing-DRC source/output parity manifest is invalid" >&2
  exit 9
fi

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

# Netlist-aware electrical label gate.  The DRC ruleset consumes the same
# labels, while this check compares their names and anchors with the netlist.
LABEL_POLICY_ARGS=()
if [ -n "$ERC_CONTRACT" ]; then
  [ -f "$ERC_CONTRACT" ] || { echo "ERROR: missing ERC contract $ERC_CONTRACT" >&2; exit 11; }
  LABEL_POLICY_ARGS+=( --erc-contract "$ERC_CONTRACT" )
fi
python3 "$NETLIST_LABEL_CHECKER" \
  --layout "$GDS_ABS" --top-cell "$TOP" --netlist "$NETLIST_ABS" \
  "${LABEL_POLICY_ARGS[@]}" \
  --output "$REPORT_DIR/netlist_labels.json"
if [ -n "$ERC_CONTRACT" ]; then
  [ -f "$ERC_CONTRACT" ] || { echo "ERROR: missing ERC contract $ERC_CONTRACT" >&2; exit 11; }
  [ -f "$ANALOG_ERC_CHECKER" ] || { echo "ERROR: analog ERC checker missing" >&2; exit 11; }
  [ -f "$ELECTRICAL_LIMITS_CONTRACT" ] || {
    echo "ERROR: electrical limits contract missing $ELECTRICAL_LIMITS_CONTRACT" >&2
    exit 11
  }
  python3 "$ANALOG_ERC_CHECKER" \
    --contract "$ERC_CONTRACT" \
    --report "$REPORT_DIR/drc.lyrdb" \
    --ruleset "$DRC_RUNSET" \
    --electrical-ruleset "$ROOT/libs.tech/klayout/tech/drc/03_Electrical.drc" \
    --limits-contract "$ELECTRICAL_LIMITS_CONTRACT" \
    --label-report "$REPORT_DIR/netlist_labels.json" \
    --output "$REPORT_DIR/erc.json"
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
python3 - "$REPORT_DIR/lvs.log" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
if "Congratulations! Netlists match" not in text:
    raise SystemExit("ERROR: LVS did not report a clean match (crash, mismatch, or missing marker)")
PY

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
# RC/PEX uses the accepted TR-1um engineering-flow value: the deterministic
# repository recipe. Callers may override it explicitly for another input.
RCX_DEF_PATH="${RCX_DEF:-${TR1UM_RCX_DEF:-}}"
if [ "$TOP" = "tr_1um_mixed_counter" ] && [ -z "$RCX_DEF_PATH" ]; then
  echo "ERROR: mixed-signal signoff requires RCX_DEF for the exact routed revision" >&2
  exit 14
fi
if [ -z "$RCX_DEF_PATH" ]; then
  # Digital fallback only. A mixed framed GDS must provide its matching DEF
  # explicitly because same-name routed runs can differ.
  for candidate in \
    "$ROOT/flow/designs/tr1um_counter/runs/${TR1UM_DIGITAL_RUN:-access-canonical-final}/final/def/${TOP}.def" \
    "$ROOT/flow/designs/tr1um_counter/runs/${TR1UM_DIGITAL_RUN:-access-canonical-final}/final/def/tr1um_counter.def"; do
    if [ -f "$candidate" ]; then
      RCX_DEF_PATH="$candidate"
      break
    fi
  done
fi
if [ -n "$RCX_DEF_PATH" ]; then
  [ -f "$RCX_DEF_PATH" ] || { echo "ERROR: missing RCX DEF $RCX_DEF_PATH" >&2; exit 14; }
  def_base="$(basename "$RCX_DEF_PATH" .def)"
  expected_def_base="tr${TOP#tr_}"
  if [ "$def_base" != "$TOP" ] && [ "$def_base" != "$expected_def_base" ]; then
    echo "ERROR: RCX DEF basename '$def_base' does not match top cell '$TOP' or canonical route basename '$expected_def_base'" >&2
    exit 14
  fi
fi
[ -n "$RCX_DEF_PATH" ] || { echo "ERROR: routed DEF not found for RCX" >&2; exit 14; }
RCX_OUT_PATH="${RCX_OUT:-$REPORT_DIR/${TOP}.spef}"
RCX_DEFAULT_COMMAND=0
if [ -z "${RCX_COMMAND:-}" ]; then
  RCX_DEFAULT_COMMAND=1
  RCX_EXTRACTED_ENV=""
  if [ -f "$REPORT_DIR/$TOP.extracted" ]; then
    RCX_EXTRACTED_ENV=" RCX_EXTRACTED=$(printf '%q' "$REPORT_DIR/$TOP.extracted")"
  fi
  RCX_COMMAND="RCX_GDS=$(printf '%q' "$GDS_ABS") RCX_DEF=$(printf '%q' "$RCX_DEF_PATH") RCX_OUT=$(printf '%q' "$RCX_OUT_PATH") RCX_TOP=$(printf '%q' "$TOP")${RCX_EXTRACTED_ENV} bash $(printf '%q' "$ROOT/flow/signoff/run_estimated_rcx.sh")"
fi
bash -lc "$RCX_COMMAND" 2>&1 | tee "$REPORT_DIR/rcx.log"
[ -s "$RCX_OUT_PATH" ] || { echo "ERROR: RCX SPEF missing or empty: $RCX_OUT_PATH" >&2; exit 14; }
if [ "$RCX_DEFAULT_COMMAND" = 1 ]; then
  RCX_BASE="${RCX_OUT_PATH%.spef}"
  [ -s "${RCX_BASE}.parasitics.json" ] || { echo "ERROR: RCX parasitic ledger missing or empty: ${RCX_BASE}.parasitics.json" >&2; exit 14; }
  [ -s "${RCX_BASE}.pex.sp" ] || { echo "ERROR: RCX capacitor network missing or empty: ${RCX_BASE}.pex.sp" >&2; exit 14; }
fi
if [ -n "$SIGNOFF_MANIFEST_ABS" ]; then
  echo "==> Analog signoff manifest"
  if ! python3 "$ANALOG_MANIFEST_CHECKER" \
    --manifest "$SIGNOFF_MANIFEST_ABS" --mode signoff \
    --output "$REPORT_DIR/analog_signoff_manifest.json"; then
    echo "ERROR: analog signoff manifest is incomplete or invalid" >&2
    exit 15
  fi
fi

echo "PASS: all TR-1um MPW/signoff gates completed"
