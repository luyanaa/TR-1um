#!/usr/bin/env python3
"""Run model-level temperature validation for the declared TR-1um devices.

This runner combines the static source/manual audit with reproducible ngspice
operating-point smoke probes at the product endpoints, the two documented
reference temperatures, and the upper model-characterization endpoint.  A
successful smoke probe demonstrates that the checked-in model can be executed
at that temperature; it does not convert an unqualified extrapolation into
signoff evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from audit_temperature_models import audit, load

NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
CURRENT_RE = re.compile(rf"(?im)^\s*i\(vmon\)\s*=\s*({NUMBER_RE})")
TEMP_RE = re.compile(rf"(?im)Doing analysis at TEMP\s*=\s*({NUMBER_RE})")
ERROR_RE = re.compile(
    r"(?im)^\s*(?:error|fatal):|simulation interrupted|unknown subckt|"
    r"undefined parameter|unknown parameter|cannot compute substitute"
)


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def portable_paths(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {key: portable_paths(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_paths(item, root) for item in value]
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                return candidate.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                pass
    return value


def as_numbers(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or not value or not all(finite_number(item) for item in value):
        raise ValueError(f"{label} must be a non-empty numeric list")
    return [float(item) for item in value]


def spice_number(value: Any) -> str:
    return f"{float(value):.17g}"


def build_deck(model_path: Path, entry: dict[str, Any], probe: dict[str, Any], temperature: float, width: float | None, length: float | None) -> str:
    kind = probe["kind"]
    name = str(entry["name"])
    lines = [
        f"* Generated temperature probe for {name} at {temperature:g} degC.",
        ".param vthMP=0 vthMN=0 vthMPE=0 vthMNE=0 magRR=1 magRS=1",
        f".temp {spice_number(temperature)}",
        f".include '{model_path.as_posix()}'",
    ]
    if kind == "mos":
        bias = probe["bias_v"]
        lines.extend(
            [
                f"VMON D 0 {spice_number(bias['drain'])}",
                f"VG G 0 {spice_number(bias['gate'])}",
                f"VS S 0 {spice_number(bias['source'])}",
                f"VB B 0 {spice_number(bias['bulk'])}",
                f"XU D G S B {probe['subckt']} w={spice_number(width)}u l={spice_number(length)}u",
            ]
        )
    elif kind == "rr":
        lines.extend(
            [
                "VSUB SUB 0 0",
                f"VMON PLUS 0 {spice_number(probe['voltage_v'])}",
                f"XU PLUS 0 SUB F_RR w={spice_number(width)}u l={spice_number(length)}u",
            ]
        )
    elif kind == "rs":
        lines.extend(
            [
                f"VMON PLUS 0 {spice_number(probe['voltage_v'])}",
                f"XU PLUS 0 F_RS w={spice_number(width)}u l={spice_number(length)}u",
            ]
        )
    elif kind == "diode":
        lines.extend(
            [
                f"VMON ANODE 0 {spice_number(probe['voltage_v'])}",
                f"D1 ANODE 0 {name}",
            ]
        )
    else:
        raise ValueError(f"unsupported runtime probe kind: {kind}")
    lines.extend(
        [
            ".op",
            ".control",
            "set noaskquit",
            "run",
            "print i(VMON)",
            ".endc",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def run_case(
    model_path: Path,
    entry: dict[str, Any],
    probe: dict[str, Any],
    temperature: float,
    width: float | None,
    length: float | None,
    workdir: Path,
    ngspice: str,
) -> dict[str, Any]:
    case_name = f"{entry['name']}_{temperature:g}_{width or 0:g}_{length or 0:g}".replace(".", "p").replace("-", "m")
    deck_path = workdir / f"{case_name}.cir"
    log_path = workdir / f"{case_name}.log"
    result: dict[str, Any] = {
        "temperature_c": temperature,
        "width_um": width,
        "length_um": length,
        "returncode": None,
        "current_a": None,
        "resistance_ohm": None,
        "status": "FAIL",
        "errors": [],
    }
    try:
        deck_path.write_text(build_deck(model_path, entry, probe, temperature, width, length), encoding="utf-8")
        completed = subprocess.run(
            [ngspice, "-b", "-o", str(log_path), str(deck_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError) as exc:
        result["errors"] = [f"cannot run probe: {exc}"]
        return result
    text = (log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else "")
    text += "\n" + completed.stdout + "\n" + completed.stderr
    result["returncode"] = completed.returncode
    current_match = CURRENT_RE.search(text)
    temperature_matches = [float(value) for value in TEMP_RE.findall(text)]
    if completed.returncode != 0:
        result["errors"].append(f"ngspice returned {completed.returncode}")
    if ERROR_RE.search(text):
        result["errors"].append("ngspice reported a simulation error")
    if not current_match:
        result["errors"].append("i(VMON) measurement is missing")
    else:
        current = float(current_match.group(1))
        if not math.isfinite(current):
            result["errors"].append("i(VMON) is not finite")
        else:
            result["current_a"] = current
            if probe["kind"] in {"rr", "rs"}:
                voltage = float(probe["voltage_v"])
                if current == 0.0:
                    result["errors"].append("resistor current is zero")
                else:
                    result["resistance_ohm"] = abs(voltage / current)
    if not any(math.isclose(value, temperature, abs_tol=1e-9) for value in temperature_matches):
        result["errors"].append(f"ngspice did not report requested temperature {temperature:g}C")
    if not result["errors"]:
        result["status"] = "PASS"
    else:
        result["log_tail"] = text[-2000:]
    return result


def model_temperatures(contract: dict[str, Any]) -> list[float]:
    runtime = contract.get("runtime_validation")
    if not isinstance(runtime, dict):
        raise ValueError("runtime_validation is required")
    return as_numbers(runtime.get("temperatures_c"), "runtime_validation.temperatures_c")


def run_model(
    base: Path,
    entry: dict[str, Any],
    temperatures: list[float],
    workdir: Path,
    ngspice: str,
) -> dict[str, Any]:
    name = entry.get("name")
    model_path = resolve(base, entry.get("path"))
    probe = entry.get("probe")
    result: dict[str, Any] = {
        "name": name,
        "used": entry.get("used", True),
        "probe": probe,
        "source": str(model_path) if model_path else entry.get("path"),
        "cases": [],
        "status": "FAIL",
        "errors": [],
    }
    if not result["used"]:
        result["status"] = "NOT_USED"
        return result
    if model_path is None or not model_path.is_file() or model_path.stat().st_size == 0:
        result["errors"].append(f"missing or empty source model: {model_path or entry.get('path')}")
        return result
    if not isinstance(probe, dict) or not isinstance(probe.get("kind"), str):
        result["errors"].append("runtime probe definition is missing")
        return result
    kind = probe["kind"]
    if kind == "static_only":
        result["status"] = "STATIC_ONLY"
        result["limitations"] = [probe.get("reason", "runtime probe intentionally omitted")]
        return result
    widths = [None]
    lengths = [None]
    if kind in {"mos", "rr", "rs"}:
        widths = as_numbers(probe.get("widths_um"), f"{name}.probe.widths_um")
        lengths = as_numbers(probe.get("lengths_um"), f"{name}.probe.lengths_um")
    for temperature in temperatures:
        for width in widths:
            for length in lengths:
                result["cases"].append(
                    run_case(model_path, entry, probe, temperature, width, length, workdir, ngspice)
                )
    failures = [case for case in result["cases"] if case["status"] != "PASS"]
    if failures:
        result["status"] = "FAIL"
        result["errors"].append(f"{len(failures)} of {len(result['cases'])} runtime probes failed")
    else:
        result["status"] = "PASS"
    return result


def rs_evidence(contract: dict[str, Any], model_result: dict[str, Any]) -> dict[str, Any]:
    qualification = contract.get("rs_extrapolation", {})
    qualification_status = qualification.get("status") if isinstance(qualification, dict) else None
    if qualification_status == "not_needed":
        return {
            "smoke_status": "NOT_NEEDED",
            "qualification_status": "not_needed",
            "low_temperature_c": [],
            "low_case_count": 0,
            "comparison_count": 0,
            "max_relative_delta_from_25C": None,
            "comparisons": [],
            "interpretation": "The 27..85 degC release scope is inside the declared 25..150 degC RS characterization range; no below-25 degC extrapolation is required.",
        }
    runtime = contract.get("runtime_validation", {})
    low_temperatures = as_numbers(runtime.get("low_temperature_temperatures_c"), "runtime_validation.low_temperature_temperatures_c")
    cases = model_result.get("cases", [])
    low_cases = [case for case in cases if case["temperature_c"] in low_temperatures]
    baseline_cases = [case for case in cases if math.isclose(case["temperature_c"], 25.0, abs_tol=1e-9)]
    baseline = {(case["width_um"], case["length_um"]): case for case in baseline_cases}
    deltas: list[float] = []
    comparisons: list[dict[str, Any]] = []
    for case in low_cases:
        key = (case["width_um"], case["length_um"])
        reference = baseline.get(key)
        if case["status"] != "PASS" or reference is None or reference.get("status") != "PASS":
            continue
        value = case.get("resistance_ohm")
        ref_value = reference.get("resistance_ohm")
        if finite_number(value) and finite_number(ref_value) and ref_value != 0:
            delta = abs(float(value) - float(ref_value)) / abs(float(ref_value))
            deltas.append(delta)
            comparisons.append(
                {
                    "temperature_c": case["temperature_c"],
                    "width_um": case["width_um"],
                    "length_um": case["length_um"],
                    "resistance_ohm": value,
                    "reference_temperature_c": 25.0,
                    "reference_resistance_ohm": ref_value,
                    "relative_delta": delta,
                }
            )
    smoke_status = "PASS" if low_cases and all(case["status"] == "PASS" for case in low_cases) else "FAIL"
    return {
        "smoke_status": smoke_status,
        "qualification_status": qualification_status,
        "low_temperature_c": low_temperatures,
        "low_case_count": len(low_cases),
        "comparison_count": len(comparisons),
        "max_relative_delta_from_25C": max(deltas) if deltas else None,
        "comparisons": comparisons,
        "interpretation": "Model-execution evidence only; this does not qualify RS extrapolation below the characterized range.",
    }


def tool_version(ngspice: str) -> str:
    try:
        completed = subprocess.run([ngspice, "-v"], capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"unavailable: {exc}"
    text = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(r"\bngspice-\S+", text)
    return match.group(0) if match else text


def run(contract: dict[str, Any], contract_path: Path, output: Path, ngspice: str) -> dict[str, Any]:
    base = contract_path.parent
    repo_root = contract_path.parent.parent.parent
    static_audit = audit(contract, contract_path)
    temperatures = model_temperatures(contract)
    models = contract.get("models")
    errors: list[str] = []
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty list")
        models = []
    if shutil.which(ngspice) is None and not Path(ngspice).is_file():
        errors.append(f"ngspice executable not found: {ngspice}")
    model_results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tr1um-temperature-validation-") as temp_dir:
        workdir = Path(temp_dir)
        if not errors:
            for entry in models:
                if not isinstance(entry, dict):
                    model_results.append({"status": "FAIL", "errors": ["model entry must be an object"]})
                    continue
                try:
                    model_results.append(run_model(base, entry, temperatures, workdir, ngspice))
                except (TypeError, ValueError, KeyError) as exc:
                    model_results.append({"name": entry.get("name"), "status": "FAIL", "errors": [str(exc)]})
    rs_result = next((item for item in model_results if item.get("name") == "F_RS"), None)
    rs_report = rs_evidence(contract, rs_result) if rs_result is not None else {"smoke_status": "FAIL", "qualification_status": None}
    runtime_failures = [item for item in model_results if item.get("status") == "FAIL"]
    static_only = [item["name"] for item in model_results if item.get("status") == "STATIC_ONLY"]
    warning_models = {
        finding["name"]
        for finding in static_audit.get("models", [])
        if finding.get("status") == "PASS_WITH_WARNINGS"
    }
    hard_static_only = [name for name in static_only if name not in warning_models]
    rs_qualification_unresolved = rs_report.get("qualification_status") not in {"qualified", "not_needed"}
    if errors or runtime_failures or rs_report["smoke_status"] == "FAIL":
        status = "FAIL"
    elif (
        static_audit["status"] in {"INVALID", "INCOMPLETE", "ENGINEERING_ONLY"}
        or hard_static_only
        or rs_qualification_unresolved
    ):
        status = "ENGINEERING_ONLY"
    elif static_audit["status"] == "PASS_WITH_WARNINGS" or static_only:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    warnings = list(static_audit.get("warnings", []))
    warnings.extend(
        {
            "name": item["name"],
            "messages": item.get("limitations", ["runtime probe is static-only"]),
        }
        for item in model_results
        if item.get("status") == "STATIC_ONLY"
    )
    limitations = [
        "PASS_WITH_WARNINGS is engineering evidence, not foundry qualification."
        if status == "PASS_WITH_WARNINGS"
        else "ENGINEERING_ONLY is not foundry qualification."
    ]
    if rs_report.get("qualification_status") == "blocked":
        limitations.append("The contract blocks RS extrapolation below 25 degC.")
    report = {
        "schema_version": 1,
        "status": status,
        "contract": portable_paths(str(contract_path.resolve()), repo_root),
        "design": contract.get("design"),
        "ngspice": tool_version(ngspice),
        "temperatures_c": temperatures,
        "static_audit": portable_paths(static_audit, repo_root),
        "models": portable_paths(model_results, repo_root),
        "rs_low_temperature_evidence": rs_report,
        "errors": errors,
        "warnings": warnings,
        "limitations": limitations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ngspice", default="ngspice")
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    report = run(load(contract_path), contract_path, args.output.resolve(), args.ngspice)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
