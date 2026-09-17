#!/usr/bin/env python3
"""Check analog electrical obligations against a layout DRC report.

This is a fail-closed integration gate, not a replacement for a foundry ERC
engine. The JSON contract supplies netlist-specific facts that geometry DRC
cannot infer (rail roles, body ties, output drivers, macro-pin semantics,
pad/diode paths, complete device-rating bindings, and redundant-via minima).
The KLayout report supplies the physical electrical rules. The netlist-label
report binds the physical top interface to the exact SPICE ``.SUBCKT`` ports
and reports the declared power-net via policy. Any unacknowledged warning
remains a release error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from electrical_limits import load_and_validate, resolve_limit


DIRECTIONS = {"INPUT", "OUTPUT", "INOUT"}



def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read ERC contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"ERROR: ERC contract must be a JSON object: {path}")
    return value


def strings(value: Any, label: str, errors: list[str], *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{label} must be a list of non-empty strings")
        return []
    if not allow_empty and not value:
        errors.append(f"{label} must not be empty")
    return value


def check_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(contract.get("design"), str) or not contract["design"]:
        errors.append("design must be a non-empty string")

    power = set(strings(contract.get("power_nets"), "power_nets", errors, allow_empty=False))
    ground = set(strings(contract.get("ground_nets"), "ground_nets", errors, allow_empty=False))
    if power & ground:
        errors.append(f"power_nets and ground_nets overlap: {sorted(power & ground)}")
    power_via_minimums = contract.get("power_net_via_minimums")
    if not isinstance(power_via_minimums, dict) or set(power_via_minimums) != power:
        errors.append(
            "power_net_via_minimums must map every declared power net exactly once"
        )
    elif any(
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or minimum < 2
        for minimum in power_via_minimums.values()
    ):
        errors.append("power_net_via_minimums values must be integers >= 2")

    external_ports = contract.get("external_ports")
    if not isinstance(external_ports, list):
        errors.append("external_ports must be a list, even when there are no signal pads")
        external_ports = []
    port_nets: dict[str, str] = {}
    for index, port in enumerate(external_ports):
        if not isinstance(port, dict):
            errors.append(f"external_ports[{index}] must be an object")
            continue
        name, net, direction = port.get("name"), port.get("net"), str(port.get("direction", "")).upper()
        if not isinstance(name, str) or not name:
            errors.append(f"external_ports[{index}].name is required")
        if not isinstance(net, str) or not net:
            errors.append(f"external_ports[{index}].net is required")
        if direction not in DIRECTIONS:
            errors.append(f"external_ports[{index}].direction must be INPUT, OUTPUT, or INOUT")
        if isinstance(name, str) and isinstance(net, str):
            if name in port_nets and port_nets[name] != net:
                errors.append(f"external port {name} maps to multiple nets")
            port_nets[name] = net

    drivers = contract.get("net_drivers")
    if not isinstance(drivers, dict):
        errors.append("net_drivers must map each driven net to driver objects")
        drivers = {}
    for net, entries in drivers.items():
        if not isinstance(net, str) or not net:
            errors.append("net_drivers contains an empty net name")
            continue
        if not isinstance(entries, list) or not entries:
            errors.append(f"net_drivers.{net} must contain at least one driver")
            continue
        output_count = 0
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"net_drivers.{net}[{index}] must be an object")
                continue
            direction = str(entry.get("direction", "")).upper()
            if direction not in DIRECTIONS:
                errors.append(f"net_drivers.{net}[{index}].direction is invalid")
            if direction in {"OUTPUT", "INOUT"}:
                output_count += 1
        if output_count > 1:
            errors.append(f"net {net} has {output_count} active output/inout drivers (contention risk)")

    body_ties = contract.get("body_ties")
    if not isinstance(body_ties, list) or not body_ties:
        errors.append("body_ties must list every MOS body/well tie")
        body_ties = []
    for index, tie in enumerate(body_ties):
        if not isinstance(tie, dict):
            errors.append(f"body_ties[{index}] must be an object")
            continue
        if not tie.get("device") or not tie.get("bulk_net"):
            errors.append(f"body_ties[{index}] requires device and bulk_net")
        elif tie["bulk_net"] not in power | ground:
            errors.append(f"body_ties[{index}] bulk_net is not a declared rail: {tie['bulk_net']}")

    macro_pins = contract.get("macro_pins")
    if not isinstance(macro_pins, list):
        errors.append("macro_pins must be a list, even when no macros are present")
        macro_pins = []
    for index, pin in enumerate(macro_pins):
        if not isinstance(pin, dict):
            errors.append(f"macro_pins[{index}] must be an object")
            continue
        required = ("macro", "pin", "net", "role", "direction")
        missing = [key for key in required if not pin.get(key)]
        if missing:
            errors.append(f"macro_pins[{index}] missing {missing}")
        elif str(pin["direction"]).upper() not in DIRECTIONS:
            errors.append(f"macro_pins[{index}].direction is invalid")

    diode_paths = contract.get("diode_paths")
    if not isinstance(diode_paths, list):
        errors.append("diode_paths must be a list")
        diode_paths = []
    if not diode_paths and not isinstance(contract.get("diode_paths_not_applicable"), str):
        errors.append("empty diode_paths requires diode_paths_not_applicable justification")
    for index, path in enumerate(diode_paths):
        if not isinstance(path, dict):
            errors.append(f"diode_paths[{index}] must be an object")
            continue
        positive, negative = path.get("positive_net"), path.get("negative_net")
        if not positive or not negative:
            errors.append(f"diode_paths[{index}] requires positive_net and negative_net")
        elif positive == negative:
            errors.append(f"diode_paths[{index}] shorts positive and negative rails")
        elif positive not in power or negative not in ground:
            errors.append(f"diode_paths[{index}] must terminate on declared power/ground rails")

    domains = contract.get("power_domains")
    if not isinstance(domains, list) or not domains:
        errors.append("power_domains must declare at least one allowed power domain")
    else:
        for index, domain in enumerate(domains):
            if not isinstance(domain, dict) or not domain.get("name"):
                errors.append(f"power_domains[{index}] requires a name")
                continue
            allowed = set(strings(domain.get("allowed_nets"), f"power_domains[{index}].allowed_nets", errors, allow_empty=False))
            unknown = allowed - power - ground
            if unknown:
                errors.append(f"power_domains[{index}] contains undeclared rail(s): {sorted(unknown)}")

    return errors


DEVICE_LIMIT_PREFIXES = {
    "mos_5v_nmos": "device_limits.mos_5v_nmos.",
    "mos_5v_pmos": "device_limits.mos_5v_pmos.",
    "rr": "device_limits.rr.",
    "rs": "device_limits.rs.",
    "c": "device_limits.c.",
    "dp": "device_limits.dp.",
    "dn": "device_limits.dn.",
    "csio": "model_characterization.csio.",
}


def check_limits_contract(path: Path, contract: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        limits, errors = load_and_validate(path)
    except SystemExit as exc:
        return None, [str(exc)]
    bindings = contract.get("rating_bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append("rating_bindings must be a non-empty list when --limits-contract is supplied")
        bindings = []
    seen: set[tuple[str, str]] = set()
    for index, binding in enumerate(bindings):
        label = f"rating_bindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{label} must be an object")
            continue
        instance = binding.get("instance")
        if not isinstance(instance, str) or not instance.strip():
            errors.append(f"{label}.instance must be a non-empty device or macro instance")
        device_kind = binding.get("device_kind")
        prefix = DEVICE_LIMIT_PREFIXES.get(device_kind)
        if prefix is None:
            errors.append(f"{label}.device_kind must be one of {sorted(DEVICE_LIMIT_PREFIXES)}")
        elif isinstance(instance, str) and instance.strip():
            key = (instance, device_kind)
            if key in seen:
                errors.append(f"{label} duplicates rating binding for {instance!r}/{device_kind!r}")
            seen.add(key)
        refs = binding.get("limit_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}.limit_refs must be a non-empty list")
            continue
        for ref in refs:
            if prefix is not None and (not isinstance(ref, str) or not ref.startswith(prefix)):
                errors.append(f"{label}.limit_refs entry must start with {prefix}: {ref!r}")
                continue
            _, error = resolve_limit(limits, ref)
            if error:
                errors.append(f"{label}: {error}")
    return limits, errors


def check_label_report(
    path: Path, contract: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        report = load_json(path)
    except SystemExit as exc:
        return None, [str(exc)]
    errors: list[str] = []
    if report.get("status") != "PASS":
        errors.append(f"netlist label report status is not PASS: {report.get('status')!r}")
    report_errors = report.get("errors")
    if not isinstance(report_errors, list):
        errors.append("netlist label report errors must be a list")
    elif report_errors:
        errors.append(f"netlist label report contains errors: {report_errors}")
    if not isinstance(report.get("netlist_ports"), list) or not report["netlist_ports"]:
        errors.append("netlist label report must contain non-empty netlist_ports")
    power_via_minimums = contract.get("power_net_via_minimums", {})
    if isinstance(power_via_minimums, dict):
        if report.get("power_net_via_minimums") != power_via_minimums:
            errors.append("netlist label report power-via policy does not match ERC contract")
        checks = report.get("power_via_checks")
        if not isinstance(checks, list):
            errors.append("netlist label report must contain power_via_checks")
        else:
            by_net = {
                item.get("net"): item
                for item in checks
                if isinstance(item, dict) and isinstance(item.get("net"), str)
            }
            for net, minimum in power_via_minimums.items():
                item = by_net.get(net)
                observed_vias = item.get("observed_vias") if item else None
                if (
                    item is None
                    or item.get("status") != "PASS"
                    or not isinstance(observed_vias, int)
                    or isinstance(observed_vias, bool)
                    or observed_vias < minimum
                ):
                    errors.append(
                        f"netlist label report power-via check failed for {net}: {item}"
                    )
    return report, errors


def report_categories(path: Path) -> tuple[Counter[str], list[str]]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise SystemExit(f"ERROR: invalid KLayout ERC report {path}: {exc}") from exc
    categories: Counter[str] = Counter()
    for item in root.iter("item"):
        category = (item.findtext("category") or "<uncategorized>").strip("'")
        categories[category] += 1
    warnings = [category for category in categories if re.match(r"^WAR\d*\s*:", category)]
    return categories, warnings


def check_ruleset(path: Path, electrical_path: Path) -> list[str]:
    errors: list[str] = []
    runset_text = ""
    if not path.is_file():
        errors.append(f"missing top-level DRC runset: {path}")
    else:
        runset_text = path.read_text(encoding="utf-8", errors="replace")
        if "03_Electrical.drc" not in runset_text:
            errors.append(f"top-level DRC runset does not include 03_Electrical.drc: {path}")
    if not electrical_path.is_file():
        return errors + [f"missing electrical ruleset: {electrical_path}"]
    text = electrical_path.read_text(encoding="utf-8", errors="replace")
    required_tokens = (
        "GC_FL",
        "M1LBL_TOP",
        "M2LBL_TOP",
        "NETLIST_LABELS_REQUIRED",
        "antenna_check",
        "V15_MARKER",
        "V27_MARKER",
        "V15V_NW",
        "V27V_PWELL",
        "V15V_M1_WIDTH",
    )
    missing = [token for token in required_tokens if token not in text]
    if missing:
        errors.append(f"electrical ruleset lacks required checks: {missing}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--ruleset", required=True, type=Path)
    parser.add_argument("--electrical-ruleset", required=True, type=Path)
    parser.add_argument("--limits-contract", required=True, type=Path)
    parser.add_argument("--label-report", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    contract = load_json(args.contract.resolve())
    errors = check_contract(contract)
    errors.extend(check_ruleset(args.ruleset.resolve(), args.electrical_ruleset.resolve()))
    limits = None
    if args.limits_contract:
        limits, limit_errors = check_limits_contract(args.limits_contract.resolve(), contract)
        errors.extend(limit_errors)
    elif "rating_bindings" in contract:
        errors.append("rating_bindings requires --limits-contract for electrical-limit enforcement")
    label_report = None
    if args.label_report:
        label_report, label_errors = check_label_report(args.label_report.resolve(), contract)
        errors.extend(label_errors)
    categories, warnings = report_categories(args.report.resolve())
    hard = {category: count for category, count in categories.items() if category not in warnings}
    acknowledged = set(contract.get("acknowledged_warnings", []))
    unacknowledged = sorted(set(warnings) - acknowledged)
    if unacknowledged:
        errors.append(f"unacknowledged electrical warnings: {unacknowledged}")
    if hard:
        errors.extend(f"{count} hard electrical item(s): {category}" for category, count in sorted(hard.items()))

    result = {
        "status": "PASS" if not errors else "FAIL",
        "contract": str(args.contract.resolve()),
        "report": str(args.report.resolve()),
        "ruleset": str(args.ruleset.resolve()),
        "electrical_ruleset": str(args.electrical_ruleset.resolve()),
        "limits_contract": str(args.limits_contract.resolve()) if args.limits_contract else None,
        "label_report": str(args.label_report.resolve()) if args.label_report else None,
        "rating_bindings": contract.get("rating_bindings", []),
        "power_net_via_minimums": contract.get("power_net_via_minimums", {}),
        "layout_markers": limits.get("layout_markers", {}) if limits else {},
        "hard_items": hard,
        "warnings": sorted(warnings),
        "acknowledged_warnings": sorted(acknowledged & set(warnings)),
        "errors": errors,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1



if __name__ == "__main__":
    raise SystemExit(main())
