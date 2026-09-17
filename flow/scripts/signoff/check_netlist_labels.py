#!/usr/bin/env python3
"""Check top-level GDS labels against a SPICE netlist interface.

KLayout's electrical DRC consumes M1/M2 text labels for top-level connectivity,
but it cannot compare those names with a schematic netlist.  This checker is
the deterministic bridge: it checks the exact top-level ``.SUBCKT`` ports,
requires each port label in the top cell or its physical boundary hierarchy,
rejects unknown labels directly on the top cell by default, verifies every
checked label anchor lies on its declared metal, and optionally checks that
each declared power net has the required aggregate number of unique V1 vias.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FLOW_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = FLOW_ROOT / "scripts" / "analysis"
sys.path.insert(0, str(ANALYSIS_ROOT))
from extract_tr1um_parasitics import flatten_gds, parse_gds  # noqa: E402

LABEL_LAYERS = {48: ("M1", 13), 49: ("M2", 20)}
VIA_LAYER = (19, 0)
NEEDED_LAYERS = {(48, 0), (49, 0), (13, 0), (20, 0), VIA_LAYER}


def canonical(value: str) -> str:
    return value.strip().strip('"').lstrip("\\").upper()


def parse_top_ports(text: str, top: str) -> tuple[str | None, list[str], str | None]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("*") or stripped.startswith(";"):
            continue
        match = re.match(r"(?i)^\.subckt\s+(\S+)(?:\s+(.*?))?\s*$", stripped)
        if not match or canonical(match.group(1)) != canonical(top):
            continue
        parts = [match.group(2) or ""]
        continuation_index = index + 1
        while continuation_index < len(lines):
            continuation = lines[continuation_index].strip()
            if not continuation.startswith("+"):
                break
            parts.append(continuation[1:])
            continuation_index += 1
        body = " ".join(parts)
        body = body.split(";", 1)[0].split("$", 1)[0]
        ports = [token for token in body.split() if not token.startswith("*")]
        return match.group(1), ports, None
    return None, [], f"netlist has no .SUBCKT {top} declaration"


def contains_point(box: tuple[float, float, float, float], point: tuple[float, float]) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def rectangles_touch(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def load_power_via_policy(path: Path | None, errors: list[str]) -> dict[str, int]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read ERC contract for power-via checks {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"ERC contract must be a JSON object: {path}")
        return {}
    power_nets = value.get("power_nets")
    raw_minimums = value.get("power_net_via_minimums")
    if (
        not isinstance(power_nets, list)
        or not power_nets
        or not all(isinstance(net, str) and net.strip() for net in power_nets)
    ):
        errors.append("ERC contract power_nets must be a non-empty list of net names")
        power_nets = []
    if not isinstance(raw_minimums, dict) or not raw_minimums:
        errors.append(
            "ERC contract power_net_via_minimums must map every power net to an integer >= 2"
        )
        return {}
    expected = {canonical(net) for net in power_nets}
    observed = {canonical(net) for net in raw_minimums}
    if observed != expected:
        errors.append(
            "ERC contract power_net_via_minimums keys must exactly match power_nets"
        )
    minimums: dict[str, int] = {}
    for net, minimum in raw_minimums.items():
        if not isinstance(net, str) or not net.strip():
            errors.append("ERC contract power_net_via_minimums contains an empty net name")
            continue
        if (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or minimum < 2
        ):
            errors.append(
                f"ERC contract power_net_via_minimums.{net} must be an integer >= 2"
            )
            continue
        minimums[canonical(net)] = minimum
    return minimums


def check(args: argparse.Namespace) -> dict[str, Any]:
    layout_path = args.layout.resolve()
    netlist_path = args.netlist.resolve()
    errors: list[str] = []
    power_via_minimums = load_power_via_policy(args.erc_contract.resolve() if args.erc_contract else None, errors)
    power_via_checks: list[dict[str, Any]] = []
    netlist_text = ""
    if not layout_path.is_file() or layout_path.stat().st_size == 0:
        errors.append(f"missing or empty layout: {layout_path}")
    if not netlist_path.is_file() or netlist_path.stat().st_size == 0:
        errors.append(f"missing or empty netlist: {netlist_path}")
    if errors:
        return {
            "status": "FAIL",
            "layout": str(layout_path),
            "top_cell": args.top_cell,
            "netlist": str(netlist_path),
            "netlist_ports": [],
            "labels": [],
            "errors": errors,
        }

    netlist_text = netlist_path.read_text(encoding="utf-8", errors="replace")
    subckt_name, ports, port_error = parse_top_ports(netlist_text, args.top_cell)
    if port_error:
        errors.append(port_error)
        ports = []

    labels: list[dict[str, Any]] = []
    if not errors:
        try:
            structures, meters_per_dbu = parse_gds(layout_path, NEEDED_LAYERS)
            shapes, parsed_labels = flatten_gds(structures, meters_per_dbu, args.top_cell, NEEDED_LAYERS)
        except SystemExit as exc:
            errors.append(str(exc))
            shapes, parsed_labels = [], []
        allowed_ports = {canonical(port) for port in ports}
        required_ports = (
            allowed_ports
            | {canonical(value) for value in args.required_net}
            | set(power_via_minimums)
        )
        if args.label_scope == "flattened":
            candidate_labels = parsed_labels
        else:
            candidate_labels = [
                label
                for label in parsed_labels
                if label.hierarchy == args.top_cell
                or (
                    canonical(label.text) in required_ports
                    and label.layer in LABEL_LAYERS
                )
            ]
        metal_shapes = [shape for shape in shapes if shape.layer in {13, 20}]
        via_shapes = [
            shape
            for shape in shapes
            if (shape.layer, shape.datatype) == VIA_LAYER
        ]
        observed_ports: set[str] = set()
        for label in candidate_labels:
            label_name = canonical(label.text)
            layer_name, metal_layer = LABEL_LAYERS.get(label.layer, (None, None))
            on_metal = metal_layer is not None and any(
                shape.layer == metal_layer and contains_point(shape.bbox_um, label.point_um)
                for shape in metal_shapes
            )
            record = {
                "text": label.text.strip(),
                "net": label_name,
                "layer": layer_name or f"{label.layer}",
                "point_um": [float(label.point_um[0]), float(label.point_um[1])],
                "hierarchy": label.hierarchy,
                "on_metal": on_metal,
            }
            labels.append(record)
            observed_ports.add(label_name)
            if label_name not in required_ports and not args.allow_extra_labels:
                errors.append(f"unknown top-level net label {label.text!r}; not a .SUBCKT {subckt_name} port")
            if layer_name is None:
                errors.append(f"label {label.text!r} is not on M1/M2 label layer")
            elif not on_metal:
                errors.append(f"label {label.text!r} at {record['point_um']} is not anchored on {layer_name}")
        for port in sorted(required_ports - observed_ports):
            errors.append(f"missing top-level net label for .SUBCKT port {port}")
        for net, minimum in sorted(power_via_minimums.items()):
            net_labels = [
                label
                for label in candidate_labels
                if canonical(label.text) == net and label.layer in LABEL_LAYERS
            ]
            observed_vias: set[Any] = set()
            label_via_counts: list[dict[str, Any]] = []
            for label in net_labels:
                _, metal_layer = LABEL_LAYERS[label.layer]
                label_metal = [
                    shape
                    for shape in metal_shapes
                    if shape.layer == metal_layer and contains_point(shape.bbox_um, label.point_um)
                ]
                local_vias = {
                    via
                    for via in via_shapes
                    if any(rectangles_touch(via.bbox_um, metal.bbox_um) for metal in label_metal)
                }
                observed_vias.update(local_vias)
                label_via_counts.append(
                    {
                        "layer": LABEL_LAYERS[label.layer][0],
                        "point_um": [float(label.point_um[0]), float(label.point_um[1])],
                        "hierarchy": label.hierarchy,
                        "via_count": len(local_vias),
                    }
                )
            check = {
                "net": net,
                "minimum_vias": minimum,
                "observed_vias": len(observed_vias),
                "label_count": len(net_labels),
                "labels": label_via_counts,
                "status": "PASS" if len(observed_vias) >= minimum else "FAIL",
            }
            power_via_checks.append(check)
            if not net_labels:
                errors.append(f"power net {net} has no anchored M1/M2 labels")
            elif len(observed_vias) < minimum:
                errors.append(
                    f"power net {net} has {len(observed_vias)} via(s); "
                    f"requires at least {minimum}"
                )

    return {
        "status": "PASS" if not errors else "FAIL",
        "layout": str(layout_path),
        "top_cell": args.top_cell,
        "netlist": str(netlist_path),
        "netlist_subckt": subckt_name,
        "netlist_ports": ports,
        "label_scope": args.label_scope,
        "allow_extra_labels": args.allow_extra_labels,
        "erc_contract": str(args.erc_contract.resolve()) if args.erc_contract else None,
        "power_net_via_minimums": power_via_minimums,
        "power_via_checks": power_via_checks,
        "labels": labels,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--top-cell", required=True)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--label-scope", choices=("top", "flattened"), default="top")
    parser.add_argument("--required-net", action="append", default=[])
    parser.add_argument("--erc-contract", type=Path)
    parser.add_argument("--allow-extra-labels", action="store_true")
    args = parser.parse_args()
    result = check(args)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
