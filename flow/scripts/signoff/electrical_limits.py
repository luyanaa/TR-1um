"""Load and validate the repository's machine-readable electrical limits."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def positive_number(value: Any) -> bool:
    return finite_number(value) and float(value) > 0.0


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read electrical limits contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"ERROR: electrical limits contract must be a JSON object: {path}")
    return value


def _require_finite(obj: dict[str, Any], key: str, label: str, errors: list[str]) -> None:
    if not finite_number(obj.get(key)) or float(obj[key]) == 0.0:
        errors.append(f"{label}.{key} must be finite and non-zero")


def _require_positive(obj: dict[str, Any], key: str, label: str, errors: list[str]) -> None:
    if not positive_number(obj.get(key)):
        errors.append(f"{label}.{key} must be finite and positive")


def _require_text(obj: dict[str, Any], key: str, label: str, errors: list[str]) -> None:
    if not nonempty_string(obj.get(key)):
        errors.append(f"{label}.{key} must be a non-empty string")


def validate(contract: dict[str, Any], base: Path) -> list[str]:
    """Return schema, provenance, and safety-contract errors."""
    errors: list[str] = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    _require_text(contract, "technology", "contract", errors)
    if contract.get("status") not in {"engineering_only", "qualified"}:
        errors.append("status must be engineering_only or qualified")

    source = contract.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    manual_path = source.get("manual_path")
    if not nonempty_string(manual_path):
        errors.append("source.manual_path must be a non-empty path")
    else:
        resolved = Path(manual_path)
        resolved = resolved if resolved.is_absolute() else (base / resolved).resolve()
        if not resolved.is_file() or resolved.stat().st_size == 0:
            errors.append(f"missing or empty source.manual_path: {resolved}")
    _require_text(source, "manual_revision", "source", errors)
    pages = source.get("pages")
    if not isinstance(pages, dict) or not pages:
        errors.append("source.pages must be a non-empty object")
    else:
        for name, page in pages.items():
            if not isinstance(name, str) or not name or not isinstance(page, int) or isinstance(page, bool) or page <= 0:
                errors.append(f"source.pages.{name} must be a positive integer")
    tables = source.get("tables")
    if not isinstance(tables, list) or not tables or not all(nonempty_string(item) for item in tables):
        errors.append("source.tables must be a non-empty list of table names")

    interpretation = contract.get("interpretation")
    if not isinstance(interpretation, dict):
        errors.append("interpretation must be an object")
        interpretation = {}
    if interpretation.get("values_are_absolute_maxima") is not True:
        errors.append("interpretation.values_are_absolute_maxima must be true")
    if interpretation.get("simulation_margin_required") is not True:
        errors.append("interpretation.simulation_margin_required must be true")
    if interpretation.get("unknown_values") != "fail_closed":
        errors.append("interpretation.unknown_values must be fail_closed")
    if interpretation.get("width_policy") != "exact_reference_width_only":
        errors.append("interpretation.width_policy must be exact_reference_width_only")
    _require_text(interpretation, "qualification_boundary", "interpretation", errors)
    _require_text(interpretation, "current_width_screening", "interpretation", errors)
    markers = contract.get("layout_markers")
    if not isinstance(markers, dict):
        errors.append("layout_markers must be an object")
        markers = {}
    marker_layers: set[tuple[int, int]] = set()
    for name in ("v15_marker", "v27_marker"):
        marker = markers.get(name)
        label = f"layout_markers.{name}"
        if not isinstance(marker, dict):
            errors.append(f"{label} must be an object")
            continue
        layer = marker.get("gds_layer")
        datatype = marker.get("datatype")
        if not isinstance(layer, int) or isinstance(layer, bool) or layer < 0:
            errors.append(f"{label}.gds_layer must be a non-negative integer")
        if not isinstance(datatype, int) or isinstance(datatype, bool) or datatype < 0:
            errors.append(f"{label}.datatype must be a non-negative integer")
        if isinstance(layer, int) and not isinstance(layer, bool) and layer >= 0 and isinstance(datatype, int) and not isinstance(datatype, bool) and datatype >= 0:
            pair = (layer, datatype)
            if pair in marker_layers:
                errors.append(f"{label} duplicates another marker layer")
            marker_layers.add(pair)
        _require_text(marker, "semantics", label, errors)
    if markers.get("status") != "engineering_only":
        errors.append("layout_markers.status must be engineering_only")

    devices = contract.get("device_limits")
    if not isinstance(devices, dict):
        errors.append("device_limits must be an object")
        devices = {}
    for name, keys in {
        "mos_5v_nmos": ("vds_abs_max_v", "vgs_abs_max_v"),
        "mos_5v_pmos": ("vds_abs_max_v", "vgs_abs_max_v"),
        "rr": (
            "terminal_to_terminal_abs_max_v",
            "terminal_to_terminal_reverse_abs_max_v",
            "island_to_pwell_abs_max_v",
        ),
        "rs": ("terminal_to_terminal_abs_max_v", "current_abs_max_a"),
        "c": ("upper_to_lower_abs_max_v", "lower_to_pwell_abs_max_v"),
        "dp": ("reverse_abs_max_v",),
        "dn": ("reverse_abs_max_v",),
    }.items():
        item = devices.get(name)
        if not isinstance(item, dict):
            errors.append(f"device_limits.{name} must be an object")
            continue
        for key in keys:
            _require_positive(item, key, f"device_limits.{name}", errors)
        if name in {"mos_5v_nmos", "mos_5v_pmos"}:
            expected_signed = (
                {"manual_bvds_v": 8.0, "manual_bvgs_v": 15.0}
                if name == "mos_5v_nmos"
                else {"manual_bvds_v": -8.0, "manual_bvgs_v": -15.0}
            )
            for key, expected in expected_signed.items():
                _require_finite(item, key, f"device_limits.{name}", errors)
                if finite_number(item.get(key)) and float(item[key]) != expected:
                    errors.append(
                        f"device_limits.{name}.{key} must equal manual value {expected:g}"
                    )
            for abs_key, signed_key in (
                ("vds_abs_max_v", "manual_bvds_v"),
                ("vgs_abs_max_v", "manual_bvgs_v"),
            ):
                if finite_number(item.get(abs_key)) and finite_number(item.get(signed_key)):
                    if float(item[abs_key]) != abs(float(item[signed_key])):
                        errors.append(
                            f"device_limits.{name}.{abs_key} must equal abs({signed_key})"
                        )
    rr = devices.get("rr")
    if isinstance(rr, dict):
        if rr.get("island_to_terminal_lower_abs_max_v") is not None:
            errors.append("device_limits.rr.island_to_terminal_lower_abs_max_v must remain null because it is non-public")
        if rr.get("island_to_terminal_lower_status") != "non_public":
            errors.append("device_limits.rr.island_to_terminal_lower_status must be non_public")

    characterization = contract.get("model_characterization")
    if not isinstance(characterization, dict):
        errors.append("model_characterization must be an object")
        characterization = {}
    csio = characterization.get("csio")
    if not isinstance(csio, dict):
        errors.append("model_characterization.csio must be an object")
    else:
        for key in ("terminal_to_terminal_abs_max_v", "terminal_to_terminal_reverse_abs_max_v"):
            _require_positive(csio, key, "model_characterization.csio", errors)
        _require_text(csio, "note", "model_characterization.csio", errors)

    interconnect = contract.get("interconnect_limits")
    if not isinstance(interconnect, dict):
        errors.append("interconnect_limits must be an object")
        interconnect = {}
    metal = interconnect.get("metal")
    if not isinstance(metal, dict):
        errors.append("interconnect_limits.metal must be an object")
        metal = {}
    for layer in ("M1", "M2"):
        item = metal.get(layer)
        if not isinstance(item, dict):
            errors.append(f"interconnect_limits.metal.{layer} must be an object")
            continue
        _require_positive(item, "reference_width_um", f"interconnect_limits.metal.{layer}", errors)
        _require_positive(item, "max_current_a", f"interconnect_limits.metal.{layer}", errors)
        _require_text(item, "basis", f"interconnect_limits.metal.{layer}", errors)
        _require_positive(item, "current_density_a_per_um", f"interconnect_limits.metal.{layer}", errors)
        if positive_number(item.get("reference_width_um")) and positive_number(item.get("max_current_a")) and positive_number(item.get("current_density_a_per_um")):
            expected_density = float(item["max_current_a"]) / float(item["reference_width_um"])
            if not math.isclose(float(item["current_density_a_per_um"]), expected_density, rel_tol=0.0, abs_tol=1.0e-15):
                errors.append(
                    f"interconnect_limits.metal.{layer}.current_density_a_per_um must equal "
                    "max_current_a/reference_width_um"
                )
    steps = interconnect.get("steps")
    if not isinstance(steps, dict):
        errors.append("interconnect_limits.steps must be an object")
        steps = {}
    step = steps.get("M1")
    if not isinstance(step, dict):
        errors.append("interconnect_limits.steps.M1 must be an object")
    else:
        _require_positive(step, "reference_width_um", "interconnect_limits.steps.M1", errors)
        _require_positive(step, "max_current_a", "interconnect_limits.steps.M1", errors)
        _require_text(step, "basis", "interconnect_limits.steps.M1", errors)
        _require_positive(step, "j_max_step_coverage_a_per_um", "interconnect_limits.steps.M1", errors)
        if positive_number(step.get("reference_width_um")) and positive_number(step.get("max_current_a")) and positive_number(step.get("j_max_step_coverage_a_per_um")):
            expected_density = float(step["max_current_a"]) / float(step["reference_width_um"])
            if not math.isclose(float(step["j_max_step_coverage_a_per_um"]), expected_density, rel_tol=0.0, abs_tol=1.0e-15):
                errors.append(
                    "interconnect_limits.steps.M1.j_max_step_coverage_a_per_um must equal "
                    "max_current_a/reference_width_um"
                )
    contacts = interconnect.get("contacts")
    if not isinstance(contacts, dict):
        errors.append("interconnect_limits.contacts must be an object")
        contacts = {}
    tc = contacts.get("TC")
    if not isinstance(tc, dict):
        errors.append("interconnect_limits.contacts.TC must be an object")
    else:
        _require_positive(tc, "reference_size_um", "interconnect_limits.contacts.TC", errors)
        _require_positive(tc, "max_current_a_per_contact", "interconnect_limits.contacts.TC", errors)
        _require_positive(
            tc,
            "instantaneous_max_current_a_per_contact",
            "interconnect_limits.contacts.TC",
            errors,
        )
        _require_text(tc, "basis", "interconnect_limits.contacts.TC", errors)
    return errors


def load_and_validate(path: Path) -> tuple[dict[str, Any], list[str]]:
    contract = load(path)
    return contract, validate(contract, path.parent)


def resolve_limit(contract: dict[str, Any], reference: str) -> tuple[float | None, str | None]:
    """Resolve a dotted limit reference to a finite positive number."""
    if not nonempty_string(reference):
        return None, "limit reference must be a non-empty dotted path"
    value: Any = contract
    for part in reference.split("."):
        if not part or not isinstance(value, dict) or part not in value:
            return None, f"unknown limit reference: {reference}"
        value = value[part]
    if not positive_number(value):
        return None, f"limit reference is not a finite positive number: {reference}"
    return float(value), None
