#!/usr/bin/env python3
"""Extract a transparent, engineering-only TR-1um parasitic network.

The open IP62 collateral does not contain a foundry RC/PEX deck.  This tool
therefore does not claim silicon-qualified values.  It combines the checked-in
DEF route geometry, optional GDS overlap geometry, optional KLayout extracted
SPICE devices, and an explicit model file into:

* a SPEF with wire-to-substrate and inter-net coupling capacitance;
* a small SPICE capacitor subcircuit for analog deck inclusion; and
* a JSON ledger that records every estimate and its source basis.

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
    coupling_records: list[dict[str, Any]]
    ground_records: list[dict[str, Any]]
    device_records: list[dict[str, Any]]

    @classmethod
    def create(cls) -> "Network":
        return cls(defaultdict(float), defaultdict(float), defaultdict(float), [], [], [])

    def add_ground(self, net: str, cap_pf: float, kind: str, basis: str, **details: Any) -> None:
        if not net or cap_pf <= 0.0:
            return
        self.ground_pf[net] += cap_pf
        self.ground_records.append(
            {"net": net, "capacitance_pf": cap_pf, "kind": kind, "basis": basis, **details}
        )

    def add_coupling(self, node1: str, node2: str, cap_pf: float, kind: str, basis: str, **details: Any) -> None:
        if not node1 or not node2 or node1 == node2 or cap_pf <= 0.0:
            return
        pair = tuple(sorted((node1, node2)))
        self.coupling_pf[pair] += cap_pf
        self.coupling_records.append(
            {
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


def parse_def_segments(text: str, rc: dict[str, Any]) -> tuple[str, list[Segment], dict[str, dict[str, float]]]:
    design, dbu = read_def_header(text)
    layers = {entry["layer"]: entry for entry in rc.get("layers", []) + rc.get("reserved_layers", [])}
    via_layer = rc.get("via", {}).get("layer", "V1")
    segments: list[Segment] = []
    by_net: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    route_re = re.compile(
        r"(?:^|\s)(?:ROUTED|NEW)\s+(M\d+)\b(.*?)(?=(?:\s+(?:ROUTED|NEW)\s+M\d+\b)|\s*;|$)",
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
            width_um = finite_positive(layers[layer]["width_um"], f"{layer}.width_um")
            body = route_match.group(2)
            points: list[tuple[float, float]] = []
            previous: tuple[float, float] | None = None
            for coordinate_match in coordinate_re.finditer(body):
                fields = coordinate_match.group(1).split()
                if len(fields) < 2:
                    continue
                x_token, y_token = fields[:2]
                x = previous[0] if x_token == "*" and previous is not None else float(x_token)
                y = previous[1] if y_token == "*" and previous is not None else float(y_token)
                point = (x / dbu, y / dbu)
                points.append(point)
                previous = point
            for first, second in zip(points, points[1:]):
                segment = Segment(net, layer, first[0], first[1], second[0], second[1], width_um)
                if segment.length_um <= 0.0:
                    continue
                segments.append(segment)
                by_net[net][layer] += segment.length_um
            for via_name in re.findall(r"\b(M\dM\d_[A-Za-z0-9_]+)\b", body):
                via_match = re.fullmatch(r"M(\d)M(\d)_.*", via_name)
                if not via_match:
                    continue
                derived_via_layer = f"V{via_match.group(1)}"
                if derived_via_layer != via_layer:
                    raise SystemExit(
                        f"parasitic extraction cannot process via {via_name} ({derived_via_layer}); "
                        f"model supports {via_layer} only"
                    )
                by_net[net][via_layer] += 1.0
        # Keep the section in the ledger so a reviewer can distinguish power routes.
        if section == "SPECIALNETS" and net in by_net:
            by_net[net]["__special_net__"] += 1.0
    return design, segments, {net: dict(values) for net, values in by_net.items()}


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


def add_route_network(
    network: Network,
    segments: list[Segment],
    net_lengths: dict[str, dict[str, float]],
    rc: dict[str, Any],
    model: dict[str, Any],
) -> None:
    layers = {entry["layer"]: entry for entry in rc.get("layers", []) + rc.get("reserved_layers", [])}
    via_layer = rc.get("via", {}).get("layer", "V1")
    via_r = finite_positive(rc.get("via", {}).get("nominal_resistance_ohm"), "via.nominal_resistance_ohm")
    for net, per_layer in net_lengths.items():
        for layer, value in per_layer.items():
            if layer.startswith("__"):
                continue
            if layer.startswith("V"):
                if layer == via_layer:
                    network.resistance_ohm[net] += value * via_r
                continue
            entry = layers[layer]
            network.resistance_ohm[net] += value * finite_positive(entry["resistance_ohm_per_um"], f"{layer}.resistance_ohm_per_um")
            network.add_ground(
                net,
                value * finite_positive(entry["capacitance_pf_per_um"], f"{layer}.capacitance_pf_per_um"),
                "wire_to_substrate",
                "derived LEF area plus edge capacitance",
                layer=layer,
                length_um=value,
            )
    lateral = model.get("lateral_coupling", {})
    by_layer_orientation: dict[tuple[str, str], list[Segment]] = defaultdict(list)
    for segment in segments:
        by_layer_orientation[(segment.layer, segment.orientation)].append(segment)
    for (layer, orientation), group in by_layer_orientation.items():
        params = lateral.get(layer)
        if not isinstance(params, dict):
            continue
        edge_pf_per_um = finite_positive(params.get("coupling_edge_capacitance_pf_per_um"), f"lateral_coupling.{layer}.coupling_edge_capacitance_pf_per_um")
        decay_um = finite_positive(params.get("decay_um"), f"lateral_coupling.{layer}.decay_um")
        max_distance_um = finite_positive(params.get("max_distance_um"), f"lateral_coupling.{layer}.max_distance_um")
        if orientation == "H":
            group.sort(key=lambda item: (item.y1_um + item.y2_um) / 2.0)
        else:
            group.sort(key=lambda item: (item.x1_um + item.x2_um) / 2.0)
        for index, first in enumerate(group):
            first_perpendicular = (first.y1_um + first.y2_um) / 2.0 if orientation == "H" else (first.x1_um + first.x2_um) / 2.0
            for second in group[index + 1 :]:
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
                network.add_coupling(
                    first.net,
                    second.net,
                    cap_pf,
                    "lateral_fringe",
                    "engineering proxy: minimum LEF edge capacitance with exponential spacing attenuation",
                    layer=layer,
                    parallel_length_um=overlap_um,
                    spacing_um=spacing_um,
                )


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


def add_vertical_network(
    network: Network,
    segments: list[Segment],
    gds_path: Path | None,
    gds_top: str,
    substrate_net: str,
    model: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    vertical = model.get("vertical_coupling", {})
    m3_m2 = vertical.get("M3_M2", {})
    m3_m1 = vertical.get("M3_M1", {})
    m3_substrate = vertical.get("M3_SUBSTRATE", {})
    for name, params in (("M3_M2", m3_m2), ("M3_M1", m3_m1), ("M3_SUBSTRATE", m3_substrate)):
        if not isinstance(params, dict):
            raise SystemExit(f"vertical_coupling.{name} must be an object")
    m3_segments = [segment for segment in segments if segment.layer == "M3"]
    underlying_geometry: list[tuple[tuple[float, float, float, float], str, str, str]] = [
        (segment.bbox, segment.layer, segment.net, f"DEF {segment.source}")
        for segment in segments
        if segment.layer in {"M1", "M2"}
    ]
    route_nets = {segment.net for segment in segments}
    gds_summary: dict[str, Any] = {
        "available": bool(gds_path),
        "m3_shapes": 0,
        "underlying_gds_shapes": 0,
        "overlap_area_um2": {"M1": 0.0, "M2": 0.0},
        "geometry_method": "axis_aligned_bounding_box_intersection",
    }
    m3_boxes: list[tuple[tuple[float, float, float, float], str, str]] = []
    if gds_path is not None:
        needed = {GDS_LAYERS[layer] for layer in ("M1", "M2", "M3")}
        needed_layer_numbers = {layer for layer, _ in needed}
        structures, meters_per_dbu = parse_gds(gds_path, needed)
        shapes, labels = flatten_gds(structures, meters_per_dbu, gds_top, needed)
        m3_layer, m3_datatype = GDS_LAYERS["M3"]
        m3_shape_boxes: list[tuple[float, float, float, float]] = []
        for shape in (
            shape for shape in shapes if shape.layer == m3_layer and shape.datatype == m3_datatype
        ):
            m3_shape_boxes.append(shape.bbox_um)
            nets = _labels_for_box(labels, m3_layer, shape.bbox_um)
            shape_net = next(
                (net for net in nets if net in route_nets or net.upper() in SUBSTRATE_ALIASES),
                next(
                    (segment.net for segment in m3_segments if rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0),
                    substrate_net,
                ),
            )
            m3_boxes.append((shape.bbox_um, shape_net, f"GDS {shape.hierarchy}"))
        for shape in (
            shape for shape in shapes if shape.layer in needed_layer_numbers and shape.layer != m3_layer
        ):
            layer = next(name for name in ("M1", "M2") if GDS_LAYERS[name][0] == shape.layer)
            nets = _labels_for_box(labels, shape.layer, shape.bbox_um)
            shape_net = next(
                (net for net in nets if net in route_nets or net.upper() in SUBSTRATE_ALIASES),
                next(
                    (
                        segment.net
                        for segment in segments
                        if segment.layer == layer and rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0
                    ),
                    None,
                ),
            )
            if shape_net is None:
                continue
            # DEF routes are authoritative where both views describe the same
            # metal.  GDS-only labelled shapes extend the overlap evidence to
            # frame/cell geometry not present in the routed DEF.
            if any(
                segment.layer == layer and rectangle_overlap(shape.bbox_um, segment.bbox) > 0.0
                for segment in segments
            ):
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
        # A DEF M3 segment can represent a routed shape absent from the GDS
        # hierarchy.  Keep only those non-overlapping segments to avoid double
        # counting a shape present in both views.
        for segment in m3_segments:
            if not any(rectangle_overlap(segment.bbox, box) > 0.0 for box in m3_shape_boxes):
                m3_boxes.append((segment.bbox, segment.net, "DEF M3 route"))
    else:
        m3_boxes = [(segment.bbox, segment.net, "DEF M3 route") for segment in m3_segments]
    if not m3_boxes:
        return gds_summary
    for m3_box, m3_net, m3_source in m3_boxes:
        if m3_net != substrate_net and m3_net.upper() not in SUBSTRATE_ALIASES:
            area = (m3_box[2] - m3_box[0]) * (m3_box[3] - m3_box[1])
            cap_density = finite_positive(m3_substrate.get("capacitance_pf_per_um2"), "vertical_coupling.M3_SUBSTRATE.capacitance_pf_per_um2")
            network.add_ground(m3_net, area * cap_density, "m3_to_substrate", str(m3_substrate.get("basis", "engineering vertical estimate")), area_um2=area, source=m3_source)
        for underlying_box, layer, underlying_net, underlying_source in underlying_geometry:
            area = rectangle_overlap(m3_box, underlying_box)
            if area <= 0.0:
                continue
            params = m3_m2 if layer == "M2" else m3_m1
            key = "M3_M2" if layer == "M2" else "M3_M1"
            cap_density = finite_positive(params.get("capacitance_pf_per_um2"), f"vertical_coupling.{key}.capacitance_pf_per_um2")
            cap_pf = area * cap_density
            gds_summary["overlap_area_um2"][layer] += area
            basis = str(params.get("basis", "engineering vertical estimate"))
            if m3_net == substrate_net or m3_net.upper() in SUBSTRATE_ALIASES:
                network.add_ground(underlying_net, cap_pf, "m3_vertical_to_substrate", basis, layer=layer, overlap_area_um2=area, source=m3_source)
            elif m3_net != underlying_net:
                network.add_coupling(underlying_net, m3_net, cap_pf, "m3_vertical_coupling", basis, layer=layer, overlap_area_um2=area, source=f"{m3_source}; {underlying_source}")
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


def write_spef(
    path: Path,
    design: str,
    substrate_net: str,
    network: Network,
    net_lengths: dict[str, dict[str, float]],
) -> None:
    nets = set(net_lengths) | set(network.ground_pf)
    for node1, node2 in network.coupling_pf:
        nets.add(node1)
        nets.add(node2)
    nets.discard("")
    out = [
        '*SPEF "IEEE 1481-1998"',
        f'*DESIGN "{design}"',
        '*DATE "2026-01-01T00:00:00"',
        '*VENDOR "TR-1um flow"',
        '*PROGRAM "extract_tr1um_parasitics"',
        '*VERSION "2.0"',
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
    pair_owner: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (node1, node2), cap_pf in sorted(network.coupling_pf.items()):
        pair_owner[node1].append((node2, cap_pf))
    total_nets = 0
    for net in sorted(nets):
        ground = float(network.ground_pf.get(net, 0.0))
        coupling_total = sum(
            cap for (node1, node2), cap in network.coupling_pf.items() if net in {node1, node2}
        )
        total_cap = ground + coupling_total
        resistance = float(network.resistance_ohm.get(net, 0.0))
        if total_cap <= 0.0 and resistance <= 0.0 and net not in pair_owner:
            continue
        total_nets += 1
        out.append(f"*D_NET {net} {total_cap:.9e}")
        out.append("*CONN")
        out.append("*CAP")
        cap_index = 1
        if ground > 0.0:
            out.append(f"{cap_index} {net} {ground:.9e}")
            cap_index += 1
        for other, cap_pf in sorted(pair_owner.get(net, [])):
            out.append(f"{cap_index} {net} {other} {cap_pf:.9e}")
            cap_index += 1
        if resistance > 0.0:
            out.append("*RES")
            out.append(f"1 {net} {net} {resistance:.9e}")
        out.append("*END")
        out.append("")
    out.append(f"*# NETS {total_nets}")
    out.append(f"*# SUBSTRATE_NET {substrate_net}")
    out.append("*# STATUS engineering_estimate_not_foundry_qualified")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_spice(path: Path, substrate_net: str, network: Network) -> None:
    nodes = {substrate_net}
    nodes.update(network.ground_pf)
    for node1, node2 in network.coupling_pf:
        nodes.update((node1, node2))
    ordered_nodes = [substrate_net] + sorted(node for node in nodes if node != substrate_net)
    out = [
        "* TR-1um engineering parasitic capacitor network.",
        "* Include this subcircuit only when its device-cap ownership is understood.",
        ".SUBCKT tr1um_parasitics " + " ".join(ordered_nodes),
    ]
    index = 1
    for net, cap_pf in sorted(network.ground_pf.items()):
        if cap_pf > 0.0:
            out.append(f"CPEX{index} {net} {substrate_net} {cap_pf:.9e}pF")
            index += 1
    for (node1, node2), cap_pf in sorted(network.coupling_pf.items()):
        out.append(f"CPEX{index} {node1} {node2} {cap_pf:.9e}pF")
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
    design, segments, net_lengths = parse_def_segments(def_text, rc)
    top = args.top or design
    warnings: list[str] = []
    if args.gds is None:
        warnings.append("no GDS supplied; M3 vertical terms are extracted only when M3 routes are present in DEF")
    if args.extracted is None:
        warnings.append("no extracted SPICE supplied; GR/RR/GC device terms are not discoverable from DEF alone")
    if not args.rr_model.exists() and args.extracted:
        raise SystemExit(f"missing F_RR model file: {args.rr_model}")
    network = Network.create()
    add_route_network(network, segments, net_lengths, rc, model)
    devices: list[Device] = []
    if args.extracted:
        devices = parse_extracted_devices(args.extracted)
    gr_region = classify_gr_substrate(args.gds, top) if args.gds and any(device.model == "F_RS" for device in devices) else None
    if args.extracted and any(device.model == "F_RS" for device in devices) and gr_region is None:
        warnings.append("F_RS devices were found but no GR geometry was classified; using the configured substrate net")
    if gr_region == "MIXED":
        warnings.append("GR geometry spans PSUB and NW; F_RS terms use the configured substrate net")
    gds_summary = add_vertical_network(network, segments, args.gds, top, args.substrate_net, model, warnings)
    if devices:
        add_device_network(network, devices, model, args.rr_model, top, args.substrate_net, args.well_net, gr_region, not args.no_device_caps, warnings, args.extracted)
    write_spef(args.spef, design, args.substrate_net, network, net_lengths)
    write_spice(args.spice, args.substrate_net, network)
    report = {
        "schema": 2,
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
        "gds": gds_summary,
        "summary": summarize(network, segments, devices, warnings),
        "ground_capacitance_pf": {net: value for net, value in sorted(network.ground_pf.items()) if value > 0.0},
        "resistance_ohm": {net: value for net, value in sorted(network.resistance_ohm.items()) if value > 0.0},
        "coupling_capacitance_pf": [
            {"node1": node1, "node2": node2, "capacitance_pf": value}
            for (node1, node2), value in sorted(network.coupling_pf.items())
        ],
        "ground_entries": network.ground_records,
        "coupling_entries": network.coupling_records,
        "device_entries": network.device_records,
        "warnings": warnings,
    }
    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "parasitics: "
        f"segments={len(segments)} devices={len(devices)} "
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
