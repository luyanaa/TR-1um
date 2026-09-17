#!/usr/bin/env python3
"""Audit non-routing M3 geometry in a framed TR-1um layout.

Run inside the LibreLane/KLayout Python runtime. The audit intentionally does
not claim parasitic extraction. It reports M3 geometry in the selected top
cell, its 2-D overlaps with M1/M2/V2, and whether the routed DEF contains an
M3 segment. A reviewer must use the report to decide whether the frame M3 is
seal-only or relevant to the M1/M2 RC scope.

KLayout batch example::

    klayout -b -r flow/scripts/signoff/audit_m3_impact.py \\
      -rd input=framed.gds -rd top_cell=tr_1um_counter \\
      -rd def_file=routed.def -rd output=m3-impact.json

The default TR-1um drawing-layer mapping is M1=13/0, M2=20/0,
V2=121/0, M3=122/0. Override layer/datatype variables when auditing a
compatible technology.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pya


def value(name: str, default: str) -> str:
    return str(globals().get(name, default))


def integer(name: str, default: int) -> int:
    return int(value(name, str(default)))


def layer_index(layout: pya.Layout, layer: int, datatype: int) -> int | None:
    index = layout.find_layer(pya.LayerInfo(layer, datatype))
    return index if index >= 0 else None


def shape_region(shape: pya.Shape, trans: pya.ICplxTrans | pya.Trans) -> pya.Region:
    region = pya.Region()
    if shape.is_box():
        region.insert(shape.box.transformed(trans))
    elif shape.is_polygon():
        region.insert(shape.polygon.transformed(trans))
    elif shape.is_path():
        region.insert(shape.path.polygon().transformed(trans))
    return region


def recursive_region(cell: pya.Cell, index: int | None) -> pya.Region:
    region = pya.Region()
    if index is None:
        return region
    iterator = cell.begin_shapes_rec(index)
    while not iterator.at_end():
        region += shape_region(iterator.shape(), iterator.trans())
        iterator.next()
    region.merge()
    return region


def bbox_um(box: pya.Box, dbu: float) -> list[float]:
    return [
        round(box.left * dbu, 6),
        round(box.bottom * dbu, 6),
        round(box.right * dbu, 6),
        round(box.top * dbu, 6),
    ]
def dbbox_um(box: pya.DBox) -> list[float]:
    return [
        round(box.left, 6),
        round(box.bottom, 6),
        round(box.right, 6),
        round(box.top, 6),
    ]




def region_summary(region: pya.Region, dbu: float) -> dict[str, Any]:
    polygons = list(region.each_merged())
    return {
        "polygon_count": len(polygons),
        "area_um2": round(sum(poly.area() for poly in polygons) * dbu * dbu, 6),
        "bbox_um": bbox_um(region.bbox(), dbu) if polygons else None,
    }


def component_summary(region: pya.Region, dbu: float) -> list[dict[str, Any]]:
    components = []
    for number, polygon in enumerate(region.each_merged(), start=1):
        components.append(
            {
                "id": number,
                "area_um2": round(polygon.area() * dbu * dbu, 6),
                "bbox_um": bbox_um(polygon.bbox(), dbu),
            }
        )
    return components


def def_route_layers(def_file: Path | None) -> dict[str, Any]:
    if def_file is None:
        return {"provided": False, "m3_route": None, "v2_route": None}
    if not def_file.is_file():
        raise SystemExit(f"ERROR: DEF file does not exist: {def_file}")
    text = def_file.read_text(encoding="utf-8", errors="replace")
    in_nets = False
    m3_route = False
    v2_route = False
    for line in text.splitlines():
        if line.startswith("NETS "):
            in_nets = True
        elif line.startswith("END NETS"):
            in_nets = False
        if not in_nets:
            continue
        if re.search(r"(?:ROUTED|NEW)\s+M3\b", line):
            m3_route = True
        if re.search(r"\b(?:M2M3_V2|V2)\b", line):
            v2_route = True
    return {"provided": True, "m3_route": m3_route, "v2_route": v2_route}


def main() -> None:
    input_path = Path(value("input", ""))
    if not input_path.is_file():
        raise SystemExit(f"ERROR: missing GDS input: {input_path}")

    layout = pya.Layout()
    layout.read(str(input_path))
    top_name = value("top_cell", "")
    if top_name:
        top = layout.cell(top_name)
        if top is None:
            raise SystemExit(f"ERROR: top cell {top_name!r} is absent from {input_path}")
    else:
        tops = list(layout.top_cells())
        if len(tops) != 1:
            raise SystemExit(
                "ERROR: supply top_cell when the GDS has multiple top cells: "
                + ", ".join(cell.name for cell in tops)
            )
        top = tops[0]
        top_name = top.name

    layers = {
        "M1": (integer("m1_layer", 13), integer("m1_datatype", 0)),
        "M2": (integer("m2_layer", 20), integer("m2_datatype", 0)),
        "V2": (integer("v2_layer", 121), integer("v2_datatype", 0)),
        "M3": (integer("m3_layer", 122), integer("m3_datatype", 0)),
    }
    indices = {
        name: layer_index(layout, layer, datatype)
        for name, (layer, datatype) in layers.items()
    }
    m3_index = indices["M3"]
    local_m3_cells = []
    if m3_index is not None:
        for cell in layout.each_cell():
            count = cell.shapes(m3_index).size()
            if count:
                local_m3_cells.append(
                    {
                        "cell": cell.name,
                        "local_shape_count": count,
                        "cell_bbox_um": dbbox_um(cell.dbbox()),
                    }
                )
    regions = {
        name: recursive_region(top, index) for name, index in indices.items()
    }
    m3 = regions["M3"]
    overlap = {
        "M3_M1_planar_overlap": region_summary(m3 & regions["M1"], layout.dbu),
        "M3_M2_planar_overlap": region_summary(m3 & regions["M2"], layout.dbu),
        "M3_V2_overlap": region_summary(m3 & regions["V2"], layout.dbu),
    }
    def_path_text = value("def_file", "")
    def_path = Path(def_path_text) if def_path_text else None
    report = {
        "status": "review_required" if m3.count() else "no_m3_in_selected_top",
        "input": str(input_path.resolve()),
        "top_cell": top_name,
        "dbu_um": layout.dbu,
        "layer_mapping": {
            name: {"layer": layer, "datatype": datatype, "index": indices[name]}
            for name, (layer, datatype) in layers.items()
        },
        "layers": {name: region_summary(region, layout.dbu) for name, region in regions.items()},
        "layout_cells_with_local_m3": local_m3_cells,
        "m3_components": component_summary(m3, layout.dbu),
        "overlap": overlap,
        "def_routing": def_route_layers(def_path),
        "conclusion": (
            "M3 geometry is present in the selected top hierarchy. Classify its "
            "net and frame/core relationship before excluding it from RC scope."
            if m3.count()
            else "No M3 geometry is present in the selected top hierarchy."
        ),
    }
    output_text = value("output", "")
    if output_text:
        output = Path(output_text)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
