#!/usr/bin/env python3
"""Check a bounded analog crosstalk signoff contract.

The checker does not infer coupling from layout.  It requires an explicit
victim/aggressor table, source evidence, extracted coupling values, measured
victim metrics, and limits.  It also reports a conservative first-order
capacitive bound for each victim.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REQUIRED_LIMITS = (
    "max_glitch_mV",
    "max_settling_ns",
    "max_delay_error_ns",
    "max_functional_error_mV",
)
REQUIRED_OBSERVED = (
    "peak_glitch_mV",
    "settling_ns",
    "delay_error_ns",
    "functional_error_mV",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read crosstalk contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: crosstalk contract must be a JSON object")
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


def validate_observed(observed: Any, label: str) -> tuple[list[str], dict[str, float]]:
    errors: list[str] = []
    normalized: dict[str, float] = {}
    if not isinstance(observed, dict):
        return [f"{label} must be an object"], normalized
    for key in REQUIRED_OBSERVED:
        value = observed.get(key)
        if not nonnegative_number(value):
            errors.append(f"{label}.{key} must be a finite non-negative number")
        else:
            normalized[key] = float(value)
    return errors, normalized


def validate(contract: dict[str, Any], base: Path) -> tuple[str, list[str], dict[str, Any]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": contract.get("schema_version"),
        "design": contract.get("design"),
        "applicable": contract.get("applicable"),
        "victims": [],
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
    if applicable is True:
        errors.extend(evidence)
        report["evidence"] = resolved_evidence
    elif applicable is False:
        if not nonempty_string(contract.get("na_basis")):
            errors.append("not-applicable contract requires na_basis")
        if evidence:
            errors.extend(evidence)
        report["evidence"] = resolved_evidence
        if errors:
            return "INVALID", errors, report
        return "NOT_APPLICABLE", [], report

    limits = contract.get("limits")
    normalized_limits: dict[str, float] = {}
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
    else:
        for key in REQUIRED_LIMITS:
            value = limits.get(key)
            if not positive_number(value):
                errors.append(f"limits.{key} must be a finite positive number")
            else:
                normalized_limits[key] = float(value)
    report["limits"] = normalized_limits

    victims = contract.get("victims")
    scope_incomplete = (
        not isinstance(contract.get("evidence"), list)
        or not contract.get("evidence")
        or not isinstance(victims, list)
        or not victims
    )
    if not isinstance(victims, list) or not victims:
        errors.append("applicable crosstalk contract requires a non-empty victims list")
        return ("BLOCKED" if scope_incomplete and applicable is True else "INVALID"), errors, report

    for victim_index, victim in enumerate(victims):
        label = f"victims[{victim_index}]"
        if not isinstance(victim, dict):
            errors.append(f"{label} must be an object")
            continue
        if not nonempty_string(victim.get("name")):
            errors.append(f"{label}.name is required")
        victim_cap = victim.get("victim_cap_fF")
        if not positive_number(victim_cap):
            errors.append(f"{label}.victim_cap_fF must be finite and positive")
            victim_cap_f = None
        else:
            victim_cap_f = float(victim_cap)
        aggressors = victim.get("aggressors")
        if not isinstance(aggressors, list) or not aggressors:
            errors.append(f"{label}.aggressors must be a non-empty list")
            aggressors = []
        analytical_peak = 0.0
        analytical_settling = 0.0
        analytical_delay = 0.0
        normalized_aggressors: list[dict[str, Any]] = []
        for aggressor_index, aggressor in enumerate(aggressors):
            alabel = f"{label}.aggressors[{aggressor_index}]"
            if not isinstance(aggressor, dict):
                errors.append(f"{alabel} must be an object")
                continue
            if not nonempty_string(aggressor.get("name")):
                errors.append(f"{alabel}.name is required")
            coupling = aggressor.get("coupling_cap_fF")
            step = aggressor.get("step_V")
            resistance = aggressor.get("driver_resistance_ohm")
            rise = aggressor.get("rise_time_ns")
            if not positive_number(coupling):
                errors.append(f"{alabel}.coupling_cap_fF must be finite and positive")
            if not finite_number(step) or float(step) == 0:
                errors.append(f"{alabel}.step_V must be a finite non-zero number")
            if not nonnegative_number(resistance):
                errors.append(f"{alabel}.driver_resistance_ohm must be finite and non-negative")
            if not positive_number(rise):
                errors.append(f"{alabel}.rise_time_ns must be finite and positive")
            if positive_number(coupling) and victim_cap_f is not None:
                coupling_f = float(coupling)
                ratio = coupling_f / (victim_cap_f + coupling_f)
                analytical_peak += abs(float(step)) * 1000.0 * ratio if finite_number(step) else 0.0
                if nonnegative_number(resistance) and positive_number(rise):
                    total_cap_f = (victim_cap_f + coupling_f) * 1e-15
                    analytical_settling = max(
                        analytical_settling,
                        float(rise) + 2.2 * float(resistance) * total_cap_f * 1e9,
                    )
                    analytical_delay += ratio * float(rise)
            normalized_aggressors.append(
                {
                    "name": aggressor.get("name"),
                    "coupling_cap_fF": float(coupling) if positive_number(coupling) else coupling,
                    "step_V": float(step) if finite_number(step) else step,
                    "driver_resistance_ohm": float(resistance) if nonnegative_number(resistance) else resistance,
                    "rise_time_ns": float(rise) if positive_number(rise) else rise,
                }
            )
        victim_observed_errors, victim_observed = validate_observed(victim.get("observed"), f"{label}.observed")
        errors.extend(victim_observed_errors)
        normalized_victim = {
            "name": victim.get("name"),
            "victim_cap_fF": victim_cap_f,
            "aggressors": normalized_aggressors,
            "observed": victim_observed,
            "analytical_bound": {
                "peak_glitch_mV": analytical_peak,
                "settling_ns": analytical_settling,
                "delay_error_ns": analytical_delay,
            },
        }
        report["victims"].append(normalized_victim)
        if victim_observed and normalized_limits:
            checks = {
                "peak_glitch_mV": max(analytical_peak, victim_observed["peak_glitch_mV"]),
                "settling_ns": max(analytical_settling, victim_observed["settling_ns"]),
                "delay_error_ns": max(analytical_delay, victim_observed["delay_error_ns"]),
            }
            limit_keys = {
                "peak_glitch_mV": "max_glitch_mV",
                "settling_ns": "max_settling_ns",
                "delay_error_ns": "max_delay_error_ns",
            }
            for metric, value in checks.items():
                limit_key = limit_keys[metric]
                if value > normalized_limits[limit_key]:
                    report["violations"].append(
                        f"{label} {metric}={value:g} exceeds {limit_key}={normalized_limits[limit_key]:g}"
                    )
            if victim_observed["functional_error_mV"] > normalized_limits["max_functional_error_mV"]:
                report["violations"].append(
                    f"{label} functional_error_mV={victim_observed['functional_error_mV']:g} exceeds "
                    f"max_functional_error_mV={normalized_limits['max_functional_error_mV']:g}"
                )
    if errors:
        return "INVALID", errors, report
    if report["violations"]:
        return "FAIL", [], report
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
