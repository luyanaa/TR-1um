#!/usr/bin/env python3
"""Validate a powered-macro PDN/EMIR contract without inventing closure.

The contract deliberately separates powered PDN analysis from a ground-only
return-path review. A powered contract is PASS only when geometry, sources,
current envelopes, explicit generic limits, central TR-1um electrical limits,
required M1/M2/step/contact checks, and a numeric result report are present and
within those limits. A ground-only contract is PASS/NOT_APPLICABLE only when
its return path is explicitly not required; otherwise it remains
ENGINEERING_ONLY until return-path evidence is complete.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from electrical_limits import finite_number, load_and_validate, resolve_limit


SCHEMA_VERSION = 1
REQUIRED_LIMITS = (
    "max_ir_drop_mV",
    "max_current_density_mA_per_um",
    "max_via_current_mA",
)
REQUIRED_GEOMETRY = ("layout", "lef")
POWERED_GEOMETRY = ("spef",)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read PDN contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: PDN contract must be a JSON object")
    return value


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive_number(value: Any) -> bool:
    return finite_number(value) and float(value) > 0.0


def nonnegative_number(value: Any) -> bool:
    return finite_number(value) and float(value) >= 0.0


def path_errors(base: Path, values: Any, label: str) -> tuple[list[str], list[str]]:
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


def validate_common(contract: dict[str, Any], base: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not nonempty_string(contract.get("design")):
        errors.append("design must be a non-empty string")
    applicable = contract.get("applicable")
    if not isinstance(applicable, bool):
        errors.append("applicable must be boolean")
    normalized["applicable"] = applicable
    limits_path = resolve(base, contract.get("electrical_limits"))
    if limits_path is None:
        errors.append("electrical_limits must identify a machine-readable limits contract")
    else:
        try:
            limits, limit_errors = load_and_validate(limits_path)
        except SystemExit as exc:
            errors.append(str(exc))
        else:
            errors.extend(limit_errors)
            normalized["_electrical_limits"] = limits
            normalized["electrical_limits"] = str(limits_path)
    for key in ("power_nets", "ground_nets"):
        values = contract.get(key)
        required = key == "ground_nets" or applicable is not False
        if not isinstance(values, list) or not all(nonempty_string(item) for item in values) or (required and not values):
            requirement = "non-empty " if required else ""
            errors.append(f"{key} must be a {requirement}list of net names")
        else:
            normalized[key] = list(values)
    if isinstance(contract.get("power_nets"), list) and isinstance(contract.get("ground_nets"), list):
        overlap = sorted(set(contract["power_nets"]) & set(contract["ground_nets"]))
        if overlap:
            errors.append(f"power and ground nets overlap: {overlap}")
    geometry = contract.get("geometry")
    if not isinstance(geometry, dict):
        errors.append("geometry must be an object")
        geometry = {}
    normalized_geometry: dict[str, str] = {}
    geometry_keys = REQUIRED_GEOMETRY + (POWERED_GEOMETRY if applicable is True else ())
    for key in geometry_keys:
        path = resolve(base, geometry.get(key))
        if path is None:
            errors.append(f"geometry.{key} is required")
        elif not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty geometry.{key}: {path}")
        else:
            normalized_geometry[key] = str(path)
    normalized["geometry"] = normalized_geometry
    return errors, normalized

def validate_powered(contract: dict[str, Any], base: Path, normalized: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_checks = contract.get("required_interconnect_checks")
    allowed_checks = {"metal:M1", "metal:M2", "step:M1", "contact:TC"}
    if (
        not isinstance(required_checks, list)
        or not all(isinstance(item, str) and item in allowed_checks for item in required_checks)
        or len(required_checks) != len(allowed_checks)
        or set(required_checks) != allowed_checks
    ):
        errors.append(
            "powered contract requires required_interconnect_checks to list exactly "
            "metal:M1, metal:M2, step:M1, and contact:TC"
        )
    power_nets = set(normalized.get("power_nets", []))
    ground_nets = set(normalized.get("ground_nets", []))
    macro_pg = contract.get("macro_pg")
    if not isinstance(macro_pg, list) or not macro_pg:
        errors.append("powered contract requires a non-empty macro_pg list")
    else:
        for index, item in enumerate(macro_pg):
            if not isinstance(item, dict):
                errors.append(f"macro_pg[{index}] must be an object")
                continue
            if not nonempty_string(item.get("instance")):
                errors.append(f"macro_pg[{index}].instance is required")
            for key, expected in (("power_pins", power_nets), ("ground_pins", ground_nets)):
                pins = item.get(key)
                if not isinstance(pins, list) or not pins or not all(nonempty_string(pin) for pin in pins):
                    errors.append(f"macro_pg[{index}].{key} must be a non-empty list")
                elif not expected:
                    errors.append(f"macro_pg[{index}].{key} cannot be checked without declared rails")
    sources = contract.get("voltage_sources")
    if not isinstance(sources, list) or not sources:
        errors.append("powered contract requires voltage_sources")
    else:
        source_nets: set[str] = set()
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                errors.append(f"voltage_sources[{index}] must be an object")
                continue
            net = item.get("net")
            if not nonempty_string(net) or net not in power_nets | ground_nets:
                errors.append(f"voltage_sources[{index}].net must name a declared power/ground net")
            elif net in source_nets:
                errors.append(f"duplicate voltage source net: {net}")
            source_nets.add(net)
            if not nonnegative_number(item.get("voltage")):
                errors.append(f"voltage_sources[{index}].voltage must be non-negative")
            if not nonempty_string(item.get("basis")):
                errors.append(f"voltage_sources[{index}].basis is required")
        missing = sorted((power_nets | ground_nets) - source_nets)
        if missing:
            errors.append(f"voltage sources missing declared rails: {missing}")
    envelopes = contract.get("current_envelopes")
    if not isinstance(envelopes, list) or not envelopes:
        errors.append("powered contract requires current_envelopes")
    else:
        envelope_nets: set[str] = set()
        for index, item in enumerate(envelopes):
            if not isinstance(item, dict):
                errors.append(f"current_envelopes[{index}] must be an object")
                continue
            net = item.get("net")
            if not nonempty_string(net) or net not in power_nets | ground_nets:
                errors.append(f"current_envelopes[{index}].net must name a declared rail")
            else:
                envelope_nets.add(net)
            for key in ("peak_mA", "rms_mA"):
                if not nonnegative_number(item.get(key)):
                    errors.append(f"current_envelopes[{index}].{key} must be non-negative")
            if not nonempty_string(item.get("activity_basis")):
                errors.append(f"current_envelopes[{index}].activity_basis is required")
        missing = sorted((power_nets | ground_nets) - envelope_nets)
        if missing:
            errors.append(f"current envelopes missing declared rails: {missing}")
    limits = contract.get("limits")
    if not isinstance(limits, dict):
        errors.append("powered contract requires limits")
    else:
        for key in REQUIRED_LIMITS:
            if not positive_number(limits.get(key)):
                errors.append(f"limits.{key} must be positive")
    report = contract.get("report")
    if not isinstance(report, dict):
        errors.append("powered contract requires a report object")
    else:
        report_path = resolve(base, report.get("path"))
        if report_path is None or not report_path.is_file() or report_path.stat().st_size == 0:
            errors.append(f"missing or empty PDN/EMIR report: {report_path or report.get('path')}")
    return errors


def validate_ground_only(contract: dict[str, Any], base: Path, normalized: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if normalized.get("power_nets"):
        errors.append("ground-only contract cannot declare power_nets")
    if not nonempty_string(contract.get("na_basis")):
        errors.append("ground-only contract requires explicit na_basis")
    return_path = contract.get("return_path")
    if not isinstance(return_path, dict):
        errors.append("ground-only contract requires return_path")
        return errors
    required = return_path.get("required")
    if not isinstance(required, bool):
        errors.append("return_path.required must be boolean")
    if required:
        if not nonempty_string(return_path.get("status")):
            errors.append("required return_path.status is missing")
        continuity_errors, _ = path_errors(base, return_path.get("continuity_evidence"), "return_path.continuity_evidence")
        errors.extend(continuity_errors)
        resistance = return_path.get("resistance_evidence")
        if not isinstance(resistance, list):
            errors.append("return_path.resistance_evidence must be a list")
        if return_path.get("status") == "pass" and (not resistance or any(resolve(base, item) is None for item in resistance)):
            errors.append("passing return path requires resistance evidence")
    elif not nonempty_string(return_path.get("na_basis")):
        errors.append("return_path.na_basis is required when return path is not required")
    return errors


def validate_interconnect_checks(
    checks: Any, limits: dict[str, Any] | None, required: Any
) -> list[str]:
    errors: list[str] = []
    if not isinstance(checks, list) or not checks:
        return ["PDN/EMIR report interconnect_checks must be a non-empty list"]
    if limits is None:
        return ["PDN/EMIR report cannot validate interconnect_checks without electrical limits"]
    required_keys = set(required) if isinstance(required, list) else set()
    observed_keys: set[str] = set()
    for index, item in enumerate(checks):
        label = f"interconnect_checks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        kind = item.get("kind")
        if kind not in {"metal", "step", "contact"}:
            errors.append(f"{label}.kind must be metal, step, or contact")
            continue
        if kind == "contact":
            feature = item.get("feature")
            key = f"contact:{feature}" if isinstance(feature, str) else "contact:<invalid>"
            observed_keys.add(key)
            if not isinstance(feature, str) or feature != "TC":
                errors.append(f"{label}.feature must be TC")
                continue
            expected_ref = "interconnect_limits.contacts.TC.max_current_a_per_contact"
            instantaneous_ref = "interconnect_limits.contacts.TC.instantaneous_max_current_a_per_contact"
            if item.get("limit_ref") != expected_ref:
                errors.append(f"{label}.limit_ref must be {expected_ref}")
            if item.get("instantaneous_limit_ref") != instantaneous_ref:
                errors.append(f"{label}.instantaneous_limit_ref must be {instantaneous_ref}")
            size = item.get("size_um")
            reference_size, reference_error = resolve_limit(
                limits, "interconnect_limits.contacts.TC.reference_size_um"
            )
            if not positive_number(size):
                errors.append(f"{label}.size_um must be finite and positive")
            elif reference_error is None and abs(float(size) - float(reference_size)) > 1.0e-9:
                errors.append(
                    f"{label}.size_um={float(size):g} does not match manual reference "
                    f"{float(reference_size):g}; width/size scaling is not permitted"
                )
            contact_count = item.get("contact_count")
            if (
                not isinstance(contact_count, int)
                or isinstance(contact_count, bool)
                or contact_count <= 0
            ):
                errors.append(f"{label}.contact_count must be a positive integer")
            current = item.get("current_a_per_contact")
            instantaneous = item.get("instantaneous_current_a_per_contact")
            steady_limit, steady_error = resolve_limit(limits, expected_ref)
            instantaneous_limit, instantaneous_error = resolve_limit(limits, instantaneous_ref)
            if not nonnegative_number(current):
                errors.append(f"{label}.current_a_per_contact must be finite and non-negative")
            elif steady_error is None and float(current) > float(steady_limit):
                errors.append(
                    f"{label}.current_a_per_contact={float(current):g} exceeds "
                    f"{expected_ref}={float(steady_limit):g}"
                )
            if not nonnegative_number(instantaneous):
                errors.append(
                    f"{label}.instantaneous_current_a_per_contact must be finite and non-negative"
                )
            elif instantaneous_error is None and float(instantaneous) > float(instantaneous_limit):
                errors.append(
                    f"{label}.instantaneous_current_a_per_contact={float(instantaneous):g} "
                    f"exceeds {instantaneous_ref}={float(instantaneous_limit):g}"
                )
            continue
        layer = item.get("layer")
        key = f"{kind}:{layer}" if isinstance(layer, str) else f"{kind}:<invalid>"
        observed_keys.add(key)
        if layer not in {"M1", "M2"}:
            errors.append(f"{label}.layer must be M1 or M2")
            continue
        if kind == "metal":
            current_ref = f"interconnect_limits.metal.{layer}.max_current_a"
            width_ref = f"interconnect_limits.metal.{layer}.reference_width_um"
        else:
            current_ref = f"interconnect_limits.steps.{layer}.max_current_a"
            width_ref = f"interconnect_limits.steps.{layer}.reference_width_um"
        if item.get("limit_ref") != current_ref:
            errors.append(f"{label}.limit_ref must be {current_ref}")
        width = item.get("width_um")
        reference_width, reference_error = resolve_limit(limits, width_ref)
        if not positive_number(width):
            errors.append(f"{label}.width_um must be finite and positive")
        elif reference_error is None and abs(float(width) - float(reference_width)) > 1.0e-9:
            errors.append(
                f"{label}.width_um={float(width):g} does not match manual reference "
                f"{float(reference_width):g}; width scaling is not permitted"
            )
        current = item.get("peak_current_a")
        density_ref = (
            f"interconnect_limits.metal.{layer}.current_density_a_per_um"
            if kind == "metal"
            else f"interconnect_limits.steps.{layer}.j_max_step_coverage_a_per_um"
        )
        density, density_error = resolve_limit(limits, density_ref)
        limit, limit_error = resolve_limit(limits, current_ref)
        if not nonnegative_number(current):
            errors.append(f"{label}.peak_current_a must be finite and non-negative")
        elif limit_error is None and float(current) > float(limit):
            errors.append(f"{label}.peak_current_a={float(current):g} exceeds {current_ref}={float(limit):g}")
        elif density_error is None and float(current) >= float(limit):
            errors.append(
                f"{label}.peak_current_a={float(current):g} must be strictly below "
                f"{current_ref}={float(limit):g}"
            )
        if nonnegative_number(current) and positive_number(width) and density_error is None:
            required_width = float(current) / float(density)
            if float(width) < required_width:
                density_name = "J_max_step_coverage" if kind == "step" else "J_current_density"
                errors.append(
                    f"{label}.width_um={float(width):g} is below "
                    f"I_peak/{density_name}={required_width:g} um "
                    f"({density_ref}={float(density):g})"
                )
    missing = sorted(required_keys - observed_keys)
    if missing:
        errors.append(f"PDN/EMIR report missing required interconnect checks: {missing}")
    return errors


def numeric_report(
    report_path: Path, limits: dict[str, Any] | None, required_checks: Any
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        value = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"PDN/EMIR report must be JSON with numeric closure fields: {exc}"]
    if not isinstance(value, dict):
        return None, ["PDN/EMIR report must be a JSON object"]
    if value.get("status") != "PASS":
        errors.append("PDN/EMIR report status is not PASS")
    if value.get("violations") != 0:
        errors.append("PDN/EMIR report violations is not zero")
    for key in ("max_ir_drop_mV", "max_current_density_mA_per_um", "max_via_current_mA"):
        if not nonnegative_number(value.get(key)):
            errors.append(f"PDN/EMIR report {key} must be non-negative")
    errors.extend(validate_interconnect_checks(value.get("interconnect_checks"), limits, required_checks))
    return value, errors


def check(contract: dict[str, Any], contract_path: Path) -> dict[str, Any]:
    base = contract_path.parent
    errors, normalized = validate_common(contract, base)
    if not errors and contract.get("applicable") is True:
        errors.extend(validate_powered(contract, base, normalized))
    elif not errors and contract.get("applicable") is False:
        errors.extend(validate_ground_only(contract, base, normalized))
    result: dict[str, Any] = {
        "status": "INVALID" if errors else "BLOCKED",
        "contract": str(contract_path),
        "design": contract.get("design"),
        "applicable": contract.get("applicable"),
        "electrical_limits": normalized.get("electrical_limits"),
        "errors": errors,
    }
    if errors:
        return result
    if contract["applicable"] is False:
        return_path = contract["return_path"]
        if return_path.get("required") and return_path.get("status") != "pass":
            result["status"] = "ENGINEERING_ONLY"
            result["errors"] = ["required ground return-path analysis is not PASS"]
        else:
            result["status"] = "NOT_APPLICABLE"
        return result
    report_path = resolve(base, contract["report"]["path"])
    assert report_path is not None
    limits = normalized.get("_electrical_limits")
    report, report_errors = numeric_report(
        report_path, limits, contract.get("required_interconnect_checks")
    )
    result["report"] = report
    result["errors"] = report_errors
    result["status"] = "PASS" if not report_errors else "FAIL"
    if result["status"] == "PASS":
        generic_limits = contract["limits"]
        for key in REQUIRED_LIMITS:
            if report[key] > generic_limits[key]:
                result["errors"].append(f"{key} {report[key]} exceeds limit {generic_limits[key]}")
        if result["errors"]:
            result["status"] = "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    result = check(load_json(contract_path), contract_path)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] in {"PASS", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
