#!/usr/bin/env python3
"""Check MOS and poly-poly capacitance recognition and value evidence.

The contract separates intrinsic MOS, CSIO/F_CSIO, and Poly_cap/CAP.  A
PCell coefficient is never accepted as qualification by itself.  Every
supported device needs expected and extracted values over explicit
voltage/temperature/process corners; unsupported Poly_cap/CAP support must be
reported with a rationale and is ENGINEERING_ONLY.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
KINDS = {"mos_intrinsic", "csio", "poly_cap", "cap"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read capacitance contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: capacitance contract must be a JSON object")
    return value


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def positive_number(value: Any) -> bool:
    return finite_number(value) and float(value) > 0


def nonnegative_number(value: Any) -> bool:
    return finite_number(value) and float(value) >= 0


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evidence_errors(base: Path, values: Any, label: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    resolved: list[str] = []
    if not isinstance(values, list) or not values:
        return [f"{label} must be a non-empty list"], resolved
    for index, value in enumerate(values):
        path = resolve(base, value)
        if path is None:
            errors.append(f"{label}[{index}] must be a non-empty path")
            continue
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty {label}[{index}]: {path}")
        resolved.append(str(path))
    return errors, resolved


def required_text(obj: dict[str, Any], key: str, label: str, errors: list[str]) -> str | None:
    value = obj.get(key)
    if not nonempty_string(value):
        errors.append(f"{label}.{key} must be a non-empty string")
        return None
    return value


def validate(contract: dict[str, Any], base: Path) -> tuple[str, list[str], dict[str, Any]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": contract.get("schema_version"),
        "design": contract.get("design"),
        "applicable": contract.get("applicable"),
        "devices": [],
        "unsupported": [],
        "violations": [],
    }
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not nonempty_string(contract.get("design")):
        errors.append("design must be a non-empty string")
    applicable = contract.get("applicable")
    if not isinstance(applicable, bool):
        errors.append("applicable must be boolean")
    evidence_errors_top, evidence_top = evidence_errors(base, contract.get("evidence"), "evidence")
    report["evidence"] = evidence_top
    if applicable is False:
        if not nonempty_string(contract.get("na_basis")):
            errors.append("not-applicable contract requires na_basis")
        errors.extend(evidence_errors_top)
        if errors:
            return "INVALID", errors, report
        return "NOT_APPLICABLE", [], report
    errors.extend(evidence_errors_top)

    limits = contract.get("limits")
    normalized_limits: dict[str, float] = {}
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
        limits = {}
    maximum_error = limits.get("max_relative_error_pct")
    if not positive_number(maximum_error):
        errors.append("limits.max_relative_error_pct must be finite and positive")
    else:
        normalized_limits["max_relative_error_pct"] = float(maximum_error)
    report["limits"] = normalized_limits

    devices = contract.get("devices")
    if not isinstance(devices, list) or not devices:
        errors.append("devices must be a non-empty list")
        return ("BLOCKED" if not contract.get("evidence") and applicable is True else "INVALID"), errors, report

    for index, device in enumerate(devices):
        label = f"devices[{index}]"
        if not isinstance(device, dict):
            errors.append(f"{label} must be an object")
            continue
        name = required_text(device, "name", label, errors)
        kind = device.get("kind")
        if kind not in KINDS:
            errors.append(f"{label}.kind must be one of {sorted(KINDS)}")
        model_support = device.get("model_support")
        if not isinstance(model_support, bool):
            errors.append(f"{label}.model_support must be boolean")
            model_support = False
        model_identifier = required_text(device, "model_identifier", label, errors)
        if not model_support:
            rationale = required_text(device, "unsupported_rationale", label, errors)
            report["unsupported"].append({"name": name, "kind": kind, "rationale": rationale})
        recognition = device.get("recognition")
        if not isinstance(recognition, dict):
            errors.append(f"{label}.recognition must be an object")
            recognition = {}
        normalized_recognition: dict[str, str] = {}
        for key in ("schematic_device", "lvs_device", "extracted_device", "model_device"):
            value = required_text(recognition, key, f"{label}.recognition", errors)
            if value is not None:
                normalized_recognition[key] = value
        geometry = device.get("geometry")
        if not isinstance(geometry, dict):
            errors.append(f"{label}.geometry must be an object")
            geometry = {}
        area = geometry.get("area_um2")
        perimeter = geometry.get("perimeter_um")
        if not positive_number(area):
            errors.append(f"{label}.geometry.area_um2 must be finite and positive")
        if not positive_number(perimeter):
            errors.append(f"{label}.geometry.perimeter_um must be finite and positive")
        device_evidence_errors, device_evidence = evidence_errors(base, device.get("evidence"), f"{label}.evidence")
        errors.extend(device_evidence_errors)
        corners = device.get("corners")
        if not isinstance(corners, list):
            errors.append(f"{label}.corners must be a list")
            corners = []
        if model_support and not corners:
            errors.append(f"{label}.corners must be non-empty when model_support is true")
        normalized_corners: list[dict[str, Any]] = []
        for corner_index, corner in enumerate(corners):
            clabel = f"{label}.corners[{corner_index}]"
            if not isinstance(corner, dict):
                errors.append(f"{clabel} must be an object")
                continue
            process = required_text(corner, "process", clabel, errors)
            temperature = corner.get("temperature_c")
            voltage = corner.get("voltage_v")
            expected = corner.get("expected_fF")
            extracted = corner.get("extracted_fF")
            if not finite_number(temperature):
                errors.append(f"{clabel}.temperature_c must be finite")
            if not finite_number(voltage):
                errors.append(f"{clabel}.voltage_v must be finite")
            if model_support:
                if not positive_number(expected):
                    errors.append(f"{clabel}.expected_fF must be finite and positive")
                if not positive_number(extracted):
                    errors.append(f"{clabel}.extracted_fF must be finite and positive")
                if positive_number(expected) and positive_number(extracted) and "max_relative_error_pct" in normalized_limits:
                    relative_error = abs(float(extracted) - float(expected)) / float(expected) * 100.0
                    if relative_error > normalized_limits["max_relative_error_pct"]:
                        report["violations"].append(
                            f"{clabel} relative error={relative_error:g}% exceeds "
                            f"max_relative_error_pct={normalized_limits['max_relative_error_pct']:g}%"
                        )
            normalized_corners.append(
                {
                    "process": process,
                    "temperature_c": float(temperature) if finite_number(temperature) else temperature,
                    "voltage_v": float(voltage) if finite_number(voltage) else voltage,
                    "expected_fF": float(expected) if positive_number(expected) else expected,
                    "extracted_fF": float(extracted) if positive_number(extracted) else extracted,
                }
            )
        substrate = device.get("substrate_connection")
        if kind in {"csio", "poly_cap", "cap"}:
            required_text(device, "substrate_connection", label, errors)
        report["devices"].append(
            {
                "name": name,
                "kind": kind,
                "model_support": model_support,
                "model_identifier": model_identifier,
                "recognition": normalized_recognition,
                "geometry": {
                    "area_um2": float(area) if positive_number(area) else area,
                    "perimeter_um": float(perimeter) if positive_number(perimeter) else perimeter,
                },
                "substrate_connection": substrate,
                "evidence": device_evidence,
                "corners": normalized_corners,
            }
        )
    qualification = contract.get("qualification")
    qualification_status = None
    qualification_evidence: list[str] = []
    if not isinstance(qualification, dict):
        errors.append("qualification must be an object")
    else:
        qualification_status = qualification.get("status")
        if qualification_status not in {"qualified", "engineering_only"}:
            errors.append("qualification.status must be qualified or engineering_only")
        qualification_errors, qualification_evidence = evidence_errors(
            base, qualification.get("evidence"), "qualification.evidence"
        )
        errors.extend(qualification_errors)
    report["qualification"] = {"status": qualification_status, "evidence": qualification_evidence}
    if errors:
        incomplete_scope = not contract.get("evidence")
        return ("BLOCKED" if incomplete_scope and applicable is True else "INVALID"), errors, report
    if report["violations"]:
        return "FAIL", [], report
    if report["unsupported"] or qualification_status == "engineering_only":
        return "ENGINEERING_ONLY", [], report
    if qualification_status != "qualified":
        return "INVALID", ["qualification.status must be qualified when all devices are supported"], report
    return "PASS", [], report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    contract = load_json(contract_path)
    status, errors, report = validate(contract, contract_path.parent)
    report.update({"status": status, "contract": str(contract_path), "errors": errors})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status in {"PASS", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
