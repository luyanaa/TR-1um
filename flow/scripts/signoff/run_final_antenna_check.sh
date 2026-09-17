#!/usr/bin/env bash
# Run the antenna gate on framed GDS, post-MDP GDS, and routed ODB evidence.
#
# Usage:
#   run_final_antenna_check.sh <framed.gds> <top_cell> <report_dir> <openroad_antenna.rpt>
set -euo pipefail

GDS="${1:?framed GDS}"
TOP="${2:?top cell}"
REPORT_DIR="${3:?report directory}"
OPENROAD_REPORT="${4:?OpenROAD antenna report}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
KLAYOUT_BIN="${KLAYOUT_BIN:-$(command -v klayout || true)}"
DRC_RUNSET="${DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run.drc}"
MDP_RUNSET="${MDP_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_mdp.drc}"
IP62_DRC_RUNSET="${IP62_DRC_RUNSET:-$ROOT/libs.tech/klayout/tech/drc/run_IP62.drc}"
CHECK_REPORT="$ROOT/flow/scripts/signoff/check_klayout_report.py"
CHECK_ANTENNA="$ROOT/flow/scripts/signoff/check_final_antenna.py"

mkdir -p "$REPORT_DIR"
GDS="$(cd "$(dirname "$GDS")" && pwd)/$(basename "$GDS")"
OPENROAD_REPORT="$(cd "$(dirname "$OPENROAD_REPORT")" && pwd)/$(basename "$OPENROAD_REPORT")"
for required in "$GDS" "$OPENROAD_REPORT" "$DRC_RUNSET" "$MDP_RUNSET" "$IP62_DRC_RUNSET" "$CHECK_REPORT" "$CHECK_ANTENNA"; do
  [ -f "$required" ] || { echo "BLOCKED: missing antenna input $required" >&2; exit 2; }
done
[ -n "$KLAYOUT_BIN" ] && [ -x "$KLAYOUT_BIN" ] || { echo "ERROR: KLayout executable is unavailable" >&2; exit 3; }

FRAMED_REPORT="$REPORT_DIR/framed_drc.lyrdb"
MDP_GDS="$REPORT_DIR/${TOP}_mdp.gds"
POST_MDP_REPORT="$REPORT_DIR/post_mdp_drc.lyrdb"

"$KLAYOUT_BIN" -b -zz -r "$DRC_RUNSET" \
  -rd "input=$GDS" -rd "top_cell=$TOP" -rd "report=$FRAMED_REPORT" \
  2>&1 | tee "$REPORT_DIR/framed_drc.log"
python3 "$CHECK_REPORT" "$FRAMED_REPORT"

"$KLAYOUT_BIN" -b -zz -r "$MDP_RUNSET" \
  -rd "input=$GDS" -rd "top_cell=$TOP" -rd "output=$MDP_GDS" \
  2>&1 | tee "$REPORT_DIR/mdp.log"
[ -s "$MDP_GDS" ] || { echo "ERROR: post-MDP GDS is empty" >&2; exit 4; }

"$KLAYOUT_BIN" -b -zz -r "$IP62_DRC_RUNSET" \
  -rd "input=$MDP_GDS" -rd "top_cell=$TOP" -rd "report=$POST_MDP_REPORT" \
  2>&1 | tee "$REPORT_DIR/post_mdp_drc.log"
python3 "$CHECK_REPORT" "$POST_MDP_REPORT"

python3 "$CHECK_ANTENNA" \
  --framed-report "$FRAMED_REPORT" \
  --post-mdp-report "$POST_MDP_REPORT" \
  --openroad-report "$OPENROAD_REPORT" \
  --framed-ruleset "$DRC_RUNSET" \
  --post-mdp-ruleset "$IP62_DRC_RUNSET" \
  --output "$REPORT_DIR/antenna_check.json"

echo "PASS: framed, post-MDP, and routed antenna evidence checked"
