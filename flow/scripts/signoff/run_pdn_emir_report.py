#!/usr/bin/env python3
"""Generate bounded engineering PDN/EMIR evidence for the TR-1um flow.

This runner reports the explicit post-streamout GND bridge estimate, the
nominal static-power observation, PDNSim failure diagnostics, and the state of
other digital configurations.  It never converts engineering estimates into
signoff closure: missing worst-case current envelopes, voltage-source
locations, qualified resistance, or EM limits keep the result
``ENGINEERING_ONLY``.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


NUMBER_RE = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
TOTAL_POWER_RE = re.compile(
    rf"(?im)^\s*Total\s+({NUMBER_RE})\s+({NUMBER_RE})\s+({NUMBER_RE})\s+({NUMBER_RE})\s+"
)
DATABASE_RE = re.compile(r"(?im)^\s*UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;")
SPECIALNETS_RE = re.compile(r"(?ms)^\s*SPECIALNETS\s+\d+\s*;(?P<body>.*?)^\s*END SPECIALNETS")


class ReportError(RuntimeError):
    """A report input is malformed or unavailable."""


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def resolve(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()


def repo_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReportError(f"{label} must be a JSON object: {path}")
    return value


def input_record(path: Path | None, root: Path, label: str) -> dict[str, Any]:
    record: dict[str, Any] = {"label": label, "path": repo_path(path, root) if path else None}
    record["exists"] = bool(path and (path.is_file() or path.is_dir()))
    if path and path.is_file():
        record["size_bytes"] = path.stat().st_size
    return record


def bridge_estimate(contract: dict[str, Any], rc_model: dict[str, Any]) -> dict[str, Any]:
    return_path = contract.get("return_path")
    bridge = return_path.get("bridge_path") if isinstance(return_path, dict) else None
    if not isinstance(bridge, dict):
        raise ReportError("return_path.bridge_path is required")
    points = bridge.get("points_dbu")
    if not isinstance(points, list) or len(points) < 2:
        raise ReportError("return_path.bridge_path.points_dbu must contain two or more points")
    if not all(
        isinstance(point, list)
        and len(point) == 2
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in point)
        for point in points
    ):
        raise ReportError("bridge points must be numeric [x, y] pairs")
    dbu_per_um = bridge.get("dbu_per_um")
    width_dbu = bridge.get("width_dbu")
    if not finite_number(dbu_per_um) or float(dbu_per_um) <= 0:
        raise ReportError("bridge_path.dbu_per_um must be positive")
    if not finite_number(width_dbu) or float(width_dbu) <= 0:
        raise ReportError("bridge_path.width_dbu must be positive")
    length_segments_dbu = [
        abs(float(points[index + 1][0]) - float(points[index][0]))
        + abs(float(points[index + 1][1]) - float(points[index][1]))
        for index in range(len(points) - 1)
    ]
    length_um = sum(length_segments_dbu) / float(dbu_per_um)
    width_um = float(width_dbu) / float(dbu_per_um)
    layers = list(rc_model.get("layers", [])) + list(rc_model.get("reserved_layers", []))
    layer_name = bridge.get("layer")
    layer = next((item for item in layers if isinstance(item, dict) and item.get("layer") == layer_name), None)
    if not isinstance(layer, dict):
        raise ReportError(f"RC model has no layer entry for {layer_name!r}")
    sheet = layer.get("sheet_resistance_ohm_per_square")
    spread = rc_model.get("method", {}).get("sheet_resistance_relative_spread")
    if not finite_number(sheet) or not finite_number(spread) or float(sheet) < 0 or not 0 <= float(spread) < 1:
        raise ReportError("RC model lacks a valid sheet resistance or sensitivity spread")
    nominal = float(sheet) * length_um / width_um
    segments = []
    for length_dbu in length_segments_dbu:
        segment_um = length_dbu / float(dbu_per_um)
        segments.append(
            {
                "length_um": segment_um,
                "nominal_resistance_ohm": float(sheet) * segment_um / width_um,
            }
        )
    return {
        "layer": layer_name,
        "width_um": width_um,
        "length_um": length_um,
        "nominal_resistance_ohm": nominal,
        "sensitivity_band_ohm": [nominal * (1.0 - float(spread)), nominal * (1.0 + float(spread))],
        "sheet_resistance_ohm_per_square": float(sheet),
        "relative_spread": float(spread),
        "segments": segments,
        "basis": "R = sheet resistance * Manhattan length / bridge width; engineering sensitivity only",
    }


def parse_def(def_path: Path, net_name: str) -> dict[str, Any]:
    text = def_path.read_text(encoding="utf-8", errors="replace")
    units = DATABASE_RE.search(text)
    if not units:
        raise ReportError(f"DEF database units are missing: {def_path}")
    match = SPECIALNETS_RE.search(text)
    if not match:
        raise ReportError(f"DEF SPECIALNETS section is missing: {def_path}")
    body = match.group("body")
    net_match = re.search(
        rf"(?ms)^\s*-\s+{re.escape(net_name)}\b(?P<block>.*?)(?=^\s*-\s+\S+\b|\Z)",
        body,
    )
    block = net_match.group("block") if net_match else ""
    route_records = re.findall(r"(?im)^\s+(?:ROUTED|NEW)\b", block)
    return {
        "database_microns": int(units.group(1)),
        "specialnet_present": bool(net_match),
        "route_record_count": len(route_records),
        "has_routed_geometry": bool(route_records),
        "note": "The post-streamout GDS bridge is not serialized into this pre-bridge DEF." if not route_records else None,
    }


def parse_power(power_report: Path, voltage_v: float) -> dict[str, Any]:
    text = power_report.read_text(encoding="utf-8", errors="replace")
    match = TOTAL_POWER_RE.search(text)
    if not match:
        raise ReportError(f"Total power row is missing: {power_report}")
    internal, switching, leakage, total = (float(value) for value in match.groups())
    if voltage_v <= 0:
        raise ReportError("nominal voltage must be positive")
    return {
        "internal_power_w": internal,
        "switching_power_w": switching,
        "leakage_power_w": leakage,
        "total_power_w": total,
        "static_leakage_current_mA": leakage / voltage_v * 1000.0,
        "voltage_v": voltage_v,
        "basis": "nominal OpenROAD static-power observation; not a worst-case activity envelope",
    }


def parse_pdn_log(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    codes = sorted(set(re.findall(r"PSM-\d+", text)))
    return {
        "status": "FAIL" if codes or "failed with the following errors" in text else "NO_FAILURE_RECORDED",
        "error_codes": codes,
        "vsrc_warning": "VSRC_LOC_FILES" in text and "was not given" in text,
        "contains_numeric_ir_result": all(token in text for token in ("Worstcase voltage", "Average IR drop", "Worstcase IR drop")),
    }


def bool_config(text: str, key: str) -> bool | None:
    match = re.search(rf"(?im)^\s*{re.escape(key)}\s*:\s*(true|false)\s*(?:#.*)?$", text)
    return None if not match else match.group(1).lower() == "true"


def digital_inventory(design_root: Path, root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not design_root.is_dir():
        return records
    for design in sorted(design_root.glob("tr1um_*/")):
        if design.name in {"tr1um_counter", "tr1um_mixed_counter"}:
            continue
        config = design / "config_access.yaml"
        if not config.is_file():
            continue
        text = config.read_text(encoding="utf-8", errors="replace")
        records.append(
            {
                "design": design.name,
                "config": repo_path(config, root),
                "run_pdn": bool_config(text, "RUN_PDN"),
                "run_irdrop_report": bool_config(text, "RUN_IRDROP_REPORT"),
                "irdrop_step_substituted": bool(re.search(r"(?im)^\s*OpenROAD\.IRDropReport:\s*null\s*$", text)),
                "pdn_step_enabled_by_default": bool_config(text, "RUN_PDN") is True,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    base = contract_path.parent
    root = Path(__file__).resolve().parents[3]
    contract = load_json(contract_path, "PDN contract")
    inputs = contract.get("analysis_inputs")
    if not isinstance(inputs, dict):
        raise SystemExit("ERROR: analysis_inputs is required in the PDN contract")
    resolved = {key: resolve(base, value) for key, value in inputs.items()}
    rc_model_path = resolved.get("rc_model")
    if rc_model_path is None or not rc_model_path.is_file():
        raise SystemExit(f"ERROR: missing RC model: {rc_model_path}")
    rc_model = load_json(rc_model_path, "RC model")
    electrical_limits_path = resolved.get("electrical_limits")
    electrical_limits = (
        load_json(electrical_limits_path, "electrical limits")
        if electrical_limits_path and electrical_limits_path.is_file()
        else {}
    )
    errors: list[str] = []
    for key, path in resolved.items():
        if path is None or not (path.is_file() or path.is_dir()) or (path.is_file() and path.stat().st_size == 0):
            errors.append(f"missing or empty analysis input {key}: {path}")
    try:
        bridge = bridge_estimate(contract, rc_model)
    except ReportError as exc:
        errors.append(str(exc))
        bridge = None
    try:
        def_observation = parse_def(resolved["canonical_def"], "GND") if resolved.get("canonical_def") else {}
    except (ReportError, OSError) as exc:
        errors.append(str(exc))
        def_observation = {}
    try:
        power = parse_power(resolved["canonical_power_report"], float(contract.get("source_assumptions", {}).get("nominal_voltage_V", 0.0))) if resolved.get("canonical_power_report") else {}
    except (ReportError, OSError, ValueError) as exc:
        errors.append(str(exc))
        power = {}
    try:
        pdnsim = parse_pdn_log(resolved["powered_pdn_experiment_log"]) if resolved.get("powered_pdn_experiment_log") else {}
    except OSError as exc:
        errors.append(str(exc))
        pdnsim = {}
    try:
        alu8_pdn = parse_pdn_log(resolved["digital_alu8_pdn_log"]) if resolved.get("digital_alu8_pdn_log") else {}
    except OSError as exc:
        errors.append(str(exc))
        alu8_pdn = {}
    uart_pdn = {
        "status": "FAIL",
        "error_codes": ["PSM-0038", "PSM-0039", "PSM-0069"],
        "evidence": repo_path(resolved["digital_uart_pdn_probe_note"], root)
        if resolved.get("digital_uart_pdn_probe_note")
        else None,
        "basis": "Saved OpenROAD probe note for the connected-power DEF; no numeric IR-drop result is accepted.",
    }
    design_root = resolved.get("digital_design_root")
    inventory = digital_inventory(design_root, root) if design_root else []
    output = {
        "schema_version": 1,
        "status": "ENGINEERING_ONLY",
        "design": contract.get("design"),
        "scope": contract.get("analysis_scope"),
        "generated_by": "flow/scripts/signoff/run_pdn_emir_report.py",
        "inputs": {key: input_record(path, root, key) for key, path in resolved.items()},
        "reference_limits": {
            "status": electrical_limits.get("status"),
            "source": electrical_limits.get("source"),
            "interconnect_limits": electrical_limits.get("interconnect_limits"),
            "qualification_boundary": electrical_limits.get("interpretation", {}).get("qualification_boundary"),
        },
        "bridge_estimate": bridge,
        "canonical_def_observation": def_observation,
        "nominal_power_observation": power,
        "powered_pdn_experiment": pdnsim,
        "digital_pdn_experiments": {
            "tr1um_alu8_enabled_pdn": alu8_pdn,
            "tr1um_uarttx_big_connected_power": uart_pdn,
        },
        "digital_design_inventory": inventory,
        "limitations": [
            "The analog leaf has no VDD pin or powered macro PG geometry, so powered PDNSim is not applicable to that leaf.",
            "The canonical mixed-counter DEF predates the post-streamout GND bridge; the bridge is evidenced by GDS geometry and estimated resistance only.",
            "The nominal leakage result is not a worst-case switching/current envelope and cannot establish ground bounce or EM margin.",
            "The available powered-core and UART connected-power PDNSim probes fail connectivity checks; no numeric IR-drop result is accepted as closure.",
            "The electrical limits and via resistance are engineering estimates, not foundry-qualified limits or parasitic extraction.",
        ],
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
