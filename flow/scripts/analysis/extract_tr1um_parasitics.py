#!/usr/bin/env python3
"""Extract a transparent, engineering-only TR-1um parasitic network.

The open IP62 collateral does not contain a foundry RC/PEX deck.  This tool
therefore does not claim silicon-qualified values.  It combines the checked-in
DEF route geometry, optional GDS overlap geometry, optional KLayout extracted
SPICE devices, and an explicit model file into:

* a distributed SPEF with route-node ground and inter-net coupling capacitance;
* a distributed SPICE RC subcircuit for analog deck inclusion; and
* a JSON ledger that records route widths, resistor edges, and every estimate basis.

The device terms deliberately preserve model ownership.  F_RR is evaluated
from the c_d0 formula in models_IP62_res_v5.lib; F_RS (the GR/poly resistor)
uses an explicitly labelled CSIO proxy because no direct GR capacitance is
published; and GC/AP/AN overlap uses the BSIM3 cgsl/cgdl values.  A consumer
must not add the GC or F_RR terms a second time when the compact device model
already owns them.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RC = ROOT / "pdk_root/TR-1um/libs.tech/librelane/rc_estimate.json"
DEFAULT_MODEL = Path(__file__).with_name("tr1um_parasitic_model.json")
DEFAULT_RR_MODEL = ROOT.parent / "libs.tech/spice/models/models_IP62_res_v5.lib"
DEFAULT_LEF_DIR = ROOT / "pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lef"

# GDS drawing-layer numbers from libs.tech/klayout/tech/drc/00_Layers.drc.
GDS_LAYERS = {
    "AP": (3, 1),
    "AN": (3, 2),
    "AR": (3, 3),
    "GC": (8, 1),
    "GR": (8, 2),
    "M1": (13, 0),
    "M2": (20, 0),
    "M3": (122, 0),
    "WN": (140, 0),
}

SUBSTRATE_ALIASES = ("VSS", "GND", "GROUND", "0", "PSUB", "SUBSTRATE")
SPICE_SUFFIXES = {
    "T": 1.0e12,
    "G": 1.0e9,
    "MEG": 1.0e6,
    "K": 1.0e3,
    "M": 1.0e-3,
    "U": 1.0e-6,
    "N": 1.0e-9,
    "P": 1.0e-12,
    "F": 1.0e-15,
}


@dataclass(frozen=True)
class Segment:
    net: str
    layer: str
    x1_um: float
    y1_um: float
    x2_um: float
    y2_um: float
    width_um: float
    source: str = "DEF"

    @property
    def length_um(self) -> float:
        return abs(self.x2_um - self.x1_um) + abs(self.y2_um - self.y1_um)

    @property
    def orientation(self) -> str:
        return "H" if abs(self.x2_um - self.x1_um) >= abs(self.y2_um - self.y1_um) else "V"

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        half = self.width_um / 2.0
        return (
            min(self.x1_um, self.x2_um) - half,
            min(self.y1_um, self.y2_um) - half,
            max(self.x1_um, self.x2_um) + half,
            max(self.y1_um, self.y2_um) + half,
        )
@dataclass(frozen=True)
class Via:
    net: str
    x_um: float
    y_um: float
    lower_layer: str
    upper_layer: str
    source: str = "DEF"


@dataclass(frozen=True)
class DefComponent:
    name: str
    cell: str
    x_um: float | None
    y_um: float | None
    orientation: str


@dataclass(frozen=True)
class DefPort:
    name: str
    direction: str
    x_um: float | None
    y_um: float | None


@dataclass(frozen=True)
class DefConnection:
    net: str
    instance: str | None
    pin: str
    cell: str | None
    direction: str
    location_um: tuple[float, float] | None

    @property
    def node_name(self) -> str:
        return self.pin if self.instance is None else f"{self.instance}:{self.pin}"


@dataclass(frozen=True)
class WireEdge:
    net: str
    layer: str
    x1_um: float
    y1_um: float
    x2_um: float
    y2_um: float
    width_um: float
    source: str = "DEF"

    @property
    def length_um(self) -> float:
        return abs(self.x2_um - self.x1_um) + abs(self.y2_um - self.y1_um)


@dataclass(frozen=True)
class WireEdgeRecord:
    edge: WireEdge
    node1: str
    midpoint: str
    node2: str


@dataclass
class RouteTopology:
    node_net: dict[str, str]
    node_coordinates: dict[str, tuple[str, float, float]]
    nodes_by_net: dict[str, set[str]]
    edge_records: list[WireEdgeRecord]
    segment_midpoints: dict[int, list[str]]
    via_edges: list[tuple[Via, str, str]]
    connections: dict[str, list[DefConnection]]
    terminal_attachments: dict[str, tuple[str, str]]
    anchor_nodes: dict[str, str]



@dataclass(frozen=True)
class Device:
    model: str
    instance: str
    subckt: str
    nodes: tuple[str, ...]
    width_um: float | None
    length_um: float | None
    source_line: int


@dataclass(frozen=True)
class GdsElement:
    kind: str
    layer: int | None = None
    datatype: int | None = None
    points: tuple[tuple[float, float], ...] = ()
    width: float = 0.0
    text: str | None = None
    child: str | None = None
    origin: tuple[float, float] = (0.0, 0.0)
    angle: float = 0.0
    magnification: float = 1.0
    reflect: bool = False


@dataclass(frozen=True)
class GdsShape:
    layer: int
    datatype: int
    bbox_um: tuple[float, float, float, float]
    hierarchy: str


@dataclass(frozen=True)
class GdsLabel:
    layer: int
    point_um: tuple[float, float]
    text: str
    hierarchy: str


@dataclass
class Network:
    ground_pf: dict[str, float]
    resistance_ohm: dict[str, float]
    coupling_pf: dict[tuple[str, str], float]
    resistor_records: list[dict[str, Any]]
    coupling_records: list[dict[str, Any]]
    ground_records: list[dict[str, Any]]
    device_records: list[dict[str, Any]]
    node_net: dict[str, str]
    net_nodes: dict[str, set[str]]
    connections: dict[str, list[DefConnection]]
    anchor_nodes: dict[str, str]

    @classmethod
    def create(cls) -> "Network":
        return cls(
            defaultdict(float),
            defaultdict(float),
            defaultdict(float),
            [],
            [],
            [],
            [],
            {},
            defaultdict(set),
            defaultdict(list),
            {},
        )

    def register_node(self, net: str, node: str) -> None:
        if not net or not node:
            return
        existing = self.node_net.get(node)
        if existing is not None and existing != net:
            raise ValueError(f"node {node} belongs to both {existing} and {net}")
        self.node_net[node] = net
        self.net_nodes[net].add(node)

    def _canonical_node(self, node: str) -> str:
        return self.anchor_nodes.get(node, node)

    def anchor_for_net(self, net: str) -> str:
        if not net:
            return ""
        anchor = self.anchor_nodes.get(net)
        if anchor is None:
            anchor = net
            self.anchor_nodes[net] = anchor
            self.register_node(net, anchor)
        return anchor

    def add_ground(self, node: str, cap_pf: float, kind: str, basis: str, **details: Any) -> None:
        if not node or cap_pf <= 0.0:
            return
        node = self._canonical_node(node)
        net = self.node_net.get(node, node)
        self.register_node(net, node)
        self.ground_pf[node] += cap_pf
        self.ground_records.append(
            {
                "net": net,
                "node": node,
                "capacitance_pf": cap_pf,
                "kind": kind,
                "basis": basis,
                **details,
            }
        )


    def add_resistor(
        self,
        net: str,
        node1: str,
        node2: str,
        resistance_ohm: float,
        kind: str,
        basis: str,
        **details: Any,
    ) -> None:
        if not net or not node1 or not node2 or resistance_ohm < 0.0:
            return
        self.register_node(net, node1)
        self.register_node(net, node2)
        self.resistance_ohm[net] += resistance_ohm
        self.resistor_records.append(
            {
                "net": net,
                "node1": node1,
                "node2": node2,
                "resistance_ohm": resistance_ohm,
                "kind": kind,
                "basis": basis,
                **details,
            }
        )

    def add_coupling(self, node1: str, node2: str, cap_pf: float, kind: str, basis: str, **details: Any) -> None:
        if not node1 or not node2 or cap_pf <= 0.0:
            return
        node1 = self._canonical_node(node1)
        node2 = self._canonical_node(node2)
        if node1 == node2:
            return
        if node1 not in self.node_net:
            self.register_node(node1, node1)
        if node2 not in self.node_net:
            self.register_node(node2, node2)
        net1 = self.node_net[node1]
        net2 = self.node_net[node2]
        if net1 == net2:
            return
        pair = tuple(sorted((node1, node2)))
        self.coupling_pf[pair] += cap_pf
        self.coupling_records.append(
            {
                "net1": self.node_net[pair[0]],
                "net2": self.node_net[pair[1]],
                "node1": pair[0],
                "node2": pair[1],
                "capacitance_pf": cap_pf,
                "kind": kind,
                "basis": basis,
                **details,
            }
        )

def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing JSON input: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def finite_positive(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} must be a finite positive number") from exc
    if not math.isfinite(number) or number <= 0.0:
        raise SystemExit(f"{label} must be a finite positive number")
    return number


def parse_spice_value(token: str, *, dimension: str = "value") -> float:
    """Parse a SPICE scalar, returning SI units."""
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z]+)?", token.strip())
    if not match:
        raise ValueError(f"invalid SPICE {dimension}: {token}")
    value = float(match.group(1))
    suffix = (match.group(2) or "").upper()
    if suffix == "U" and dimension in {"length", "width"}:
        return value * 1.0e-6
    if suffix in SPICE_SUFFIXES:
        return value * SPICE_SUFFIXES[suffix]
    if not suffix:
        return value
    raise ValueError(f"unsupported SPICE suffix in {dimension}: {token}")


def parse_dimension_um(token: str) -> float:
    return parse_spice_value(token, dimension="length") * 1.0e6


def resolve_path(path: Path, base: Path) -> Path:
    if path.is_absolute():
        return path
    candidate = base / path
    if candidate.exists():
        return candidate
    return ROOT.parent / path


def read_def_header(text: str) -> tuple[str, int]:
    design_match = re.search(r"^DESIGN\s+(\S+)\s*;", text, re.MULTILINE)
    units_match = re.search(r"^UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", text, re.MULTILINE)
    if not design_match or not units_match:
        raise SystemExit("DEF must declare DESIGN and UNITS DISTANCE MICRONS")
    return design_match.group(1), int(units_match.group(1))


def _route_blocks(text: str) -> Iterable[tuple[str, str, str]]:
    """Yield (section, net, complete_net_block) for NETS and SPECIALNETS."""
    section: str | None = None
    current_net: str | None = None
    block: list[str] = []
    for line in text.splitlines():
        section_match = re.match(r"^(NETS|SPECIALNETS)\s+\d+\s*;", line)
        if section_match:
            section = section_match.group(1)
            current_net = None
            block = []
            continue
        if section and re.match(rf"^END {section}\b", line):
            if current_net is not None and block:
                yield section, current_net, "\n".join(block)
            section = None
            current_net = None
            block = []
            continue
        if not section:
            continue
        net_match = re.match(r"^\s*-\s+(\S+)(?:\s|$)", line)
        if net_match:
            if current_net is not None and block:
                yield section, current_net, "\n".join(block)
            current_net = net_match.group(1)
            block = [line]
        elif current_net is not None:
            block.append(line)
            if ";" in line:
                yield section, current_net, "\n".join(block)
                current_net = None
                block = []
    if current_net is not None and block:
        yield section or "NETS", current_net, "\n".join(block)


def _is_number_token(token: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", token))


def _parse_def_components(text: str, dbu: int) -> dict[str, DefComponent]:
    components: dict[str, DefComponent] = {}
    section_match = re.search(r"^COMPONENTS\s+\d+\s*;(.*?)^END COMPONENTS\b", text, re.MULTILINE | re.DOTALL)
    if not section_match:
        return components
    component_re = re.compile(
        r"^\s*-\s+(\S+)\s+(\S+).*?\+\s+(?:FIXED|PLACED)\s+\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)\s+(\S+)",
        re.MULTILINE,
    )
    for match in component_re.finditer(section_match.group(1)):
        components[match.group(1)] = DefComponent(
            name=match.group(1),
            cell=match.group(2),
            x_um=float(match.group(3)) / dbu,
            y_um=float(match.group(4)) / dbu,
            orientation=match.group(5).upper(),
        )
    return components


def _parse_def_ports(text: str, dbu: int) -> dict[str, DefPort]:
    ports: dict[str, DefPort] = {}
    section_match = re.search(r"^PINS\s+\d+\s*;(.*?)^END PINS\b", text, re.MULTILINE | re.DOTALL)
    if not section_match:
        return ports
    block_re = re.compile(r"^\s*-\s+(\S+)(.*?)(?=^\s*-\s+\S+|\Z)", re.MULTILINE | re.DOTALL)
    for match in block_re.finditer(section_match.group(1)):
        name, body = match.groups()
        direction_match = re.search(r"\+\s+DIRECTION\s+(\S+)", body, re.IGNORECASE)
        placement_match = re.search(
            r"\+\s+(?:FIXED|PLACED)\s+\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
            body,
            re.IGNORECASE,
        )
        ports[name] = DefPort(
            name=name,
            direction=(direction_match.group(1).upper() if direction_match else "INOUT"),
            x_um=(float(placement_match.group(1)) / dbu if placement_match else None),
            y_um=(float(placement_match.group(2)) / dbu if placement_match else None),
        )
    return ports


def _lef_pin_geometry(lef_dir: Path | None, cell: str) -> tuple[tuple[float, float], dict[str, tuple[str, float, float]]] | None:
    if lef_dir is None:
        return None
    lef_path = lef_dir / f"{cell}.lef"
    if not lef_path.exists():
        return None
    text = lef_path.read_text(encoding="utf-8", errors="replace")
    macro_match = re.search(rf"\bMACRO\s+{re.escape(cell)}\b(.*?)\bEND\s+{re.escape(cell)}\b", text, re.IGNORECASE | re.DOTALL)
    if not macro_match:
        return None
    body = macro_match.group(1)
    size_match = re.search(r"\bSIZE\s+([0-9.eE+-]+)\s+BY\s+([0-9.eE+-]+)", body, re.IGNORECASE)
    if not size_match:
        return None
    size_um = (float(size_match.group(1)), float(size_match.group(2)))
    pins: dict[str, tuple[str, float, float]] = {}
    pin_re = re.compile(r"\bPIN\s+(\S+)(.*?)(?=\bPIN\s+\S+|\bEND\s+%s\b)" % re.escape(cell), re.IGNORECASE | re.DOTALL)
    for pin_match in pin_re.finditer(body):
        pin_name, pin_body = pin_match.groups()
        direction_match = re.search(r"\bDIRECTION\s+(\S+)", pin_body, re.IGNORECASE)
        rects = [
            tuple(float(value) for value in values)
            for values in re.findall(
                r"\bRECT\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)",
                pin_body,
                re.IGNORECASE,
            )
        ]
        if not rects:
            continue
        x1 = min(rect[0] for rect in rects)
        y1 = min(rect[1] for rect in rects)
        x2 = max(rect[2] for rect in rects)
        y2 = max(rect[3] for rect in rects)
        pins[pin_name] = (
            direction_match.group(1).upper() if direction_match else "INOUT",
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0,
        )
    return size_um, pins


def _transform_pin_location(
    local_x_um: float,
    local_y_um: float,
    size_um: tuple[float, float],
    orientation: str,
) -> tuple[float, float]:
    width_um, height_um = size_um
    orientation = orientation.upper()
    if orientation == "S":
        return width_um - local_x_um, height_um - local_y_um
    if orientation == "FN":
        return width_um - local_x_um, local_y_um
    if orientation == "FS":
        return local_x_um, height_um - local_y_um
    if orientation == "E":
        return height_um - local_y_um, local_x_um
    if orientation == "W":
        return local_y_um, width_um - local_x_um
    if orientation == "FE":
        return height_um - local_y_um, width_um - local_x_um
    if orientation == "FW":
        return local_y_um, local_x_um
    return local_x_um, local_y_um


def _connection_direction(value: str | None) -> str:
    return {"INPUT": "I", "OUTPUT": "O", "INOUT": "B"}.get((value or "INOUT").upper(), "B")


def _parse_def_connections(
    text: str,
    dbu: int,
    lef_dir: Path | None,
) -> dict[str, list[DefConnection]]:
    components = _parse_def_components(text, dbu)
    ports = _parse_def_ports(text, dbu)
    lef_cache: dict[str, tuple[tuple[float, float], dict[str, tuple[str, float, float]]] | None] = {}
    connections: dict[str, list[DefConnection]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    def add_connection(net: str, instance: str | None, pin: str) -> None:
        if not net or not pin or instance == "*":
            return
        node_key = (net, pin if instance is None else f"{instance}:{pin}")
        if node_key in seen:
            return
        seen.add(node_key)
        cell: str | None = None
        direction = "B"
        location: tuple[float, float] | None = None
        if instance is None:
            port = ports.get(pin)
            if port is not None:
                direction = _connection_direction(port.direction)
                if port.x_um is not None and port.y_um is not None:
                    location = (port.x_um, port.y_um)
        else:
            component = components.get(instance)
            if component is not None:
                cell = component.cell
                geometry = lef_cache.setdefault(cell, _lef_pin_geometry(lef_dir, cell))
                if geometry is not None:
                    size_um, pin_geometry = geometry
                    pin_info = pin_geometry.get(pin)
                    if pin_info is None:
                        pin_info = pin_geometry.get(pin.upper())
                    if pin_info is not None:
                        direction = _connection_direction(pin_info[0])
                        local = _transform_pin_location(pin_info[1], pin_info[2], size_um, component.orientation)
                        if component.x_um is not None and component.y_um is not None:
                            location = (component.x_um + local[0], component.y_um + local[1])
        connections[net].append(
            DefConnection(net, instance, pin, cell, direction, location)
        )

    connection_re = re.compile(r"\(\s*(\S+)\s+(\S+)\s*\)")
    for section, net, block in _route_blocks(text):
        for match in connection_re.finditer(block):
            first, second = match.groups()
            if _is_number_token(first) or _is_number_token(second):
                continue
            if first.upper() == "PIN":
                add_connection(net, None, second)
            elif first != "*":
                add_connection(net, first, second)
        if section == "SPECIALNETS" and net not in connections:
            connections[net] = []
    return dict(connections)


def parse_def_segments(
    text: str,
    rc: dict[str, Any],
    lef_dir: Path | None = None,
) -> tuple[
    str,
    list[Segment],
    dict[str, dict[str, float]],
    list[Via],
    dict[str, list[DefConnection]],
]:
    design, dbu = read_def_header(text)
    layers = {entry["layer"]: entry for entry in rc.get("layers", []) + rc.get("reserved_layers", [])}
    via_layer = rc.get("via", {}).get("layer", "V1")
    segments: list[Segment] = []
    vias: list[Via] = []
    seen_vias: set[tuple[str, float, float, str]] = set()
    by_net: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    route_re = re.compile(
        r"(?:^|\s)\+?\s*(?:ROUTED|NEW)\s+(M\d+)\b"
        r"(?:\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+)))?"
        r"(.*?)(?=(?:\s+\+?\s*(?:ROUTED|NEW)\s+M\d+\b)|\s*;|$)",
        re.IGNORECASE | re.DOTALL,
    )
    coordinate_re = re.compile(r"\(\s*([^)]*?)\s*\)")
    for section, net, block in _route_blocks(text):
        for route_match in route_re.finditer(block):
            layer = route_match.group(1).upper()
            if layer not in layers:
                raise SystemExit(
                    f"parasitic extraction cannot process routed layer {layer} on net {net}; "
                    f"model layers: {', '.join(sorted(layers))}"
                )
            nominal_width_um = finite_positive(layers[layer]["width_um"], f"{layer}.width_um")
            width_token = route_match.group(2)
            width_um = nominal_width_um
            if width_token is not None and float(width_token) > 0.0:
                width_um = float(width_token) / dbu
            body = route_match.group(3)
            points: list[tuple[float, float]] = []
            coordinate_matches = list(coordinate_re.finditer(body))
            previous: tuple[float, float] | None = None
            for coordinate_match in coordinate_matches:
                fields = coordinate_match.group(1).split()
                if len(fields) < 2:
                    continue
                x_token, y_token = fields[:2]
                if x_token == "*" and previous is None:
                    continue
                if y_token == "*" and previous is None:
                    continue
                x = previous[0] if x_token == "*" else float(x_token) / dbu
                y = previous[1] if y_token == "*" else float(y_token) / dbu
                point = (x, y)
                points.append(point)
                previous = point
            for first, second in zip(points, points[1:]):
                segment = Segment(net, layer, first[0], first[1], second[0], second[1], width_um, section)
                if segment.length_um <= 0.0:
                    continue
                segments.append(segment)
                by_net[net][layer] += segment.length_um
            for via_match in re.finditer(r"\b(M\dM\d_[A-Za-z0-9_]+)\b", body):
                via_name = via_match.group(1)
                layer_match = re.fullmatch(r"M(\d)M(\d)_.*", via_name)
                if not layer_match:
                    continue
                lower_layer = f"M{layer_match.group(1)}"
                upper_layer = f"M{layer_match.group(2)}"
                derived_via_layer = f"V{layer_match.group(1)}"
                if derived_via_layer != via_layer:
                    raise SystemExit(
                        f"parasitic extraction cannot process via {via_name} ({derived_via_layer}); "
                        f"model supports {via_layer} only"
                    )
                coordinate = None
                for coordinate_match in coordinate_matches:
                    if coordinate_match.end() <= via_match.start():
                        fields = coordinate_match.group(1).split()
                        if len(fields) >= 2 and _is_number_token(fields[0]) and _is_number_token(fields[1]):
                            coordinate = (float(fields[0]) / dbu, float(fields[1]) / dbu)
                if coordinate is None and points:
                    coordinate = points[-1]
                if coordinate is None:
                    continue
                via_key = (net, coordinate[0], coordinate[1], via_name)
                if via_key in seen_vias:
                    continue
                seen_vias.add(via_key)
                vias.append(Via(net, coordinate[0], coordinate[1], lower_layer, upper_layer, section))
                by_net[net][via_layer] += 1.0
        if section == "SPECIALNETS" and net in by_net:
            by_net[net]["__special_net__"] += 1.0
    return design, segments, {net: dict(values) for net, values in by_net.items()}, vias, _parse_def_connections(text, dbu, lef_dir)


def route_rectangle(segment: Segment) -> tuple[float, float, float, float]:
    return segment.bbox


def rectangle_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, dx) * max(0.0, dy)


def parallel_overlap(a: Segment, b: Segment) -> float:
    if a.orientation != b.orientation:
        return 0.0
    if a.orientation == "H":
        return max(0.0, min(max(a.x1_um, a.x2_um), max(b.x1_um, b.x2_um)) - max(min(a.x1_um, a.x2_um), min(b.x1_um, b.x2_um)))
    return max(0.0, min(max(a.y1_um, a.y2_um), max(b.y1_um, b.y2_um)) - max(min(a.y1_um, a.y2_um), min(b.y1_um, b.y2_um)))


def perpendicular_spacing(a: Segment, b: Segment) -> float:
    if a.orientation == "H":
        return max(0.0, abs((a.y1_um + a.y2_um) / 2.0 - (b.y1_um + b.y2_um) / 2.0) - (a.width_um + b.width_um) / 2.0)
    return max(0.0, abs((a.x1_um + a.x2_um) / 2.0 - (b.x1_um + b.x2_um) / 2.0) - (a.width_um + b.width_um) / 2.0)


def _project_to_segment(segment: Segment, point: tuple[float, float]) -> tuple[float, float] | None:
    x, y = point
    tolerance = max(1.0e-6, segment.width_um / 2.0)
    if segment.orientation == "H":
        low = min(segment.x1_um, segment.x2_um)
        high = max(segment.x1_um, segment.x2_um)
        if low - tolerance <= x <= high + tolerance and abs(y - segment.y1_um) <= tolerance:
            return max(low, min(high, x)), segment.y1_um
    else:
        low = min(segment.y1_um, segment.y2_um)
        high = max(segment.y1_um, segment.y2_um)
        if low - tolerance <= y <= high + tolerance and abs(x - segment.x1_um) <= tolerance:
            return segment.x1_um, max(low, min(high, y))
    return None
def _same_layer_intersections(first: Segment, second: Segment) -> list[tuple[float, float]]:
    if first.layer != second.layer or first.net != second.net:
        return []
    if first.orientation == second.orientation:
        if first.orientation == "H":
            if abs(first.y1_um - second.y1_um) > 1.0e-9:
                return []
            low = max(min(first.x1_um, first.x2_um), min(second.x1_um, second.x2_um))
            high = min(max(first.x1_um, first.x2_um), max(second.x1_um, second.x2_um))
            if low > high:
                return []
            return [(low, first.y1_um), (high, first.y1_um)]
        if abs(first.x1_um - second.x1_um) > 1.0e-9:
            return []
        low = max(min(first.y1_um, first.y2_um), min(second.y1_um, second.y2_um))
        high = min(max(first.y1_um, first.y2_um), max(second.y1_um, second.y2_um))
        if low > high:
            return []
        return [(first.x1_um, low), (first.x1_um, high)]
    horizontal, vertical = (
        (first, second) if first.orientation == "H" else (second, first)
    )
    point = (vertical.x1_um, horizontal.y1_um)
    if (
        min(horizontal.x1_um, horizontal.x2_um) - 1.0e-9 <= point[0] <= max(horizontal.x1_um, horizontal.x2_um) + 1.0e-9
        and min(vertical.y1_um, vertical.y2_um) - 1.0e-9 <= point[1] <= max(vertical.y1_um, vertical.y2_um) + 1.0e-9
    ):
        return [point]
    return []



def _node_for_coordinate(
    network: Network,
    node_coordinates: dict[str, tuple[str, float, float]],
    coordinate_nodes: dict[tuple[str, str, float, float], str],
    counters: dict[str, int],
    net: str,
    layer: str,
    point: tuple[float, float],
) -> str:
    key = (net, layer, round(point[0], 9), round(point[1], 9))
    node = coordinate_nodes.get(key)
    if node is None:
        index = counters["__global__"]
        counters["__global__"] += 1
        node = f"{net}:{index}"
        node_coordinates[node] = (layer, point[0], point[1])
        network.register_node(net, node)
    return node


def _nearest_route_node(
    node_coordinates: dict[str, tuple[str, float, float]],
    candidates: Iterable[str],
    point: tuple[float, float],
) -> str | None:
    candidate_list = [candidate for candidate in candidates if candidate in node_coordinates]
    if not candidate_list:
        return None
    return min(
        candidate_list,
        key=lambda node: abs(node_coordinates[node][1] - point[0]) + abs(node_coordinates[node][2] - point[1]),
    )


def _coupling_node(
    topology: RouteTopology,
    segment_index: int,
    segment: Segment,
    target: tuple[float, float],
) -> str | None:
    nodes = topology.segment_midpoints.get(segment_index, [])
    if not nodes:
        return None
    return _nearest_route_node(topology.node_coordinates, nodes, target)


def build_route_topology(
    network: Network,
    segments: list[Segment],
    vias: list[Via],
    connections: dict[str, list[DefConnection]],
    rc: dict[str, Any],
) -> RouteTopology:
    node_coordinates: dict[str, tuple[str, float, float]] = {}
    coordinate_nodes: dict[tuple[str, str, float, float], str] = {}
    counters: dict[str, int] = defaultdict(int)
    edge_records: list[WireEdgeRecord] = []
    segment_midpoints: dict[int, list[str]] = defaultdict(list)
    vias_by_net = defaultdict(list)
    for via in vias:
        vias_by_net[via.net].append(via)
    connections_by_net = defaultdict(list)
    for net, entries in connections.items():
        connections_by_net[net].extend(entries)
    segments_by_net_layer: dict[tuple[str, str], list[tuple[int, Segment]]] = defaultdict(list)
    for segment_index, segment in enumerate(segments):
        segments_by_net_layer[(segment.net, segment.layer)].append((segment_index, segment))

    for index, segment in enumerate(segments):
        split_points = [(segment.x1_um, segment.y1_um), (segment.x2_um, segment.y2_um)]
        for other_index, other in segments_by_net_layer[(segment.net, segment.layer)]:
            if other_index != index:
                split_points.extend(_same_layer_intersections(segment, other))
        for via in vias_by_net.get(segment.net, []):
            if segment.layer not in {via.lower_layer, via.upper_layer}:
                continue
            projected = _project_to_segment(segment, (via.x_um, via.y_um))
            if projected is not None:
                split_points.append(projected)
        for connection in connections_by_net.get(segment.net, []):
            if connection.location_um is None:
                continue
            projected = _project_to_segment(segment, connection.location_um)
            if projected is not None:
                split_points.append(projected)
        if segment.orientation == "H":
            split_points.sort(key=lambda point: (point[0], point[1]))
        else:
            split_points.sort(key=lambda point: (point[1], point[0]))
        unique_points: list[tuple[float, float]] = []
        for point in split_points:
            if not unique_points or abs(point[0] - unique_points[-1][0]) > 1.0e-9 or abs(point[1] - unique_points[-1][1]) > 1.0e-9:
                unique_points.append(point)
        for first, second in zip(unique_points, unique_points[1:]):
            interval = WireEdge(
                segment.net,
                segment.layer,
                first[0],
                first[1],
                second[0],
                second[1],
                segment.width_um,
                segment.source,
            )
            if interval.length_um <= 0.0:
                continue
            node1 = _node_for_coordinate(
                network,
                node_coordinates,
                coordinate_nodes,
                counters,
                segment.net,
                segment.layer,
                first,
            )
            node2 = _node_for_coordinate(
                network,
                node_coordinates,
                coordinate_nodes,
                counters,
                segment.net,
                segment.layer,
                second,
            )
            midpoint = f"{segment.net}:{counters['__global__']}"
            counters["__global__"] += 1
            node_coordinates[midpoint] = (
                segment.layer,
                (first[0] + second[0]) / 2.0,
                (first[1] + second[1]) / 2.0,
            )
            network.register_node(segment.net, midpoint)
            edge_records.append(WireEdgeRecord(interval, node1, midpoint, node2))
            segment_midpoints[index].append(midpoint)
            layers = {entry["layer"]: entry for entry in rc.get("layers", []) + rc.get("reserved_layers", [])}
            entry = layers[segment.layer]
            sheet_resistance = finite_positive(
                entry.get("sheet_resistance_ohm_per_square"),
                f"{segment.layer}.sheet_resistance_ohm_per_square",
            )
            half_resistance = sheet_resistance * (interval.length_um / segment.width_um) / 2.0
            details = {
                "layer": segment.layer,
                "length_um": interval.length_um / 2.0,
                "width_um": segment.width_um,
                "route_source": segment.source,
            }
            network.add_resistor(
                segment.net,
                node1,
                midpoint,
                half_resistance,
                "wire",
                "sheet resistance divided by explicit DEF route width",
                **details,
            )
            network.add_resistor(
                segment.net,
                midpoint,
                node2,
                half_resistance,
                "wire",
                "sheet resistance divided by explicit DEF route width",
                **details,
            )

    anchor_nodes: dict[str, str] = {}
    all_nets = set(connections) | {segment.net for segment in segments} | {via.net for via in vias}
    for net in all_nets:
        coordinate_candidates = [
            node for node in network.net_nodes.get(net, set()) if node in node_coordinates
        ]
        anchor_nodes[net] = (
            sorted(coordinate_candidates)[0] if coordinate_candidates else network.anchor_for_net(net)
        )
        network.anchor_nodes[net] = anchor_nodes[net]

    via_r = finite_positive(rc.get("via", {}).get("nominal_resistance_ohm"), "via.nominal_resistance_ohm")
    via_edges: list[tuple[Via, str, str]] = []
    for via in vias:
        lower_candidates = [
            node
            for node, (layer, _x, _y) in node_coordinates.items()
            if network.node_net.get(node) == via.net and layer == via.lower_layer
        ]
        upper_candidates = [
            node
            for node, (layer, _x, _y) in node_coordinates.items()
            if network.node_net.get(node) == via.net and layer == via.upper_layer
        ]
        lower = _nearest_route_node(node_coordinates, lower_candidates, (via.x_um, via.y_um))
        upper = _nearest_route_node(node_coordinates, upper_candidates, (via.x_um, via.y_um))
        if lower is None:
            lower = _node_for_coordinate(
                network,
                node_coordinates,
                coordinate_nodes,
                counters,
                via.net,
                via.lower_layer,
                (via.x_um, via.y_um),
            )
        if upper is None:
            upper = _node_for_coordinate(
                network,
                node_coordinates,
                coordinate_nodes,
                counters,
                via.net,
                via.upper_layer,
                (via.x_um, via.y_um),
            )
        network.add_resistor(
            via.net,
            lower,
            upper,
            via_r,
            "via",
            str(rc.get("via", {}).get("basis", "nominal via resistance")),
            lower_layer=via.lower_layer,
            upper_layer=via.upper_layer,
            x_um=via.x_um,
            y_um=via.y_um,
            route_source=via.source,
        )
        via_edges.append((via, lower, upper))

    terminal_attachments: dict[str, tuple[str, str]] = {}
    for net, entries in connections.items():
        anchor = anchor_nodes.get(net, network.anchor_for_net(net))
        for connection in entries:
            terminal = connection.node_name
            network.register_node(net, terminal)
            target = anchor
            if connection.location_um is not None:
                target = _nearest_route_node(
                    node_coordinates,
                    network.net_nodes.get(net, set()),
                    connection.location_um,
                ) or anchor
            if target in node_coordinates and terminal != target:
                network.add_resistor(
                    net,
                    terminal,
                    target,
                    0.0,
                    "terminal_attachment",
                    "zero-ohm attachment to nearest routed graph node",
                    terminal=terminal,
                    x_um=connection.location_um[0] if connection.location_um else None,
                    y_um=connection.location_um[1] if connection.location_um else None,
                )
            terminal_attachments[terminal] = (net, target)

    network.connections = dict(connections)
    return RouteTopology(
        network.node_net,
        node_coordinates,
        network.net_nodes,
        edge_records,
        dict(segment_midpoints),
        via_edges,
        dict(connections),
        terminal_attachments,
        anchor_nodes,
    )


def _wire_capacitance_pf(entry: dict[str, Any], length_um: float, width_um: float, layer: str) -> float:
    area = finite_positive(entry.get("capacitance_area_pf_per_um2"), f"{layer}.capacitance_area_pf_per_um2")
    edge = finite_positive(entry.get("edge_capacitance_pf_per_um"), f"{layer}.edge_capacitance_pf_per_um")
    return length_um * (area * width_um + 2.0 * edge)


def add_route_network(
    network: Network,
    segments: list[Segment],
    net_lengths: dict[str, dict[str, float]],
    vias: list[Via],
    connections: dict[str, list[DefConnection]],
    rc: dict[str, Any],
    model: dict[str, Any],
) -> RouteTopology:
    layers = {entry["layer"]: entry for entry in rc.get("layers", []) + rc.get("reserved_layers", [])}
    topology = build_route_topology(network, segments, vias, connections, rc)
    for net in set(net_lengths) | set(connections):
        topology.anchor_nodes.setdefault(net, network.anchor_for_net(net))
    for record in topology.edge_records:
        entry = layers[record.edge.layer]
        network.add_ground(
            record.midpoint,
            _wire_capacitance_pf(entry, record.edge.length_um, record.edge.width_um, record.edge.layer),
            "wire_to_substrate",
            "derived LEF area plus edge capacitance using actual DEF route width",
            layer=record.edge.layer,
            length_um=record.edge.length_um,
            width_um=record.edge.width_um,
            route_source=record.edge.source,
        )
    lateral = model.get("lateral_coupling", {})
    by_layer_orientation: dict[tuple[str, str], list[tuple[int, Segment]]] = defaultdict(list)
    for index, segment in enumerate(segments):
        by_layer_orientation[(segment.layer, segment.orientation)].append((index, segment))
    for (layer, orientation), group in by_layer_orientation.items():
        params = lateral.get(layer)
        if not isinstance(params, dict):
            continue
        edge_pf_per_um = finite_positive(
            params.get("coupling_edge_capacitance_pf_per_um"),
            f"lateral_coupling.{layer}.coupling_edge_capacitance_pf_per_um",
        )
        decay_um = finite_positive(params.get("decay_um"), f"lateral_coupling.{layer}.decay_um")
        max_distance_um = finite_positive(params.get("max_distance_um"), f"lateral_coupling.{layer}.max_distance_um")
        if orientation == "H":
            group.sort(key=lambda item: (item[1].y1_um + item[1].y2_um) / 2.0)
        else:
            group.sort(key=lambda item: (item[1].x1_um + item[1].x2_um) / 2.0)
        for position, (first_index, first) in enumerate(group):
            first_perpendicular = (first.y1_um + first.y2_um) / 2.0 if orientation == "H" else (first.x1_um + first.x2_um) / 2.0
            for second_index, second in group[position + 1 :]:
                second_perpendicular = (second.y1_um + second.y2_um) / 2.0 if orientation == "H" else (second.x1_um + second.x2_um) / 2.0
                center_gap = abs(second_perpendicular - first_perpendicular)
                if center_gap - (first.width_um + second.width_um) / 2.0 > max_distance_um:
                    break
                if first.net == second.net:
                    continue
                overlap_um = parallel_overlap(first, second)
                if overlap_um <= 0.0:
                    continue
                spacing_um = perpendicular_spacing(first, second)
                if spacing_um > max_distance_um:
                    continue
                cap_pf = overlap_um * edge_pf_per_um * math.exp(-spacing_um / decay_um)
                target = (
                    (max(min(first.x1_um, first.x2_um), min(second.x1_um, second.x2_um)) + min(max(first.x1_um, first.x2_um), max(second.x1_um, second.x2_um))) / 2.0,
                    (first_perpendicular + second_perpendicular) / 2.0,
                ) if orientation == "H" else (
                    (first_perpendicular + second_perpendicular) / 2.0,
                    (max(min(first.y1_um, first.y2_um), min(second.y1_um, second.y2_um)) + min(max(first.y1_um, first.y2_um), max(second.y1_um, second.y2_um))) / 2.0,
                )
                first_node = _coupling_node(topology, first_index, first, target)
                second_node = _coupling_node(topology, second_index, second, target)
                if first_node is None or second_node is None:
                    continue
                network.add_coupling(
                    first_node,
                    second_node,
                    cap_pf,
                    "lateral_fringe",
                    "engineering proxy: minimum LEF edge capacitance with exponential spacing attenuation",
                    net1=first.net,
                    net2=second.net,
                    layer=layer,
                    parallel_length_um=overlap_um,
                    spacing_um=spacing_um,
                    width1_um=first.width_um,
                    width2_um=second.width_um,
                )
    return topology

def _gds_data_size(data_type: int) -> int:
    return {0: 0, 1: 2, 2: 2, 3: 4, 4: 4, 5: 8, 6: 1}[data_type]


def _gds_real(raw: bytes) -> float:
    if len(raw) != 8:
        raise ValueError("GDS real must be 8 bytes")
    if raw == b"\0" * 8:
        return 0.0
    sign = -1.0 if raw[0] & 0x80 else 1.0
    exponent = (raw[0] & 0x7F) - 64
    mantissa = int.from_bytes(raw[1:], "big") / float(1 << 56)
    return sign * mantissa * (16.0 ** exponent)


def _gds_ints(raw: bytes, size: int) -> tuple[int, ...]:
    if size == 2:
        return tuple(struct.unpack(f">{len(raw) // 2}h", raw))
    if size == 4:
        return tuple(struct.unpack(f">{len(raw) // 4}i", raw))
    raise ValueError(f"unsupported GDS integer size: {size}")


def parse_gds(path: Path, needed_layers: set[tuple[int, int]]) -> tuple[dict[str, list[GdsElement]], float]:
    structures: dict[str, list[GdsElement]] = {}
    current_name: str | None = None
    current: list[GdsElement] = []
    current_element: dict[str, Any] | None = None
    meters_per_dbu = 1.0e-9
    data = path.read_bytes()
    offset = 0
    record_names = {
        0x00: "HEADER", 0x01: "BGNLIB", 0x02: "LIBNAME", 0x03: "UNITS", 0x04: "ENDLIB",
        0x05: "BGNSTR", 0x06: "STRNAME", 0x07: "ENDSTR", 0x08: "BOUNDARY", 0x09: "PATH",
        0x0A: "SREF", 0x0B: "AREF", 0x0C: "TEXT", 0x0D: "LAYER", 0x0E: "DATATYPE",
        0x0F: "WIDTH", 0x10: "XY", 0x11: "ENDEL", 0x12: "SNAME", 0x16: "TEXTTYPE",
        0x17: "PRESENTATION", 0x19: "STRING", 0x1A: "STRANS", 0x1B: "MAG", 0x1C: "ANGLE",
    }
    while offset < len(data):
        if offset + 4 > len(data):
            raise SystemExit(f"truncated GDS record in {path}")
        record_length, record_type, data_type = struct.unpack_from(">HBB", data, offset)
        if record_length < 4 or offset + record_length > len(data):
            raise SystemExit(f"invalid GDS record length in {path} at byte {offset}")
        raw = data[offset + 4 : offset + record_length]
        name = record_names.get(record_type)
        if name == "UNITS" and len(raw) >= 16:
            meters_per_dbu = _gds_real(raw[8:16])
        elif name == "BGNSTR":
            current_name = None
            current = []
        elif name == "STRNAME":
            current_name = raw.rstrip(b"\0").decode("ascii", errors="replace")
            structures[current_name] = current
        elif name == "ENDSTR":
            current_name = None
            current = []
        elif current_name is not None:
            if name in {"BOUNDARY", "PATH", "TEXT", "SREF", "AREF"}:
                current_element = {
                    "kind": name,
                    "layer": None,
                    "datatype": None,
                    "width": 0.0,
                    "text": None,
                    "child": None,
                    "origin": (0.0, 0.0),
                    "angle": 0.0,
                    "magnification": 1.0,
                    "reflect": False,
                }
            elif current_element is not None and name == "LAYER":
                values = _gds_ints(raw, 2)
                current_element["layer"] = values[0]
            elif current_element is not None and name == "DATATYPE":
                values = _gds_ints(raw, 2)
                current_element["datatype"] = values[0]
            elif current_element is not None and name == "WIDTH":
                current_element["width"] = float(_gds_ints(raw, 4)[0])
            elif current_element is not None and name == "XY":
                values = _gds_ints(raw, 4)
                current_element["points"] = tuple(zip(values[::2], values[1::2]))
                if current_element["kind"] in {"SREF", "AREF"} and current_element["points"]:
                    current_element["origin"] = current_element["points"][0]
            elif current_element is not None and name == "SNAME":
                current_element["child"] = raw.rstrip(b"\0").decode("ascii", errors="replace")
            elif current_element is not None and name == "STRING":
                current_element["text"] = raw.rstrip(b"\0").decode("ascii", errors="replace")
            elif current_element is not None and name == "ANGLE" and len(raw) == 8:
                current_element["angle"] = _gds_real(raw)
            elif current_element is not None and name == "MAG" and len(raw) == 8:
                current_element["magnification"] = _gds_real(raw)
            elif current_element is not None and name == "STRANS":
                values = _gds_ints(raw, 2)
                current_element["reflect"] = bool(values[0] & 0x8000) if values else False
            elif name == "ENDEL" and current_element is not None:
                layer = current_element.get("layer")
                layer_datatype = (layer, current_element.get("datatype"))
                if current_element["kind"] in {"SREF", "AREF"} or layer_datatype in needed_layers or current_element["kind"] == "TEXT":
                    current.append(GdsElement(**current_element))
        offset += record_length
    if not structures:
        raise SystemExit(f"GDS contains no structures: {path}")
    return structures, meters_per_dbu


def _compose_transform(parent: tuple[float, float, float, float, float, float], child: tuple[float, float, float, float, float, float]) -> tuple[float, float, float, float, float, float]:
    pa, pb, pc, pd, pe, pf = parent
    ca, cb, cc, cd, ce, cf = child
    return (
        pa * ca + pb * cc,
        pa * cb + pb * cd,
        pc * ca + pd * cc,
        pc * cb + pd * cd,
        pa * ce + pb * cf + pe,
        pc * ce + pd * cf + pf,
    )


def _apply_transform(transform: tuple[float, float, float, float, float, float], point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, e, f = transform
    return a * point[0] + b * point[1] + e, c * point[0] + d * point[1] + f


def _gds_element_transform(element: GdsElement) -> tuple[float, float, float, float, float, float]:
    scale = element.magnification
    angle = math.radians(element.angle)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    reflect = -1.0 if element.reflect else 1.0
    # GDS reflection is across the local x-axis before magnification/rotation.
    return (
        scale * cos_a,
        -scale * sin_a * reflect,
        scale * sin_a,
        scale * cos_a * reflect,
        element.origin[0],
        element.origin[1],
    )


def flatten_gds(
    structures: dict[str, list[GdsElement]],
    meters_per_dbu: float,
    top: str,
    needed_layers: set[tuple[int, int]],
) -> tuple[list[GdsShape], list[GdsLabel]]:
    if top not in structures:
        available = ", ".join(sorted(structures)[:12])
        raise SystemExit(f"GDS top structure {top!r} not found; available examples: {available}")
    scale_um = meters_per_dbu * 1.0e6
    needed_layer_numbers = {layer for layer, _ in needed_layers}
    shapes: list[GdsShape] = []
    labels: list[GdsLabel] = []
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def visit(name: str, transform: tuple[float, float, float, float, float, float], hierarchy: str, stack: tuple[str, ...]) -> None:
        if name in stack:
            raise SystemExit(f"cyclic GDS reference at {'/'.join(stack + (name,))}")
        for element in structures.get(name, []):
            if element.kind in {"BOUNDARY", "PATH"} and (element.layer, element.datatype) in needed_layers:
                points = [_apply_transform(transform, point) for point in element.points]
                if element.kind == "PATH" and element.width:
                    half = abs(element.width * transform[0] if transform[0] else element.width) / 2.0
                    points = [(x - half, y - half) for x, y in points] + [(x + half, y + half) for x, y in points]
                if points:
                    xs = [point[0] for point in points]
                    ys = [point[1] for point in points]
                    shapes.append(
                        GdsShape(
                            int(element.layer),
                            int(element.datatype or 0),
                            (min(xs) * scale_um, min(ys) * scale_um, max(xs) * scale_um, max(ys) * scale_um),
                            hierarchy,
                        )
                    )
            elif element.kind == "TEXT" and element.layer in needed_layer_numbers and element.points and element.text:
                point = _apply_transform(transform, element.points[0])
                labels.append(GdsLabel(int(element.layer), (point[0] * scale_um, point[1] * scale_um), element.text, hierarchy))
            elif element.kind == "SREF" and element.child:
                visit(element.child, _compose_transform(transform, _gds_element_transform(element)), f"{hierarchy}/{element.child}", stack + (name,))
    visit(top, identity, top, ())
    return shapes, labels


def _labels_for_box(labels: list[GdsLabel], layer: int, box: tuple[float, float, float, float]) -> list[str]:
    margin = 0.1
    return [
        label.text.strip()
        for label in labels
        if label.layer == layer
        and box[0] - margin <= label.point_um[0] <= box[2] + margin
        and box[1] - margin <= label.point_um[1] <= box[3] + margin
        and label.text.strip()
    ]


def _route_node_for_box(
    network: Network,
    topology: RouteTopology,
    net: str,
    layer: str,
    box: tuple[float, float, float, float],
) -> str:
    center = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    candidates = [
        node
        for node, (node_layer, _x, _y) in topology.node_coordinates.items()
        if node_layer == layer and topology.node_net.get(node) == net
    ]
    return _nearest_route_node(topology.node_coordinates, candidates, center) or network.anchor_for_net(net)


def add_vertical_network(
    network: Network,
    topology: RouteTopology,
    segments: list[Segment],
    gds_path: Path | None,
    gds_top: str,
    substrate_net: str,
    model: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    vertical = model.get("vertical_coupling", {})
    m2_m1 = vertical.get("M2_M1", {})
    m3_m2 = vertical.get("M3_M2", {})
    m3_m1 = vertical.get("M3_M1", {})
    m3_substrate = vertical.get("M3_SUBSTRATE", {})
    for name, params in (
        ("M2_M1", m2_m1),
        ("M3_M2", m3_m2),
        ("M3_M1", m3_m1),
        ("M3_SUBSTRATE", m3_substrate),
    ):
        if not isinstance(params, dict):
            raise SystemExit(f"vertical_coupling.{name} must be an object")

    indexed_segments = list(enumerate(segments))
    m3_segments = [(index, segment) for index, segment in indexed_segments if segment.layer == "M3"]
    underlying_geometry: list[tuple[tuple[float, float, float, float], str, str, str]] = [
        (segment.bbox, segment.layer, segment.net, f"DEF {segment.source}")
        for _index, segment in indexed_segments
        if segment.layer in {"M1", "M2"}
    ]
    route_nets = {segment.net for segment in segments} | set(network.connections)
    gds_summary: dict[str, Any] = {
        "available": bool(gds_path),
        "m3_shapes": 0,
        "underlying_gds_shapes": 0,
        "overlap_area_um2": {"M1": 0.0, "M2": 0.0},
        "m1_m2_overlap_area_um2": 0.0,
        "geometry_method": "axis_aligned_bounding_box_intersection",
    }

    m2_m1_density = finite_positive(
        m2_m1.get("capacitance_pf_per_um2"),
        "vertical_coupling.M2_M1.capacitance_pf_per_um2",
    )
    for first_index, first in indexed_segments:
        if first.layer != "M1":
            continue
        for second_index, second in indexed_segments:
            if second.layer != "M2" or first.net == second.net:
                continue
            area = rectangle_overlap(first.bbox, second.bbox)
            if area <= 0.0:
                continue
            overlap_box = (
                max(first.bbox[0], second.bbox[0]),
                max(first.bbox[1], second.bbox[1]),
                min(first.bbox[2], second.bbox[2]),
                min(first.bbox[3], second.bbox[3]),
            )
            target = ((overlap_box[0] + overlap_box[2]) / 2.0, (overlap_box[1] + overlap_box[3]) / 2.0)
            first_node = _coupling_node(topology, first_index, first, target) or network.anchor_for_net(first.net)
            second_node = _coupling_node(topology, second_index, second, target) or network.anchor_for_net(second.net)
            network.add_coupling(
                first_node,
                second_node,
                area * m2_m1_density,
                "m1_m2_overlap",
                str(m2_m1.get("basis", "engineering adjacent-metal overlap estimate")),
                layer1="M1",
                layer2="M2",
                overlap_area_um2=area,
                width1_um=first.width_um,
                width2_um=second.width_um,
                source=f"DEF {first.source}; DEF {second.source}",
            )
            gds_summary["m1_m2_overlap_area_um2"] += area

    m3_boxes: list[tuple[tuple[float, float, float, float], str, str]] = []
    if gds_path is not None:
        needed = {GDS_LAYERS[layer] for layer in ("M1", "M2", "M3")}
        needed_layer_numbers = {layer for layer, _ in needed}
        structures, meters_per_dbu = parse_gds(gds_path, needed)
        shapes, labels = flatten_gds(structures, meters_per_dbu, gds_top, needed)
        m3_layer, m3_datatype = GDS_LAYERS["M3"]
        m3_shape_boxes: list[tuple[float, float, float, float]] = []
        for shape in (shape for shape in shapes if shape.layer == m3_layer and shape.datatype == m3_datatype):
            m3_shape_boxes.append(shape.bbox_um)
            nets = _labels_for_box(labels, m3_layer, shape.bbox_um)
            shape_net = next(
                (net for net in nets if net in route_nets or net.upper() in SUBSTRATE_ALIASES),
                next(
                    (segment.net for _index, segment in m3_segments if rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0),
                    substrate_net,
                ),
            )
            m3_boxes.append((shape.bbox_um, shape_net, f"GDS {shape.hierarchy}"))
        for shape in (shape for shape in shapes if shape.layer in needed_layer_numbers and shape.layer != m3_layer):
            layer = next(name for name in ("M1", "M2") if GDS_LAYERS[name][0] == shape.layer)
            nets = _labels_for_box(labels, shape.layer, shape.bbox_um)
            shape_net = next(
                (net for net in nets if net in route_nets or net.upper() in SUBSTRATE_ALIASES),
                next(
                    (
                        segment.net
                        for _index, segment in indexed_segments
                        if segment.layer == layer and rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0
                    ),
                    None,
                ),
            )
            if shape_net is None:
                continue
            if any(segment.layer == layer and rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0 for segment in segments):
                continue
            underlying_geometry.append((shape.bbox_um, layer, shape_net, f"GDS {shape.hierarchy}"))
        gds_summary["m3_shapes"] = len(m3_shape_boxes)
        gds_summary["underlying_gds_shapes"] = len(underlying_geometry) - len(
            [segment for segment in segments if segment.layer in {"M1", "M2"}]
        )
        if gds_summary["m3_shapes"] == 0:
            warnings.append("GDS was supplied but contains no M3 drawing geometry in the selected hierarchy")
        else:
            warnings.append("M3 vertical overlap uses axis-aligned GDS bounding boxes; review before signoff")
        for _index, segment in m3_segments:
            if not any(rectangle_overlap(segment.bbox, box) > 0.0 for box in m3_shape_boxes):
                m3_boxes.append((segment.bbox, segment.net, "DEF M3 route"))
    else:
        m3_boxes = [(segment.bbox, segment.net, "DEF M3 route") for _index, segment in m3_segments]

    for m3_box, m3_net, m3_source in m3_boxes:
        m3_node = _route_node_for_box(network, topology, m3_net, "M3", m3_box)
        if m3_net != substrate_net and m3_net.upper() not in SUBSTRATE_ALIASES:
            area = (m3_box[2] - m3_box[0]) * (m3_box[3] - m3_box[1])
            cap_density = finite_positive(
                m3_substrate.get("capacitance_pf_per_um2"),
                "vertical_coupling.M3_SUBSTRATE.capacitance_pf_per_um2",
            )
            network.add_ground(
                m3_node,
                area * cap_density,
                "m3_to_substrate",
                str(m3_substrate.get("basis", "engineering vertical estimate")),
                area_um2=area,
                source=m3_source,
            )
        for underlying_box, layer, underlying_net, underlying_source in underlying_geometry:
            area = rectangle_overlap(m3_box, underlying_box)
            if area <= 0.0:
                continue
            params = m3_m2 if layer == "M2" else m3_m1
            key = "M3_M2" if layer == "M2" else "M3_M1"
            cap_density = finite_positive(
                params.get("capacitance_pf_per_um2"),
                f"vertical_coupling.{key}.capacitance_pf_per_um2",
            )
            cap_pf = area * cap_density
            gds_summary["overlap_area_um2"][layer] += area
            basis = str(params.get("basis", "engineering vertical estimate"))
            underlying_node = _route_node_for_box(network, topology, underlying_net, layer, underlying_box)
            if m3_net == substrate_net or m3_net.upper() in SUBSTRATE_ALIASES:
                network.add_ground(
                    underlying_node,
                    cap_pf,
                    "m3_vertical_to_substrate",
                    basis,
                    layer=layer,
                    overlap_area_um2=area,
                    source=m3_source,
                )
            elif m3_net != underlying_net:
                network.add_coupling(
                    underlying_node,
                    m3_node,
                    cap_pf,
                    "m3_vertical_coupling",
                    basis,
                    layer=layer,
                    overlap_area_um2=area,
                    source=f"{m3_source}; {underlying_source}",
                )
    return gds_summary


def _logical_spice_lines(text: str) -> Iterable[tuple[int, str]]:
    pending = ""
    start_line = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not pending:
            start_line = line_number
        if line.startswith("+"):
            pending += " " + line[1:].strip()
        else:
            if pending:
                yield start_line, pending
            pending = line
            start_line = line_number
    if pending:
        yield start_line, pending


def _parameter_value(tokens: list[str], name: str) -> float | None:
    name_upper = name.upper()
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key.upper() == name_upper:
            try:
                return parse_dimension_um(value)
            except ValueError:
                return None
    return None


def parse_extracted_devices(path: Path) -> list[Device]:
    devices: list[Device] = []
    subckt_stack: list[str] = []
    for line_number, line in _logical_spice_lines(path.read_text(encoding="utf-8", errors="replace")):
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        subckt_match = re.match(r"\.SUBCKT\s+(\S+)(?:\s+(.*))?$", stripped, re.IGNORECASE)
        if subckt_match:
            subckt_stack.append(subckt_match.group(1))
            continue
        if re.match(r"\.ENDS\b", stripped, re.IGNORECASE):
            if subckt_stack:
                subckt_stack.pop()
            continue
        if not subckt_stack or stripped.startswith("."):
            continue
        tokens = stripped.split()
        if len(tokens) < 3:
            continue
        instance = tokens[0]
        model_index = next((index for index, token in enumerate(tokens[1:], 1) if token.upper() in {"F_RS", "F_RR", "PMOS", "NMOS", "MPE", "MNE"}), None)
        if model_index is None:
            continue
        model = tokens[model_index].upper()
        node_count = 3 if model == "F_RR" else 2 if model == "F_RS" else 4
        if model_index < node_count:
            continue
        nodes = tuple(tokens[1 : 1 + node_count])
        width_um = _parameter_value(tokens[model_index + 1 :], "W")
        length_um = _parameter_value(tokens[model_index + 1 :], "L")
        if model in {"F_RS", "F_RR", "PMOS", "NMOS", "MPE", "MNE"}:
            devices.append(Device(model, instance, subckt_stack[-1], nodes, width_um, length_um, line_number))
    return devices


def parse_rr_capacitance(model_path: Path) -> dict[float, tuple[float, float]]:
    """Return width_um -> (slope_fF_per_um, intercept_fF) for F_RR c_d0."""
    text = model_path.read_text(encoding="utf-8", errors="replace")
    section = re.search(r"(?is)\.subckt\s+F_RR\b(.*?)(?:\.ends\s+F_RR\b)", text)
    if not section:
        raise SystemExit(f"F_RR subcircuit missing from {model_path}")
    body = section.group(1)
    result: dict[float, tuple[float, float]] = {}
    branch_matches = list(re.finditer(r"(?i)\.if\s*\(\s*w\s*==\s*([0-9.]+)u\s*\)(.*?)(?=(?:\.elseif|\.endif))", body, re.DOTALL))
    branch_matches += list(re.finditer(r"(?i)\.elseif\s*\(\s*w\s*==\s*([0-9.]+)u\s*\)(.*?)(?=(?:\.elseif|\.endif))", body, re.DOTALL))
    for branch in branch_matches:
        width = float(branch.group(1))
        cap_match = re.search(
            r"c_d0\s+PLUS\s+SUB\s+c\s*=\s*'\s*\(\s*"
            r"([0-9.eE+-]+)\s*\*\s*\(\s*10\s*\*\*\s*-?4\s*\)\s*"
            r"\*\s*l\s*\*\s*\(\s*10\s*\*\*\s*6\s*\)\s*\+\s*"
            r"([0-9.eE+-]+)\s*\*\s*\(\s*10\s*\*\*\s*-?3\s*\)",
            branch.group(2),
            re.IGNORECASE,
        )
        if not cap_match:
            # The checked-in model has changed exponent spelling in prior
            # revisions; keep a bounded fallback anchored to c_d0.
            cap_match = re.search(
                r"c_d0\s+PLUS\s+SUB\s+c\s*=\s*'\s*\(\s*"
                r"([0-9.eE+-]+)\s*\*.*?l.*?\+\s*"
                r"([0-9.eE+-]+)\s*\*.*?\)\s*\*.*?10",
                branch.group(2),
                re.IGNORECASE | re.DOTALL,
            )
        if not cap_match:
            raise SystemExit(f"unable to parse F_RR c_d0 formula for W={width:g}u in {model_path}")
        # l is in metres in the compact expression.  Convert the parsed
        # coefficient to fF/um and the intercept to fF.
        result[width] = (float(cap_match.group(1)) * 0.1, float(cap_match.group(2)))
    if not result:
        raise SystemExit(f"no F_RR c_d0 branches found in {model_path}")
    return result


def rr_capacitance_ff(width_um: float, length_um: float, formulas: dict[float, tuple[float, float]]) -> tuple[float, float]:
    width = min(formulas, key=lambda candidate: abs(candidate - width_um))
    if abs(width - width_um) > 0.05:
        raise SystemExit(f"F_RR width {width_um:g}um is not one of the model branches {sorted(formulas)}")
    slope, intercept = formulas[width]
    return slope * length_um + intercept, width


def infer_substrate_net(subckt_ports: dict[str, tuple[str, ...]], subckt: str, configured: str) -> str | None:
    ports = subckt_ports.get(subckt, ())
    configured_key = configured.upper().lstrip("\\").rstrip("!")
    if configured:
        for node in ports:
            node_key = node.upper().lstrip("\\").rstrip("!")
            if node == configured or node_key == configured_key:
                return node
    aliases = {alias.upper() for alias in SUBSTRATE_ALIASES}
    for node in ports:
        if node.upper().lstrip("\\").rstrip("!") in aliases:
            return node
    return configured if not ports else None


def extract_subckt_ports(path: Path) -> dict[str, tuple[str, ...]]:
    ports: dict[str, tuple[str, ...]] = {}
    for _, line in _logical_spice_lines(path.read_text(encoding="utf-8", errors="replace")):
        match = re.match(r"\.SUBCKT\s+(\S+)(?:\s+(.*))?$", line.strip(), re.IGNORECASE)
        if match:
            ports[match.group(1)] = tuple((match.group(2) or "").split())
    return ports
def classify_gr_substrate(gds_path: Path | None, top: str) -> str | None:
    """Classify GR geometry by overlap with the N-well drawing layer."""
    if gds_path is None:
        return None
    needed = {GDS_LAYERS["GR"], GDS_LAYERS["WN"]}
    structures, meters_per_dbu = parse_gds(gds_path, needed)
    shapes, _ = flatten_gds(structures, meters_per_dbu, top, needed)
    gr_layer, gr_datatype = GDS_LAYERS["GR"]
    wn_layer, wn_datatype = GDS_LAYERS["WN"]
    gr_boxes = [
        shape.bbox_um
        for shape in shapes
        if shape.layer == gr_layer and shape.datatype == gr_datatype
    ]
    wn_boxes = [
        shape.bbox_um
        for shape in shapes
        if shape.layer == wn_layer and shape.datatype == wn_datatype
    ]
    if not gr_boxes:
        return None
    nw_overlap = any(
        rectangle_overlap(gr_box, wn_box) > 0.0 for gr_box in gr_boxes for wn_box in wn_boxes
    )
    psub_overlap = any(
        not any(rectangle_overlap(gr_box, wn_box) > 0.0 for wn_box in wn_boxes)
        for gr_box in gr_boxes
    )
    if nw_overlap and psub_overlap:
        return "MIXED"
    return "NW" if nw_overlap else "PSUB"


def add_device_network(
    network: Network,
    devices: list[Device],
    model: dict[str, Any],
    rr_model_path: Path,
    top_subckt: str,
    substrate_net: str,
    well_net: str,
    gr_substrate_region: str | None,
    include_device_caps: bool,
    warnings: list[str],
    extracted_path: Path | None,
) -> None:
    rr_formulas = parse_rr_capacitance(rr_model_path) if any(device.model == "F_RR" for device in devices) else {}
    device_config = model.get("devices", {})
    rs_config = device_config.get("F_RS", {})
    mos_config = device_config.get("GC", {})
    subckt_ports = extract_subckt_ports(extracted_path) if extracted_path else {}
    nested_models_warned: set[str] = set()

    def warn_nested(model_name: str, device: Device) -> None:
        if model_name not in nested_models_warned:
            warnings.append(
                f"nested {model_name} terms are retained in JSON, not mapped into top-level SPEF "
                f"(first occurrence {device.subckt}/{device.instance})"
            )
            nested_models_warned.add(model_name)
    for device in devices:
        record: dict[str, Any] = {
            "instance": device.instance,
            "subckt": device.subckt,
            "model": device.model,
            "source_line": device.source_line,
            "nodes": list(device.nodes),
            "width_um": device.width_um,
            "length_um": device.length_um,
            "materialized_in_spef": False,
            "ownership": "explicit_parasitic_network",
        }
        eligible_top = device.subckt == top_subckt
        if device.model == "F_RR":
            if device.width_um is None or device.length_um is None:
                warnings.append(f"{device.subckt}/{device.instance}: F_RR missing W/L; capacitance omitted")
                continue
            cap_ff, branch_width = rr_capacitance_ff(device.width_um, device.length_um, rr_formulas)
            record.update(
                {
                    "kind": "RR",
                    "terminal_layer": "AR",
                    "bulk_layer": "AR/WR",
                    "substrate_terminal": device.nodes[2],
                    "capacitance_ff": cap_ff,
                    "formula_width_um": branch_width,
                    "formula": "F_RR c_d0 PLUS-SUB; c_d1 MINUS-SUB=0",
                    "ownership": "F_RR compact model; do not add a second C in an analog deck",
                }
            )
            if include_device_caps and eligible_top:
                network.add_coupling(device.nodes[0], device.nodes[2], cap_ff / 1000.0, "active_resistor_bulk", "F_RR compact-model c_d0 formula", instance=device.instance, subckt=device.subckt, length_um=device.length_um, width_um=device.width_um)
                record["materialized_in_spef"] = True
            elif include_device_caps and not eligible_top:
                warn_nested("F_RR", device)
        elif device.model == "F_RS":
            if device.width_um is None or device.length_um is None:
                warnings.append(f"{device.subckt}/{device.instance}: F_RS missing W/L; capacitance omitted")
                continue
            density = finite_positive(rs_config.get("area_capacitance_pf_per_um2"), "devices.F_RS.area_capacitance_pf_per_um2")
            total_pf = density * device.width_um * device.length_um
            split = bool(rs_config.get("split_between_terminals", True))
            region = str(gr_substrate_region or rs_config.get("default_substrate_region") or "unknown").upper()
            target_net = well_net if region == "NW" else substrate_net
            substrate = infer_substrate_net(subckt_ports, device.subckt, target_net)
            record.update(
                {
                    "kind": "GR",
                    "terminal_layer": "GR",
                    "bulk_layer": region,
                    "substrate_region": region,
                    "capacitance_pf": total_pf,
                    "capacitance_ff": total_pf * 1000.0,
                    "substrate_net": substrate,
                    "formula": "C_GR = area_capacitance * W * L; split equally over PLUS/MINUS",
                    "basis": rs_config.get("basis", "engineering estimate"),
                }
            )
            if include_device_caps and eligible_top and substrate:
                each = total_pf / 2.0 if split else total_pf
                network.add_coupling(device.nodes[0], substrate, each, "gr_to_substrate", str(rs_config.get("basis", "engineering estimate")), instance=device.instance, subckt=device.subckt, area_um2=device.width_um * device.length_um)
                if split:
                    network.add_coupling(device.nodes[1], substrate, each, "gr_to_substrate", str(rs_config.get("basis", "engineering estimate")), instance=device.instance, subckt=device.subckt, area_um2=device.width_um * device.length_um)
                else:
                    network.add_ground(device.nodes[0], each, "gr_to_substrate", str(rs_config.get("basis", "engineering estimate")), instance=device.instance, subckt=device.subckt, area_um2=device.width_um * device.length_um)
                record["materialized_in_spef"] = True
            elif include_device_caps and not eligible_top:
                warn_nested("F_RS", device)
        else:
            if device.width_um is None:
                warnings.append(f"{device.subckt}/{device.instance}: {device.model} missing W; overlap capacitance omitted")
                continue
            mos_key = "PMOS" if device.model == "PMOS" or device.model == "MPE" else "NMOS"
            mos_params = mos_config.get(mos_key, {})
            cgsl = finite_positive(mos_params.get("cgsl_fF_per_um"), f"devices.GC.{mos_key}.cgsl_fF_per_um")
            cgdl = finite_positive(mos_params.get("cgdl_fF_per_um"), f"devices.GC.{mos_key}.cgdl_fF_per_um")
            cgs_ff = cgsl * device.width_um
            cgd_ff = cgdl * device.width_um
            record.update(
                {
                    "kind": "GC",
                    "gate_layer": "GC",
                    "active_layer": "AP" if mos_key == "PMOS" else "AN",
                    "drain_terminal": device.nodes[0],
                    "gate_terminal": device.nodes[1],
                    "source_terminal": device.nodes[2],
                    "bulk_terminal": device.nodes[3],
                    "cgs_ff": cgs_ff,
                    "cgd_ff": cgd_ff,
                    "formula": "C_GS/ C_GD = cgsl/cgdl * W; compact BSIM3 overlap terms",
                    "basis": mos_params.get("basis", "BSIM3 compact-model coefficient"),
                    "ownership": "MOS compact model; do not add a second C in an analog deck",
                }
            )
            if include_device_caps and eligible_top:
                network.add_coupling(device.nodes[1], device.nodes[2], cgs_ff / 1000.0, "gc_to_active", str(mos_params.get("basis", "BSIM3 compact-model coefficient")), instance=device.instance, subckt=device.subckt, terminal="source", active_layer=record["active_layer"])
                network.add_coupling(device.nodes[1], device.nodes[0], cgd_ff / 1000.0, "gc_to_active", str(mos_params.get("basis", "BSIM3 compact-model coefficient")), instance=device.instance, subckt=device.subckt, terminal="drain", active_layer=record["active_layer"])
                record["materialized_in_spef"] = True
            elif include_device_caps and not eligible_top:
                warn_nested("GC", device)
        network.device_records.append(record)


def _net_for_node(network: Network, node: str) -> str:
    return network.node_net.get(node, node)


def _net_ground_capacitance(network: Network, net: str) -> float:
    return sum(
        cap
        for node, cap in network.ground_pf.items()
        if _net_for_node(network, node) == net
    )


def _net_coupling_capacitance(network: Network, net: str) -> float:
    return sum(
        cap
        for (node1, node2), cap in network.coupling_pf.items()
        if _net_for_node(network, node1) == net or _net_for_node(network, node2) == net
    )


def write_spef(
    path: Path,
    design: str,
    substrate_net: str,
    network: Network,
    net_lengths: dict[str, dict[str, float]],
) -> None:
    nets = set(net_lengths) | set(network.net_nodes) | set(network.connections) | {substrate_net}
    for node1, node2 in network.coupling_pf:
        nets.add(_net_for_node(network, node1))
        nets.add(_net_for_node(network, node2))
    nets.discard("")
    out = [
        '*SPEF "IEEE 1481-1998"',
        f'*DESIGN "{design}"',
        '*DATE "2026-01-01T00:00:00"',
        '*VENDOR "TR-1um flow"',
        '*PROGRAM "extract_tr1um_parasitics"',
        '*VERSION "3.0"',
        '*DESIGN_FLOW "PIN_CAP NONE" "NAME_SCOPE LOCAL"',
        '*DIVIDER /',
        '*DELIMITER :',
        '*BUS_DELIMITER [ ]',
        '*T_UNIT 1 NS',
        '*C_UNIT 1 PF',
        '*R_UNIT 1 OHM',
        '*L_UNIT 1 HENRY',
        "",
    ]
    total_nets = 0
    for net in sorted(nets):
        ground_cap = _net_ground_capacitance(network, net)
        coupling_cap = _net_coupling_capacitance(network, net)
        if (
            ground_cap <= 0.0
            and coupling_cap <= 0.0
            and not any(record["net"] == net for record in network.resistor_records)
        ):
            continue
        total_nets += 1
        out.append(f"*D_NET {net} {ground_cap + coupling_cap:.9e}")
        out.append("*CONN")
        for connection in sorted(network.connections.get(net, []), key=lambda item: item.node_name):
            if connection.instance is None:
                out.append(f"*P {connection.pin} {connection.direction}")
            elif connection.cell:
                out.append(f"*I {connection.node_name} {connection.direction} *D {connection.cell}")
            else:
                out.append(f"*I {connection.node_name} {connection.direction}")
        out.append("*CAP")
        cap_index = 1
        for node, cap_pf in sorted(network.ground_pf.items()):
            if cap_pf > 0.0 and _net_for_node(network, node) == net:
                out.append(f"{cap_index} {node} {cap_pf:.9e}")
                cap_index += 1
        for (node1, node2), cap_pf in sorted(network.coupling_pf.items()):
            if cap_pf <= 0.0:
                continue
            if _net_for_node(network, node1) == net or _net_for_node(network, node2) == net:
                out.append(f"{cap_index} {node1} {node2} {cap_pf:.9e}")
                cap_index += 1
        net_resistors = [
            record for record in network.resistor_records if record["net"] == net
        ]
        if net_resistors:
            out.append("*RES")
            for index, record in enumerate(net_resistors, 1):
                out.append(
                    f"{index} {record['node1']} {record['node2']} "
                    f"{float(record['resistance_ohm']):.9e}"
                )
        out.append("*END")
        out.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_spice(path: Path, substrate_net: str, network: Network) -> None:
    nodes = {substrate_net}
    nodes.update(network.net_nodes)
    nodes.update(network.ground_pf)
    for node1, node2 in network.coupling_pf:
        nodes.update((node1, node2))
    for record in network.resistor_records:
        nodes.update((record["node1"], record["node2"]))
    ordered_nodes = [substrate_net] + sorted(node for node in nodes if node != substrate_net)
    out = [
        "* TR-1um engineering distributed parasitic RC network.",
        "* Include this subcircuit only when its device-cap ownership is understood.",
        ".SUBCKT tr1um_parasitics " + " ".join(ordered_nodes),
    ]
    index = 1
    for node, cap_pf in sorted(network.ground_pf.items()):
        if cap_pf > 0.0:
            out.append(f"CPEX{index} {node} {substrate_net} {cap_pf:.9e}pF")
            index += 1
    for (node1, node2), cap_pf in sorted(network.coupling_pf.items()):
        out.append(f"CPEX{index} {node1} {node2} {cap_pf:.9e}pF")
        index += 1
    for record in network.resistor_records:
        out.append(
            f"RPEX{index} {record['node1']} {record['node2']} "
            f"{float(record['resistance_ohm']):.9e}"
        )
        index += 1
    out.extend([".ENDS tr1um_parasitics", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


def summarize(network: Network, segments: list[Segment], devices: list[Device], warnings: list[str]) -> dict[str, Any]:
    return {
        "wire_segment_count": len(segments),
        "device_count": len(devices),
        "ground_cap_entry_count": len(network.ground_records),
        "coupling_pair_count": len(network.coupling_pf),
        "ground_capacitance_pf": sum(network.ground_pf.values()),
        "coupling_capacitance_pf": sum(network.coupling_pf.values()),
        "device_record_count": len(network.device_records),
        "warning_count": len(warnings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--def", dest="def_path", type=Path, required=True)
    parser.add_argument("--gds", type=Path)
    parser.add_argument("--extracted", type=Path, help="KLayout extracted SPICE netlist")
    parser.add_argument("--rc", type=Path, default=DEFAULT_RC)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--rr-model", type=Path, default=DEFAULT_RR_MODEL)
    parser.add_argument("--lef-dir", type=Path, default=DEFAULT_LEF_DIR)
    parser.add_argument("--top", help="GDS/SPICE top subcircuit; defaults to DEF DESIGN")
    parser.add_argument("--substrate-net", default="VSS")
    parser.add_argument("--well-net", default="VDD", help="net used for GR geometry classified inside N-well")
    parser.add_argument("--spef", type=Path, required=True)
    parser.add_argument("--spice", type=Path, required=True)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--no-device-caps", action="store_true", help="report device terms but do not materialize them in SPEF/SPICE")
    args = parser.parse_args()

    def_text = args.def_path.read_text(encoding="utf-8", errors="replace")
    rc = read_json(args.rc)
    model = read_json(args.model)
    design, segments, net_lengths, vias, connections = parse_def_segments(def_text, rc, args.lef_dir)
    top = args.top or design
    warnings: list[str] = []
    if args.gds is None:
        warnings.append("no GDS supplied; M3 vertical terms are extracted only when M3 routes are present in DEF")
    if args.extracted is None:
        warnings.append("no extracted SPICE supplied; GR/RR/GC device terms are not discoverable from DEF alone")
    if not args.lef_dir.exists():
        warnings.append(f"LEF directory {args.lef_dir} is unavailable; SPEF pin locations use route anchors")
    if not args.rr_model.exists() and args.extracted:
        raise SystemExit(f"missing F_RR model file: {args.rr_model}")
    network = Network.create()
    topology = add_route_network(network, segments, net_lengths, vias, connections, rc, model)
    devices: list[Device] = []
    if args.extracted:
        devices = parse_extracted_devices(args.extracted)
    gr_region = classify_gr_substrate(args.gds, top) if args.gds and any(device.model == "F_RS" for device in devices) else None
    if args.extracted and any(device.model == "F_RS" for device in devices) and gr_region is None:
        warnings.append("F_RS devices were found but no GR geometry was classified; using the configured substrate net")
    if gr_region == "MIXED":
        warnings.append("GR geometry spans PSUB and NW; F_RS terms use the configured substrate net")
    gds_summary = add_vertical_network(network, topology, segments, args.gds, top, args.substrate_net, model, warnings)
    if devices:
        add_device_network(network, devices, model, args.rr_model, top, args.substrate_net, args.well_net, gr_region, not args.no_device_caps, warnings, args.extracted)
    write_spef(args.spef, design, args.substrate_net, network, net_lengths)
    write_spice(args.spice, args.substrate_net, network)
    report_nets = set(net_lengths) | set(network.net_nodes) | set(network.connections)
    report_nets.discard("")
    report = {
        "schema": 3,
        "status": "engineering_estimate_not_foundry_qualified",
        "design": design,
        "top_subckt": top,
        "substrate_net": args.substrate_net,
        "well_net": args.well_net,
        "gr_substrate_region": gr_region,
        "inputs": {
            "def": str(args.def_path),
            "gds": str(args.gds) if args.gds else None,
            "extracted_spice": str(args.extracted) if args.extracted else None,
            "rc_model": str(args.rc),
            "parasitic_model": str(args.model),
            "rr_model": str(args.rr_model),
            "lef_dir": str(args.lef_dir),
        },
        "outputs": {
            "spef": str(args.spef),
            "spice": str(args.spice),
            "ledger": str(args.json_path),
        },
        "materialization": {
            "device_caps_requested": not args.no_device_caps,
            "top_level_device_terms": sum(
                1 for entry in network.device_records if entry["subckt"] == top and entry["materialized_in_spef"]
            ),
            "nested_device_terms": sum(
                1 for entry in network.device_records if entry["subckt"] != top
            ),
        },
        "topology": {
            "node_count": len(network.node_net),
            "wire_interval_count": len(topology.edge_records),
            "via_edge_count": len(topology.via_edges),
            "resistor_edge_count": len(network.resistor_records),
            "terminal_attachment_count": sum(
                1 for record in network.resistor_records if record["kind"] == "terminal_attachment"
            ),
            "connection_count": sum(len(entries) for entries in connections.values()),
        },
        "gds": gds_summary,
        "summary": summarize(network, segments, devices, warnings),
        "ground_capacitance_pf": {
            net: _net_ground_capacitance(network, net)
            for net in sorted(report_nets)
            if _net_ground_capacitance(network, net) > 0.0
        },
        "node_ground_capacitance_pf": {
            node: value for node, value in sorted(network.ground_pf.items()) if value > 0.0
        },
        "resistance_ohm": {
            net: value for net, value in sorted(network.resistance_ohm.items()) if value > 0.0
        },
        "resistor_entries": network.resistor_records,
        "coupling_capacitance_pf": [
            {
                "net1": _net_for_node(network, node1),
                "net2": _net_for_node(network, node2),
                "node1": node1,
                "node2": node2,
                "capacitance_pf": value,
            }
            for (node1, node2), value in sorted(network.coupling_pf.items())
        ],
        "ground_entries": network.ground_records,
        "coupling_entries": network.coupling_records,
        "device_entries": network.device_records,
        "connections": {
            net: [
                {
                    "node": connection.node_name,
                    "instance": connection.instance,
                    "pin": connection.pin,
                    "cell": connection.cell,
                    "direction": connection.direction,
                    "location_um": connection.location_um,
                }
                for connection in entries
            ]
            for net, entries in sorted(connections.items())
        },
        "node_net": {node: net for node, net in sorted(network.node_net.items())},
        "warnings": warnings,
    }
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "parasitics: "
        f"segments={len(segments)} vias={len(vias)} devices={len(devices)} "
        f"nodes={len(network.node_net)} resistor_edges={len(network.resistor_records)} "
        f"ground_caps={len(network.ground_pf)} coupling_pairs={len(network.coupling_pf)}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"wrote SPEF {args.spef}")
    print(f"wrote SPICE {args.spice}")
    print(f"wrote ledger {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
