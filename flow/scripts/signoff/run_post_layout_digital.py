#!/usr/bin/env python3
"""Run SPEF-backed gate-level digital simulations for completed TR-1um runs.

The repository extractor emits distributed, connection-aware estimated RC
SPEF. This runner consumes that distributed network directly for OpenSTA,
generates fresh SDF, and runs the final PNL with an Icarus timing model. The
legacy lumped-RC bridge remains only for older engineering SPEF files that
have an empty ``*CONN`` section; newly extracted timing never collapses its
route resistors or coupling records.

The SDF derivative retains cell IOPATH delays, which include the SPEF-derived
loads, and removes top-level INTERCONNECT records. The result JSON reports
this explicitly. OpenSTA also writes JSON max-path reports for combinational,
register-to-register, input-to-register, and register-to-output classes. Their
frequency estimates are reciprocal full-data-arrival estimates, not
setup/hold-qualified signoff frequencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / "flow/qualification/post_layout_digital_manifest.json"

PATH_CLASS_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("combinational", "in-out", "primary_inputs", "primary_outputs"),
    ("reg_to_reg", "reg-reg", "reg_q", "reg_d"),
    ("input_to_reg", "in-reg", "primary_inputs", "reg_d"),
    ("reg_to_output", "reg-out", "reg_q", "primary_outputs"),
)



class RunnerError(RuntimeError):
    """A case cannot be prepared or executed reproducibly."""


@dataclass(frozen=True)
class CellModel:
    name: str
    header_ports: tuple[str, ...]
    body: str
    explicit_outputs: frozenset[str]
    assigned_outputs: frozenset[str]
    procedural_outputs: frozenset[str]

    @property
    def outputs(self) -> frozenset[str]:
        return frozenset(
            self.explicit_outputs | self.assigned_outputs | self.procedural_outputs
        )


@dataclass(frozen=True)
class SpefNet:
    raw_name: str
    total_cap_pf: float
    lines: tuple[str, ...]


@dataclass(frozen=True)
class SdfCell:
    celltype: str
    instance: str
    block: str
    arcs: tuple[tuple[str, str], ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    candidate = (base / path).resolve()
    if candidate.exists():
        return candidate
    fallback = (REPO_ROOT / path).resolve()
    return fallback


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid manifest JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RunnerError("manifest root must be an object")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RunnerError("manifest must contain a non-empty cases list")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise RunnerError(f"manifest case {index} must be an object")
    return value


def require_tools() -> None:
    missing = [tool for tool in ("sta", "iverilog", "vvp", "make") if shutil.which(tool) is None]
    if missing:
        raise RunnerError(
            "missing required tools: "
            + ", ".join(missing)
            + "; enter the LibreLane development shell first"
        )


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_s: float,
) -> tuple[int, str, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return 124, output + f"\nTIMEOUT after {timeout_s:.1f}s\n", time.monotonic() - started
    return completed.returncode, completed.stdout, time.monotonic() - started


def module_header_ports(text: str, top: str) -> list[str]:
    match = re.search(
        rf"\bmodule\s+{re.escape(top)}\s*\((.*?)\)\s*;",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RunnerError(f"cannot find module header for {top}")
    ports = [token.strip() for token in match.group(1).split(",") if token.strip()]
    if not ports:
        raise RunnerError(f"module {top} has no ports")
    return ports


def parse_decl_names(declaration: str) -> list[str]:
    names: list[str] = []
    for token in declaration.split(","):
        token = token.strip()
        token = re.sub(r"\b(?:wire|reg|logic|signed)\b", "", token).strip()
        if token:
            names.append(token)
    return names


def expand_decl_names(width: str | None, names: Iterable[str]) -> list[str]:
    clean_names = [name.strip() for name in names if name.strip()]
    if not width:
        return clean_names
    bounds = re.fullmatch(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", width.strip())
    if not bounds:
        raise RunnerError(f"unsupported vector declaration: {width}")
    first, second = int(bounds.group(1)), int(bounds.group(2))
    indices = range(first, second - 1, -1) if first >= second else range(first, second + 1)
    expanded: list[str] = []
    for name in clean_names:
        expanded.extend(f"{name}[{index}]" for index in indices)
    return expanded


def top_port_directions(text: str, top: str) -> dict[str, str]:
    header = re.search(
        rf"\bmodule\s+{re.escape(top)}\s*\(.*?\)\s*;",
        text,
        flags=re.DOTALL,
    )
    if not header:
        raise RunnerError(f"cannot find module body for {top}")
    end = text.find("endmodule", header.end())
    if end < 0:
        raise RunnerError(f"module {top} has no endmodule")
    body = text[header.end() : end]
    declaration_re = re.compile(
        r"^[ \t]*(input|output|inout)[ \t]+"
        r"(?:(?:wire|reg|logic|signed)[ \t]+)*"
        r"(?:(\[[ \t]*\d+[ \t]*:[ \t]*\d+[ \t]*\])[ \t]+)?"
        r"([^;\n]+);",
        flags=re.MULTILINE,
    )
    directions: dict[str, str] = {}
    for match in declaration_re.finditer(body):
        direction, width, declaration = match.groups()
        for name in expand_decl_names(width, parse_decl_names(declaration)):
            directions[name] = direction
    if not directions:
        raise RunnerError(f"module {top} has no ANSI-style port declarations")
    return directions


def normalize_net(value: str) -> str:
    net = value.strip()
    if net.startswith("\\"):
        net = net[1:]
    net = net.replace(r"\[", "[").replace(r"\]", "]")
    return net.strip()


def parse_netlist_connections(
    netlist_text: str,
    top: str,
    cell_models: dict[str, CellModel],
) -> tuple[dict[str, list[tuple[str, str, str]]], list[str]]:
    directions = top_port_directions(netlist_text, top)
    connections: dict[str, list[tuple[str, str, str]]] = {}
    for net, direction in directions.items():
        connections.setdefault(net, []).append(("PORT", net, direction))

    header = re.search(
        rf"\bmodule\s+{re.escape(top)}\s*\(.*?\)\s*;",
        netlist_text,
        flags=re.DOTALL,
    )
    if not header:
        raise RunnerError(f"cannot find module {top}")
    end = netlist_text.find("endmodule", header.end())
    if end < 0:
        raise RunnerError(f"module {top} has no endmodule")
    body = netlist_text[header.end() : end]
    instance_re = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_$]*)\s+"
        r"([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;",
        flags=re.MULTILINE | re.DOTALL,
    )
    port_re = re.compile(r"\.([A-Za-z_][A-Za-z0-9_$]*)\s*\(([^()]*)\)")
    unknown_cells: set[str] = set()
    for match in instance_re.finditer(body):
        celltype, instance, connection_text = match.groups()
        if celltype not in cell_models:
            unknown_cells.add(celltype)
            continue
        for pin_match in port_re.finditer(connection_text):
            pin, expression = pin_match.groups()
            net = normalize_net(expression)
            if not net:
                raise RunnerError(f"empty connection: {celltype} {instance}.{pin}")
            if pin in {"VDD", "GND"}:
                direction = "B"
            elif pin in cell_models[celltype].outputs:
                direction = "O"
            else:
                direction = "I"
            entry = ("INSTANCE", f"{instance}:{pin}", direction)
            if entry not in connections.setdefault(net, []):
                connections[net].append(entry)
    if unknown_cells:
        raise RunnerError(
            "PNL references cells absent from the access model: "
            + ", ".join(sorted(unknown_cells))
        )
    return connections, sorted(directions)


def parse_cell_models(text: str) -> dict[str, CellModel]:
    module_re = re.compile(
        r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;"
        r"(.*?)^\s*endmodule\b",
        flags=re.MULTILINE | re.DOTALL,
    )
    models: dict[str, CellModel] = {}
    declaration_re = re.compile(
        r"^[ \t]*(input|output|inout)[ \t]+([^;\n]+);",
        flags=re.MULTILINE,
    )
    for match in module_re.finditer(text):
        name, port_text, body = match.groups()
        ports = tuple(token.strip() for token in port_text.split(",") if token.strip())
        explicit_outputs: set[str] = set()
        for declaration in declaration_re.finditer(body):
            direction, names = declaration.groups()
            if direction == "output":
                explicit_outputs.update(parse_decl_names(names))
        assigned_outputs = set(re.findall(r"\bassign\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=", body))
        procedural_outputs = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*<=", body))
        models[name] = CellModel(
            name=name,
            header_ports=ports,
            body=body,
            explicit_outputs=frozenset(explicit_outputs),
            assigned_outputs=frozenset(assigned_outputs),
            procedural_outputs=frozenset(procedural_outputs),
        )
    if not models:
        raise RunnerError("no cell modules found in access Verilog model")
    return models


def extract_sdf_cells(text: str) -> list[SdfCell]:
    lines = text.splitlines()
    blocks: list[str] = []
    active: list[str] | None = None
    depth = 0
    for line in lines:
        if active is None and line.strip() == "(CELL":
            active = []
            depth = 0
        if active is None:
            continue
        active.append(line)
        depth += line.count("(") - line.count(")")
        if depth == 0:
            blocks.append("\n".join(active))
            active = None
    if active is not None:
        raise RunnerError("unterminated CELL block in generated SDF")

    cells: list[SdfCell] = []
    for block in blocks:
        cell_match = re.search(r'\(CELLTYPE\s+"([^"]+)"\)', block)
        instance_match = re.search(r"\(INSTANCE\s*([^\)]*)\)", block)
        if not cell_match or not instance_match:
            raise RunnerError("malformed CELL block in generated SDF")
        arcs = tuple(
            (source, destination)
            for source, destination in re.findall(
                r"\(IOPATH\s+([^\s()]+)\s+([^\s()]+)", block
            )
        )
        cells.append(
            SdfCell(
                celltype=cell_match.group(1),
                instance=instance_match.group(1).strip(),
                block=block,
                arcs=arcs,
            )
        )
    return cells


def generate_timing_cell_model(
    source_text: str,
    sdf_text: str,
    output_path: Path,
) -> dict[str, int]:
    models = parse_cell_models(source_text)
    arc_map: dict[str, set[tuple[str, str]]] = {}
    for cell in extract_sdf_cells(sdf_text):
        arc_map.setdefault(cell.celltype, set()).update(cell.arcs)

    module_re = re.compile(
        r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;"
        r"(.*?)^\s*endmodule\b",
        flags=re.MULTILINE | re.DOTALL,
    )
    declaration_re = re.compile(
        r"^[ \t]*(input|output|inout)[ \t]+[^;\n]+;[ \t]*(?:\n|$)",
        flags=re.MULTILINE,
    )
    rendered: list[str] = ["// Generated from the TR-1um access behavioral model for SDF simulation.", "`timescale 1ns/1ps", ""]
    arc_count = 0
    initialized_count = 0
    module_count = 0
    for match in module_re.finditer(source_text):
        name, port_text, body = match.groups()
        ports = tuple(token.strip() for token in port_text.split(",") if token.strip())
        model = models[name]
        outputs = set(model.outputs)
        outputs.intersection_update(ports)
        power = {pin for pin in ports if pin in {"VDD", "GND"}}
        inputs = [pin for pin in ports if pin not in outputs and pin not in power]
        output_regs = sorted(outputs.intersection(model.procedural_outputs))
        output_wires = sorted(outputs.difference(output_regs))
        body_without_declarations = declaration_re.sub("", body).strip()
        rendered.append(f"module {name} ({', '.join(ports)});")
        if inputs:
            rendered.append(f"  input {', '.join(inputs)};")
        if output_wires:
            rendered.append(f"  output wire {', '.join(output_wires)};")
        if output_regs:
            rendered.append(f"  output reg {', '.join(output_regs)};")
        if power:
            rendered.append(f"  inout {', '.join(pin for pin in ports if pin in power)};")
        if output_regs:
            for pin in output_regs:
                rendered.append(f"  initial {pin} = 1'b0;")
            initialized_count += len(output_regs)
        if body_without_declarations:
            rendered.extend("  " + line if line else "" for line in body_without_declarations.splitlines())
        arcs = sorted(
            (source, destination)
            for source, destination in arc_map.get(name, set())
            if source in ports and destination in ports
        )
        if arcs:
            rendered.append("")
            rendered.append("  specify")
            for source, destination in arcs:
                rendered.append(f"    ({source} *> {destination}) = (0, 0);")
            rendered.append("  endspecify")
            arc_count += len(arcs)
        rendered.append("endmodule")
        rendered.append("")
        module_count += 1
    if module_count != len(models):
        raise RunnerError("cell model parser lost one or more modules")
    output_path.write_text("\n".join(rendered), encoding="utf-8")
    return {
        "cell_module_count": module_count,
        "specify_arc_count": arc_count,
        "initialized_sequential_output_count": initialized_count,
    }


def parse_spef_nets(text: str) -> list[SpefNet]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("*D_NET ")]
    if not starts:
        raise RunnerError("SPEF contains no *D_NET records")
    nets: list[SpefNet] = []
    for offset, start in enumerate(starts):
        stop = starts[offset + 1] if offset + 1 < len(starts) else next(
            (index for index in range(start + 1, len(lines)) if lines[index].startswith("*#")),
            len(lines),
        )
        fields = lines[start].split()
        if len(fields) < 3:
            raise RunnerError(f"malformed SPEF D_NET line: {lines[start]}")
        try:
            total_cap = float(fields[2])
        except ValueError as exc:
            raise RunnerError(f"invalid SPEF capacitance: {lines[start]}") from exc
        if not math.isfinite(total_cap) or total_cap < 0.0:
            raise RunnerError(f"invalid SPEF capacitance: {lines[start]}")
        nets.append(SpefNet(fields[1], total_cap, tuple(lines[start:stop])))
    return nets


def spef_record_stats(text: str) -> dict[str, int]:
    """Count connection, capacitance, and distributed resistance records."""
    nets = parse_spef_nets(text)
    connection_count = 0
    ground_cap_count = 0
    coupling_count = 0
    resistor_count = 0
    distributed_node_count = 0
    distributed_nodes: set[str] = set()
    for net in nets:
        section: str | None = None
        for line in net.lines[1:]:
            stripped = line.strip()
            if stripped == "*CONN":
                section = "CONN"
                continue
            if stripped == "*CAP":
                section = "CAP"
                continue
            if stripped == "*RES":
                section = "RES"
                continue
            if stripped == "*END":
                break
            fields = stripped.split()
            if not fields:
                continue
            if section == "CONN" and fields[0] in {"*P", "*I"}:
                connection_count += 1
                continue
            if section == "CAP":
                if len(fields) == 3:
                    ground_cap_count += 1
                elif len(fields) >= 4:
                    coupling_count += 1
                    distributed_nodes.update(
                        node for node in fields[1:3] if ":" in node and node.rsplit(":", 1)[1].isdigit()
                    )
            elif section == "RES" and len(fields) >= 4:
                resistor_count += 1
                distributed_nodes.update(
                    node for node in fields[1:3] if ":" in node and node.rsplit(":", 1)[1].isdigit()
                )
        distributed_node_count = len(distributed_nodes)
    return {
        "spef_net_count": len(nets),
        "spef_connection_count": connection_count,
        "spef_ground_cap_record_count": ground_cap_count,
        "spef_coupling_record_count": coupling_count,
        "spef_resistor_record_count": resistor_count,
        "spef_distributed_node_count": distributed_node_count,
    }


def prepare_sta_spef(
    source_text: str,
    netlist_text: str,
    top: str,
    cell_models: dict[str, CellModel],
    output_path: Path,
) -> dict[str, int | str]:
    """Use distributed source PEX, with an explicit legacy-file fallback."""
    source_stats = spef_record_stats(source_text)
    if source_stats["spef_connection_count"] > 0 and source_stats["spef_distributed_node_count"] > 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            source_text if source_text.endswith("\n") else source_text + "\n",
            encoding="utf-8",
        )
        return {
            **source_stats,
            "spef_source_mode": "distributed_direct",
            "spef_coupling_records_collapsed": 0,
            "spef_star_resistor_count": 0,
        }
    legacy_stats = make_lumped_spef(
        source_text,
        netlist_text,
        top,
        cell_models,
        output_path,
    )
    return {
        **source_stats,
        **legacy_stats,
        "spef_source_mode": "legacy_lumped_bridge",
    }


def original_spef_stats(net: SpefNet) -> tuple[int, float]:
    in_cap = False
    in_res = False
    coupling_count = 0
    resistance = 0.0
    for line in net.lines[1:]:
        stripped = line.strip()
        if stripped == "*CAP":
            in_cap, in_res = True, False
            continue
        if stripped == "*RES":
            in_cap, in_res = False, True
            continue
        if stripped == "*END":
            break
        fields = stripped.split()
        if in_cap and len(fields) >= 4:
            coupling_count += 1
        if in_res and len(fields) >= 4 and resistance == 0.0:
            try:
                resistance = float(fields[3])
            except ValueError as exc:
                raise RunnerError(f"invalid SPEF resistance line: {line}") from exc
    return coupling_count, resistance


def make_lumped_spef(
    source_text: str,
    netlist_text: str,
    top: str,
    cell_models: dict[str, CellModel],
    output_path: Path,
) -> dict[str, int]:
    connections, _ = parse_netlist_connections(netlist_text, top, cell_models)
    source_nets = parse_spef_nets(source_text)
    header_end = source_text.find("*D_NET ")
    if header_end < 0:
        raise RunnerError("SPEF contains no global header")
    header = source_text[:header_end].rstrip().splitlines()
    output: list[str] = list(header)
    unconnected: list[str] = []
    total_connections = 0
    collapsed_couplings = 0
    resistor_records = 0
    for net in source_nets:
        key = normalize_net(net.raw_name)
        entries = connections.get(key, [])
        if not entries:
            unconnected.append(key)
            continue
        seen: set[tuple[str, str]] = set()
        unique_entries: list[tuple[str, str, str]] = []
        for kind, node_or_port, direction in entries:
            identity = (kind, node_or_port)
            if identity not in seen:
                seen.add(identity)
                unique_entries.append((kind, node_or_port, direction))
        if not unique_entries:
            unconnected.append(key)
            continue
        coupling_count, resistance = original_spef_stats(net)
        output.append(f"*D_NET {net.raw_name} {net.total_cap_pf:.9e}")
        output.append("*CONN")
        nodes: list[str] = []
        for kind, node_or_port, direction in unique_entries:
            if kind == "PORT":
                spef_direction = {"input": "I", "output": "O", "inout": "B"}[direction]
                output.append(f"*P {net.raw_name} {spef_direction}")
                nodes.append(net.raw_name)
            else:
                output.append(f"*I {node_or_port} {direction[0].upper()}")
                nodes.append(node_or_port)
        collapsed_couplings += coupling_count
        if resistance > 0.0 and len(nodes) > 1:
            output.append("*RES")
            branch = resistance / float(len(nodes) - 1)
            for index, node in enumerate(nodes[1:], start=1):
                output.append(f"{index} {nodes[0]} {node} {branch:.9e}")
                resistor_records += 1
        output.append("*END")
        output.append("")
        total_connections += len(nodes)
    if unconnected:
        preview = ", ".join(unconnected[:12])
        suffix = "" if len(unconnected) <= 12 else f" (+{len(unconnected) - 12} more)"
        raise RunnerError(
            f"{len(unconnected)} SPEF nets have no PNL connection ({preview}{suffix})"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return {
        "spef_net_count": len(source_nets),
        "spef_connection_count": total_connections,
        "spef_coupling_records_collapsed": collapsed_couplings,
        "spef_star_resistor_count": resistor_records,
    }


def tcl_quote(path: Path) -> str:
    return "{" + str(path).replace("}", "\\}").replace("{", "\\{") + "}"


def write_sta_script(
    path: Path,
    *,
    liberty: Path,
    netlist: Path,
    top: str,
    sdc: Path,
    spef: Path,
    sdf: Path,
    path_reports: dict[str, Path],
) -> None:
    lines = [
        f"read_liberty {tcl_quote(liberty)}",
        f"read_verilog {tcl_quote(netlist)}",
        f"link_design {top}",
        f"read_sdc {tcl_quote(sdc)}",
        f"read_spef {tcl_quote(spef)}",
        f"write_sdf {tcl_quote(sdf)}",
        "",
        "set regs [all_registers -cells]",
        "set reg_d [get_pins -of_objects $regs -filter {name == D}]",
        "set reg_q [all_registers -output_pins]",
        "set primary_inputs {}",
        "foreach port [all_inputs -no_clocks] {",
        "    if {[get_property $port direction] == \"input\"} {",
        "        lappend primary_inputs $port",
        "    }",
        "}",
        "set primary_outputs {}",
        "foreach port [all_outputs] {",
        "    if {[get_property $port direction] == \"output\"} {",
        "        lappend primary_outputs $port",
        "    }",
        "}",
        "",
    ]
    for class_name, _, from_var, to_var in PATH_CLASS_SPECS:
        report_path = tcl_quote(path_reports[class_name])
        lines.extend(
            [
                f"if {{[llength ${from_var}] > 0 && [llength ${to_var}] > 0}} {{",
                "    report_checks "
                f"-from ${from_var} -to ${to_var} "
                "-path_delay max -unconstrained -format json "
                "-digits 6 -group_path_count 1000000 "
                f"> {report_path}",
                "} else {",
                f"    set report_handle [open {report_path} w]",
                '    puts $report_handle {{"checks": []}}',
                "    close $report_handle",
                "}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_sdf_metrics(text: str) -> dict[str, float | int]:
    iopath_lines = [line for line in text.splitlines() if "(IOPATH " in line]
    interconnect_lines = [line for line in text.splitlines() if "(INTERCONNECT " in line]
    max_delay = 0.0
    for line in iopath_lines:
        groups = re.findall(r"\(([^()]*)\)", line)
        for group in groups:
            for token in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", group):
                max_delay = max(max_delay, float(token))
    return {
        "iopath_record_count": len(iopath_lines),
        "interconnect_record_count": len(interconnect_lines),
        "max_iopath_delay_ns": max_delay,
    }


def finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_sta_path_report(path: Path, *, path_kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"invalid OpenSTA path report {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("checks"), list):
        raise RunnerError(f"OpenSTA path report has no checks list: {path}")

    checks = payload["checks"]
    candidates: list[dict[str, Any]] = []
    for check in checks:
        if not isinstance(check, dict):
            raise RunnerError(f"OpenSTA path report contains a non-object check: {path}")
        source_path = check.get("source_path")
        if not isinstance(source_path, list):
            continue
        arrivals = [
            arrival
            for point in source_path
            if isinstance(point, dict)
            for arrival in [finite_float(point.get("arrival"))]
            if arrival is not None
        ]
        if not arrivals:
            continue
        data_arrival_s = finite_float(check.get("data_arrival_time"))
        if data_arrival_s is None:
            data_arrival_s = arrivals[-1]
        logic_delay_s = arrivals[-1] - arrivals[0] if len(arrivals) >= 2 else None
        if logic_delay_s is not None and logic_delay_s < 0.0:
            logic_delay_s = None
        candidates.append(
            {
                "data_arrival_s": data_arrival_s,
                "logic_delay_s": logic_delay_s,
                "startpoint": check.get("startpoint"),
                "endpoint": check.get("endpoint"),
                "type": check.get("type"),
            }
        )

    report_hash = sha256_file(path)
    if not candidates:
        return {
            "status": "not_found",
            "path_kind": path_kind,
            "path_count": len(checks),
            "valid_path_count": 0,
            "max_path_delay_ns": None,
            "max_data_arrival_ns": None,
            "max_logic_segment_delay_ns": None,
            "frequency_hz": None,
            "frequency_mhz": None,
            "worst_startpoint": None,
            "worst_endpoint": None,
            "worst_check_type": None,
            "report_sha256": report_hash,
            "reason": "OpenSTA reported no max path with arrival data in this class.",
        }

    worst = max(candidates, key=lambda candidate: candidate["data_arrival_s"])
    logic_candidates = [
        candidate for candidate in candidates if candidate["logic_delay_s"] is not None
    ]
    worst_logic = (
        max(logic_candidates, key=lambda candidate: candidate["logic_delay_s"])
        if logic_candidates
        else None
    )
    data_arrival_s = worst["data_arrival_s"]
    frequency_hz = 1.0 / data_arrival_s if data_arrival_s > 0.0 else None
    return {
        "status": "available",
        "path_kind": path_kind,
        "path_count": len(checks),
        "valid_path_count": len(candidates),
        "max_path_delay_ns": round(data_arrival_s * 1.0e9, 6),
        "max_data_arrival_ns": round(data_arrival_s * 1.0e9, 6),
        "max_logic_segment_delay_ns": (
            round(worst_logic["logic_delay_s"] * 1.0e9, 6)
            if worst_logic is not None
            else None
        ),
        "frequency_hz": round(frequency_hz, 3) if frequency_hz is not None else None,
        "frequency_mhz": (
            round(frequency_hz / 1.0e6, 6)
            if frequency_hz is not None
            else None
        ),
        "worst_startpoint": worst["startpoint"],
        "worst_endpoint": worst["endpoint"],
        "worst_check_type": worst["type"],
        "logic_worst_startpoint": (
            worst_logic["startpoint"] if worst_logic is not None else None
        ),
        "logic_worst_endpoint": worst_logic["endpoint"] if worst_logic is not None else None,
        "report_sha256": report_hash,
    }


def iverilog_sdf(text: str, top: str, output_path: Path) -> dict[str, int]:
    lines = text.splitlines()
    blocks: list[tuple[int, int, SdfCell]] = []
    active: list[str] | None = None
    active_start = 0
    depth = 0
    for index, line in enumerate(lines):
        if active is None and line.strip() == "(CELL":
            active = []
            active_start = index
            depth = 0
        if active is None:
            continue
        active.append(line)
        depth += line.count("(") - line.count(")")
        if depth == 0:
            block_text = "\n".join(active)
            cell_match = re.search(r'\(CELLTYPE\s+"([^"]+)"\)', block_text)
            instance_match = re.search(r"\(INSTANCE\s*([^\)]*)\)", block_text)
            if not cell_match or not instance_match:
                raise RunnerError("malformed SDF CELL while preparing Icarus view")
            arcs = tuple(
                (source, destination)
                for source, destination in re.findall(
                    r"\(IOPATH\s+([^\s()]+)\s+([^\s()]+)", block_text
                )
            )
            cell = SdfCell(
                celltype=cell_match.group(1),
                instance=instance_match.group(1).strip(),
                block=block_text,
                arcs=arcs,
            )
            blocks.append((active_start, index + 1, cell))
            active = None
    if active is not None:
        raise RunnerError("unterminated SDF CELL while preparing Icarus view")
    if not blocks:
        raise RunnerError("generated SDF has no CELL blocks")

    first_cell = blocks[0][0]
    last_cell = blocks[-1][1]
    retained: list[str] = list(lines[:first_cell])
    removed_root = 0
    for _, _, cell in blocks:
        if cell.celltype == top and not cell.instance:
            removed_root += 1
            continue
        if not cell.arcs:
            continue
        retained.extend(cell.block.splitlines())
    retained.extend(lines[last_cell:])
    filtered = [
        line
        for line in retained
        if "(INTERCONNECT " not in line and not line.lstrip().startswith("*#")
    ]
    normalized = "\n".join(filtered) + "\n"
    normalized = re.sub(
        r"\(([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?):"
        r":([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\)",
        lambda match: f"({match.group(1)}:{match.group(1)}:{match.group(2)})",
        normalized,
    )
    if "(INTERCONNECT " in normalized:
        raise RunnerError("Icarus SDF still contains INTERCONNECT records")
    if normalized.count("(") != normalized.count(")"):
        raise RunnerError("Icarus SDF parentheses are unbalanced")
    if "(IOPATH " not in normalized:
        raise RunnerError("Icarus SDF contains no IOPATH records")
    output_path.write_text(normalized, encoding="utf-8")
    return {
        "sdf_root_cell_blocks_removed": removed_root,
        "sdf_interconnect_records_removed": text.count("(INTERCONNECT "),
        "sdf_iopath_records_retained": normalized.count("(IOPATH "),
    }


def verilog_string(path: Path) -> str:
    return json.dumps(str(path))


def replace_dut_instance(
    tb_text: str,
    *,
    top: str,
    instance: str,
    pnl_ports: list[str],
    port_map: dict[str, str],
    sdf_path: Path,
) -> str:
    missing = [port for port in pnl_ports if port not in port_map]
    if missing:
        raise RunnerError(f"{top} manifest port map misses: {', '.join(missing)}")
    named_connections = ",\n".join(
        f"    .{port}({port_map[port]})" for port in pnl_ports
    )
    replacement = (
        f"  {top} {instance} (\n"
        f"{named_connections}\n"
        "  );\n"
        f"  initial $sdf_annotate({verilog_string(sdf_path)}, {instance});"
    )
    pattern = re.compile(
        rf"^\s*{re.escape(top)}\s+{re.escape(instance)}\s*\(.*?\)\s*;",
        flags=re.MULTILINE | re.DOTALL,
    )
    matches = list(pattern.finditer(tb_text))
    if len(matches) != 1:
        raise RunnerError(
            f"expected one {top} {instance} instantiation in testbench, found {len(matches)}"
        )
    match = matches[0]
    return tb_text[: match.start()] + replacement + tb_text[match.end() :]


def slow_testbench(
    text: str,
    *,
    case: dict[str, Any],
    max_delay_ns: float,
) -> tuple[str, dict[str, float]]:
    base_period = float(case.get("clock_period_ns", 10.0))
    if base_period <= 0.0:
        raise RunnerError(f"{case['name']} clock_period_ns must be positive")
    margin = float(case.get("slow_clock_cell_delay_margin", 20.0))
    settle_factor = float(case.get("slow_settle_delay_factor", 1.25))
    slow_period = max(base_period, base_period + margin * max_delay_ns)
    settle_ns = max(1.0, settle_factor * max_delay_ns)
    ratio = slow_period / base_period
    style = case.get("timing_style", "small")
    if style == "uart":
        text, count_clock = re.subn(
            r"(CLOCK_PERIOD_NS\s*=\s*)[-+0-9.eE]+",
            rf"\g<1>{slow_period:.9f}",
            text,
            count=1,
        )
        text, count_bit = re.subn(
            r"(BIT_PERIOD_NS\s*=\s*)[-+0-9.eE]+",
            rf"\g<1>{float(case['bit_period_ns']) * ratio:.9f}",
            text,
            count=1,
        )
        text, count_timeout = re.subn(
            r"#7000000\s*;",
            f"#{7000000.0 * ratio:.3f};",
            text,
            count=1,
        )
        if count_clock != 1 or count_bit != 1 or count_timeout != 1:
            raise RunnerError(f"could not scale UART timing literals for {case['name']}")
    else:
        text, count_clock = re.subn(
            r"#5\s+clk\s*=\s*~clk\s*;",
            f"#{slow_period / 2.0:.9f} clk=~clk;",
            text,
            count=1,
        )
        if count_clock != 1:
            raise RunnerError(f"could not scale clock literal for {case['name']}")
        text = re.sub(r"#1\b", f"#{settle_ns:.9f}", text)
    return text, {
        "slow_clock_period_ns": slow_period,
        "slow_settle_delay_ns": settle_ns,
        "slow_time_ratio": ratio,
    }


def run_rtl_case(case: dict[str, Any], case_output: Path, manifest_path: Path) -> dict[str, Any]:
    rtl_source = resolve_path(case["rtl_source"], manifest_path.parent)
    rtl_tb = resolve_path(case["rtl_testbench"], manifest_path.parent)
    source_dir = rtl_source.parent
    if not rtl_source.is_file() or not rtl_tb.is_file():
        raise RunnerError(f"missing RTL simulation source for {case['name']}")
    code, output, elapsed = run_command(
        ["make", "-C", str(source_dir), "clean", "sim"],
        cwd=REPO_ROOT,
        timeout_s=120.0,
    )
    cleanup_code, cleanup_output, _ = run_command(
        ["make", "-C", str(source_dir), "clean"],
        cwd=REPO_ROOT,
        timeout_s=30.0,
    )
    (case_output / "rtl.log").write_text(
        output + "\n--- cleanup ---\n" + cleanup_output,
        encoding="utf-8",
    )
    marker = str(case["pass_marker"])
    passed = code == 0 and marker in output
    return {
        "status": "pass" if passed else "fail",
        "returncode": code,
        "pass_marker_found": marker in output,
        "elapsed_s": elapsed,
        "cleanup_returncode": cleanup_code,
    }


def run_gate_sim(
    *,
    case: dict[str, Any],
    mode: str,
    source_tb: Path,
    netlist: Path,
    cell_model: Path,
    sdf_path: Path,
    pnl_ports: list[str],
    output_dir: Path,
    sdf_metrics: dict[str, Any],
    timing_info: dict[str, float],
    timeout_s: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    text = source_tb.read_text(encoding="utf-8")
    text = replace_dut_instance(
        text,
        top=str(case["top"]),
        instance=str(case.get("instance", "dut")),
        pnl_ports=pnl_ports,
        port_map=dict(case["ports"]),
        sdf_path=sdf_path,
    )
    if mode == "slow":
        text, slow_info = slow_testbench(
            text,
            case=case,
            max_delay_ns=float(sdf_metrics["max_iopath_delay_ns"]),
        )
    else:
        slow_info = {}
    tb_path = output_dir / f"{case['top']}_{mode}_tb.v"
    tb_path.write_text(text, encoding="utf-8")
    sim_path = output_dir / f"{case['top']}_{mode}.vvp"
    compile_code, compile_output, compile_elapsed = run_command(
        [
            "iverilog",
            "-g2012",
            "-gspecify",
            "-s",
            str(case.get("tb_module", f"{case['top']}_tb")),
            "-o",
            str(sim_path),
            str(netlist),
            str(cell_model),
            str(tb_path),
        ],
        cwd=REPO_ROOT,
        timeout_s=timeout_s,
    )
    (output_dir / "compile.log").write_text(compile_output, encoding="utf-8")
    if compile_code != 0:
        return {
            "status": "fail",
            "stage": "compile",
            "returncode": compile_code,
            "pass_marker_found": False,
            "elapsed_s": 0.0,
            "compile_elapsed_s": compile_elapsed,
            "timing": timing_info,
            "slow": slow_info,
        }
    run_code, run_output, run_elapsed = run_command(
        ["vvp", str(sim_path)],
        cwd=REPO_ROOT,
        timeout_s=timeout_s,
    )
    (output_dir / "run.log").write_text(run_output, encoding="utf-8")
    marker = str(case["pass_marker"])
    passed = run_code == 0 and marker in run_output
    return {
        "status": "pass" if passed else "fail",
        "stage": "simulation",
        "returncode": run_code,
        "pass_marker_found": marker in run_output,
        "elapsed_s": run_elapsed,
        "compile_elapsed_s": compile_elapsed,
        "timing": timing_info,
        "slow": slow_info,
    }


def run_case(
    case: dict[str, Any],
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    output_root: Path,
    modes: set[str],
    compare_rtl: bool,
    timeout_s: float,
) -> dict[str, Any]:
    name = str(case.get("name", ""))
    required = ["top", "netlist", "spef", "sdc", "testbench", "ports", "pass_marker"]
    missing = [key for key in required if key not in case]
    if missing:
        raise RunnerError(f"{name or '<unnamed>'} missing manifest keys: {', '.join(missing)}")
    top = str(case["top"])
    netlist = resolve_path(str(case["netlist"]), manifest_path.parent)
    spef = resolve_path(str(case["spef"]), manifest_path.parent)
    sdc = resolve_path(str(case["sdc"]), manifest_path.parent)
    testbench = resolve_path(str(case["testbench"]), manifest_path.parent)
    cell_verilog = resolve_path(str(manifest["cell_model"]), manifest_path.parent)
    liberty = resolve_path(str(manifest["timing_library"]), manifest_path.parent)
    for path in (netlist, spef, sdc, testbench, cell_verilog, liberty):
        if not path.is_file():
            raise RunnerError(f"{name}: missing input {path}")
    netlist_text = netlist.read_text(encoding="utf-8")
    cell_source = cell_verilog.read_text(encoding="utf-8")
    cell_models = parse_cell_models(cell_source)
    case_root = output_root / name
    case_root.mkdir(parents=True, exist_ok=True)
    path_report_dir = case_root / "path_reports"
    path_report_dir.mkdir(parents=True, exist_ok=True)
    path_reports = {
        class_name: path_report_dir / f"{class_name}.json"
        for class_name, _, _, _ in PATH_CLASS_SPECS
    }

    normalized_spef = case_root / f"{top}.for_sta.spef"
    spef_stats = prepare_sta_spef(
        spef.read_text(encoding="utf-8"),
        netlist_text,
        top,
        cell_models,
        normalized_spef,
    )
    raw_sdf = case_root / f"{top}.from_spef.sdf"
    sta_tcl = case_root / "sta.tcl"
    write_sta_script(
        sta_tcl,
        liberty=liberty,
        netlist=netlist,
        top=top,
        sdc=sdc,
        spef=normalized_spef,
        sdf=raw_sdf,
        path_reports=path_reports,
    )
    sta_code, sta_output, sta_elapsed = run_command(
        ["sta", str(sta_tcl)],
        cwd=case_root,
        timeout_s=timeout_s,
    )
    (case_root / "sta.log").write_text(sta_output, encoding="utf-8")
    if sta_code != 0 or not raw_sdf.is_file():
        raise RunnerError(f"{name}: OpenSTA failed (returncode {sta_code})")
    for report_path in path_reports.values():
        if not report_path.is_file():
            raise RunnerError(f"{name}: OpenSTA did not write path report {report_path}")
    path_analysis: dict[str, Any] = {}
    for class_name, path_kind, _, _ in PATH_CLASS_SPECS:
        report_path = path_reports[class_name]
        metric = parse_sta_path_report(report_path, path_kind=path_kind)
        metric["report_file"] = str(report_path.relative_to(case_root))
        path_analysis[class_name] = metric

    raw_sdf_text = raw_sdf.read_text(encoding="utf-8")
    sdf_metrics = parse_sdf_metrics(raw_sdf_text)
    iverilog_sdf_path = case_root / f"{top}.for_iverilog.sdf"
    sdf_view_stats = iverilog_sdf(raw_sdf_text, top, iverilog_sdf_path)
    timing_model = case_root / f"{top}.timing_cells.v"
    cell_stats = generate_timing_cell_model(cell_source, raw_sdf_text, timing_model)
    pnl_ports = module_header_ports(netlist_text, top)
    timing_info: dict[str, Any] = {
        **sdf_metrics,
        **sdf_view_stats,
        "path_analysis": {
            "frequency_basis": (
                "reciprocal of OpenSTA max data arrival from the launch edge; "
                "setup, hold, skew, and uncertainty are not added"
            ),
            "classes": path_analysis,
        },
        "sdf_interconnect_annotated": False,
        "opensta_elapsed_s": sta_elapsed,
        "source_spef_sha256": sha256_file(spef),
        "normalized_spef_sha256": sha256_file(normalized_spef),
        "iverilog_sdf_sha256": sha256_file(iverilog_sdf_path),
        **spef_stats,
        **cell_stats,
    }
    result: dict[str, Any] = {
        "name": name,
        "top": top,
        "status": "pass",
        "inputs": {
            "netlist": str(netlist),
            "spef": str(spef),
            "sdc": str(sdc),
            "testbench": str(testbench),
        },
        "timing": timing_info,
    }
    if compare_rtl:
        result["rtl"] = run_rtl_case(case, case_root, manifest_path)
    for mode in sorted(modes):
        result[mode] = run_gate_sim(
            case=case,
            mode=mode,
            source_tb=testbench,
            netlist=netlist,
            cell_model=timing_model,
            sdf_path=iverilog_sdf_path,
            pnl_ports=pnl_ports,
            output_dir=case_root / mode,
            sdf_metrics=sdf_metrics,
            timing_info=timing_info,
            timeout_s=timeout_s,
        )
    return result


def aggregate_status(results: list[dict[str, Any]], modes: set[str], compare_rtl: bool) -> dict[str, str]:
    execution_ok = all(
        all(result.get(mode, {}).get("status") in {"pass", "fail"} for mode in modes)
        and (not compare_rtl or result.get("rtl", {}).get("status") in {"pass", "fail"})
        for result in results
    )
    functional_ok = execution_ok and all(
        result.get("slow", result.get("strict", {})).get("status") == "pass"
        and (not compare_rtl or result.get("rtl", {}).get("status") == "pass")
        for result in results
    )
    timing_ok = "strict" not in modes or all(
        result.get("strict", {}).get("status") == "pass" for result in results
    )
    return {
        "execution_status": "PASS" if execution_ok else "FAIL",
        "functional_status": "PASS" if functional_ok else "FAIL",
        "strict_timing_status": "PASS" if timing_ok else "FAIL",
        "status": (
            "PASS"
            if functional_ok and timing_ok
            else "PASS_WITH_TIMING_FAILURES"
            if functional_ok and execution_ok
            else "FAIL"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("strict", "slow", "both"),
        default="both",
        help="strict source-clock timing, slow functional timing, or both",
    )
    parser.add_argument("--no-rtl", action="store_true", help="skip pre-layout RTL comparison")
    parser.add_argument("--timeout", type=float, default=180.0, help="per-command timeout in seconds")
    parser.add_argument("--case", action="append", dest="cases", help="run only this manifest case; repeatable")
    parser.add_argument(
        "--fail-on-strict",
        action="store_true",
        help="return nonzero when a strict source-clock simulation fails",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0.0:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    try:
        require_tools()
        manifest_path = args.manifest.resolve()
        manifest = read_manifest(manifest_path)
        requested = set(args.cases or [])
        cases = [case for case in manifest["cases"] if not requested or case.get("name") in requested]
        if requested and {str(case.get("name")) for case in cases} != requested:
            unknown = sorted(requested - {str(case.get("name")) for case in cases})
            raise RunnerError("unknown manifest case(s): " + ", ".join(unknown))
        output_root = args.output.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        modes = {"strict", "slow"} if args.mode == "both" else {args.mode}
        results: list[dict[str, Any]] = []
        for case in cases:
            name = str(case.get("name", "<unnamed>"))
            print(f"===== {name} =====", flush=True)
            try:
                result = run_case(
                    case,
                    manifest=manifest,
                    manifest_path=manifest_path,
                    output_root=output_root,
                    modes=modes,
                    compare_rtl=not args.no_rtl,
                    timeout_s=args.timeout,
                )
                result["status"] = "pass" if all(
                    result.get(mode, {}).get("status") in {"pass", "fail"} for mode in modes
                ) else "error"
            except RunnerError as exc:
                result = {"name": name, "status": "error", "error": str(exc)}
                print(f"ERROR {name}: {exc}", file=sys.stderr, flush=True)
            results.append(result)
            (output_root / name / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            if result.get("status") == "pass":
                print(f"PREPARED {name}", flush=True)
        aggregate = aggregate_status(results, modes, not args.no_rtl) if results else {
            "execution_status": "FAIL",
            "functional_status": "FAIL",
            "strict_timing_status": "FAIL",
            "status": "FAIL",
        }
        summary = {
            "schema_version": 1,
            "manifest": str(manifest_path),
            "output_root": str(output_root),
            "modes": sorted(modes),
            "compare_rtl": not args.no_rtl,
            **aggregate,
            "cases": results,
        }
        (output_root / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(aggregate, sort_keys=True), flush=True)
        if aggregate["execution_status"] != "PASS" or aggregate["functional_status"] != "PASS":
            return 1
        if args.fail_on_strict and aggregate["strict_timing_status"] != "PASS":
            return 1
        return 0
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
