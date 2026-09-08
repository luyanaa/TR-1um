#!/usr/bin/env bash
# TR-1um ALIGN hard-macro signoff runner.
#
# This is a macro-level gate, not an MPW-frame submission gate. KLayout is the
# authoritative drawing/mask DRC and LVS implementation for this PDK. Magic is
# an optional diagnostic only because the checked-in Magic technology is not a
# qualified TR-1um signoff deck.
#
# Usage:
#   run_align_macro_signoff.sh <macro.gds> <top_cell> <circuit.sp> <report_dir> [macro.lef]
#
# Environment:
#   KLAYOUT_BIN, DRC_RUNSET, LVS_RUNSET, MDP_RUNSET, IP62_DRC_RUNSET
#   RUN_MAGIC_DRC=1 enables the optional Magic diagnostic.
set -euo pipefail

GDS="${1:?macro GDS}"
TOP="${2:?top cell}"
CIRCUIT="${3:?macro circuit netlist}"
REPORT_DIR="${4:?report directory}"
LEF="${5:-${GDS%.gds}.lef}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
KLAYOUT_BIN="${KLAYOUT_BIN:-$(command -v klayout || true)}"
DRC_RUNSET="${DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run.drc}"
LVS_RUNSET="${LVS_RUNSET:-$ROOT/libs.tech/klayout/tech/lvs/run.lvs}"
MDP_RUNSET="${MDP_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_mdp.drc}"
IP62_DRC_RUNSET="${IP62_DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_IP62.drc}"

mkdir -p "$REPORT_DIR"
abs_path() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$PWD" "$(basename "$1")"); }
GDS="$(abs_path "$GDS")"
LEF="$(abs_path "$LEF")"
CIRCUIT="$(abs_path "$CIRCUIT")"

for required in "$GDS" "$LEF" "$CIRCUIT" "$DRC_RUNSET" "$LVS_RUNSET" "$MDP_RUNSET" "$IP62_DRC_RUNSET"; do
    if [[ ! -f "$required" ]]; then
        echo "BLOCKED: missing required macro signoff input: $required" >&2
        exit 2
    fi
done
if [[ -z "$KLAYOUT_BIN" || ! -x "$KLAYOUT_BIN" ]]; then
    echo "ERROR: KLayout executable is unavailable" >&2
    exit 3
fi

python3 - "$GDS" "$TOP" "$LEF" <<'PY'
from pathlib import Path
import re
import sys

gds, top, lef = map(Path, sys.argv[1:])
top_name = str(top)
text = lef.read_text(encoding="utf-8", errors="replace")
if not re.search(rf"(?m)^\s*MACRO\s+{re.escape(top_name)}\s*$", text):
    raise SystemExit(f"ERROR: LEF has no exact MACRO {top_name} declaration: {lef}")
print(f"handoff inputs: GDS={gds} LEF={lef} TOP={top}")
PY

count_report_items() {
    python3 - "$1" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"ERROR: expected KLayout report was not created: {path}")
try:
    root = ET.parse(path).getroot()
except ET.ParseError as exc:
    raise SystemExit(f"ERROR: invalid KLayout report {path}: {exc}")
print(sum(1 for item in root.iter("item")))
PY
}

count_report_errors() {
    python3 - "$1" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
path = Path(sys.argv[1])
root = ET.parse(path).getroot()
warning_names = {"WAR06: Floating SG Detected"}
errors = []
for item in root.iter("item"):
    category = (item.findtext("category") or "").strip("'")
    if category not in warning_names:
        errors.append(category)
print(len(errors))
PY
}

run_klayout_drc() {
    local input_gds="$1" runset="$2" report="$3" label="$4"
    echo "==> $label"
    "$KLAYOUT_BIN" -b -zz -r "$runset" \
        -rd "input=$input_gds" -rd "top_cell=$TOP" -rd "report=$report" \
        2>&1 | tee "${report%.lyrdb}.log"
    local count errors
    count="$(count_report_items "$report")"
    errors="$(count_report_errors "$report")"
    echo "$label items: $count errors: $errors"
    if [[ "$errors" != 0 ]]; then
        echo "ERROR: $label failed" >&2
        return 10
    fi
    if [[ "$count" != 0 ]]; then
        echo "$label warnings: $((count - errors))"
    fi
}

run_klayout_drc "$GDS" "$DRC_RUNSET" "$REPORT_DIR/drawing_drc.lyrdb" "KLayout drawing-layer DRC"

echo "==> KLayout LVS"
"$KLAYOUT_BIN" -b -zz -r "$LVS_RUNSET" \
    -rd "input=$GDS" -rd "top_cell=$TOP" -rd "circuit=$CIRCUIT" \
    -rd "report=$REPORT_DIR/lvs.lvsdb" -rd "extracted=$REPORT_DIR/$TOP.extracted" \
    2>&1 | tee "$REPORT_DIR/lvs.log"
python3 - "$REPORT_DIR/lvs.log" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
if "Netlists don't match" in text or "ERROR : Netlists don't match" in text:
    raise SystemExit("ERROR: KLayout LVS mismatch")
if "Netlists match" not in text and "Netlists match." not in text:
    raise SystemExit("ERROR: KLayout LVS did not produce a match result")
print("KLayout LVS: match")
PY

echo "==> MDP layer generation"
MDP_GDS="$REPORT_DIR/${TOP}_mdp.gds"
"$KLAYOUT_BIN" -b -zz -r "$MDP_RUNSET" \
    -rd "input=$GDS" -rd "top_cell=$TOP" -rd "output=$MDP_GDS" \
    2>&1 | tee "$REPORT_DIR/mdp.log"
[[ -s "$MDP_GDS" ]] || { echo "ERROR: MDP output missing: $MDP_GDS" >&2; exit 12; }
run_klayout_drc "$MDP_GDS" "$IP62_DRC_RUNSET" "$REPORT_DIR/mask_drc.lyrdb" "KLayout mask-layer DRC"

if [[ "${RUN_MAGIC_DRC:-0}" == 1 ]]; then
    MAGIC_BIN="${MAGIC_BIN:-$(command -v magic || true)}"
    MAGICRC="${MAGICRC:-$ROOT/flow/pdk_root/TR-1um/libs.tech/magic/TR-1um.magicrc}"
    if [[ -z "$MAGIC_BIN" || ! -x "$MAGIC_BIN" ]]; then
        echo "ERROR: RUN_MAGIC_DRC=1 but Magic is unavailable" >&2
        exit 20
    fi
    if [[ ! -f "$MAGICRC" ]]; then
        echo "ERROR: RUN_MAGIC_DRC=1 but Magic rcfile is missing: $MAGICRC" >&2
        exit 20
    fi
    echo "==> Magic diagnostic DRC (non-authoritative)"
    MAGIC_REPORT="$REPORT_DIR/magic.drc.rpt"
    MAGIC_SCRIPT="$REPORT_DIR/magic_drc.tcl"
    cat > "$MAGIC_SCRIPT" <<EOF
crashbackups disable
locking disable
units microns
gds readonly true
gds read {$GDS}
load {$TOP}
drc euclidean on
drc style drc(full)
drc check
set f [open {$MAGIC_REPORT} w]
set result [drc listall why]
puts \$f "\$result"
close \$f
quit -noprompt
EOF
    "$MAGIC_BIN" -dnull -noconsole -rcfile "$MAGICRC" "$MAGIC_SCRIPT" \
        2>&1 | tee "$REPORT_DIR/magic.log"
    magic_report_has_errors="$(python3 - "$MAGIC_REPORT" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
print("1" if text.strip() and text.strip() not in {"{}", ""} else "0")
PY
)"
    if [[ "$magic_report_has_errors" == 1 ]]; then
        echo "ERROR: Magic diagnostic reported violations; KLayout remains the authoritative gate" >&2
        exit 21
    fi
else
    echo "Magic diagnostic: SKIPPED (basic experimental technology; not authoritative)"
fi

echo "PASS: TR-1um ALIGN macro KLayout gates completed"
