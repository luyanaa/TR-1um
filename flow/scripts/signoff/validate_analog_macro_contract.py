#!/usr/bin/env python3
"""Validate matching physical and logical views for an analog hard macro.

The manifest is the electrical contract.  This checker deliberately does not
infer supply semantics from a cell name or invent missing power pins.  It
checks the exact macro name, pin sets, CDL order, LEF directions, black-box
Verilog directions, and the declared power/ground/body contract.

A structurally valid contract is not a process or performance qualification.
The manifest's qualification status and evidence remain visible in the JSON
report and are evaluated by the top-level signoff manifest gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DIRECTIONS = {"INPUT", "OUTPUT", "INOUT"}
ROLES = {"power", "ground", "signal", "body"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"ERROR: manifest must contain a JSON object: {path}")
    return value


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def parse_lef(path: Path, macro: str) -> tuple[dict[str, str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        rf"(?ims)^\s*MACRO\s+{re.escape(macro)}\s*$.*?^\s*END\s+{re.escape(macro)}\s*$",
        text,
    )
    if match is None:
        raise ValueError(f"LEF has no exact MACRO {macro} declaration")
    block = match.group(0)
    pins: dict[str, str] = {}
    pin_matches = list(re.finditer(r"(?im)^\s*PIN\s+(\S+)\s*$", block))
    for index, pin_match in enumerate(pin_matches):
        name = pin_match.group(1)
        end = pin_matches[index + 1].start() if index + 1 < len(pin_matches) else len(block)
        pin_block = block[pin_match.start() : end]
        direction = re.search(r"(?im)^\s*DIRECTION\s+(INPUT|OUTPUT|INOUT)\s*;", pin_block)
        if direction is None:
            raise ValueError(f"LEF PIN {name} has no INPUT/OUTPUT/INOUT direction")
        pins[name] = direction.group(1).upper()
    return pins, [match.group(1) for match in pin_matches]


def parse_cdl(path: Path, macro: str) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"\s*\.SUBCKT\s+(\S+)(.*)$", line, re.IGNORECASE)
        if match is None or match.group(1).upper() != macro.upper():
            continue
        ports = match.group(2).split()
        cursor = index + 1
        while cursor < len(lines) and re.match(r"\s*\+", lines[cursor]):
            ports.extend(re.sub(r"^\s*\+\s*", "", lines[cursor]).split())
            cursor += 1
        return ports
    raise ValueError(f"CDL has no exact .SUBCKT {macro} declaration")


def parse_blackbox(path: Path, macro: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    module = re.search(
        rf"(?ims)^\s*module\s+{re.escape(macro)}\s*\((.*?)\)\s*;(?P<body>.*?)^\s*endmodule\b",
        text,
    )
    if module is None:
        raise ValueError(f"black-box Verilog has no exact module {macro}")
    declarations: dict[str, str] = {}
    header_ports = module.group(1)
    for declaration in header_ports.split(","):
        fields = declaration.strip().split()
        if not fields or fields[0].upper() not in DIRECTIONS:
            continue
        clean = re.sub(r"\[[^]]+\]", "", fields[-1]).strip()
        if clean:
            declarations[clean] = fields[0].upper()
    body = module.group("body")
    for direction, names in re.findall(
        r"(?im)\b(input|output|inout)\b(?:\s+wire|\s+reg|\s+logic|\s+signed|\s+unsigned)*\s+([^;]+);",
        body,
    ):
        for name in names.split(","):
            clean = re.sub(r"\[[^]]+\]", "", name).strip()
            clean = clean.split()[-1]
            if clean:
                declarations[clean] = direction.upper()
    if not declarations:
        for name in header_ports.split(","):
            clean = name.strip().split()[-1]
            if clean:
                declarations[clean] = "UNKNOWN"
    return declarations


def check_manifest(manifest_path: Path) -> tuple[dict[str, Any], list[str]]:
    manifest = read_json(manifest_path)
    errors: list[str] = []
    warnings: list[str] = []
    base = manifest_path.parent

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    macro = manifest.get("macro")
    if not isinstance(macro, str) or not macro:
        errors.append("macro must be a non-empty string")
        macro = "<missing>"

    views = manifest.get("views")
    if not isinstance(views, dict):
        errors.append("views must be an object with gds, lef, cdl, and blackbox_verilog")
        views = {}
    resolved_views: dict[str, Path] = {}
    for key in ("gds", "lef", "cdl", "blackbox_verilog"):
        value = views.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"views.{key} must be a non-empty path")
            continue
        path = resolve(base, value)
        resolved_views[key] = path
        if not path.is_file():
            errors.append(f"missing {key} view: {path}")
        elif key != "gds" and path.stat().st_size == 0:
            errors.append(f"empty {key} view: {path}")

    pin_order = manifest.get("pin_order")
    if not isinstance(pin_order, list) or not all(isinstance(pin, str) and pin for pin in pin_order):
        errors.append("pin_order must be a non-empty list of pin names")
        pin_order = []
    if len(pin_order) != len(set(pin_order)):
        errors.append("pin_order contains duplicate pin names")

    pin_contract = manifest.get("pins")
    if not isinstance(pin_contract, dict):
        errors.append("pins must be an object keyed by canonical pin name")
        pin_contract = {}
    for pin in pin_order:
        spec = pin_contract.get(pin)
        if not isinstance(spec, dict):
            errors.append(f"pins.{pin} is missing")
            continue
        role = spec.get("role")
        direction = str(spec.get("direction", "")).upper()
        if role not in ROLES:
            errors.append(f"pins.{pin}.role must be one of {sorted(ROLES)}")
        if direction not in DIRECTIONS:
            errors.append(f"pins.{pin}.direction must be one of {sorted(DIRECTIONS)}")
    extra_contract_pins = sorted(set(pin_contract) - set(pin_order))
    if extra_contract_pins:
        errors.append(f"pins contains names absent from pin_order: {extra_contract_pins}")

    electrical = manifest.get("electrical")
    if not isinstance(electrical, dict):
        errors.append("electrical must declare power_pins, ground_pins, and body_substrate_pins")
        electrical = {}
    power = electrical.get("power_pins", [])
    ground = electrical.get("ground_pins", [])
    body = electrical.get("body_substrate_pins", [])
    for label, values in (("power_pins", power), ("ground_pins", ground), ("body_substrate_pins", body)):
        if not isinstance(values, list) or not all(isinstance(pin, str) for pin in values):
            errors.append(f"electrical.{label} must be a list of pin names")
            continue
        for pin in values:
            if pin not in pin_order:
                errors.append(f"electrical.{label} names undeclared pin {pin}")
    if set(power) & set(ground):
        errors.append("power_pins and ground_pins must be disjoint")
    allow_ground_only = electrical.get("allow_ground_only") is True
    if allow_ground_only and power:
        errors.append("allow_ground_only=true requires power_pins to be empty; do not invent VDD")
    if not allow_ground_only and (not power or not ground):
        errors.append("powered macro contract requires at least one power pin and one ground pin")
    if not ground:
        errors.append("every analog macro contract must declare at least one ground/reference pin")
    unassigned = sorted(set(pin_order) - (set(power) | set(ground) | set(body) | {
        pin for pin, spec in pin_contract.items() if isinstance(spec, dict) and spec.get("role") == "signal"
    }))
    if unassigned:
        errors.append(f"pins have no electrical role: {unassigned}")

    qualification = manifest.get("qualification", {})
    if not isinstance(qualification, dict):
        errors.append("qualification must be an object")
        qualification = {}
    status = qualification.get("status")
    if status not in {"qualified", "engineering_only", "unqualified"}:
        errors.append("qualification.status must be qualified, engineering_only, or unqualified")
    evidence = qualification.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("qualification.evidence must be a list")
    limitations = qualification.get("limitations", [])
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item for item in limitations):
        errors.append("qualification.limitations must be a non-empty list of strings")
    if status != "qualified":
        warnings.append(f"macro qualification status is {status!r}; structural contract is not signoff qualification")

    parsed: dict[str, Any] = {}
    if not errors or all(key in resolved_views for key in ("lef", "cdl", "blackbox_verilog")):
        try:
            lef_pins, lef_order = parse_lef(resolved_views["lef"], macro)
            cdl_order = parse_cdl(resolved_views["cdl"], macro)
            bb_pins = parse_blackbox(resolved_views["blackbox_verilog"], macro)
            parsed = {
                "lef_pins": lef_pins,
                "lef_pin_order": lef_order,
                "cdl_pin_order": cdl_order,
                "blackbox_pins": bb_pins,
            }
            expected = set(pin_order)
            for label, actual in (("LEF", set(lef_pins)), ("CDL", set(cdl_order)), ("black-box Verilog", set(bb_pins))):
                if actual != expected:
                    errors.append(
                        f"{label} pin set mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}"
                    )
            if cdl_order != pin_order:
                errors.append(f"CDL pin order {cdl_order} does not match manifest pin_order {pin_order}")
            for pin in pin_order:
                expected_direction = str(pin_contract[pin].get("direction", "")).upper()
                if lef_pins.get(pin) != expected_direction:
                    errors.append(f"LEF direction for {pin} is {lef_pins.get(pin)!r}, expected {expected_direction!r}")
                if bb_pins.get(pin) != expected_direction:
                    errors.append(
                        f"black-box Verilog direction for {pin} is {bb_pins.get(pin)!r}, expected {expected_direction!r}"
                    )
        except (KeyError, OSError, ValueError) as exc:
            errors.append(str(exc))

    report = {
        "status": "PASS" if not errors else "FAIL",
        "manifest": str(manifest_path.resolve()),
        "macro": macro,
        "views": {key: str(path) for key, path in resolved_views.items()},
        "pin_order": pin_order,
        "electrical": electrical,
        "qualification": qualification,
        "parsed": parsed,
        "errors": errors,
        "warnings": warnings,
    }
    return report, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report, warnings = check_manifest(args.manifest.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
