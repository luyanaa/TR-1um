#!/usr/bin/env python3
"""Run a bounded coupling-capacitance sensitivity sweep on a VCO deck."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

NUMBER = r"([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)"
MEASURE_RE = {
    "period_s": re.compile(r"^period\s*=\s*" + NUMBER, re.IGNORECASE | re.MULTILINE),
    "frequency_Hz": re.compile(r"^freq\s*=\s*" + NUMBER, re.IGNORECASE | re.MULTILINE),
    "vout_min_V": re.compile(r"^vout_min\s*=\s*" + NUMBER, re.IGNORECASE | re.MULTILINE),
    "vout_max_V": re.compile(r"^vout_max\s*=\s*" + NUMBER, re.IGNORECASE | re.MULTILINE),
    "data_rows": re.compile(r"^No\. of Data Rows\s*:\s*(\d+)", re.IGNORECASE | re.MULTILINE),
}


def _ground_net(post_text: str) -> str:
    match = re.search(r"(?im)^\.subckt\s+tr1um_parasitics\s+(\S+)", post_text)
    if not match:
        raise RuntimeError("distributed RC subcircuit header is missing")
    return match.group(1)


def scale_coupling(post_text: str, factor: float) -> tuple[str, dict[str, float | int | str]]:
    ground_net = _ground_net(post_text)
    out: list[str] = []
    total = ground = coupling = 0
    base_pf = coupling_pf = 0.0
    for line in post_text.splitlines(keepends=True):
        fields = line.split()
        if fields and fields[0].startswith("CPEX") and len(fields) >= 4:
            total += 1
            value_match = re.search(rf"\s{NUMBER}(pF\s*(?:\*.*)?\n?)$", line)
            if value_match is None:
                raise RuntimeError(f"cannot parse CPEX value: {line.rstrip()}")
            value = float(value_match.group(1))
            base_pf += value
            if fields[1] == ground_net or fields[2] == ground_net:
                ground += 1
            else:
                coupling += 1
                value *= factor
                coupling_pf += value
                line = line[: value_match.start(1)] + f"{value:.12g}" + line[value_match.end(1) :]
            out.append(line)
            continue
        out.append(line)
    return "".join(out), {
        "ground_net": ground_net,
        "cpex_total": total,
        "ground_entries": ground,
        "coupling_entries": coupling,
        "base_total_pf": base_pf,
        "scaled_coupling_pf": coupling_pf,
    }


def parse_log(log_text: str) -> dict[str, float | int | None]:
    result: dict[str, float | int | None] = {}
    for key, pattern in MEASURE_RE.items():
        match = pattern.search(log_text)
        result[key] = float(match.group(1)) if match and key != "data_rows" else int(match.group(1)) if match else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-postlayout", required=True, type=Path)
    parser.add_argument("--base-testbench", required=True, type=Path)
    parser.add_argument("--outroot", required=True, type=Path)
    parser.add_argument("--factors", nargs="+", type=float, default=[0.8, 1.0, 1.2])
    args = parser.parse_args()

    post_text = args.base_postlayout.read_text(encoding="utf-8")
    base_tb = args.base_testbench.read_text(encoding="utf-8")
    base_post_path = str(args.base_postlayout)
    base_post_resolved = str(args.base_postlayout.resolve())
    include_token = base_post_resolved if base_post_resolved in base_tb else base_post_path
    if include_token not in base_tb:
        raise RuntimeError(f"base testbench does not include {base_post_path}")

    args.outroot.mkdir(parents=True, exist_ok=True)
    variants: list[dict] = []
    counts: dict | None = None
    for factor in args.factors:
        name = f"k{factor:g}"
        directory = args.outroot / name
        directory.mkdir(parents=True, exist_ok=True)
        post_path = directory / "vco.post.sp"
        scaled_text, current_counts = scale_coupling(post_text, factor)
        shape = {
            key: current_counts[key]
            for key in ("ground_net", "cpex_total", "ground_entries", "coupling_entries", "base_total_pf")
        }
        if counts is None:
            counts = shape
        elif shape != counts:
            raise RuntimeError(f"CPEX count changed for factor {factor}: {shape} != {counts}")
        post_path.write_text(scaled_text, encoding="utf-8")

        tb_path = directory / "vco.canonical.tb.sp"
        tb_path.write_text(base_tb.replace(include_token, str(post_path.resolve())), encoding="utf-8")
        log_path = directory / "vco.canonical.log"
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log_path), str(tb_path)],
            check=False,
            timeout=600,
        )
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        row = {
            "k_c_coupling": factor,
            "postlayout_spice": str(post_path.resolve()),
            "testbench": str(tb_path.resolve()),
            "log": str(log_path.resolve()),
            "returncode": completed.returncode,
            "status": "ran" if completed.returncode == 0 else "failed",
            "measurements": parse_log(log_text),
        }
        variants.append(row)
        if completed.returncode != 0:
            raise RuntimeError(f"ngspice failed for factor {factor}; see {log_path}")

    manifest = {
        "design": "TR10-1 VCO",
        "base_postlayout_spice": str(args.base_postlayout.resolve()),
        "base_testbench": str(args.base_testbench.resolve()),
        "factors": list(args.factors),
        "factor_definition": "scale only non-ground CPEX coupling entries; preserve ground CPEX entries, device hierarchy, and RPEX",
        "cpex_counts": counts,
        "variants": variants,
        "limitations": [
            "engineering-estimate PEX, not foundry-qualified RCX",
            "coupling sensitivity does not replace extraction uncertainty or lateral-coupling calibration",
        ],
    }
    manifest_path = args.outroot / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path.resolve()), "variants": len(variants), "cpex_counts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
