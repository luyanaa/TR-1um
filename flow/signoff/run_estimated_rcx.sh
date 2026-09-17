#!/usr/bin/env bash
# Deterministic TR-1um RC/PEX estimate: DEF/GDS-derived distributed SPEF and RC.
#
# A real foundry RC/PEX deck is unavailable for TR-1um (the open IP62 manual
# lists parasitic extraction as unavailable).  The companion extractor now
# materializes:
#   * width-aware wire-to-substrate capacitance and distributed resistance
#     from DEF/LEF geometry;
#   * explicit V1 resistor edges and DEF/LEF *CONN terminal records;
#   * lateral M1/M1 and M2/M2 fringe coupling plus DEF M1/M2 overlap coupling;
#   * M3-to-M2/M1 vertical overlap when M3 geometry is available;
#   * GR/F_RS, RR/F_RR, and GC/MOS device capacitance when an extracted SPICE
#     view is supplied; unresolved nested devices remain ledger-only.
# Set RCX_INCLUDE_DEVICE_CAPS=0 to leave compact-model/device terms out of the
# materialized network while retaining them in the JSON ledger.
#
# Every non-compact-model term is explicitly labelled as an engineering
# estimate.  The output SPEF is not foundry-qualified extraction.
set -euo pipefail
: "${RCX_GDS:?RCX_GDS must point to framed GDS}"
: "${RCX_DEF:?RCX_DEF must point to routed DEF}"
: "${RCX_OUT:?RCX_OUT must point to output SPEF}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PDK_ROOT="${PDK_ROOT:-$ROOT/pdk_root}"
export PDK="${PDK:-TR-1um}"
RCX_RC_OUT="${RCX_RC_OUT:-$ROOT/pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json}"
RCX_MODEL="${RCX_MODEL:-$ROOT/scripts/analysis/tr1um_parasitic_model.json}"
RCX_SPICE_OUT="${RCX_SPICE_OUT:-${RCX_OUT%.spef}.pex.sp}"
RCX_JSON_OUT="${RCX_JSON_OUT:-${RCX_OUT%.spef}.parasitics.json}"
RCX_SUBSTRATE_NET="${RCX_SUBSTRATE_NET:-VSS}"
RCX_WELL_NET="${RCX_WELL_NET:-VDD}"
mkdir -p "$(dirname "$RCX_OUT")" "$(dirname "$RCX_SPICE_OUT")" "$(dirname "$RCX_JSON_OUT")"
[ -f "$RCX_GDS" ] || { echo "ERROR: missing RCX GDS $RCX_GDS" >&2; exit 2; }
[ -f "$RCX_DEF" ] || { echo "ERROR: missing RCX DEF $RCX_DEF" >&2; exit 2; }
[ -f "$RCX_MODEL" ] || { echo "ERROR: missing parasitic model $RCX_MODEL" >&2; exit 2; }

echo "RCX estimate: GDS=$RCX_GDS DEF=$RCX_DEF OUT=$RCX_OUT"
cp "$RCX_DEF" "${RCX_OUT%.spef}.def"

python3 "$ROOT/scripts/analysis/estimate_tr1um_rc.py" --out "$RCX_RC_OUT"

extract_args=(
  python3 "$ROOT/scripts/analysis/extract_tr1um_parasitics.py"
  --def "$RCX_DEF"
  --rc "$RCX_RC_OUT"
  --model "$RCX_MODEL"
  --substrate-net "$RCX_SUBSTRATE_NET"
  --well-net "$RCX_WELL_NET"
  --spef "$RCX_OUT"
  --spice "$RCX_SPICE_OUT"
  --json "$RCX_JSON_OUT"
)
if [ -n "${RCX_GDS:-}" ]; then
  extract_args+=(--gds "$RCX_GDS")
fi
if [ -n "${RCX_EXTRACTED:-}" ]; then
  [ -f "$RCX_EXTRACTED" ] || { echo "ERROR: missing extracted SPICE $RCX_EXTRACTED" >&2; exit 2; }
  extract_args+=(--extracted "$RCX_EXTRACTED")
fi
if [ "${RCX_INCLUDE_DEVICE_CAPS:-1}" = 0 ]; then
  extract_args+=(--no-device-caps)
fi
if [ -n "${RCX_TOP:-}" ]; then
  extract_args+=(--top "$RCX_TOP")
fi
"${extract_args[@]}"
echo "RCX estimate complete (engineering estimate, not foundry-qualified)"
