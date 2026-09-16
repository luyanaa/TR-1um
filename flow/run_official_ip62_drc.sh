#!/usr/bin/env bash
# Run the foundry IP62 deck in the official TR-1um EDA container.
set -Eeuo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 <input.gds> <top-cell> [report.lyrdb]" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT_GDS="$(realpath "$1")"
TOP="$2"
REPORT="${3:-$(dirname "$INPUT_GDS")/${TOP}.official_ip62.lyrdb}"
mkdir -p "$(dirname "$REPORT")"
REPORT="$(realpath -m "$REPORT")"

IMAGE="${TR1UM_OFFICIAL_EDA_IMAGE:-factory.symbioticeda.com/tr-1um-official-eda:ubuntu2204-ishi-kai}"
DECK="${TR1UM_OFFICIAL_IP62_DECK:-/home/ishi-kai/pdk/TR-1um/libs.tech/klayout/tech/drc/run_IP62.drc}"
INPUT_DIR="$(dirname "$INPUT_GDS")"
OUTPUT_DIR="$(dirname "$REPORT")"
INPUT_NAME="$(basename "$INPUT_GDS")"
REPORT_NAME="$(basename "$REPORT")"

command -v docker >/dev/null || {
    echo "ERROR: docker is required for official TR-1um IP62 signoff" >&2
    exit 3
}

set -x
docker run --rm \
    -v "$INPUT_DIR:/input:ro" \
    -v "$OUTPUT_DIR:/output" \
    "$IMAGE" \
    klayout -b -r "$DECK" \
        -rd "input=/input/$INPUT_NAME" \
        -rd "top_cell=$TOP" \
        -rd "report=/output/$REPORT_NAME"
set +x

test -s "$REPORT"
# Unlike the drawing-DRC compatibility gate, official signoff rejects warnings:
# WAR06 Floating SG has previously exposed electrically floating cell terminals.
python3 "$ROOT/flow/scripts/signoff/check_klayout_report.py" \
    --fail-warnings "$REPORT"
echo "PASS: official-container IP62 DRC has zero items: $REPORT"
