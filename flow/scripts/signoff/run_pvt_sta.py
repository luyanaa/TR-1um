#!/usr/bin/env python3
"""Run fail-closed multi-corner STA from an explicit PVT manifest.

Every corner must name a process/voltage/temperature role, Liberty, routed
netlist parasitics, and share an explicit top-level SDC.  The manifest must
also declare the operating-temperature range and the sheet-resistance
characterization range.  If the operating range extends beyond the
RS-characterized range, qualified extrapolation evidence is required before
STA can run; a nominal-only or placeholder library set is rejected.  This
prevents a single-corner result from being presented as PVT closure.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_ROLES = ("slow", "typ", "fast")
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")



def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read PVT manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: PVT manifest must be a JSON object")
    return value


def resolve(base: Path, value: Any) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def parse_range(value: Any, label: str) -> tuple[list[float] | None, str | None]:
    if not isinstance(value, list) or len(value) != 2:
        return None, f"{label} must be a two-element [min, max] list"
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in value):
        return None, f"{label} values must be finite numbers"
    low, high = float(value[0]), float(value[1])
    if low > high:
        return None, f"{label} minimum exceeds maximum"
    return [low, high], None


def validate(manifest: dict[str, Any], manifest_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    base = manifest_path.parent
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    design = manifest.get("design")
    top = manifest.get("top")
    if not isinstance(design, str) or not design:
        errors.append("design must be a non-empty string")
    if not isinstance(top, str) or not top:
        errors.append("top must be a non-empty string")
    elif not SAFE_IDENTIFIER.fullmatch(top):
        errors.append(f"top is not a safe STA identifier: {top}")
    for key in ("netlist", "sdc"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{key} must be a non-empty path")
        else:
            path = resolve(base, value)
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"missing or empty {key}: {path}")
    temperature_contract = manifest.get("temperature_contract")
    operating_range: list[float] | None = None
    rs_range: list[float] | None = None
    required_temperatures: list[float] = []
    if not isinstance(temperature_contract, dict):
        errors.append("temperature_contract is required")
    else:
        operating_range, range_error = parse_range(
            temperature_contract.get("operating_range_c"),
            "temperature_contract.operating_range_c",
        )
        if range_error:
            errors.append(range_error)
        rs_range, range_error = parse_range(
            temperature_contract.get("rs_characterization_range_c"),
            "temperature_contract.rs_characterization_range_c",
        )
        if range_error:
            errors.append(range_error)
        required_value = manifest.get(
            "required_temperatures_c",
            operating_range if operating_range is not None else [],
        )
        if not isinstance(required_value, list) or not required_value:
            errors.append("required_temperatures_c must be a non-empty list")
        elif not all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(item)
            for item in required_value
        ):
            errors.append("required_temperatures_c values must be finite numbers")
        else:
            required_temperatures = [float(item) for item in required_value]
        extrapolation = manifest.get("rs_extrapolation")
        if not isinstance(extrapolation, dict) or extrapolation.get("status") not in {"blocked", "qualified", "not_needed"}:
            errors.append("rs_extrapolation.status must be blocked, qualified, or not_needed")
        elif operating_range is not None and rs_range is not None:
            outside_rs = operating_range[0] < rs_range[0] or operating_range[1] > rs_range[1]
            if outside_rs and extrapolation["status"] != "qualified":
                errors.append(
                    "operating temperature range extends beyond RS characterization; "
                    "qualified RS extrapolation evidence is required"
                )
            if extrapolation["status"] == "qualified":
                evidence = extrapolation.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    errors.append("qualified rs_extrapolation requires evidence")
                else:
                    for index, value in enumerate(evidence):
                        path = resolve(base, value)
                        if path is None or not path.is_file() or path.stat().st_size == 0:
                            errors.append(f"missing or empty rs_extrapolation.evidence[{index}]: {path or value}")

    required_roles = manifest.get("required_roles", list(DEFAULT_ROLES))
    if not isinstance(required_roles, list) or not required_roles or not all(isinstance(role, str) and role for role in required_roles):
        errors.append("required_roles must be a non-empty list of role names")
        required_roles = list(DEFAULT_ROLES)
    corners = manifest.get("corners")
    if not isinstance(corners, list) or not corners:
        errors.append("corners must be a non-empty list")
        corners = []
    seen_names: set[str] = set()
    seen_roles: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, corner in enumerate(corners):
        if not isinstance(corner, dict):
            errors.append(f"corners[{index}] must be an object")
            continue
        name = corner.get("name")
        role = corner.get("role")
        if not isinstance(name, str) or not name:
            errors.append(f"corners[{index}].name is required")
            continue
        if not SAFE_IDENTIFIER.fullmatch(name):
            errors.append(f"corners[{index}].name is not a safe STA identifier: {name}")
        if name in seen_names:
            errors.append(f"duplicate corner name: {name}")
        seen_names.add(name)
        if not isinstance(role, str) or not role:
            errors.append(f"corners[{index}].role is required")
        elif role in seen_roles:
            errors.append(f"duplicate corner role: {role}")
        else:
            seen_roles.add(role)
        process = corner.get("process")
        voltage = corner.get("voltage")
        temperature = corner.get("temperature")
        if not isinstance(process, str) or not process:
            errors.append(f"corners[{index}].process is required")
        elif not SAFE_IDENTIFIER.fullmatch(process):
            errors.append(f"corners[{index}].process is not a safe identifier: {process}")
        if not isinstance(voltage, (int, float)):
            errors.append(f"corners[{index}].voltage must be numeric")
        if not isinstance(temperature, (int, float)):
            errors.append(f"corners[{index}].temperature must be numeric")
        liberty = corner.get("liberty")
        spef = corner.get("spef")
        if not isinstance(liberty, str) or not liberty:
            errors.append(f"corners[{index}].liberty is required")
            liberty_path = Path("<missing>")
        else:
            liberty_path = resolve(base, liberty)
            if not liberty_path.is_file() or liberty_path.stat().st_size == 0:
                errors.append(f"missing or empty Liberty for {name}: {liberty_path}")
        if not isinstance(spef, str) or not spef:
            errors.append(f"corners[{index}].spef is required for routed STA")
            spef_path = Path("<missing>")
        else:
            spef_path = resolve(base, spef)
            if not spef_path.is_file() or spef_path.stat().st_size == 0:
                errors.append(f"missing or empty SPEF for {name}: {spef_path}")
        normalized.append(
            {
                "name": name,
                "role": role,
                "process": process,
                "voltage": voltage,
                "temperature": temperature,
                "liberty": liberty_path,
                "spef": spef_path,
            }
        )
    if operating_range is not None:
        for corner in normalized:
            temperature = corner["temperature"]
            if isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and math.isfinite(temperature):
                if not operating_range[0] <= temperature <= operating_range[1]:
                    errors.append(
                        f"corner {corner['name']} temperature {temperature}C is outside "
                        f"operating range {operating_range}C"
                    )
        missing_temperatures = [
            required
            for required in required_temperatures
            if not any(
                isinstance(corner["temperature"], (int, float))
                and not isinstance(corner["temperature"], bool)
                and math.isclose(float(corner["temperature"]), required, abs_tol=1e-9)
                for corner in normalized
            )
        ]
        if missing_temperatures:
            errors.append(f"required operating temperatures are missing: {missing_temperatures}C")
    missing_roles = sorted(set(required_roles) - seen_roles)
    if missing_roles:
        errors.append(f"required PVT corner roles are missing: {missing_roles}")
    return normalized, errors


def tcl_path(path: Path) -> str:
    return "{" + path.as_posix().replace("}", "\\}") + "}"


def make_script(manifest: dict[str, Any], corner: dict[str, Any], manifest_path: Path, script_path: Path) -> None:
    base = manifest_path.parent
    netlist = resolve(base, manifest["netlist"])
    sdc = resolve(base, manifest["sdc"])
    name = corner["name"]
    body = f"""# Generated by run_pvt_sta.py; do not hand-edit.
define_corners {name}
read_liberty -corner {name} {tcl_path(corner['liberty'])}
read_verilog {tcl_path(netlist)}
link_design {manifest['top']}
read_sdc {tcl_path(sdc)}
read_spef -corner {name} {tcl_path(corner['spef'])}
puts \"PVT_CORNER {name}\"
puts \"PVT_PROCESS {corner['process']}\"
puts \"PVT_VOLTAGE {corner['voltage']}\"
puts \"PVT_TEMPERATURE {corner['temperature']}\"
puts \"__SETUP_BEGIN__\"
report_checks -sort_by_slack -path_delay max -fields {{slew cap input net fanout}} -format full_clock_expanded -group_path_count 1000 -corner {name}
puts \"__SETUP_END__\"
puts \"__HOLD_BEGIN__\"
report_checks -sort_by_slack -path_delay min -fields {{slew cap input net fanout}} -format full_clock_expanded -group_path_count 1000 -corner {name}
puts \"__HOLD_END__\"
puts \"__UNCONSTRAINED_BEGIN__\"
report_checks -unconstrained -fields {{slew cap input net fanout}} -format full_clock_expanded -corner {name}
puts \"__UNCONSTRAINED_END__\"
puts \"__DRC_BEGIN__\"
report_check_types -max_slew -max_capacitance -max_fanout -violators -corner {name}
puts \"__DRC_END__\"
puts \"__SKEW_SETUP_BEGIN__\"
report_clock_skew -corner {name} -setup
puts \"__SKEW_SETUP_END__\"
puts \"__SKEW_HOLD_BEGIN__\"
report_clock_skew -corner {name} -hold
puts \"__SKEW_HOLD_END__\"
puts \"__CHECK_SETUP_BEGIN__\"
check_setup -verbose -unconstrained_endpoints -multiple_clock -no_clock -no_input_delay -loops -generated_clocks
puts \"__CHECK_SETUP_END__\"
puts \"PVT_CORNER_COMPLETE {name}\"
"""
    script_path.write_text(body, encoding="utf-8")


def analyze_log(text: str, corner: dict[str, Any]) -> dict[str, Any]:
    def section(start: str, end: str) -> str:
        match = re.search(re.escape(start) + r"(.*?)" + re.escape(end), text, re.DOTALL)
        return match.group(1) if match else ""

    unconstrained = section("__UNCONSTRAINED_BEGIN__", "__UNCONSTRAINED_END__")
    unconstrained_paths = len(re.findall(r"^Startpoint:", unconstrained, re.MULTILINE))
    setup = section("__SETUP_BEGIN__", "__SETUP_END__")
    hold = section("__HOLD_BEGIN__", "__HOLD_END__")
    drc = section("__DRC_BEGIN__", "__DRC_END__")
    check_setup = section("__CHECK_SETUP_BEGIN__", "__CHECK_SETUP_END__")
    violations = len(re.findall(r"\bVIOLATED\b", setup + hold + drc, re.IGNORECASE))
    check_setup_warnings = re.findall(r"(?im)^\s*Warning:\s*(.+)$", check_setup)
    errors = re.findall(r"(?im)^\s*Error:\s*(.+)$", text)
    complete = f"PVT_CORNER_COMPLETE {corner['name']}" in text
    return {
        "name": corner["name"],
        "role": corner["role"],
        "process": corner["process"],
        "voltage": corner["voltage"],
        "temperature": corner["temperature"],
        "setup_hold_or_drc_violations": violations,
        "unconstrained_paths": unconstrained_paths,
        "check_setup_warnings": check_setup_warnings,
        "sta_errors": errors,
        "complete_marker": complete,
        "status": "PASS" if complete and not errors and not violations and not unconstrained_paths and not check_setup_warnings else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sta-bin", default="sta")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest = load(manifest_path)
    corners, errors = validate(manifest, manifest_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if shutil.which(args.sta_bin) is None:
        errors.append(f"STA executable not found: {args.sta_bin}")
    results: list[dict[str, Any]] = []
    if not errors:
        for corner in corners:
            script = args.output_dir / f"{corner['name']}.tcl"
            log_path = args.output_dir / f"{corner['name']}.log"
            make_script(manifest, corner, manifest_path, script)
            completed = subprocess.run(
                [args.sta_bin, "-no_init", "-exit", str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            text = completed.stdout + completed.stderr
            log_path.write_text(text, encoding="utf-8")
            result = analyze_log(text, corner)
            result["returncode"] = completed.returncode
            result["log"] = str(log_path.resolve())
            if completed.returncode != 0:
                result["status"] = "FAIL"
            results.append(result)

    overall = "PASS" if not errors and results and all(item["status"] == "PASS" for item in results) else ("BLOCKED" if errors else "FAIL")
    report = {
        "status": overall,
        "manifest": str(manifest_path),
        "design": manifest.get("design"),
        "top": manifest.get("top"),
        "required_roles": manifest.get("required_roles", list(DEFAULT_ROLES)),
        "temperature_contract": manifest.get("temperature_contract"),
        "required_temperatures_c": manifest.get(
            "required_temperatures_c",
            manifest.get("temperature_contract", {}).get("operating_range_c")
            if isinstance(manifest.get("temperature_contract"), dict)
            else None,
        ),
        "rs_extrapolation": manifest.get("rs_extrapolation"),
        "errors": errors,
        "corners": results,
    }
    output = args.output_dir / "pvt_sta.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
