import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN = ROOT / "flow/designs/tr1um_counter/runs/access-canonical-final"
REQUIRED_METRICS = {
    "design__instance_unmapped__count": 0,
    "route__drc_errors": 0,
    "timing__setup__wns": 0,
    "timing__hold__wns": 0,
    "klayout__drc_error__count": 0,
}


def main() -> int:
    run = Path(os.environ.get("TR1UM_RUN", DEFAULT_RUN))
    metrics = json.loads((run / "final/metrics.json").read_text())
    failures = [
        f"{key}={metrics.get(key)!r}"
        for key, expected in REQUIRED_METRICS.items()
        if metrics.get(key) != expected
    ]
    print(f"baseline={run}")
    for key in REQUIRED_METRICS:
        print(f"{key}={metrics.get(key)}")
    if failures:
        print("DIGITAL_TAPEOUT_GATE=FAIL")
        print("; ".join(failures))
        return 1
    print("DIGITAL_TAPEOUT_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
