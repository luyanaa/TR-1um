#!/usr/bin/env bash
# Deterministic TR-1um RC/PEX estimate: GDS device extraction plus
# DEF/GDS-derived distributed SPEF, RC, and merged post-layout SPICE.
#
# The physical hierarchy is extracted from the final GDS with the active
# KLayout LVS runset.  The routed DEF/GDS geometry then supplies the distributed
# engineering RC graph.  When the extracted physical names are not already the
# routed logical names, RCX_REFERENCE_NETLIST or RCX_NET_MAP supplies the
# explicit LVS mapping; the merge manifest records every unresolved boundary.
#
# Outputs beside RCX_OUT:
#   <base>.spef              distributed digital timing parasitics
#   <base>.pex.sp            compatibility alias for the RC sidecar
#   <base>.interconnect.sp   distributed tr1um_parasitics subcircuit
#   <base>.parasitics.json   geometry/ownership/topology ledger
#
#   <base>.extracted         KLayout device hierarchy (when auto-extracted)
#   <base>.extraction.log    KLayout extraction log
#   <base>.devices.sp        rewritten device hierarchy
#   <base>.devices.json     device-terminal mapping ledger
#   <base>.postlayout.sp     merged device plus distributed RC SPICE
#   <base>.pex_manifest.json merge ownership and qualification manifest
#
# Every non-compact-model term is explicitly labelled as an engineering
# estimate.  No output is a foundry-qualified RC/PEX deck.
set -euo pipefail
: "${RCX_GDS:?RCX_GDS must point to final GDS}"
: "${RCX_DEF:?RCX_DEF must point to routed DEF}"
: "${RCX_OUT:?RCX_OUT must point to output SPEF}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
export PDK_ROOT="${PDK_ROOT:-$ROOT/pdk_root}"
export PDK="${PDK:-TR-1um}"
RCX_BASE="${RCX_OUT%.spef}"
RCX_RC_OUT="${RCX_RC_OUT:-$ROOT/pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json}"
RCX_MODEL="${RCX_MODEL:-$ROOT/scripts/analysis/tr1um_parasitic_model.json}"
RCX_SPICE_OUT="${RCX_SPICE_OUT:-$RCX_BASE.pex.sp}"
RCX_INTERCONNECT_OUT="${RCX_INTERCONNECT_OUT:-$RCX_BASE.interconnect.sp}"
RCX_JSON_OUT="${RCX_JSON_OUT:-$RCX_BASE.parasitics.json}"
RCX_EXTRACTED_OUT="${RCX_EXTRACTED_OUT:-$RCX_BASE.extracted}"
RCX_DEVICES_OUT="${RCX_DEVICES_OUT:-$RCX_BASE.devices.sp}"
RCX_DEVICES_JSON_OUT="${RCX_DEVICES_JSON_OUT:-$RCX_BASE.devices.json}"
RCX_POSTLAYOUT_OUT="${RCX_POSTLAYOUT_OUT:-$RCX_BASE.postlayout.sp}"
RCX_MANIFEST_OUT="${RCX_MANIFEST_OUT:-$RCX_BASE.pex_manifest.json}"
RCX_EXTRACT_REPORT="${RCX_EXTRACT_REPORT:-$RCX_BASE.extraction.lvsdb}"
RCX_EXTRACT_LOG="${RCX_EXTRACT_LOG:-$RCX_BASE.extraction.log}"
RCX_SUBSTRATE_NET="${RCX_SUBSTRATE_NET:-VSS}"
RCX_WELL_NET="${RCX_WELL_NET:-VDD}"
RCX_MERGE_POSTLAYOUT="${RCX_MERGE_POSTLAYOUT:-1}"
RCX_AUTO_EXTRACT="${RCX_AUTO_EXTRACT:-1}"
RCX_ALLOW_PARTIAL_MERGE="${RCX_ALLOW_PARTIAL_MERGE:-0}"
RCX_MODEL_MANIFEST="${RCX_MODEL_MANIFEST:-$REPO_ROOT/libs.tech/spice/models/ip62_models_calibrated}"
RCX_LVS_RUNSET="${RCX_LVS_RUNSET:-$REPO_ROOT/libs.tech/klayout/tech/lvs/run.lvs}"
mkdir -p "$(dirname "$RCX_RC_OUT")" "$(dirname "$RCX_OUT")" "$(dirname "$RCX_SPICE_OUT")" \
  "$(dirname "$RCX_INTERCONNECT_OUT")" "$(dirname "$RCX_JSON_OUT")" "$(dirname "$RCX_EXTRACTED_OUT")" \
  "$(dirname "$RCX_DEVICES_OUT")" "$(dirname "$RCX_DEVICES_JSON_OUT")" "$(dirname "$RCX_POSTLAYOUT_OUT")" \
  "$(dirname "$RCX_MANIFEST_OUT")" "$(dirname "$RCX_EXTRACT_REPORT")" "$(dirname "$RCX_EXTRACT_LOG")"
[ -f "$RCX_GDS" ] || { echo "ERROR: missing RCX GDS $RCX_GDS" >&2; exit 2; }
[ -f "$RCX_DEF" ] || { echo "ERROR: missing RCX DEF $RCX_DEF" >&2; exit 2; }
[ -f "$RCX_MODEL" ] || { echo "ERROR: missing parasitic model $RCX_MODEL" >&2; exit 2; }
[ -f "$RCX_LVS_RUNSET" ] || { echo "ERROR: missing KLayout LVS runset $RCX_LVS_RUNSET" >&2; exit 2; }

if [ -z "${RCX_TOP:-}" ]; then
  RCX_TOP="$(python3 -c 'import re,sys; text=open(sys.argv[1], encoding=\"utf-8\", errors=\"replace\").read(); match=re.search(r\"^DESIGN\\s+(\\S+)\\s*;\", text, re.M); print(match.group(1) if match else \"\")' "$RCX_DEF")"
fi
[ -n "${RCX_TOP:-}" ] || { echo "ERROR: RCX_TOP is empty and DEF has no DESIGN header" >&2; exit 2; }

echo "RCX estimate: GDS=$RCX_GDS DEF=$RCX_DEF TOP=$RCX_TOP OUT=$RCX_OUT"
cp "$RCX_DEF" "$RCX_BASE.def"

# A supplied extracted view is preferred.  Otherwise the active KLayout LVS
# deck performs the GDS-first netlist-only device extraction here.
if [ -z "${RCX_EXTRACTED:-}" ] && [ "$RCX_MERGE_POSTLAYOUT" != 0 ] && [ "$RCX_AUTO_EXTRACT" != 0 ]; then
  RCX_KLAYOUT_BIN="${RCX_KLAYOUT_BIN:-${KLAYOUT_BIN:-$(command -v klayout || true)}}"
  [ -n "$RCX_KLAYOUT_BIN" ] || {
    echo "ERROR: KLayout is required for GDS-first device extraction; set RCX_EXTRACTED, RCX_KLAYOUT_BIN, or RCX_AUTO_EXTRACT=0 for SPEF-only mode" >&2
    exit 3
  }
  echo "RCX device extraction: $RCX_KLAYOUT_BIN"
  "$RCX_KLAYOUT_BIN" -b -zz -r "$RCX_LVS_RUNSET" \
    -rd "input=$RCX_GDS" -rd "top_cell=$RCX_TOP" -rd "netlist_only=true" \
    -rd "extracted=$RCX_EXTRACTED_OUT" -rd "report=$RCX_EXTRACT_REPORT" \
    2>&1 | tee "$RCX_EXTRACT_LOG"
  RCX_EXTRACTED="$RCX_EXTRACTED_OUT"
fi

python3 "$ROOT/scripts/analysis/estimate_tr1um_rc.py" --out "$RCX_RC_OUT"

extract_args=(
  python3 "$ROOT/scripts/analysis/extract_tr1um_parasitics.py"
  --def "$RCX_DEF"
  --gds "$RCX_GDS"
  --rc "$RCX_RC_OUT"
  --model "$RCX_MODEL"
  --substrate-net "$RCX_SUBSTRATE_NET"
  --well-net "$RCX_WELL_NET"
  --top "$RCX_TOP"
  --spef "$RCX_OUT"
  --spice "$RCX_INTERCONNECT_OUT"
  --json "$RCX_JSON_OUT"
)
if [ -n "${RCX_EXTRACTED:-}" ]; then
  [ -f "$RCX_EXTRACTED" ] || { echo "ERROR: missing extracted SPICE $RCX_EXTRACTED" >&2; exit 2; }
  extract_args+=(--extracted "$RCX_EXTRACTED")
fi
if [ "${RCX_INCLUDE_DEVICE_CAPS:-1}" = 0 ]; then
  extract_args+=(--no-device-caps)
fi
"${extract_args[@]}"
cp "$RCX_INTERCONNECT_OUT" "$RCX_SPICE_OUT"

if [ "$RCX_MERGE_POSTLAYOUT" != 0 ]; then
  [ -n "${RCX_EXTRACTED:-}" ] || {
    echo "ERROR: merged post-layout SPICE requires a KLayout extracted view; set RCX_EXTRACTED or RCX_AUTO_EXTRACT=1" >&2
    exit 4
  }
  merge_args=(
    python3 "$ROOT/scripts/analysis/build_postlayout_spice.py"
    --extracted "$RCX_EXTRACTED"
    --interconnect "$RCX_INTERCONNECT_OUT"
    --parasitics "$RCX_JSON_OUT"
    --top "$RCX_TOP"
    --gds "$RCX_GDS"
    --def "$RCX_DEF"
    --output "$RCX_POSTLAYOUT_OUT"
    --devices-out "$RCX_DEVICES_OUT"
    --devices-json "$RCX_DEVICES_JSON_OUT"
    --manifest "$RCX_MANIFEST_OUT"
  )
  if [ -f "$RCX_MODEL_MANIFEST" ]; then
    merge_args+=(--model-manifest "$RCX_MODEL_MANIFEST")
  elif [ -n "${RCX_MODEL_MANIFEST:-}" ]; then
    echo "WARNING: compact-model manifest not found; merged deck will not include one: $RCX_MODEL_MANIFEST" >&2
  fi
  if [ -n "${RCX_REFERENCE_NETLIST:-}" ]; then
    [ -f "$RCX_REFERENCE_NETLIST" ] || { echo "ERROR: missing RCX_REFERENCE_NETLIST $RCX_REFERENCE_NETLIST" >&2; exit 2; }
    merge_args+=(--reference-netlist "$RCX_REFERENCE_NETLIST")
  fi
  if [ -n "${RCX_REFERENCE_TOP:-}" ]; then
    merge_args+=(--reference-top "$RCX_REFERENCE_TOP")
  fi
  if [ "${RCX_COMPLETE_REFERENCE_PORTS:-0}" != 0 ]; then
    merge_args+=(--complete-reference-ports)
  fi
  if [ -n "${RCX_NET_MAP:-}" ]; then
    [ -f "$RCX_NET_MAP" ] || { echo "ERROR: missing RCX_NET_MAP $RCX_NET_MAP" >&2; exit 2; }
    merge_args+=(--net-map "$RCX_NET_MAP")
  fi
  if [ "$RCX_ALLOW_PARTIAL_MERGE" != 0 ]; then
    merge_args+=(--allow-partial)
  fi
  "${merge_args[@]}"
else
  echo "RCX post-layout merge disabled; SPEF, interconnect, and ledger outputs remain available"
fi

echo "RCX estimate complete (engineering estimate, not foundry-qualified)"
