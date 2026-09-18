#!/usr/bin/env python3
"""Run reproducible reference-only RC/timing sensitivity analysis.

The input SPEF is an engineering RC estimate.  Each sample scales all
resistive and capacitive terms, then runs OpenSTA.  Complete executions are
reported as PASS_WITH_WARNINGS; sentinel slacks returned when no constrained
path exists are rejected rather than reported as timing results.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

STA_TCL = """read_liberty {lib}
read_verilog {netlist}
link_design {top}
read_spef {spef}
read_sdc {sdc}
report_checks -path_delay max -format json -digits 9 -group_path_count 1000000 > {path_report}
puts "WNS: [sta::worst_slack -max]"
"""
NO_PATH_SENTINEL = 1e30


def scale_spef(text: str, r_factor: float, c_factor: float) -> str:
    result = []
    section = None
    for line in text.splitlines():
        if line.startswith("*D_NET"):
            parts = line.split()
            if len(parts) >= 3 and re.fullmatch(r"[-+\d.eE]+", parts[-1]):
                parts[-1] = f"{float(parts[-1]) * c_factor:.9g}"
                line = " ".join(parts)
            section = None
        elif line.startswith("*CAP"):
            section = "cap"
            parts = line.split()
            if len(parts) >= 4 and re.fullmatch(r"[-+\d.eE]+", parts[-1]):
                parts[-1] = f"{float(parts[-1]) * c_factor:.9g}"
                line = " ".join(parts)
        elif line.startswith("*RES"):
            section = "res"
            parts = line.split()
            if len(parts) >= 5 and re.fullmatch(r"[-+\d.eE]+", parts[-1]):
                parts[-1] = f"{float(parts[-1]) * r_factor:.9g}"
                line = " ".join(parts)
        elif line.startswith("*") and not re.match(r"^\d+\s", line):
            section = None
        if section == "cap" and re.match(r"^\d+\s+\S+\s+(?:\S+\s+)?[-+\d.eE]+$", line):
            parts = line.split()
            parts[-1] = f"{float(parts[-1]) * c_factor:.9g}"
            line = " ".join(parts)
        elif section == "res" and re.match(r"^\d+\s+\S+\s+\S+\s+[-+\d.eE]+$", line):
            parts = line.split()
            parts[-1] = f"{float(parts[-1]) * r_factor:.9g}"
            line = " ".join(parts)
        result.append(line)
    return "\n".join(result) + "\n"


def finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_path_metrics(path: Path) -> dict[str, float] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, list):
        return None
    candidates: list[dict[str, float]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        arrival_s = finite_float(check.get("data_arrival_time"))
        slack_s = finite_float(check.get("slack"))
        required_s = finite_float(check.get("required_time"))
        if arrival_s is None or slack_s is None:
            continue
        candidate = {
            "critical_path_delay_ns": arrival_s * 1.0e9,
            "wns": slack_s * 1.0e9,
        }
        if required_s is not None:
            candidate["required_time_ns"] = required_s * 1.0e9
        candidates.append(candidate)
    if not candidates:
        return None
    return min(candidates, key=lambda item: item["wns"])


def run_sta(sta: str, lib: Path, netlist: Path, spef: Path, sdc: Path, top: str) -> dict[str, float] | None:
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as handle:
        tcl_path = Path(handle.name)
        path_report = tcl_path.with_suffix(".json")
        handle.write(
            STA_TCL.format(
                lib=lib,
                netlist=netlist,
                spef=spef,
                sdc=sdc,
                top=top,
                path_report=path_report,
            )
        )
    try:
        result = subprocess.run(
            [sta, "-no_init", "-exit", str(tcl_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            return None
        values = re.findall(r"WNS:\s+([-+\d.eE]+)", result.stdout + "\n" + result.stderr)
        if not values:
            return None
        precise_wns = float(values[-1])
        if not math.isfinite(precise_wns) or abs(precise_wns) >= NO_PATH_SENTINEL:
            return None
        metrics = parse_path_metrics(path_report)
        if metrics is None:
            return None
        required_time_ns = metrics.pop("required_time_ns", None)
        if required_time_ns is not None:
            metrics["critical_path_delay_ns"] = required_time_ns - precise_wns
        metrics["wns"] = precise_wns
        metrics["wns_ns"] = precise_wns
        return metrics
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        tcl_path.unlink(missing_ok=True)
        path_report.unlink(missing_ok=True)



def tool_version(sta: str) -> str:
    try:
        result = subprocess.run([sta, "-version"], capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"unavailable: {exc}"
    text = (result.stdout + "\n" + result.stderr).strip()
    return text.splitlines()[-1] if text else f"returncode={result.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spef", type=Path, required=True)
    parser.add_argument("--lib", type=Path, required=True)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument("--sdc", type=Path, required=True)
    parser.add_argument("--top", default="tr1um_counter")
    parser.add_argument("--sta", default="sta")
    parser.add_argument("--out", type=Path, default=Path("/tmp/tr1um_rc_sensitivity"))
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--r-spread", type=float, default=0.50)
    parser.add_argument("--c-spread", type=float, default=0.50)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()
    if args.n < 1 or args.r_spread < 0 or args.c_spread < 0 or args.r_spread >= 1 or args.c_spread >= 1:
        raise SystemExit("n must be positive and spreads must be in [0, 1)")
    missing = [
        str(path)
        for path in (args.spef, args.lib, args.netlist, args.sdc)
        if not path.is_file() or path.stat().st_size == 0
    ]
    if missing:
        raise SystemExit(f"missing or empty timing input(s): {', '.join(missing)}")
    if shutil.which(args.sta) is None and not Path(args.sta).is_file():
        raise SystemExit(f"STA executable not found: {args.sta}")
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    source = args.spef.read_text(encoding="utf-8", errors="replace")

    def metric_value(metrics: dict[str, float] | None, key: str) -> float | None:
        if metrics is None:
            return None
        return metrics.get(key)

    def delta(left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return round(left - right, 9)

    nominal_spef = args.out / "nominal.spef"
    nominal_spef.write_text(source, encoding="utf-8")
    nominal_metrics = run_sta(args.sta, args.lib, args.netlist, nominal_spef, args.sdc, args.top)
    nominal_spef.unlink(missing_ok=True)

    cases: list[dict[str, object]] = []
    for index in range(args.n):
        rf = 1.0 + rng.uniform(-args.r_spread, args.r_spread)
        cf = 1.0 + rng.uniform(-args.c_spread, args.c_spread)
        spef_paths = {
            "rc": args.out / f"sample_{index}.spef",
            "r": args.out / f"sample_{index}_r_only.spef",
            "c": args.out / f"sample_{index}_c_only.spef",
        }
        spef_paths["rc"].write_text(scale_spef(source, rf, cf), encoding="utf-8")
        spef_paths["r"].write_text(scale_spef(source, rf, 1.0), encoding="utf-8")
        spef_paths["c"].write_text(scale_spef(source, 1.0, cf), encoding="utf-8")
        try:
            rc_metrics = run_sta(args.sta, args.lib, args.netlist, spef_paths["rc"], args.sdc, args.top)
            r_metrics = run_sta(args.sta, args.lib, args.netlist, spef_paths["r"], args.sdc, args.top)
            c_metrics = run_sta(args.sta, args.lib, args.netlist, spef_paths["c"], args.sdc, args.top)
        finally:
            for spef_path in spef_paths.values():
                spef_path.unlink(missing_ok=True)

        nominal_delay = metric_value(nominal_metrics, "critical_path_delay_ns")
        rc_delay = metric_value(rc_metrics, "critical_path_delay_ns")
        r_delay = metric_value(r_metrics, "critical_path_delay_ns")
        c_delay = metric_value(c_metrics, "critical_path_delay_ns")
        delta_r = delta(r_delay, nominal_delay)
        delta_c = delta(c_delay, nominal_delay)
        delta_rc = delta(rc_delay, nominal_delay)
        interaction = (
            round(rc_delay - r_delay - c_delay + nominal_delay, 9)
            if None not in (rc_delay, r_delay, c_delay, nominal_delay)
            else None
        )
        complete = nominal_metrics is not None and all(
            metrics is not None for metrics in (rc_metrics, r_metrics, c_metrics)
        )
        cases.append(
            {
                "sample": index,
                "r_factor": rf,
                "c_factor": cf,
                "critical_path_delay_ns": rc_delay,
                "wns": metric_value(rc_metrics, "wns"),
                "wns_ns": metric_value(rc_metrics, "wns"),
                "r_only_critical_path_delay_ns": r_delay,
                "c_only_critical_path_delay_ns": c_delay,
                "delta_t_r_ns": delta_r,
                "delta_t_c_ns": delta_c,
                "delta_t_rc_ns": delta_rc,
                "delta_t_interaction_ns": interaction,
                "status": "PASS" if complete else "FAIL",
            }
        )

    valid_cases = [case for case in cases if case["status"] == "PASS"]

    def values(name: str) -> list[float]:
        result: list[float] = []
        for case in valid_cases:
            value = finite_float(case.get(name))
            if value is not None:
                result.append(value)
        return result

    def stats(name: str) -> dict[str, float | None]:
        numbers = values(name)
        return {
            "min": min(numbers) if numbers else None,
            "median": statistics.median(numbers) if numbers else None,
            "max": max(numbers) if numbers else None,
        }

    wns_values = values("wns")
    summary = args.out / "summary.txt"
    summary_lines = [
        "sample r_factor c_factor critical_path_delay_ns delta_t_r_ns delta_t_c_ns delta_t_rc_ns delta_t_interaction_ns wns"
    ]
    for case in cases:
        summary_lines.append(
            " ".join(
                [
                    str(case["sample"]),
                    f"{float(case['r_factor']):.6f}",
                    f"{float(case['c_factor']):.6f}",
                    *(f"{float(case[key]):.9g}" if case[key] is not None else "NA" for key in (
                        "critical_path_delay_ns",
                        "delta_t_r_ns",
                        "delta_t_c_ns",
                        "delta_t_rc_ns",
                        "delta_t_interaction_ns",
                        "wns",
                    )),
                ]
            )
        )
    summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    nominal_report = {
        "r_factor": 1.0,
        "c_factor": 1.0,
        "critical_path_delay_ns": metric_value(nominal_metrics, "critical_path_delay_ns"),
        "wns": metric_value(nominal_metrics, "wns"),
        "wns_ns": metric_value(nominal_metrics, "wns"),
        "status": "PASS" if nominal_metrics is not None else "FAIL",
    }
    summary_json: dict[str, object] = {
        "count": len(wns_values),
        "valid_samples": len(valid_cases),
        "total_samples": len(cases),
        "violating_samples": sum(value < 0 for value in wns_values),
        "critical_path_delay_ns": stats("critical_path_delay_ns"),
        "wns": stats("wns"),
        "wns_ns": stats("wns"),
        "delta_t_r_ns": stats("delta_t_r_ns"),
        "delta_t_c_ns": stats("delta_t_c_ns"),
        "delta_t_rc_ns": stats("delta_t_rc_ns"),
        "delta_t_interaction_ns": stats("delta_t_interaction_ns"),
    }
    complete = nominal_metrics is not None and len(valid_cases) == len(cases)
    report = {
        "schema_version": 1,
        "status": "PASS_WITH_WARNINGS" if complete else "FAIL",
        "execution_status": "PASS" if complete else "FAIL",
        "tool": {"command": args.sta, "version": tool_version(args.sta)},
        "inputs": {
            "spef": str(args.spef.resolve()),
            "liberty": str(args.lib.resolve()),
            "netlist": str(args.netlist.resolve()),
            "sdc": str(args.sdc.resolve()),
            "top": args.top,
        },
        "sampling": {
            "samples": args.n,
            "seed": args.seed,
            "r_spread": args.r_spread,
            "c_spread": args.c_spread,
            "method": "independent uniform scaling of all SPEF R and C terms",
            "delta_method": "R-only, C-only, and coupled RC perturbations relative to the nominal unscaled SPEF",
        },
        "nominal": nominal_report,
        "summary": summary_json,
        "cases": cases,
        "warnings": [
            "Reference-only timing screen using an engineering SPEF and nominal-corner Liberty.",
            "No process-qualified PVT Liberty set or timing signoff claim is made.",
        ],
        "limitations": [
            "The SPEF is an engineering RC estimate, not foundry-qualified extraction.",
            "This is an RC timing sensitivity screen, not a PVT STA signoff report.",
            "delta_t_r_ns and delta_t_c_ns are isolated one-factor delay changes; delta_t_rc_ns includes their coupled RC effect.",
            "A missing or sentinel OpenSTA slack or path report is recorded as FAIL; it is never converted to zero or a passing result.",
        ],
        "summary_text": str(summary.resolve()),
    }
    json_out = args.json_out or (args.out / "rc_sensitivity.json")
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"samples={len(cases)} parsed={len(wns_values)}")
    if wns_values:
        print(f"wns_min={min(wns_values):.3f} wns_median={statistics.median(wns_values):.3f} wns_max={max(wns_values):.3f}")
        print(f"violating_samples={sum(value < 0 for value in wns_values)}/{len(wns_values)}")
    delay_values = values("critical_path_delay_ns")
    if delay_values:
        print(f"critical_path_delay_min={min(delay_values):.6f} critical_path_delay_median={statistics.median(delay_values):.6f} critical_path_delay_max={max(delay_values):.6f}")
    print(f"summary={summary}")
    print(f"report={json_out}")
    return 0 if complete else 1

if __name__ == "__main__":
    raise SystemExit(main())
