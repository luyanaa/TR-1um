#!/usr/bin/env python3
"""Audit temperature behavior and characterization coverage of SPICE models.

The audit distinguishes simulator temperature parameters from qualified
characterization.  A token such as ``tnom`` does not by itself prove a model
is valid over the product temperature range.  Scoped model blocks, source
files, characterization ranges, and manual/figure evidence are reported
explicitly so missing temperature behavior remains a release blocker.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
BEHAVIORS = {"explicit", "implicit", "nominal_only", "missing", "unsupported"}
TEMPERATURE_POLICIES = {"blocker", "warning_only"}
NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read temperature model contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit("ERROR: temperature model contract must be a JSON object")
    return value


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def parse_range(value: Any, label: str) -> tuple[list[float] | None, str | None]:
    if not isinstance(value, list) or len(value) != 2:
        return None, f"{label} must be [min, max]"
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in value):
        return None, f"{label} must contain finite numbers"
    low, high = float(value[0]), float(value[1])
    if low > high:
        return None, f"{label} minimum exceeds maximum"
    return [low, high], None


def extract_scope(text: str, start: Any, end: Any) -> tuple[str | None, str | None]:
    if not isinstance(start, str) or not start:
        return None, "scope_start is required"
    start_index = text.lower().find(start.lower())
    if start_index < 0:
        return None, f"scope_start not found: {start}"
    end_index = len(text)
    if isinstance(end, str) and end:
        candidate = text.lower().find(end.lower(), start_index + len(start))
        if candidate < 0:
            return None, f"scope_end not found: {end}"
        end_index = candidate + len(end)
    return text[start_index:end_index], None


def token_present(scope: str, token: str) -> bool:
    try:
        return re.search(token, scope, re.IGNORECASE | re.MULTILINE) is not None
    except re.error as exc:
        raise ValueError(f"invalid temperature token regex {token!r}: {exc}") from exc


def numeric_assignments(scope: str, token: str) -> list[float]:
    pattern = rf"\b{re.escape(token)}\s*=\s*({NUMBER_RE})"
    return [float(value) for value in re.findall(pattern, scope, re.IGNORECASE)]


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def audit_reference_temperature(contract: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    reconciliation = contract.get("reference_temperature_reconciliation")
    result: dict[str, Any] = {
        "status": "INCOMPLETE",
        "model_reference_c": None,
        "manual_model_reference_c": None,
        "manual_measurement_c": None,
        "manual_guaranteed_operating_range_c": None,
        "manual_guarantee_scope": None,
        "resolution": None,
        "errors": [],
    }

    if not isinstance(reconciliation, dict):
        message = "reference_temperature_reconciliation is required"
        errors.append(message)
        result["errors"].append(message)
        return result
    result["model_reference_c"] = reconciliation.get("model_reference_c")
    result["manual_model_reference_c"] = reconciliation.get("manual_model_reference_c")
    result["manual_measurement_c"] = reconciliation.get("manual_measurement_c")
    result["manual_guarantee_scope"] = reconciliation.get("manual_guarantee_scope")
    if not isinstance(result["manual_guarantee_scope"], str) or not result["manual_guarantee_scope"].strip():
        message = "reference_temperature_reconciliation.manual_guarantee_scope must be non-empty"
        errors.append(message)
        result["errors"].append(message)
    result["resolution"] = reconciliation.get("resolution")
    manual_range, range_error = parse_range(
        reconciliation.get("manual_guaranteed_operating_range_c"),
        "reference_temperature_reconciliation.manual_guaranteed_operating_range_c",
    )
    if range_error:
        errors.append(range_error)
        result["errors"].append(range_error)
    result["manual_guaranteed_operating_range_c"] = manual_range
    for field in ("model_reference_c", "manual_model_reference_c", "manual_measurement_c"):
        if not finite_number(result[field]):
            message = f"reference_temperature_reconciliation.{field} must be finite"
            errors.append(message)
            result["errors"].append(message)
    if isinstance(result["model_reference_c"], (int, float)) and isinstance(
        result["manual_model_reference_c"], (int, float)
    ) and not math.isclose(float(result["model_reference_c"]), float(result["manual_model_reference_c"]), abs_tol=1e-9):
        message = "model and manual model reference temperatures disagree"
        errors.append(message)
        result["errors"].append(message)
    if reconciliation.get("status") != "reconciled":
        message = "reference_temperature_reconciliation.status must be reconciled"
        errors.append(message)
        result["errors"].append(message)
    if not isinstance(result["resolution"], str) or not result["resolution"].strip():
        message = "reference_temperature_reconciliation.resolution must be non-empty"
        errors.append(message)
        result["errors"].append(message)
    if not result["errors"]:
        result["status"] = "PASS"
    return result


def audit(contract: dict[str, Any], contract_path: Path) -> dict[str, Any]:
    base = contract_path.parent
    errors: list[str] = []
    operating_range, range_error = parse_range(contract.get("operating_range_c"), "operating_range_c")
    if range_error:
        errors.append(range_error)
    rs_range, range_error = parse_range(contract.get("rs_characterization_range_c"), "rs_characterization_range_c")
    if range_error:
        errors.append(range_error)
    reference_temperature = audit_reference_temperature(contract, errors)
    manual_operating_range = reference_temperature.get("manual_guaranteed_operating_range_c")
    if operating_range is not None and isinstance(manual_operating_range, list):
        if manual_operating_range[0] > operating_range[0] or manual_operating_range[1] < operating_range[1]:
            errors.append(
                f"manual guaranteed range {manual_operating_range}C does not cover operating range {operating_range}C"
            )

    validation_temperatures = contract.get("validation_temperatures_c")
    if not isinstance(validation_temperatures, list) or not validation_temperatures:
        errors.append("validation_temperatures_c must be a non-empty list")
        validation_temperatures = []
    elif not all(finite_number(item) for item in validation_temperatures):
        errors.append("validation_temperatures_c values must be finite numbers")
        validation_temperatures = []
    else:
        validation_temperatures = [float(item) for item in validation_temperatures]
        if operating_range is not None:
            outside = [item for item in validation_temperatures if not operating_range[0] <= item <= operating_range[1]]
            if outside:
                errors.append(f"validation temperatures outside operating range: {outside}C")

    model_reference = reference_temperature.get("model_reference_c")

    models = contract.get("models")
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty list")
        models = []
    manual_evidence: list[dict[str, Any]] = []
    for index, item in enumerate(contract.get("manual_evidence", [])):
        if not isinstance(item, dict):
            errors.append(f"manual_evidence[{index}] must be an object")
            continue
        path = resolve(base, item.get("path"))
        entry = {"path": str(path) if path else item.get("path"), "location": item.get("location"), "claim": item.get("claim")}
        if path is None or not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty manual_evidence[{index}]: {path or item.get('path')}")
            entry["exists_nonempty"] = False
        else:
            entry["exists_nonempty"] = True
        manual_evidence.append(entry)
    findings: list[dict[str, Any]] = []
    for index, item in enumerate(models):
        prefix = f"models[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = item.get("name")
        path = resolve(base, item.get("path"))
        temperature_policy = item.get("temperature_policy", "blocker")
        finding: dict[str, Any] = {
            "name": name,
            "path": str(path) if path else item.get("path"),
            "behavior": item.get("behavior"),
            "temperature_policy": temperature_policy,
        }
        model_errors: list[str] = []
        if not isinstance(name, str) or not name:
            model_errors.append("name is required")
        if path is None or not path.is_file() or path.stat().st_size == 0:
            model_errors.append(f"missing or empty source model: {path or item.get('path')}")
            scope = ""
        else:
            scope, scope_error = extract_scope(
                path.read_text(encoding="utf-8", errors="replace"),
                item.get("scope_start"),
                item.get("scope_end"),
            )
            if scope_error:
                model_errors.append(scope_error)
                scope = ""
        finding["scope_start"] = item.get("scope_start")
        finding["scope_end"] = item.get("scope_end")
        finding["used"] = item.get("used", True)
        source_tnom_values = numeric_assignments(scope, "tnom")
        finding["source_tnom_values_c"] = source_tnom_values
        required_tokens = item.get("required_tokens", [])
        temperature_tokens = item.get("temperature_tokens", [])
        if not isinstance(required_tokens, list) or not all(isinstance(token, str) and token for token in required_tokens):
            model_errors.append("required_tokens must be a list of regex strings")
            required_tokens = []
        if not isinstance(temperature_tokens, list) or not all(isinstance(token, str) and token for token in temperature_tokens):
            model_errors.append("temperature_tokens must be a list of regex strings")
            temperature_tokens = []
        missing_tokens = [token for token in required_tokens if not token_present(scope, token)]
        found_temperature_tokens = [token for token in temperature_tokens if token_present(scope, token)]
        finding["required_tokens"] = required_tokens
        finding["missing_required_tokens"] = missing_tokens
        finding["temperature_tokens_found"] = found_temperature_tokens
        behavior = item.get("behavior")
        if behavior not in BEHAVIORS:
            model_errors.append(f"behavior must be one of {sorted(BEHAVIORS)}")
        if temperature_policy not in TEMPERATURE_POLICIES:
            model_errors.append(f"temperature_policy must be one of {sorted(TEMPERATURE_POLICIES)}")
        if missing_tokens:
            model_errors.append(f"missing required model tokens: {missing_tokens}")
        finding["expected_model_reference_c"] = model_reference
        if finite_number(model_reference):
            if not source_tnom_values:
                model_errors.append("no numeric tnom assignment found in scoped model")
            elif any(not math.isclose(value, float(model_reference), abs_tol=1e-9) for value in source_tnom_values):
                model_errors.append(
                    f"source tnom values {source_tnom_values}C do not match model reference {model_reference}C"
                )

        if behavior in {"explicit", "implicit"} and not found_temperature_tokens:
            model_errors.append("no declared temperature token found in scoped model")
        characterization_range, range_error = parse_range(item.get("characterized_range_c"), f"{prefix}.characterized_range_c")
        if range_error:
            model_errors.append(range_error)
        finding["characterized_range_c"] = characterization_range
        limitations: list[str] = []
        if operating_range is not None and characterization_range is not None:
            if characterization_range[0] > operating_range[0] or characterization_range[1] < operating_range[1]:
                limitations.append(
                    f"characterization {characterization_range}C does not cover operating range {operating_range}C"
                )
        if behavior in {"nominal_only", "missing", "unsupported"}:
            limitations.append(f"temperature behavior is {behavior}")
        finding["limitations"] = limitations
        finding["warnings"] = []
        if model_errors:
            finding["status"] = "INCOMPLETE"
            finding["errors"] = model_errors
        elif limitations and temperature_policy == "warning_only":
            finding["status"] = "PASS_WITH_WARNINGS"
            finding["warnings"] = limitations
            finding["errors"] = []
        elif limitations:
            finding["status"] = "ENGINEERING_ONLY"
            finding["errors"] = []
        else:
            finding["status"] = "PASS"
            finding["errors"] = []
        findings.append(finding)
    if errors:
        overall = "INVALID"
    elif any(finding["status"] == "INCOMPLETE" for finding in findings):
        overall = "INCOMPLETE"
    elif any(finding["status"] == "ENGINEERING_ONLY" for finding in findings):
        overall = "ENGINEERING_ONLY"
    elif any(finding["status"] == "PASS_WITH_WARNINGS" for finding in findings):
        overall = "PASS_WITH_WARNINGS"
    else:
        overall = "PASS"
    warnings = [
        {"name": finding["name"], "messages": finding.get("warnings", [])}
        for finding in findings
        if finding.get("status") == "PASS_WITH_WARNINGS"
    ]
    return {
        "status": overall,
        "contract": str(contract_path),
        "design": contract.get("design"),
        "operating_range_c": operating_range,
        "rs_characterization_range_c": rs_range,
        "rs_extrapolation": contract.get("rs_extrapolation"),
        "validation_temperatures_c": validation_temperatures,
        "reference_temperature_reconciliation": reference_temperature,
        "manual_evidence": manual_evidence,
        "models": findings,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    result = audit(load(contract_path), contract_path)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
