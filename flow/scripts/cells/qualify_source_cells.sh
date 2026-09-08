#!/usr/bin/env bash
# Qualify every immutable source digital cell under the native TR-1um DRC.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DUTY="$ROOT/STDLIB/LogicCells/gds"
DRC="$ROOT/libs.tech/klayout/tech/drc/run.drc"
OUT="${TR1UM_DRC_OUT:-$ROOT/flow/qualification/source_cell_drc}"
mkdir -p "$OUT"
for gds in "$DUTY"/*.gds; do
  name="$(basename "$gds" .gds)"
  case "$name" in RS|RR\$1|TOP) continue ;; esac
  klayout -b -r "$DRC" -rd "input=$gds" -rd "report=$OUT/$name.lyrdb"
done
python3 - "$OUT" <<'PY'
from pathlib import Path
import collections, sys, xml.etree.ElementTree as ET
out=Path(sys.argv[1]); bad={}
for p in sorted(out.glob('*.lyrdb')):
    counts=collections.Counter((item.findtext('category') or '').strip("'") for item in ET.parse(p).getroot().iter('item'))
    if sum(counts.values()): bad[p.stem]=counts
if bad:
    print('source-cell DRC failures:',bad)
    raise SystemExit(1)
print(f'source-cell native DRC PASS: {len(list(out.glob("*.lyrdb")))} cells, zero items')
PY

# The per-cell gate above is the authoritative source-cell check. Top-level
# routed DRC is intentionally run by the LibreLane artifact-specific gate.

# The native source extracted netlists use `M$` device names; KLayout netlist
# extraction uses `XM$` names. Compare device count after normalizing names.
