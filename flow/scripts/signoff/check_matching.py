#!/usr/bin/env python3
"""Check analog matching and overdesign evidence.

The checker accepts either qualified sigma evidence or an explicit guardband
review.  A guardbanded result is reported as ENGINEERING_ONLY, never as
signoff PASS, because it is not a substitute for process-valid mismatch data.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
LAYOUT_STRATEGIES = {"common_centroid", "interdigitated", "unit_array", "single_device", "other"}
LIMIT_KEYS = (
    "max_current_density_mA_per_um",
    "min_headroom_mV",
    "max_area_um2",
    "max_mismatch_sigma_pct",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read matching contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: matching contract must be a JSON object")
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


def positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
        "groups": [],
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

    limits = contract.get("limits")
    normalized_limits: dict[str, float] = {}
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
        limits = {}
    for key in LIMIT_KEYS:
        value = limits.get(key)
        if key == "min_headroom_mV":
            valid = nonnegative_number(value)
        else:
            valid = positive_number(value)
        if not valid:
            errors.append(f"limits.{key} must be finite and {'non-negative' if key == 'min_headroom_mV' else 'positive'}")
        else:
            normalized_limits[key] = float(value)
    report["limits"] = normalized_limits

    groups = contract.get("device_groups")
    if not isinstance(groups, list) or not groups:
        errors.append("device_groups must be a non-empty list")
        return ("BLOCKED" if not contract.get("evidence") and applicable is True else "INVALID"), errors, report

    for group_index, group in enumerate(groups):
        label = f"device_groups[{group_index}]"
        if not isinstance(group, dict):
            errors.append(f"{label} must be an object")
            continue
        name = required_text(group, "name", label, errors)
        matched = group.get("matched")
        if not isinstance(matched, bool):
            errors.append(f"{label}.matched must be boolean")
            matched = False
        if not matched:
            required_text(group, "not_matched_rationale", label, errors)
        layout = group.get("layout")
        if not isinstance(layout, dict):
            errors.append(f"{label}.layout must be an object")
            layout = {}
        strategy = required_text(layout, "strategy", f"{label}.layout", errors)
        if strategy not in LAYOUT_STRATEGIES:
            errors.append(f"{label}.layout.strategy must be one of {sorted(LAYOUT_STRATEGIES)}")
        orientation = required_text(layout, "orientation", f"{label}.layout", errors)
        route_symmetry = required_text(layout, "route_symmetry", f"{label}.layout", errors)
        surroundings = required_text(layout, "surroundings", f"{label}.layout", errors)
        guard_ring = required_text(layout, "guard_ring", f"{label}.layout", errors)
        layout_errors, layout_evidence = evidence_errors(base, layout.get("evidence"), f"{label}.layout.evidence")
        errors.extend(layout_errors)
        if matched and strategy in {"single_device", "other"}:
            errors.append(f"{label}.layout.strategy must explicitly implement a matched array")
        dummies = layout.get("dummies")
        if matched and (not isinstance(dummies, list) or not dummies):
            errors.append(f"{label}.layout.dummies must be a non-empty list for a matched group")
        unit_w = group.get("unit_w_um")
        unit_l = group.get("unit_l_um")
        tolerance = group.get("dimension_tolerance_pct")
        if not positive_number(unit_w):
            errors.append(f"{label}.unit_w_um must be finite and positive")
        if not positive_number(unit_l):
            errors.append(f"{label}.unit_l_um must be finite and positive")
        if not nonnegative_number(tolerance):
            errors.append(f"{label}.dimension_tolerance_pct must be finite and non-negative")
        devices = group.get("devices")
        if not isinstance(devices, list) or not devices:
            errors.append(f"{label}.devices must be a non-empty list")
            devices = []
        normalized_devices: list[dict[str, Any]] = []
        for device_index, device in enumerate(devices):
            dlabel = f"{label}.devices[{device_index}]"
            if not isinstance(device, dict):
                errors.append(f"{dlabel} must be an object")
                continue
            device_name = required_text(device, "name", dlabel, errors)
            w = device.get("w_um")
            l = device.get("l_um")
            fingers = device.get("fingers")
            multiplicity = device.get("multiplicity")
            ratio = device.get("expected_ratio", 1.0)
            current_density = device.get("current_density_mA_per_um")
            area = device.get("area_um2")
            if not positive_number(w):
                errors.append(f"{dlabel}.w_um must be finite and positive")
            if not positive_number(l):
                errors.append(f"{dlabel}.l_um must be finite and positive")
            if not positive_integer(fingers):
                errors.append(f"{dlabel}.fingers must be a positive integer")
            if not positive_integer(multiplicity):
                errors.append(f"{dlabel}.multiplicity must be a positive integer")
            if not positive_number(ratio):
                errors.append(f"{dlabel}.expected_ratio must be finite and positive")
            if not nonnegative_number(current_density):
                errors.append(f"{dlabel}.current_density_mA_per_um must be finite and non-negative")
            elif "max_current_density_mA_per_um" in normalized_limits and float(current_density) > normalized_limits["max_current_density_mA_per_um"]:
                report["violations"].append(
                    f"{dlabel} current_density_mA_per_um={float(current_density):g} exceeds "
                    f"max_current_density_mA_per_um={normalized_limits['max_current_density_mA_per_um']:g}"
                )
            if not positive_number(area):
                errors.append(f"{dlabel}.area_um2 must be finite and positive")
            elif "max_area_um2" in normalized_limits and float(area) > normalized_limits["max_area_um2"]:
                report["violations"].append(
                    f"{dlabel} area_um2={float(area):g} exceeds max_area_um2={normalized_limits['max_area_um2']:g}"
                )
            if matched and positive_number(unit_w) and positive_number(unit_l) and positive_number(w) and positive_number(l) and nonnegative_number(tolerance) and positive_number(ratio):
                expected_w = float(unit_w) * float(ratio)
                allowed = float(tolerance) / 100.0
                if abs(float(w) - expected_w) > expected_w * allowed:
                    report["violations"].append(f"{dlabel} width is outside declared matching tolerance")
                if abs(float(l) - float(unit_l)) > float(unit_l) * allowed:
                    report["violations"].append(f"{dlabel} length is outside declared matching tolerance")
            normalized_devices.append(
                {
                    "name": device_name,
                    "w_um": float(w) if positive_number(w) else w,
                    "l_um": float(l) if positive_number(l) else l,
                    "fingers": fingers,
                    "multiplicity": multiplicity,
                    "expected_ratio": float(ratio) if positive_number(ratio) else ratio,
                    "current_density_mA_per_um": float(current_density) if nonnegative_number(current_density) else current_density,
                    "area_um2": float(area) if positive_number(area) else area,
                }
            )
        headroom = group.get("minimum_headroom_mV")
        if not nonnegative_number(headroom):
            errors.append(f"{label}.minimum_headroom_mV must be finite and non-negative")
        elif "min_headroom_mV" in normalized_limits and float(headroom) < normalized_limits["min_headroom_mV"]:
            report["violations"].append(
                f"{label} minimum_headroom_mV={float(headroom):g} is below "
                f"min_headroom_mV={normalized_limits['min_headroom_mV']:g}"
            )
        group_area = group.get("total_area_um2")
        if not positive_number(group_area):
            errors.append(f"{label}.total_area_um2 must be finite and positive")
        elif "max_area_um2" in normalized_limits and float(group_area) > normalized_limits["max_area_um2"]:
            report["violations"].append(
                f"{label} total_area_um2={float(group_area):g} exceeds max_area_um2={normalized_limits['max_area_um2']:g}"
            )

        mismatch = group.get("mismatch")
        if not isinstance(mismatch, dict):
            errors.append(f"{label}.mismatch must be an object")
            mismatch = {}
        mismatch_status = mismatch.get("status")
        if mismatch_status not in {"qualified", "guardbanded"}:
            errors.append(f"{label}.mismatch.status must be qualified or guardbanded")
        sigma = mismatch.get("predicted_sigma_pct")
        sigma_errors, sigma_evidence = evidence_errors(base, mismatch.get("sigma_model_evidence"), f"{label}.mismatch.sigma_model_evidence")
        if mismatch_status == "qualified":
            errors.extend(sigma_errors)
            if not nonnegative_number(sigma):
                errors.append(f"{label}.mismatch.predicted_sigma_pct must be finite and non-negative")
            elif "max_mismatch_sigma_pct" in normalized_limits and float(sigma) > normalized_limits["max_mismatch_sigma_pct"]:
                report["violations"].append(
                    f"{label} predicted_sigma_pct={float(sigma):g} exceeds "
                    f"max_mismatch_sigma_pct={normalized_limits['max_mismatch_sigma_pct']:g}"
                )
        else:
            required_text(mismatch, "guardband_rationale", f"{label}.mismatch", errors)
            guardband = mismatch.get("guardband_pct")
            if not positive_number(guardband):
                errors.append(f"{label}.mismatch.guardband_pct must be finite and positive")
            elif "max_mismatch_sigma_pct" in normalized_limits and float(guardband) > normalized_limits["max_mismatch_sigma_pct"]:
                report["violations"].append(
                    f"{label} guardband_pct={float(guardband):g} exceeds "
                    f"max_mismatch_sigma_pct={normalized_limits['max_mismatch_sigma_pct']:g}"
                )
        report["groups"].append(
            {
                "name": name,
                "matched": matched,
                "layout": {
                    "strategy": strategy,
                    "orientation": orientation,
                    "route_symmetry": route_symmetry,
                    "surroundings": surroundings,
                    "guard_ring": guard_ring,
                    "dummies": dummies,
                    "evidence": layout_evidence,
                },
                "unit_w_um": float(unit_w) if positive_number(unit_w) else unit_w,
                "unit_l_um": float(unit_l) if positive_number(unit_l) else unit_l,
                "dimension_tolerance_pct": float(tolerance) if nonnegative_number(tolerance) else tolerance,
                "devices": normalized_devices,
                "minimum_headroom_mV": float(headroom) if nonnegative_number(headroom) else headroom,
                "total_area_um2": float(group_area) if positive_number(group_area) else group_area,
                "mismatch": {
                    "status": mismatch_status,
                    "predicted_sigma_pct": float(sigma) if nonnegative_number(sigma) else sigma,
                    "guardband_pct": float(mismatch.get("guardband_pct")) if positive_number(mismatch.get("guardband_pct")) else mismatch.get("guardband_pct"),
                    "sigma_model_evidence": sigma_evidence,
                },
            }
        )
    if errors:
        incomplete_scope = not contract.get("evidence")
        return ("BLOCKED" if incomplete_scope and applicable is True else "INVALID"), errors, report
    if report["violations"]:
        return "FAIL", [], report
    if any(group.get("mismatch", {}).get("status") == "guardbanded" for group in report["groups"]):
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
