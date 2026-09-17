#!/usr/bin/env python3
"""Check a bounded analog latch-up safeguards contract.

This is an evidence gate, not a latch-up simulator.  It requires the process
well/substrate topology, tap and guard-ring evidence, injection assumptions,
and explicit I/O/ESD interaction paths before reporting PASS.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TOPOLOGY_KEYS = ("substrate", "well_type", "isolation_strategy", "guard_ring_strategy")
LIMIT_KEYS = (
    "max_guard_resistance_ohm",
    "max_substrate_resistance_ohm",
    "max_injected_current_mA",
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read latch-up contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: latch-up contract must be a JSON object")
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
        "violations": [],
        "taps": [],
        "injection_paths": [],
        "io_esd_interactions": [],
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

    topology = contract.get("topology")
    normalized_topology: dict[str, str] = {}
    if not isinstance(topology, dict):
        errors.append("topology must be an object")
        topology = {}
    for key in TOPOLOGY_KEYS:
        value = required_text(topology, key, "topology", errors)
        if value is not None:
            normalized_topology[key] = value
    report["topology"] = normalized_topology

    limits = contract.get("limits")
    normalized_limits: dict[str, float] = {}
    if not isinstance(limits, dict):
        errors.append("limits must be an object")
        limits = {}
    for key in LIMIT_KEYS:
        value = limits.get(key)
        if not positive_number(value):
            errors.append(f"limits.{key} must be finite and positive")
        else:
            normalized_limits[key] = float(value)
    report["limits"] = normalized_limits

    taps = contract.get("taps")
    if not isinstance(taps, list) or not taps:
        errors.append("taps must be a non-empty list")
        taps = []
    for index, tap in enumerate(taps):
        label = f"taps[{index}]"
        if not isinstance(tap, dict):
            errors.append(f"{label} must be an object")
            continue
        name = required_text(tap, "name", label, errors)
        region = required_text(tap, "region", label, errors)
        kind = tap.get("resistance_kind")
        if kind not in {"guard", "substrate"}:
            errors.append(f"{label}.resistance_kind must be guard or substrate")
        count = tap.get("count")
        if not positive_integer(count):
            errors.append(f"{label}.count must be a positive integer")
        continuity_errors, continuity = evidence_errors(base, tap.get("continuity_evidence"), f"{label}.continuity_evidence")
        resistance_errors, resistance = evidence_errors(base, tap.get("resistance_evidence"), f"{label}.resistance_evidence")
        errors.extend(continuity_errors)
        errors.extend(resistance_errors)
        measured = tap.get("measured_resistance_ohm")
        if not nonnegative_number(measured):
            errors.append(f"{label}.measured_resistance_ohm must be finite and non-negative")
        else:
            limit_key = "max_guard_resistance_ohm" if kind == "guard" else "max_substrate_resistance_ohm"
            if limit_key in normalized_limits and float(measured) > normalized_limits[limit_key]:
                report["violations"].append(
                    f"{label} measured_resistance_ohm={float(measured):g} exceeds "
                    f"{limit_key}={normalized_limits[limit_key]:g}"
                )
        report["taps"].append(
            {
                "name": name,
                "region": region,
                "resistance_kind": kind,
                "count": count,
                "measured_resistance_ohm": float(measured) if nonnegative_number(measured) else measured,
                "continuity_evidence": continuity,
                "resistance_evidence": resistance,
            }
        )

    injections = contract.get("injection_paths")
    if not isinstance(injections, list) or not injections:
        errors.append("injection_paths must be a non-empty list")
        injections = []
    for index, path in enumerate(injections):
        label = f"injection_paths[{index}]"
        if not isinstance(path, dict):
            errors.append(f"{label} must be an object")
            continue
        name = required_text(path, "name", label, errors)
        source = required_text(path, "source", label, errors)
        destination = required_text(path, "destination", label, errors)
        polarity = required_text(path, "polarity", label, errors)
        peak_current = path.get("peak_current_mA")
        duration = path.get("duration_us")
        if not positive_number(peak_current):
            errors.append(f"{label}.peak_current_mA must be finite and positive")
        elif "max_injected_current_mA" in normalized_limits and float(peak_current) > normalized_limits["max_injected_current_mA"]:
            report["violations"].append(
                f"{label} peak_current_mA={float(peak_current):g} exceeds "
                f"max_injected_current_mA={normalized_limits['max_injected_current_mA']:g}"
            )
        if not positive_number(duration):
            errors.append(f"{label}.duration_us must be finite and positive")
        path_errors, resolved = evidence_errors(base, path.get("evidence"), f"{label}.evidence")
        errors.extend(path_errors)
        report["injection_paths"].append(
            {
                "name": name,
                "source": source,
                "destination": destination,
                "polarity": polarity,
                "peak_current_mA": float(peak_current) if positive_number(peak_current) else peak_current,
                "duration_us": float(duration) if positive_number(duration) else duration,
                "evidence": resolved,
            }
        )

    io_paths = contract.get("io_esd_interactions")
    if not isinstance(io_paths, list) or not io_paths:
        errors.append("io_esd_interactions must be a non-empty list")
        io_paths = []
    for index, interaction in enumerate(io_paths):
        label = f"io_esd_interactions[{index}]"
        if not isinstance(interaction, dict):
            errors.append(f"{label} must be an object")
            continue
        for key in ("pad", "positive_path", "negative_path", "well_or_guard"):
            required_text(interaction, key, label, errors)
        path_errors, resolved = evidence_errors(base, interaction.get("evidence"), f"{label}.evidence")
        errors.extend(path_errors)
        report["io_esd_interactions"].append({"pad": interaction.get("pad"), "evidence": resolved})

    assumptions = contract.get("substrate_current_assumptions")
    if not isinstance(assumptions, dict):
        errors.append("substrate_current_assumptions must be an object")
        assumptions = {}
    required_text(assumptions, "basis", "substrate_current_assumptions", errors)
    expected = assumptions.get("max_expected_current_mA")
    if not nonnegative_number(expected):
        errors.append("substrate_current_assumptions.max_expected_current_mA must be finite and non-negative")
    elif "max_injected_current_mA" in normalized_limits and float(expected) > normalized_limits["max_injected_current_mA"]:
        report["violations"].append(
            "substrate_current_assumptions.max_expected_current_mA exceeds max_injected_current_mA"
        )
    assumption_errors, assumption_evidence = evidence_errors(
        base, assumptions.get("evidence"), "substrate_current_assumptions.evidence"
    )
    errors.extend(assumption_errors)
    report["substrate_current_assumptions"] = {
        "basis": assumptions.get("basis"),
        "max_expected_current_mA": float(expected) if nonnegative_number(expected) else expected,
        "evidence": assumption_evidence,
    }

    if errors:
        scope_incomplete = not isinstance(contract.get("evidence"), list) or not contract.get("evidence")
        return ("BLOCKED" if scope_incomplete and applicable is True else "INVALID"), errors, report
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
