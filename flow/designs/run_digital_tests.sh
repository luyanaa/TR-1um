#!/usr/bin/env bash
# Run one or more design-local TR-1um RTL-to-GDS-to-LVS tests and package
# reusable hierarchical macro views. Run from the LibreLane nix shell.
set -Euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEFAULT_DESIGNS=(tr1um_alu8 tr1um_fifo4 tr1um_irqctrl tr1um_spitx tr1um_busdecode)
TAG="local-regression"
ARTIFACT_ROOT="$SCRIPT_DIR/artifacts"
CLEAN=1
CLEAN_ALL=0

usage() {
    cat <<EOF
Usage: $0 [--tag TAG] [--artifacts DIR] [--clean-all] [--no-clean] [DESIGN_OR_CONFIG ...]

With no designs, runs: ${DEFAULT_DESIGNS[*]}
A design may be a name under flow/designs, a design directory, or a YAML file.
DESIGN_NAME is read from config_access.yaml, so custom top names are supported.
By default existing runs/<TAG> and artifacts/<TAG> for selected designs are removed.
--clean-all removes every prior run for each explicitly selected design.
EOF
}

requested=()
while (($#)); do
    case "$1" in
        --tag) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; TAG="$2"; shift 2 ;;
        --artifacts) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; ARTIFACT_ROOT="$2"; shift 2 ;;
        --clean-all) CLEAN_ALL=1; CLEAN=1; shift ;;
        --no-clean) CLEAN=0; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; requested+=("$@"); break ;;
        -*) echo "ERROR: unknown option $1" >&2; usage >&2; exit 2 ;;
        *) requested+=("$1"); shift ;;
    esac
done
((${#requested[@]})) || requested=("${DEFAULT_DESIGNS[@]}")

for command in make iverilog vvp librelane openroad klayout python3; do
    command -v "$command" >/dev/null || {
        echo "ERROR: $command unavailable; enter the LibreLane nix-shell first" >&2
        exit 3
    }
done

ARTIFACT_ROOT="$(realpath -m "$ARTIFACT_ROOT")/$TAG"
mkdir -p "$ARTIFACT_ROOT/logs"
failures=()
passes=()

for requested_design in "${requested[@]}"; do
    if [[ -f "$requested_design" ]]; then
        config="$(realpath "$requested_design")"
    elif [[ -d "$requested_design" ]]; then
        config="$(realpath "$requested_design")/config_access.yaml"
    else
        config="$SCRIPT_DIR/$requested_design/config_access.yaml"
    fi
    [[ -f "$config" ]] || { echo "ERROR: no config_access.yaml for $requested_design" >&2; exit 4; }
    design_dir="$(dirname "$config")"
    top="$(awk -F: '/^DESIGN_NAME:/ {gsub(/[[:space:]"]/, "", $2); print $2; exit}' "$config")"
    [[ -n "$top" ]] || { echo "ERROR: DESIGN_NAME missing in $config" >&2; exit 4; }
    run_dir="$design_dir/runs/$TAG"
    bundle="$ARTIFACT_ROOT/$top"

    if ((CLEAN)); then
        [[ "$(basename "$(dirname "$run_dir")")" == runs && "$(basename "$run_dir")" == "$TAG" ]] || {
            echo "ERROR: refusing unsafe run cleanup target $run_dir" >&2; exit 5;
        }
        if ((CLEAN_ALL)); then
            runs_dir="$design_dir/runs"
            [[ "$(basename "$runs_dir")" == runs && "$(dirname "$runs_dir")" == "$design_dir" ]] || {
                echo "ERROR: refusing unsafe all-run cleanup target $runs_dir" >&2; exit 5;
            }
            rm -rf -- "$runs_dir"
        else
            rm -rf -- "$run_dir"
        fi
        rm -rf -- "$bundle"
    elif [[ -e "$run_dir" ]]; then
        echo "ERROR: $run_dir exists; use a new --tag or omit --no-clean" >&2
        exit 5
    fi

    echo "===== $top: simulation -> RTL -> powered GDS -> DRC -> LVS -> bundle ====="
    if (
        set -uo pipefail
        run_step() {
            local name="$1"
            shift
            echo "----- $name -----"
            set -x
            "$@"
            local status=$?
            set +x
            ((status == 0)) || exit "$status"
        }
        run_step "RTL simulation" make -C "$design_dir/src" clean sim
        run_step "Remove simulation product" make -C "$design_dir/src" clean
        run_step "RTL to connected-power GDS, DRC, and strict LVS" \
            "$ROOT/flow/run_tr1um_digital.sh" "$config" "$top" "$TAG"
        run_step "Package hierarchical macro views" python3 \
            "$ROOT/flow/scripts/signoff/package_digital_macro.py" \
            --run-dir "$run_dir" --top "$top" --output "$bundle"
    ) 2>&1 | tee "$ARTIFACT_ROOT/logs/$top.log"; then
        passes+=("$top")
    else
        failures+=("$top")
    fi
done

echo "===== regression summary ====="
((${#passes[@]})) && printf 'PASS %s\n' "${passes[@]}"
if ((${#failures[@]})); then
    printf 'FAIL %s\n' "${failures[@]}" >&2
    exit 1
fi
echo "All ${#passes[@]} design(s) passed. Macro bundles: $ARTIFACT_ROOT"
