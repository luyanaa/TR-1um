#!/usr/bin/env python3
"""Merge a KLayout device netlist with the distributed TR-1um RC network.

The physical device view remains the authority for extracted device hierarchy.
The RC sidecar remains the authority for distributed interconnect topology.  A
merge is made only through explicit shared SPICE nodes: logical device nodes are
mapped to route anchors from the parasitic ledger, and the distributed RC
subcircuit is instantiated inside the selected top-level subcircuit.  When a
KLayout extraction has unnamed top-level nets, an optional LVS/reference
netlist can map cell-instance connectivity back to the routed logical names.

This is an engineering merge, not a foundry-qualified PEX deck.  The manifest
reports unresolved hierarchy and every node-mapping method so a partial merge
cannot be mistaken for a complete extraction.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEVICE_NODE_COUNTS = {
    "F_CSIO": 3,
    "F_RS": 2,
    "F_RR": 3,
    "DP": 2,
    "DN": 2,
    "PMOS": 4,
    "NMOS": 4,
    "NMOSE": 4,
    "MPE": 4,
    "MNE": 4,
}

# Models emitted by the active KLayout writer as X/M/D elements.
KNOWN_DEVICE_MODELS = frozenset(DEVICE_NODE_COUNTS)


@dataclass(frozen=True)
class Statement:
    start: int
    end: int
    logical: str
    first_line: str


@dataclass(frozen=True)
class Subckt:
    name: str
    start: int
    end: int
    ports: tuple[str, ...]
    statement_indices: tuple[int, ...]


@dataclass(frozen=True)
class DeviceLine:
    element: str
    model: str
    model_index: int
    node_count: int
    nodes: tuple[str, ...]


@dataclass(frozen=True)
class InstanceLine:
    instance: str
    master: str
    nodes: tuple[str, ...]


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def _canonical(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "\\" and value[-1] == "!":
        value = value[1:-1]
    elif value.startswith("\\"):
        value = value[1:]
    return value.upper()


def _line_is_continuation(line: str) -> bool:
    return line.lstrip().startswith("+")


def _logical_statements(text: str) -> list[Statement]:
    lines = text.splitlines()
    result: list[Statement] = []
    index = 0
    while index < len(lines):
        start = index
        parts = [lines[index].strip()]
        index += 1
        while index < len(lines) and _line_is_continuation(lines[index]):
            parts.append(lines[index].lstrip()[1:].strip())
            index += 1
        result.append(Statement(start + 1, index, " ".join(parts), lines[start]))
    return result


def _parse_subckts(text: str) -> tuple[list[Statement], dict[str, Subckt], dict[int, str | None]]:
    statements = _logical_statements(text)
    stack: list[tuple[str, int, tuple[str, ...]]] = []
    sections: dict[str, Subckt] = {}
    enclosing: dict[int, str | None] = {}
    section_statements: dict[int, list[int]] = {}

    for index, statement in enumerate(statements):
        enclosing[index] = stack[-1][0] if stack else None
        subckt_match = re.match(r"(?i)^\.subckt\s+(\S+)(?:\s+(.*))?$", statement.logical)
        if subckt_match:
            name = subckt_match.group(1)
            ports = tuple((subckt_match.group(2) or "").split())
            stack.append((name, index, ports))
            section_statements[index] = []
            continue
        if stack:
            section_statements.setdefault(stack[-1][1], []).append(index)
        ends_match = re.match(r"(?i)^\.ends(?:\s+(\S+))?", statement.logical)
        if ends_match and stack:
            name, start, ports = stack.pop()
            sections[name] = Subckt(name, statements[start].start, statement.end, ports, tuple(section_statements[start]))

    if stack:
        raise SystemExit(f"unterminated .SUBCKT {stack[-1][0]}")
    return statements, sections, enclosing


def _subckt_by_name(sections: dict[str, Subckt], name: str) -> Subckt | None:
    if name in sections:
        return sections[name]
    wanted = _canonical(name)
    return next((section for section in sections.values() if _canonical(section.name) == wanted), None)


def _known_model_index(tokens: list[str], known_models: set[str]) -> tuple[int, str] | None:
    for index, token in enumerate(tokens[1:], 1):
        if "=" in token:
            continue
        model = token.upper()
        if model in known_models:
            return index, model
    return None


def _parse_device_line(logical: str, known_models: set[str]) -> DeviceLine | None:
    tokens = logical.split()
    if len(tokens) < 3 or tokens[0].startswith("*") or tokens[0].startswith("."):
        return None
    element = tokens[0][:1].upper()
    if element == "M":
        if len(tokens) < 6:
            return None
        model_index = 5
        model = tokens[model_index].upper()
        if model not in known_models or DEVICE_NODE_COUNTS.get(model) != 4:
            return None
        return DeviceLine(element, model, model_index, 4, tuple(tokens[1:5]))
    if element == "D":
        if len(tokens) < 4:
            return None
        model_index = 3
        model = tokens[model_index].upper()
        if model not in known_models or DEVICE_NODE_COUNTS.get(model) != 2:
            return None
        return DeviceLine(element, model, model_index, 2, tuple(tokens[1:3]))
    if element == "X":
        found = _known_model_index(tokens, known_models)
        if found is None:
            return None
        model_index, model = found
        node_count = DEVICE_NODE_COUNTS[model]
        if model_index < node_count + 1:
            return None
        return DeviceLine(element, model, model_index, node_count, tuple(tokens[1 : 1 + node_count]))
    # Some KLayout custom-writer revisions use the numeric device id as the
    # element prefix for DP/DN/F_* devices.  Recognize those records so the
    # simulation-facing copy can normalize them to legal SPICE elements.
    found = _known_model_index(tokens, known_models)
    if found is None:
        return None
    model_index, model = found
    node_count = DEVICE_NODE_COUNTS[model]
    if model_index < node_count + 1:
        return None
    normalized_element = "D" if model in {"DP", "DN"} else "X"
    return DeviceLine(normalized_element, model, model_index, node_count, tuple(tokens[1 : 1 + node_count]))


def _parse_instance_line(logical: str) -> InstanceLine | None:
    tokens = logical.split()
    if len(tokens) < 3 or not tokens[0].upper().startswith("X"):
        return None
    if any("=" in token for token in tokens[1:]):
        # Reference mapping is intentionally limited to plain KLayout cell
        # instances; parameterized subcircuits need a dedicated contract.
        return None
    return InstanceLine(tokens[0], tokens[-1], tuple(tokens[1:-1]))


def _subckt_statements(statements: list[Statement], section: Subckt) -> Iterable[tuple[int, Statement]]:
    for index, statement in enumerate(statements):
        if section.start <= statement.start and statement.end <= section.end:
            yield index, statement


def _load_net_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    value = _read_json(path)
    mapping = value.get("map", value)
    if not isinstance(mapping, dict):
        raise SystemExit(f"node map must be a JSON object: {path}")
    return {str(key): str(target) for key, target in mapping.items()}


def _mapping_tables(parasitics: dict, interconnect_ports: tuple[str, ...], net_map: dict[str, str]) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    node_net_raw = parasitics.get("node_net", {})
    node_net = {str(node): str(net) for node, net in node_net_raw.items()} if isinstance(node_net_raw, dict) else {}
    topology = parasitics.get("topology", {})
    anchor_raw = topology.get("anchor_nodes", {}) if isinstance(topology, dict) else {}
    anchors = {str(net): str(node) for net, node in anchor_raw.items()} if isinstance(anchor_raw, dict) else {}
    nodes_by_net: dict[str, list[str]] = {}
    for node, net in node_net.items():
        nodes_by_net.setdefault(_canonical(net), []).append(node)
    for values in nodes_by_net.values():
        values.sort(key=lambda value: (_canonical(value), value))

    port_by_canonical = {_canonical(port): port for port in interconnect_ports}
    anchor_by_canonical = {_canonical(net): node for net, node in anchors.items()}
    alias_map = {_canonical(key): value for key, value in net_map.items()}
    return port_by_canonical, anchor_by_canonical, nodes_by_net | {"__ports__": list(interconnect_ports), "__alias__": alias_map}


def _map_node(
    node: str,
    port_by_canonical: dict[str, str],
    anchor_by_canonical: dict[str, str],
    nodes_by_net: dict[str, list[str]],
    alias_map: dict[str, str],
) -> tuple[str, str]:
    original = node
    logical = alias_map.get(_canonical(node), node)
    logical_key = _canonical(logical)
    if logical_key in port_by_canonical:
        return port_by_canonical[logical_key], "shared_logical_net"
    anchor = anchor_by_canonical.get(logical_key)
    if anchor is not None:
        mapped = port_by_canonical.get(_canonical(anchor))
        if mapped is not None:
            return mapped, "route_anchor"
    candidates = [candidate for candidate in nodes_by_net.get(logical_key, []) if _canonical(candidate) in port_by_canonical]
    if candidates:
        return port_by_canonical[_canonical(candidates[0])], "deterministic_route_node"
    return original, "unmapped"


def _rewrite_tokens(logical: str, replacements: dict[int, str]) -> str:
    tokens = logical.split()
    for index, value in replacements.items():
        if index < len(tokens):
            tokens[index] = value
    return " ".join(tokens)
def _simulation_prefix(tokens: list[str], device: DeviceLine) -> str | None:
    original = tokens[0]
    if device.model in {"DP", "DN"} and not original.upper().startswith("D"):
        suffix = original[1:] if original[:1].isalpha() else original
        return f"D{suffix}"
    if device.element == "M":
        return f"X{original[1:]}"
    return None
def _simulation_line(logical: str, device: DeviceLine, replacements: dict[int, str]) -> str:
    tokens = logical.split()
    prefix = _simulation_prefix(tokens, device)
    if prefix is not None:
        tokens[0] = prefix
    for index, value in replacements.items():
        if index < len(tokens):
            tokens[index] = value
    if device.model in {"DP", "DN"}:
        tokens = [
            token
            for token in tokens
            if not (
                "=" in token
                and token.split("=", 1)[0].upper() in {"A", "P"}
            )
        ]
    return " ".join(tokens)




def _rewrite_device_statement(
    logical: str,
    device: DeviceLine,
    mapper,
) -> tuple[str, list[dict]]:
    tokens = logical.split()
    records: list[dict] = []
    prefix = _simulation_prefix(tokens, device)
    replacements: dict[int, str] = {0: prefix} if prefix is not None else {}
    for offset, original in enumerate(device.nodes, start=1):
        mapped, method = mapper(original)
        replacements[offset] = mapped
        records.append({"terminal_index": offset, "logical_node": original, "mapped_node": mapped, "method": method})
    return _simulation_line(logical, device, replacements), records




def _section_instance_table(text: str, section: Subckt, known_models: set[str]) -> dict[str, list[InstanceLine]]:
    statements, sections, enclosing = _parse_subckts(text)
    actual = _subckt_by_name(sections, section.name)
    if actual is None:
        return {}
    table: dict[str, list[InstanceLine]] = {}
    for index, statement in _subckt_statements(statements, actual):
        if enclosing.get(index) != actual.name:
            continue
        instance = _parse_instance_line(statement.logical)
        if instance is None or _parse_device_line(statement.logical, known_models) is not None:
            continue
        table.setdefault(_canonical(instance.master), []).append(instance)
    return table


def _physical_instance_table(
    statements: list[Statement],
    section: Subckt,
    enclosing: dict[int, str | None],
    known_models: set[str],
) -> dict[str, list[InstanceLine]]:
    table: dict[str, list[InstanceLine]] = {}
    for index, statement in _subckt_statements(statements, section):
        if enclosing.get(index) != section.name:
            continue
        instance = _parse_instance_line(statement.logical)
        if instance is None or _parse_device_line(statement.logical, known_models) is not None:
            continue
        table.setdefault(_canonical(instance.master), []).append(instance)
    return table


def _choose_reference_subckt(
    physical: dict[str, list[InstanceLine]],
    reference_sections: dict[str, Subckt],
    reference_text: str,
    known_models: set[str],
    requested: str | None,
) -> tuple[Subckt | None, dict[str, list[InstanceLine]]]:
    if requested:
        section = _subckt_by_name(reference_sections, requested)
        if section is None:
            raise SystemExit(f"reference netlist has no .SUBCKT {requested}")
        return section, _section_instance_table(reference_text, section, known_models)

    physical_counts = {master: len(items) for master, items in physical.items()}
    best: tuple[tuple[int, int, int], Subckt | None, dict[str, list[InstanceLine]]] = ((0, -10**9, -10**9), None, {})
    for section in reference_sections.values():
        candidate = _section_instance_table(reference_text, section, known_models)
        candidate_counts = {master: len(items) for master, items in candidate.items()}
        matched = sum(min(physical_counts.get(master, 0), count) for master, count in candidate_counts.items())
        missing = sum(abs(physical_counts.get(master, 0) - count) for master, count in candidate_counts.items())
        extra = sum(count for master, count in physical_counts.items() if master not in candidate_counts)
        score = (matched, -(missing + extra), -abs(sum(physical_counts.values()) - sum(candidate_counts.values())))
        if score > best[0]:
            best = (score, section, candidate)
    if best[1] is None or best[0][0] == 0:
        return None, {}
    return best[1], best[2]


def _reference_rewrite(
    statement: str,
    physical: InstanceLine,
    reference: InstanceLine,
    mapper,
    complete_reference_ports: bool,
) -> tuple[str, dict]:
    target_nodes = list(reference.nodes)
    method = "reference_instance_order"
    if len(physical.nodes) != len(target_nodes):
        if not complete_reference_ports or len(target_nodes) != len(physical.nodes) + 1:
            return statement, {
                "instance": physical.instance,
                "master": physical.master,
                "status": "unresolved_port_count",
                "physical_nodes": list(physical.nodes),
                "reference_nodes": list(reference.nodes),
            }
        if _canonical(physical.nodes[-1]) != _canonical(target_nodes[-1]):
            return statement, {
                "instance": physical.instance,
                "master": physical.master,
                "status": "unresolved_supply_alignment",
                "physical_nodes": list(physical.nodes),
                "reference_nodes": list(reference.nodes),
            }
        method = "reference_supply_completion"
    mapped_nodes = []
    node_records = []
    for node in target_nodes:
        mapped, map_method = mapper(node)
        mapped_nodes.append(mapped)
        node_records.append({"logical_node": node, "mapped_node": mapped, "method": map_method})
    tokens = statement.split()
    # Instance/master are the first/last token for plain X statements.
    rewritten = " ".join([tokens[0], *mapped_nodes, tokens[-1]])
    return rewritten, {
        "instance": physical.instance,
        "master": physical.master,
        "status": "mapped",
        "method": method,
        "physical_nodes": list(physical.nodes),
        "reference_nodes": list(reference.nodes),
        "mapped_nodes": mapped_nodes,
        "terminals": node_records,
    }


def _render_with_replacements(text: str, replacements: dict[int, tuple[int, str]], inserts: dict[int, list[str]]) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 1
    while index <= len(lines):
        for line in inserts.get(index, []):
            output.append(line)
        replacement = replacements.get(index)
        if replacement is not None:
            end, value = replacement
            output.append(value)
            index = end + 1
            continue
        output.append(lines[index - 1])
        index += 1
    for line in inserts.get(len(lines) + 1, []):
        output.append(line)
    return "\n".join(output).rstrip() + "\n"


def _interconnect_ports(text: str) -> tuple[str, ...]:
    statements, sections, _ = _parse_subckts(text)
    section = _subckt_by_name(sections, "tr1um_parasitics")
    if section is None:
        raise SystemExit("distributed interconnect SPICE has no .SUBCKT tr1um_parasitics")
    header = next((statement.logical for statement in statements if statement.start == section.start), None)
    if header is None:
        raise SystemExit("unable to read tr1um_parasitics header")
    match = re.match(r"(?i)^\.subckt\s+\S+(?:\s+(.*))?$", header)
    return tuple((match.group(1) or "").split()) if match else ()


def _make_xpex(ports: tuple[str, ...]) -> str:
    if not ports:
        raise SystemExit("distributed interconnect subcircuit has no ports")
    return "XPEX_TR1UM " + " ".join(ports) + " tr1um_parasitics"


def _absolute(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def build(args: argparse.Namespace) -> dict:
    extracted_text = args.extracted.read_text(encoding="utf-8", errors="replace")
    interconnect_text = args.interconnect.read_text(encoding="utf-8", errors="replace")
    parasitics = _read_json(args.parasitics)
    statements, sections, enclosing = _parse_subckts(extracted_text)
    top = _subckt_by_name(sections, args.top)
    if top is None:
        raise SystemExit(f"extracted netlist has no .SUBCKT {args.top}")
    pex_ports = _interconnect_ports(interconnect_text)
    if not pex_ports:
        raise SystemExit("distributed interconnect SPICE has no routable ports")

    net_map = _load_net_map(args.net_map)
    port_by_canonical, anchor_by_canonical, table = _mapping_tables(parasitics, pex_ports, net_map)
    nodes_by_net = {key: values for key, values in table.items() if not key.startswith("__")}
    alias_map = table.get("__alias__", {})
    physical_node_aliases: dict[str, str] = {}
    alias_conflicts: dict[str, set[str]] = {}
    mapping_records: dict[str, dict] = {}

    def mapper(node: str) -> tuple[str, str]:
        mapped, method = _map_node(node, port_by_canonical, anchor_by_canonical, nodes_by_net, alias_map)
        key = f"{node}->{mapped}"
        mapping_records.setdefault(key, {"logical_node": node, "mapped_node": mapped, "method": method})
        return mapped, method

    def map_physical_node(node: str) -> tuple[str, str]:
        logical = physical_node_aliases.get(_canonical(node), node)
        mapped, method = mapper(logical)
        if logical != node:
            method = f"reference_node_alias:{method}"
        key = f"{node}->{mapped}"
        mapping_records.setdefault(key, {"logical_node": node, "mapped_node": mapped, "method": method})
        return mapped, method

    known_models = set(KNOWN_DEVICE_MODELS)
    for entry in parasitics.get("device_entries", []):
        if isinstance(entry, dict) and entry.get("model"):
            known_models.add(str(entry["model"]).upper())

    replacements: dict[int, tuple[int, str]] = {}
    inserts: dict[int, list[str]] = {}
    device_records: list[dict] = []
    unresolved_devices: list[dict] = []
    top_level_instances: list[dict] = []
    simulation_normalization_count = 0
    for index, statement in _subckt_statements(statements, top):
        if enclosing.get(index) != top.name:
            continue
        device = _parse_device_line(statement.logical, known_models)
        if device is not None:
            rewritten, terminals = _rewrite_device_statement(statement.logical, device, mapper)
            if _simulation_line(statement.logical, device, {}) != statement.logical:
                simulation_normalization_count += 1
            replacements[statement.start] = (statement.end, rewritten)
            device_records.append(
                {
                    "instance": statement.logical.split()[0],
                    "model": device.model,
                    "subckt": top.name,
                    "kind": "top_level_device",
                    "original_nodes": list(device.nodes),
                    "mapped_nodes": [record["mapped_node"] for record in terminals],
                    "terminals": terminals,
                    "status": "mapped" if all(record["method"] != "unmapped" for record in terminals) else "partial",
                }
            )
            if any(record["method"] == "unmapped" for record in terminals):
                unresolved_devices.append(device_records[-1])
            continue
        instance = _parse_instance_line(statement.logical)
        if instance is not None:
            top_level_instances.append({"statement": statement, "instance": instance})

    # KLayout's LVS writer may emit MOS elements as M<id> and diode/device
    # records with a numeric id.  Convert those records to legal simulation
    # elements while preserving their extracted model and parameters.
    for statement in statements:
        device = _parse_device_line(statement.logical, known_models)
        if device is None or statement.start in replacements:
            continue
        normalized = _simulation_line(statement.logical, device, {})
        if normalized == statement.logical:
            continue
        replacements[statement.start] = (statement.end, normalized)
        simulation_normalization_count += 1

    reference_records: list[dict] = []
    reference_section_name: str | None = None
    if args.reference_netlist:
        reference_text = args.reference_netlist.read_text(encoding="utf-8", errors="replace")
        _, reference_sections, _ = _parse_subckts(reference_text)
        physical_table = _physical_instance_table(statements, top, enclosing, known_models)
        reference_section, reference_table = _choose_reference_subckt(
            physical_table,
            reference_sections,
            reference_text,
            known_models,
            args.reference_top,
        )
        if reference_section is not None:
            reference_section_name = reference_section.name
            consumed: dict[str, int] = {}
            for item in top_level_instances:
                physical = item["instance"]
                key = _canonical(physical.master)
                offset = consumed.get(key, 0)
                candidates = reference_table.get(key, [])
                if offset >= len(candidates):
                    continue
                reference = candidates[offset]
                consumed[key] = offset + 1
                rewritten, record = _reference_rewrite(
                    item["statement"].logical,
                    physical,
                    reference,
                    mapper,
                    args.complete_reference_ports,
                )
                reference_records.append(record)
                if record.get("status") != "mapped":
                    continue
                replacements[item["statement"].start] = (item["statement"].end, rewritten)
                physical_nodes = list(physical.nodes)
                reference_nodes = list(reference.nodes)
                if len(physical_nodes) == len(reference_nodes):
                    pairs = zip(physical_nodes, reference_nodes)
                elif args.complete_reference_ports and len(reference_nodes) == len(physical_nodes) + 1:
                    pairs = zip(physical_nodes, reference_nodes[:-1])
                else:
                    pairs = ()
                for physical_node, reference_node in pairs:
                    canonical = _canonical(physical_node)
                    existing = physical_node_aliases.get(canonical)
                    if existing is not None and _canonical(existing) != _canonical(reference_node):
                        alias_conflicts.setdefault(canonical, set()).update({existing, reference_node})
                        physical_node_aliases.pop(canonical, None)
                    elif canonical not in alias_conflicts:
                        physical_node_aliases[canonical] = reference_node
        else:
            reference_records.append({"status": "no_compatible_reference_subckt"})

    # Extra physical black-box instances (most commonly antenna diodes) can
    # still be connected when their unnamed nets are equivalent to nodes seen
    # on reference-mapped instances.  This preserves hierarchy without
    # inventing a cell-specific pin order.
    for item in top_level_instances:
        statement = item["statement"]
        if statement.start in replacements:
            continue
        physical = item["instance"]
        mapped_nodes = [map_physical_node(node)[0] for node in physical.nodes]
        methods = [map_physical_node(node)[1] for node in physical.nodes]
        if mapped_nodes and all(method != "unmapped" for method in methods):
            tokens = statement.logical.split()
            rewritten = " ".join([tokens[0], *mapped_nodes, tokens[-1]])
            replacements[statement.start] = (statement.end, rewritten)
            reference_records.append(
                {
                    "instance": physical.instance,
                    "master": physical.master,
                    "status": "mapped_by_reference_node_alias",
                    "physical_nodes": list(physical.nodes),
                    "mapped_nodes": mapped_nodes,
                    "terminals": [
                        {"physical_node": node, "mapped_node": mapped, "method": method}
                        for node, mapped, method in zip(physical.nodes, mapped_nodes, methods)
                    ],
                }
            )
    # Inject the interconnect instance in the selected physical top.  It is
    # intentionally inside the top subcircuit so distributed nodes are local
    # and device terminals can share them without a wrapper-level short.
    end_statement = next(
        statement for statement in statements if statement.start <= top.end and statement.end == top.end and re.match(r"(?i)^\.ends", statement.logical)
    )
    inserts.setdefault(end_statement.start, []).extend(
        [
            "* Distributed RC ownership: wire/via/coupling network from the PEX sidecar.",
            _make_xpex(pex_ports),
        ]
    )

    rewritten_devices = _render_with_replacements(extracted_text, replacements, {})
    merged_body = _render_with_replacements(extracted_text, replacements, inserts)

    mapped_nodes = {record["mapped_node"] for record in mapping_records.values() if record["mapped_node"] in pex_ports}
    top_text = "\n".join(
        statement.logical
        for index, statement in _subckt_statements(statements, top)
        if enclosing.get(index) == top.name
    )
    top_tokens = {_canonical(token) for token in top_text.split()}
    shared_top_nodes = sorted({port for port in pex_ports if _canonical(port) in top_tokens})
    signal_shared_nodes = [
        port for port in shared_top_nodes if _canonical(port) not in {"0", "VSS", "VDD", "GND", "VCC"}
    ]
    mapped_terminal_count = sum(
        1 for record in device_records for terminal in record["terminals"] if terminal["method"] != "unmapped"
    )
    total_terminal_count = sum(len(record["terminals"]) for record in device_records)
    unresolved_reference = [record for record in reference_records if record.get("status") != "mapped"]
    reference_mapped_count = sum(record.get("status") == "mapped" for record in reference_records)
    if not shared_top_nodes and not mapped_nodes and not reference_records:
        warning = "no extracted top-level node was shared with the distributed RC port list"
    else:
        warning = None

    warnings = []
    if unresolved_devices:
        warnings.append(f"{len(unresolved_devices)} top-level extracted device records retain unmapped terminals")
    if unresolved_reference:
        warnings.append(f"{len(unresolved_reference)} top-level hierarchy records were not reference-mapped")
    if alias_conflicts:
        warnings.append(f"{len(alias_conflicts)} physical node aliases were ambiguous and remain unmapped")
    if warning:
        warnings.append(warning)
    if not args.model_manifest:
        warnings.append("no compact-model manifest was included; caller must provide compatible device models")
    if args.complete_reference_ports:
        warnings.append("reference supply completion is enabled; added reference ports are not independently re-extracted from GDS")

    complete = (
        not unresolved_devices
        and not unresolved_reference
        and (
            bool(signal_shared_nodes)
            or bool(mapped_nodes)
            or reference_mapped_count > 0
            or (total_terminal_count > 0 and mapped_terminal_count == total_terminal_count)
        )
    )
    status = "merged" if complete else "partial_hierarchy"
    if not complete and not args.allow_partial:
        raise SystemExit(
            "post-layout merge is incomplete; use --allow-partial only when the manifest's unresolved hierarchy is accepted"
        )

    args.devices_out.parent.mkdir(parents=True, exist_ok=True)
    args.devices_out.write_text(rewritten_devices, encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    postlayout_parts = [
        "* TR-1um engineering post-layout SPICE merge.",
        "* Device hierarchy is from KLayout GDS extraction; distributed RC is from the PEX sidecar.",
        "* Status and unresolved mappings are recorded in the adjacent PEX manifest.",
    ]
    if args.model_manifest:
        postlayout_parts.append(f'.include "{_absolute(args.model_manifest)}"')
    postlayout_parts.extend(
        [
            f'* Begin device hierarchy: {_absolute(args.devices_out)}',
            merged_body.rstrip(),
            f'* Begin distributed interconnect: {_absolute(args.interconnect)}',
            interconnect_text.rstrip(),
            "",
        ]
    )
    args.output.write_text("\n".join(postlayout_parts), encoding="utf-8")

    device_json = {
        "schema": 1,
        "status": "engineering_estimate_not_foundry_qualified",
        "top_subckt": top.name,
        "source_extracted_spice": _absolute(args.extracted),
        "outputs": {"devices_spice": _absolute(args.devices_out), "postlayout_spice": _absolute(args.output)},
        "device_count": len(device_records),
        "simulation_normalized_device_count": simulation_normalization_count,
        "mapped_terminal_count": mapped_terminal_count,
        "devices": device_records,
        "terminal_mappings": sorted(mapping_records.values(), key=lambda record: (record["logical_node"], record["mapped_node"])),
        "reference_mapping": {
            "source": _absolute(args.reference_netlist) if args.reference_netlist else None,
            "selected_subckt": reference_section_name,
            "records": reference_records,
        },
        "physical_node_aliases": {key: value for key, value in sorted(physical_node_aliases.items())},
        "alias_conflicts": {
            key: sorted(values) for key, values in sorted(alias_conflicts.items())
        },
        "warnings": warnings,
    }
    args.devices_json.parent.mkdir(parents=True, exist_ok=True)
    args.devices_json.write_text(json.dumps(device_json, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema": 1,
        "status": "engineering_estimate_not_foundry_qualified",
        "merge_status": status,
        "architecture": {
            "physical_truth": "final GDS",
            "device_extraction": "KLayout LVS netlist-only extraction",
            "interconnect_extraction": "DEF route graph plus optional GDS overlap engineering estimate",
            "merge_boundary": "selected top-level subcircuit; nested cell/device definitions preserved",
        },
        "ownership": {
            "compact_models": "intrinsic MOS, F_RR, and other device-model terms remain model-owned unless explicitly materialized by the RC ledger",
            "interconnect": "distributed wire/via resistance, node-ground capacitance, and coupling capacitors are owned by tr1um_parasitics",
            "hierarchy": "nested KLayout cells remain intact; only selected-top direct devices and reference-mapped instances are rewritten",
            "simulation_normalization": "KLayout MOS prefixes become subcircuit calls and LVS-only diode area/perimeter parameters are removed",
        },
        "inputs": {
            "gds": _absolute(args.gds) if args.gds else None,
            "def": _absolute(args.def_path) if args.def_path else None,
            "extracted_spice": _absolute(args.extracted),
            "interconnect_spice": _absolute(args.interconnect),
            "parasitics_json": _absolute(args.parasitics),
            "model_manifest": _absolute(args.model_manifest) if args.model_manifest else None,
            "reference_netlist": _absolute(args.reference_netlist) if args.reference_netlist else None,
            "node_map": _absolute(args.net_map) if args.net_map else None,
        },
        "outputs": {
            "devices_spice": _absolute(args.devices_out),
            "devices_json": _absolute(args.devices_json),
            "interconnect_spice": _absolute(args.interconnect),
            "postlayout_spice": _absolute(args.output),
            "manifest": _absolute(args.manifest),
        },
        "hierarchy": {
            "top_subckt": top.name,
            "top_ports": list(top.ports),
            "reference_subckt": reference_section_name,
            "top_level_device_count": len(device_records),
            "simulation_normalized_device_count": simulation_normalization_count,
            "unresolved_top_level_devices": len(unresolved_devices),
            "reference_mapped_instances": sum(record.get("status") == "mapped" for record in reference_records),
            "unresolved_reference_instances": len(unresolved_reference),
            "shared_top_nodes": shared_top_nodes,
            "mapped_interconnect_nodes": sorted(mapped_nodes),
        },
        "mapping": {
            "unique_node_mappings": len(mapping_records),
            "mapped_terminal_count": mapped_terminal_count,
            "total_top_level_terminal_count": total_terminal_count,
            "methods": sorted({record["method"] for record in mapping_records.values()}),
            "physical_node_aliases": {key: value for key, value in sorted(physical_node_aliases.items())},
            "alias_conflicts": {
                key: sorted(values) for key, values in sorted(alias_conflicts.items())
            },
            "records": sorted(mapping_records.values(), key=lambda record: (record["logical_node"], record["mapped_node"])),
        },
        "warnings": warnings,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"postlayout: status={status} top={top.name} devices={len(device_records)} "
        f"mapped_terminals={mapped_terminal_count}/{total_terminal_count} "
        f"reference_instances={sum(record.get('status') == 'mapped' for record in reference_records)}"
    )
    for item in warnings:
        print(f"WARNING: {item}")
    print(f"wrote devices SPICE {args.devices_out}")
    print(f"wrote post-layout SPICE {args.output}")
    print(f"wrote device ledger {args.devices_json}")
    print(f"wrote PEX manifest {args.manifest}")
    return manifest




def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", required=True, type=Path, help="KLayout extracted SPICE device hierarchy")
    parser.add_argument("--interconnect", required=True, type=Path, help="distributed tr1um_parasitics SPICE sidecar")
    parser.add_argument("--parasitics", required=True, type=Path, help="extract_tr1um_parasitics JSON ledger")
    parser.add_argument("--top", required=True, help="selected physical top .SUBCKT")
    parser.add_argument("--output", required=True, type=Path, help="merged post-layout SPICE output")
    parser.add_argument("--devices-out", required=True, type=Path, help="rewritten device hierarchy output")
    parser.add_argument("--devices-json", required=True, type=Path, help="device mapping ledger output")
    parser.add_argument("--manifest", required=True, type=Path, help="PEX merge manifest output")
    parser.add_argument("--gds", type=Path)
    parser.add_argument("--def", dest="def_path", type=Path)
    parser.add_argument("--model-manifest", type=Path)
    parser.add_argument("--reference-netlist", type=Path, help="optional LVS/reference SPICE for top-instance net mapping")
    parser.add_argument("--reference-top", help="reference .SUBCKT; otherwise choose by instance-master population")
    parser.add_argument("--complete-reference-ports", action="store_true", help="allow one missing physical supply port to be completed from the reference")
    parser.add_argument("--net-map", type=Path, help="JSON map of extracted physical node names to routed logical names")
    parser.add_argument("--allow-partial", action="store_true", help="write artifacts and report partial hierarchy instead of failing")
    args = parser.parse_args()
    for path in (args.extracted, args.interconnect, args.parasitics):
        if not path.is_file():
            raise SystemExit(f"missing required PEX input: {path}")
    if args.model_manifest and not args.model_manifest.is_file():
        raise SystemExit(f"missing model manifest: {args.model_manifest}")
    if args.reference_netlist and not args.reference_netlist.is_file():
        raise SystemExit(f"missing reference netlist: {args.reference_netlist}")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
