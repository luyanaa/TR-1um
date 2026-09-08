#!/usr/bin/env python3
"""Run a bounded RC sensitivity analysis on an existing TR-1um SPEF."""
from __future__ import annotations

import argparse
import random
import re
import subprocess
import tempfile
from pathlib import Path

STA_TCL = """read_liberty {lib}
read_verilog {netlist}
link_design {top}
read_spef {spef}
read_sdc {sdc}
report_checks -path_delay max -format short -digits 3
puts \"WNS: [sta::worst_slack -max]\"
"""


def scale_spef(text: str, r_factor: float, c_factor: float) -> str:
    result = []
    section = None
    for line in text.splitlines():
        if line.startswith("*CAP"):
            section = "cap"
        elif line.startswith("*RES"):
            section = "res"
        elif line.startswith("*") and not re.match(r"^\d+\s", line):
            section = None
        if section == "cap" and re.match(r"^\d+\s+\S+\s+[-\d.eE+]+", line):
            parts = line.split()
            parts[2] = f"{float(parts[2]) * c_factor:.9g}"
            if len(parts) > 3:
                parts[3] = f"{float(parts[3]) * c_factor:.9g}"
            line = " ".join(parts)
        elif section == "res" and re.match(r"^\d+\s+\S+\s+\S+\s+[-\d.eE+]+$", line):
            parts = line.split()
            parts[-1] = f"{float(parts[-1]) * r_factor:.9g}"
            line = " ".join(parts)
        result.append(line)
    return "\n".join(result) + "\n"


def run_sta(sta: str, lib: Path, netlist: Path, spef: Path, sdc: Path, top: str) -> float | None:
    script = STA_TCL.format(lib=lib, netlist=netlist, spef=spef, sdc=sdc, top=top)
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as handle:
        handle.write(script)
        path = Path(handle.name)
    try:
        result = subprocess.run([sta, "-no_init", "-exit", str(path)], capture_output=True, text=True, timeout=120)
    finally:
        path.unlink(missing_ok=True)
    values = re.findall(r"WNS:\s+([-+\d.eE]+)", result.stdout)
    return float(values[-1]) if values else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spef", type=Path, required=True)
    parser.add_argument("--lib", type=Path, required=True)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument("--sdc", type=Path, required=True)
    parser.add_argument("--top", default="tr1um_counter")
    parser.add_argument("--sta", default="sta")
    parser.add_argument("--out", type=Path, default=Path("/tmp/tr1um_rc_sensitivity"))
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--r-spread", type=float, default=0.50)
    parser.add_argument("--c-spread", type=float, default=0.50)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()
    if args.n < 1 or args.r_spread >= 1 or args.c_spread >= 1:
        raise SystemExit("n must be positive and spreads must be below 1")
    random.seed(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.spef.read_text()
    rows = []
    for index in range(args.n):
        rf = 1.0 + random.uniform(-args.r_spread, args.r_spread)
        cf = 1.0 + random.uniform(-args.c_spread, args.c_spread)
        spef = args.out / f"sample_{index}.spef"
        spef.write_text(scale_spef(source, rf, cf))
        wns = run_sta(args.sta, args.lib, args.netlist, spef, args.sdc, args.top)
        spef.unlink(missing_ok=True)
        rows.append((rf, cf, wns))
    parsed = [row[2] for row in rows if row[2] is not None]
    summary = args.out / "summary.txt"
    summary.write_text("r_factor c_factor wns_ns\n" + "\n".join(f"{r:.6f} {c:.6f} {w if w is not None else 'NA'}" for r, c, w in rows) + "\n")
    print(f"samples={len(rows)} parsed={len(parsed)}")
    if parsed:
        print(f"wns_min={min(parsed):.3f} wns_median={sorted(parsed)[len(parsed)//2]:.3f} wns_max={max(parsed):.3f}")
        print(f"violating_samples={sum(value < 0 for value in parsed)}/{len(parsed)}")
    print(f"summary={summary}")
    return 0 if len(parsed) == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
