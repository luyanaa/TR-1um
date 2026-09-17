#!/usr/bin/env python3
"""Check pad-level ESD discharge-path evidence for analog signoff.

A PASS requires every declared external pad to have explicit positive and
negative paths, clamps, body/trigger nets, package assumptions, and evidence
through schematic, CDL, LVS, GDS, and parasitic views.  The checker does not
infer protection from a pad name or from a DRC result.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
VIEW_KEYS = ("schematic", "cdl", "lvs", "gds", "parasitic")
PATH_KEYS = ("positive_path", "negative_path")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read ESD contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: ESD contract must be a JSON object")
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


def validate_views(base: Path, views: Any, label: str, errors: list[str]) -> dict[str, list[str]]:
    if not isinstance(views, dict):
        errors.append(f"{label} must be an object")
        return {}
    normalized: dict[str, list[str]] = {}
    for key in VIEW_KEYS:
        view_errors, resolved = evidence_errors(base, views.get(key), f"{label}.{key}")
        errors.extend(view_errors)
        normalized[key] = resolved
    return normalized


def validate_path(
    base: Path,
    path: Any,
    label: str,
    limits: dict[str, float],
    errors: list[str],
    violations: list[str],
) -> dict[str, Any]:
    if not isinstance(path, dict):
        errors.append(f"{label} must be an object")
        return {}
    rail = required_text(path, "rail", label, errors)
    clamp = required_text(path, "clamp_device", label, errors)
    body_trigger = required_text(path, "body_trigger", label, errors)
    peak = path.get("peak_current_A")
    maximum = path.get("max_current_A")
    resistance = path.get("resistance_ohm")
    if not positive_number(peak):
        errors.append(f"{label}.peak_current_A must be finite and positive")
    if not positive_number(maximum):
        errors.append(f"{label}.max_current_A must be finite and positive")
    elif positive_number(peak) and float(peak) > float(maximum):
        violations.append(f"{label}.peak_current_A exceeds its max_current_A")
    if not nonnegative_number(resistance):
        errors.append(f"{label}.resistance_ohm must be finite and non-negative")
    elif "max_path_resistance_ohm" in limits and float(resistance) > limits["max_path_resistance_ohm"]:
        violations.append(
            f"{label}.resistance_ohm={float(resistance):g} exceeds "
            f"max_path_resistance_ohm={limits['max_path_resistance_ohm']:g}"
        )
    path_errors, evidence = evidence_errors(base, path.get("evidence"), f"{label}.evidence")
    errors.extend(path_errors)
    return {
        "rail": rail,
        "clamp_device": clamp,
        "body_trigger": body_trigger,
        "peak_current_A": float(peak) if positive_number(peak) else peak,
        "max_current_A": float(maximum) if positive_number(maximum) else maximum,
        "resistance_ohm": float(resistance) if nonnegative_number(resistance) else resistance,
        "evidence": evidence,
    }


def validate(contract: dict[str, Any], base: Path) -> tuple[str, list[str], dict[str, Any]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": contract.get("schema_version"),
        "design": contract.get("design"),
        "applicable": contract.get("applicable"),
        "pads": [],
        "violations": [],
    }
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not nonempty_string(contract.get("design")):
        errors.append("design must be a non-empty string")
    applicable = contract.get("applicable")
    if not isinstance(applicable, bool):
        errors.append("applicable must be boolean")
    evidence, resolved_evidence = evidence_errors(base, contract.get("evidence"), "evidence")
    report["evidence"] = resolved_evidence
    if applicable is False:
        if not nonempty_string(contract.get("na_basis")):
            errors.append("not-applicable contract requires na_basis")
        errors.extend(evidence)
        if errors:
            return "INVALID", errors, report
        return "NOT_APPLICABLE", [], report
    errors.extend(evidence)

    rails = contract.get("rails")
    if not isinstance(rails, dict):
        errors.append("rails must be an object")
        rails = {}
    vdd = required_text(rails, "vdd", "rails", errors)
    vss = required_text(rails, "vss", "rails", errors)
    if vdd is not None and vss is not None and vdd == vss:
        errors.append("rails.vdd and rails.vss must be distinct")
    report["rails"] = {"vdd": vdd, "vss": vss}

    limits = contract.get("limits")
    normalized_limits: dict[str, float] = {}
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
        limits = {}
    maximum_path_resistance = limits.get("max_path_resistance_ohm")
    if not positive_number(maximum_path_resistance):
        errors.append("limits.max_path_resistance_ohm must be finite and positive")
    else:
        normalized_limits["max_path_resistance_ohm"] = float(maximum_path_resistance)
    report["limits"] = normalized_limits

    pads = contract.get("pads")
    if not isinstance(pads, list) or not pads:
        errors.append("pads must be a non-empty list")
        return ("BLOCKED" if not contract.get("evidence") and applicable is True else "INVALID"), errors, report
    for index, pad in enumerate(pads):
        label = f"pads[{index}]"
        if not isinstance(pad, dict):
            errors.append(f"{label} must be an object")
            continue
        name = required_text(pad, "name", label, errors)
        domain = required_text(pad, "domain", label, errors)
        package = required_text(pad, "package_assumption", label, errors)
        if pad.get("external") is not True:
            errors.append(f"{label}.external must be true for every declared pad")
        body_nets = pad.get("body_trigger_nets")
        if not isinstance(body_nets, list) or not body_nets or not all(nonempty_string(value) for value in body_nets):
            errors.append(f"{label}.body_trigger_nets must be a non-empty list of net names")
            body_nets = []
        views = validate_views(base, pad.get("view_evidence"), f"{label}.view_evidence", errors)
        paths: dict[str, Any] = {}
        for path_key in PATH_KEYS:
            path = validate_path(base, pad.get(path_key), f"{label}.{path_key}", normalized_limits, errors, report["violations"])
            paths[path_key] = path
            expected_rail = vdd if path_key == "positive_path" else vss
            if path.get("rail") != expected_rail:
                errors.append(f"{label}.{path_key}.rail must be the declared {expected_rail} rail")
        report["pads"].append(
            {
                "name": name,
                "domain": domain,
                "package_assumption": package,
                "body_trigger_nets": body_nets,
                "view_evidence": views,
                **paths,
            }
        )
    qualification = contract.get("qualification")
    if not isinstance(qualification, dict):
        errors.append("qualification must be an object")
        qualification = {}
    qualification_status = qualification.get("status")
    if qualification_status not in {"qualified", "engineering_only"}:
        errors.append("qualification.status must be qualified or engineering_only")
    qualification_evidence_errors, qualification_evidence = evidence_errors(
        base, qualification.get("evidence"), "qualification.evidence"
    )
    errors.extend(qualification_evidence_errors)
    report["qualification"] = {"status": qualification_status, "evidence": qualification_evidence}

    if errors:
        incomplete_scope = not contract.get("evidence")
        return ("BLOCKED" if incomplete_scope and applicable is True else "INVALID"), errors, report
    if report["violations"]:
        return "FAIL", [], report
    if qualification_status == "engineering_only":
        return "ENGINEERING_ONLY", [], report
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
