#!/usr/bin/env bash
# Deterministic TR-1um RC/PEX estimate: DEF-derived SPEF + layer RC JSON.
#
# A real foundry RC/PEX deck is unavailable for TR-1um (the open IP62 manual
# lists parasitic extraction as unavailable). This recipe therefore:
#   1. writes a real SPEF whose per-net capacitance/resistance comes from the
#      routed DEF geometry (wire lengths per layer, via counts) and the
#      documented per-layer R/C estimates, and
#   2. regenerates the per-layer RC table used by OpenROAD.
#
# The SPEF is a layout-derived engineering estimate, NOT foundry-qualified
# extraction; the JSON labels this explicitly.
set -euo pipefail
: "${RCX_GDS:?RCX_GDS must point to framed GDS}"
: "${RCX_DEF:?RCX_DEF must point to routed DEF}"
: "${RCX_OUT:?RCX_OUT must point to output SPEF}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PDK_ROOT="${PDK_ROOT:-$ROOT/pdk_root}"
export PDK="${PDK:-TR-1um}"
mkdir -p "$(dirname "$RCX_OUT")"

echo "RCX estimate: GDS=$RCX_GDS DEF=$RCX_DEF OUT=$RCX_OUT"
cp "$RCX_DEF" "${RCX_OUT%.spef}.def"

python3 "$ROOT/scripts/analysis/estimate_tr1um_rc.py" --out "$ROOT/pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json"

python3 - "$RCX_DEF" "$RCX_OUT" "$ROOT/pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json" <<'PY'
import json
import re
import sys
from pathlib import Path

def_path, spef_path, rc_path = sys.argv[1], sys.argv[2], sys.argv[3]
rc = json.loads(Path(rc_path).read_text())
layers = {l["layer"]: l for l in rc["layers"]}
via_r = rc["via"]["nominal_resistance_ohm"]

text = Path(def_path).read_text()
dbu = int(re.search(r"^UNITS DISTANCE MICRONS (\d+) ;", text, re.M).group(1))

# Special nets (power) -> estimate from total wire length too, but keep them.
net_blocks = re.findall(r"^- (\S+) \+ NET \S+(.*?) ;", text, re.M | re.S)
routing = {}
for m in re.finditer(r"^(?:NEW|-) .*$", text, re.M):
    pass

# Parse ROUTED/NEW statements in the NETS section: net -> {layer: length_um}
# and {via: count}. Coordinates are DEF database units; via entries appear as
# "( x y 0 )" extension integers or explicit via names like M1M2_V1.
in_nets = False
current_net = None
segments = {}
for line in text.splitlines():
    if line.startswith("NETS "):
        in_nets = True
        continue
    if line.startswith("END NETS"):
        in_nets = False
        current_net = None
        continue
    if not in_nets:
        continue
    net_m = re.match(r"^\s*- (\S+) ", line)
    if net_m:
        current_net = net_m.group(1)
    if current_net is None:
        continue
    for rm in re.finditer(r"(?:ROUTED|NEW)\s+(M\d)\b([^;]*)", line):
        layer = rm.group(1)
        body = rm.group(2)
        coords = []
        for cm in re.finditer(r"\(\s*([^)]*)\)", body):
            fields = cm.group(1).split()
            if len(fields) >= 2:
                fx, fy = fields[0], fields[1]
                ext = fields[2] if len(fields) >= 3 else ""
                x = None if fx == "*" else float(fx)
                y = None if fy == "*" else float(fy)
                coords.append((x, y, ext))
        prev = None
        for x, y, via_ext in coords:
            if x is None and prev is not None:
                x = prev[0]
            if y is None and prev is not None:
                y = prev[1]
            if x is None or y is None:
                continue
            point = (x / dbu, y / dbu)
            if prev is not None:
                length = abs(point[0] - prev[0]) + abs(point[1] - prev[1])
                if length > 0:
                    seg = segments.setdefault(current_net, {})
                    seg[layer] = seg.get(layer, 0.0) + length
            if via_ext:
                via_layer = "V" + layer[1]
                seg = segments.setdefault(current_net, {})
                seg[via_layer] = seg.get(via_layer, 0.0) + 1.0
            prev = point
        for via_name in re.findall(r"\b(M\dM\d_\S+)\b", body):
            m = re.match(r"M(\d)M(\d)", via_name)
            if m:
                via_layer = "V" + m.group(1)
                seg = segments.setdefault(current_net, {})
                seg[via_layer] = seg.get(via_layer, 0.0) + 1.0

# Net connection count (for *D_NET pin list we just emit the net name).
conn_blocks = re.findall(r"^- (\S+) \+ NET.*?;", text, re.M | re.S)

now = "2026-00-00T00:00:00"
out = []
out.append("*SPEF \"IEEE 1481-1998\"")
out.append("*DESIGN \"tr1um\"")
out.append("*DATE \"2026-01-01T00:00:00\"")
out.append("*VENDOR \"TR-1um flow\"")
out.append("*PROGRAM \"run_estimated_rcx\"")
out.append("*VERSION \"1.0\"")
out.append("*DESIGN_FLOW \"PIN_CAP NONE\" \"NAME_SCOPE LOCAL\"")
out.append("*DIVIDER /")
out.append("*DELIMITER :")
out.append("*BUS_DELIMITER [ ]")
out.append("*T_UNIT 1 NS")
out.append("*C_UNIT 1 PF")
out.append("*R_UNIT 1 OHM")
out.append("*L_UNIT 1 HENRY")
out.append("")
total_nets = 0
for net, per_layer in sorted(segments.items()):
    cap = 0.0
    res = 0.0
    parts = []
    for name, value in sorted(per_layer.items()):
        if name.startswith("V"):
            res += value * via_r
            parts.append(f"{name}:{int(value)} vias")
        else:
            if name not in layers:
                continue
            l = layers[name]
            cap += value * l["capacitance_pf_per_um"]
            res += value * l["resistance_ohm_per_um"]
            parts.append(f"{name}:{value:.3f} um")
    if not per_layer:
        continue
    total_nets += 1
    out.append(f"*D_NET {net} {cap:.6e}")
    out.append("*CONN")
    out.append("*END")
    out.append(f"*CAP 1 {net} {cap:.6e}")
    out.append(f"*RES 1 {net} {net} {res:.6e}")
    out.append("*END")
    out.append(f"*# estimate from: {'; '.join(parts)}")
    out.append("")
out.append(f"*# NETS {total_nets}")
out.append("*# STATUS engineering_estimate_not_foundry_qualified")
Path(spef_path).write_text("\n".join(out) + "\n")
print(f"wrote SPEF with {total_nets} nets")
PY
echo "RCX estimate complete (engineering estimate, not foundry-qualified)"
