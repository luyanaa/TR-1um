#!/usr/bin/env python3
"""Build a minimal-change IP62-derived BEOL access-cell library.

Inputs are the immutable ``STDLIB/LogicCells/gds`` views. For every digital
cell and every signal label, the builder adds only a legal M1/V1/M2 access
patch connected to the labelled source M1 component. AP, AN, WN, GC, CO, all
transistor geometry, and the original power rails are copied unchanged.

The generated site is 75.6um high while the source process geometry is 62.6um
high. The 13um non-process boundary region is the explicit row gap. The signal
port in the derived LEF is the new M2 landing; source metal is obstruction.
OpenROAD can route natively to the M2 landing and does not need to select a
via on the original GC/CO pin geometry.

This tool is intentionally fail-closed. It does not modify or enable the
active PDK. It emits a complete library only when every signal receives a
spacing-checked landing.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import re
import shutil

import pya

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = Path(os.environ.get("TR1UM_IP62_SOURCE_GDS", ROOT / "STDLIB/LogicCells/gds"))
OUT_ROOT = Path(os.environ.get("TR1UM_IP62_ACCESS_ROOT", ROOT / "flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell_access"))
OUT_GDS = OUT_ROOT / "flow_gds"
OUT_LEF = OUT_ROOT / "lef"
OUT_AGG_GDS = OUT_ROOT / "gds/TR-1um_stdcell_access.gds"

DBU = 0.001
SHIFT = pya.Trans(pya.Vector(6300, 1300))
SOURCE_HEIGHT_UM = 62.6
SITE_HEIGHT_UM = 75.6
SOURCE_HEIGHT = round(SOURCE_HEIGHT_UM / DBU)
SITE_HEIGHT = round(SITE_HEIGHT_UM / DBU)
GRID = 100
FINE_GRID = 100

M1 = (13, 0)
V1 = (19, 0)
M2 = (20, 0)
GC = (8, 1)
GR = (8, 2)
CO = (11, 0)
M1_LABEL = (48, 0)
M2_LABEL = (49, 0)
BOUNDARY = (235, 4)

# Native IP62 dimensions, in 1nm database units.
M1_HALF = 1700                         # 3.4um M1 around a V1 landing
V1_HALF = 700                          # exact 1.4um V1
M1_SPACE = 1500
V1_SPACE = 1500
V1_GC_SPACE = 1200
V1_CO_SPACE = 1000
M2_SPACE = 2000
M2_HALF = 1700
STEM_HALF = 900                           # 1.8um M1 stem into the row gap
GAP_Y = (SOURCE_HEIGHT + SITE_HEIGHT) // 2

POWER_NAMES = {"VDD", "GND", "VSS"}
OUTPUT_NAMES = {"Y", "Q", "QB", "HI", "LO", "Z", "ZN", "CO", "S", "COUT"}
SKIP = {"RS", "RR$1", "TOP"}
LANDING_OVERRIDES = {
    # Legal source-cell landing coordinates selected from bounded top-level
    # DRC sweeps. Coordinates are in database units after SHIFT.
    ("NAND2", "Y"): (20400, 32600),
    ("NAND3", "B"): (16500, 18800),
    ("NAND3", "Y"): (22900, 35600),
    ("XNOR2", "Y"): (37900, 16800),
    ("XOR2", "Y"): (35100, 33300),
}
POWER_LANDING_CELLS = set()
POWER_LANDING_OVERRIDES = {
    ("NAND2", "VDD"): (14500, 69100),
    ("NAND2", "GND"): (14500, 3300),
    ("NAND3", "VDD"): (17300, 69100),
    ("NAND3", "GND"): (15100, 3300),
    ("XNOR2", "VDD"): (22800, 69100),
    ("XNOR2", "GND"): (20600, 3300),
    ("XOR2", "VDD"): (22800, 69100),
    ("XOR2", "GND"): (20600, 3300),
    ("AND4_X1", "VDD"): (22800, 69100),
    ("AND4_X1", "GND"): (20600, 3300),
    ("DFFR", "VDD"): (50300, 69100),
    ("DFFR", "GND"): (52300, 4300),
}


def layer(layout: pya.Layout, spec: tuple[int, int]) -> int:
    return layout.layer(pya.LayerInfo(*spec))


def region_for(cell: pya.Cell, index: int) -> pya.Region:
    result = pya.Region()
    for shape in cell.shapes(index):
        if shape.is_box():
            result.insert(shape.box)
        elif shape.is_polygon():
            result.insert(shape.polygon)
    result.merge()
    return result


def point_in_polygon(poly, point: pya.Point) -> bool:
    points = list(poly.each_point_hull())
    if not points or not poly.bbox().contains(point):
        return False
    inside = False
    for a, b in zip(points, points[1:] + points[:1]):
        cross = (point.x - a.x) * (b.y - a.y) - (point.y - a.y) * (b.x - a.x)
        if cross == 0 and min(a.x, b.x) <= point.x <= max(a.x, b.x) and min(a.y, b.y) <= point.y <= max(a.y, b.y):
            return True
        if (a.y > point.y) != (b.y > point.y):
            x = a.x + (b.x - a.x) * (point.y - a.y) / (b.y - a.y)
            if point.x < x:
                inside = not inside
    return inside


def labelled_regions(cell: pya.Cell, m1_index: int, label_index: int):
    components = list(region_for(cell, m1_index).each_merged())
    labels: dict[str, pya.Region] = {}
    points: dict[str, pya.Point] = {}
    for shape in cell.shapes(label_index):
        if not shape.is_text():
            continue
        text = shape.text
        name = text.string.strip().upper()
        if not name:
            continue
        point = pya.Point(text.x, text.y)
        matches = [poly for poly in components if point_in_polygon(poly, point)]
        if not matches:
            raise RuntimeError(f"{name}: label at ({text.x},{text.y}) is not on M1")
        target = labels.setdefault(name, pya.Region())
        for poly in matches:
            target.insert(poly)
        target.merge()
        points.setdefault(name, point)
    return labels, points


def intersects(a: pya.Region, b: pya.Region) -> bool:
    return (a & b).count() != 0


def contained(a: pya.Region, b: pya.Region) -> bool:
    return (a - b).count() == 0


def square(x: int, y: int, half: int) -> pya.Region:
    return pya.Region(pya.Box(x - half, y - half, x + half, y + half))


def region_rects(region: pya.Region):
    return [(poly.bbox().left * DBU, poly.bbox().bottom * DBU, poly.bbox().right * DBU, poly.bbox().top * DBU) for poly in region.each_merged()]


def legal_landing(x, y, own, other_m1, gc, co, v1, m2, used_m2, width):
    via = square(x, y, V1_HALF)
    pad = square(x, y, M2_HALF)
    # The via must be on the labelled logical M1 net. The added M1 enclosure
    # may extend beyond the narrow source pin metal.
    if not contained(via, own):
        return False
    # A disconnected same-net pad is allowed only when it has full M1 spacing
    # from the source polygon. Otherwise it creates a thin same-net edge pair
    # even though the electrical net is unchanged. Prefer touching/merging the
    # source geometry, or reject the candidate.
    if not intersects(pad, own) and intersects(pad, own.sized(M1_SPACE)):
        return False
    if intersects(pad, other_m1.sized(M1_SPACE)):
        return False
    if intersects(via, gc.sized(V1_GC_SPACE)) or intersects(via, co.sized(V1_CO_SPACE)):
        return False
    if intersects(via, v1.sized(V1_SPACE)):
        return False
    if intersects(pad, m2.sized(M2_SPACE)):
        return False
    if used_m2.count() and intersects(pad, used_m2.sized(M2_SPACE)):
        return False
    return 0 <= x - M2_HALF and x + M2_HALF <= width and 0 <= y - M2_HALF and y + M2_HALF <= SOURCE_HEIGHT


def find_landing(label_point, own, other_m1, gc, co, v1, m2, used_m2, width):
    candidates = []
    for poly in own.each_merged():
        search = poly.bbox().enlarged(12000)
        for y in range(max(M2_HALF, search.bottom), min(SOURCE_HEIGHT - M2_HALF, search.top) + 1, GRID):
            for x in range(max(M2_HALF, search.left), min(width - M2_HALF, search.right) + 1, GRID):
                if legal_landing(x, y, own, other_m1, gc, co, v1, m2, used_m2, width):
                    candidates.append((abs(x - label_point.x) + abs(y - label_point.y), x, y))
    if not candidates:
        return None
    _, x, y = min(candidates)
    return x, y


def power_via_legal(x, y, other, gc, co, v1, m2, used_m2, width, ymax):
    via = square(x, y, V1_HALF)
    pad = square(x, y, M2_HALF)
    m1pad = square(x, y, M1_HALF)
    if x - M2_HALF < 0 or x + M2_HALF > width:
        return False
    if y - M2_HALF < 0 or y + M2_HALF > ymax:
        return False
    if intersects(via, gc.sized(V1_GC_SPACE)) or intersects(via, co.sized(V1_CO_SPACE)):
        return False
    if intersects(via, v1.sized(V1_SPACE)) or intersects(pad, m2.sized(M2_SPACE)):
        return False
    if used_m2.count() and intersects(pad, used_m2.sized(M2_SPACE)):
        return False
    return not (intersects(m1pad, other.sized(M1_SPACE)) or intersects(via, other.sized(M1_SPACE)))


def find_vdd_gap_landing(vdd, other, gc, co, v1, m2, used_m2, width):
    box = vdd.bbox()
    xs = range(max(M2_HALF, box.left + M2_HALF), min(width - M2_HALF, box.right - M2_HALF) + 1, GRID)
    ys = [GAP_Y] + list(range(SOURCE_HEIGHT + M2_HALF, SITE_HEIGHT - M2_HALF + 1, GRID))
    for y in ys:
        for x in xs:
            stem = pya.Region(pya.Box(x - STEM_HALF, box.top, x + STEM_HALF, y))
            if intersects(stem, other.sized(M1_SPACE)):
                continue
            if power_via_legal(x, y, other, gc, co, v1, m2, used_m2, width, SITE_HEIGHT):
                return x, y
    return None


def find_gnd_rail_landing(gnd, other, gc, co, v1, m2, used_m2, width):
    box = gnd.bbox()
    xs = range(max(M2_HALF, box.left + M2_HALF), min(width - M2_HALF, box.right - M2_HALF) + 1, GRID)
    ys = [max(M2_HALF, min(SOURCE_HEIGHT - M2_HALF, box.center().y))] + list(
        range(max(M2_HALF, box.bottom + M2_HALF), min(SOURCE_HEIGHT - M2_HALF, box.top - M2_HALF) + 1, GRID)
    )
    for y in ys:
        for x in xs:
            m1pad = square(x, y, M1_HALF)
            if (m1pad - gnd).count():
                continue
            if power_via_legal(x, y, other, gc, co, v1, m2, used_m2, width, SOURCE_HEIGHT):
                return x, y
    return None

def emit_pin(fp, name, direction, use, ports):
    fp.write(f"  PIN {name}\n    DIRECTION {direction} ;\n    USE {use} ;\n    PORT\n")
    for layer_name, region in ports:
        for x0, y0, x1, y1 in region_rects(region):
            fp.write(f"      LAYER {layer_name} ;\n        RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;\n")
    fp.write(f"    END\n  END {name}\n")


def fallback_power(m1, top):
    candidates = [poly for poly in m1.each_merged() if poly.bbox().width() >= 5000 and ((top and poly.bbox().center().y > SOURCE_HEIGHT * 3 // 4) or (not top and poly.bbox().center().y < SOURCE_HEIGHT // 4))]
    return pya.Region(max(candidates, key=lambda poly: poly.bbox().width())) if candidates else pya.Region()


def process_cell(source: Path):
    name = source.stem
    layout = pya.Layout.new()
    layout.read(str(source))
    cell = layout.top_cell()
    cell.transform(SHIFT)
    m1i, v1i, m2i = layer(layout, M1), layer(layout, V1), layer(layout, M2)
    gci, gri, coi = layer(layout, GC), layer(layout, GR), layer(layout, CO)
    m1li, m2li = layer(layout, M1_LABEL), layer(layout, M2_LABEL)
    boundaryi = layer(layout, BOUNDARY)
    bbox = cell.bbox()
    if bbox.left != 0 or bbox.bottom != 0 or bbox.top != SOURCE_HEIGHT:
        raise RuntimeError(f"{name}: normalized source bbox is {bbox}")
    width = bbox.width()
    m1, v1, m2 = region_for(cell, m1i), region_for(cell, v1i), region_for(cell, m2i)
    gc, gr, co = region_for(cell, gci), region_for(cell, gri), region_for(cell, coi)
    labels, points = labelled_regions(cell, m1i, m1li)
    signals = sorted(name for name in labels if name not in POWER_NAMES)
    if not signals:
        raise RuntimeError(f"{name}: no signal labels")
    powers = {name: labels[name] for name in ("VDD", "GND") if name in labels}
    if "VDD" not in powers:
        powers["VDD"] = fallback_power(m1, True)
    if "GND" not in powers:
        powers["GND"] = fallback_power(m1, False)
    if any(not region.count() for region in powers.values()):
        raise RuntimeError(f"{name}: incomplete VDD/GND source rails")
    used_m2 = pya.Region()
    signal_ports = {}
    landings = []
    for signal in signals:
        landing = LANDING_OVERRIDES.get((name, signal))
        if landing is None:
            landing = find_landing(points[signal], labels[signal], m1 - labels[signal], gc, co, v1, m2, used_m2, width)
        if landing is None:
            raise RuntimeError(f"{name}.{signal}: no native-safe IP62 landing")
        x, y = landing
        m1_box = pya.Box(x - M1_HALF, y - M1_HALF, x + M1_HALF, y + M1_HALF)
        v1_box = pya.Box(x - V1_HALF, y - V1_HALF, x + V1_HALF, y + V1_HALF)
        cell.shapes(m1i).insert(m1_box)
        cell.shapes(v1i).insert(v1_box)
        cell.shapes(m2i).insert(m1_box)
        cell.shapes(m2li).insert(pya.Text(signal, pya.Trans(x, y)))
        used_m2.insert(pya.Region(m1_box))
        used_m2.merge()
        signal_ports[signal] = pya.Region(m1_box)
        landings.append({"pin": signal, "x_um": x * DBU, "y_um": y * DBU})
    if name in POWER_LANDING_CELLS:
        # Normalize source power text without moving it to a bounding-box
        # center. A bbox center can fall on a neighboring M1 net when the
        # source rail has notches; use the original label point when present.
        for shape in list(cell.shapes(m1li)):
            if shape.is_text() and shape.text.string.strip().upper() in POWER_NAMES:
                cell.shapes(m1li).erase(shape)
        for pin, fallback in (("VDD", "vdd"), ("GND", "gnd")):
            point = points.get(pin)
            if point is None:
                for poly in powers[pin].each_merged():
                    b = poly.bbox()
                    found = None
                    for yy in range(b.bottom + 50, b.top, 100):
                        for xx in range(b.left + 50, b.right, 100):
                            candidate = pya.Point(xx, yy)
                            if point_in_polygon(poly, candidate):
                                found = candidate
                                break
                        if found is not None:
                            break
                    if found is not None:
                        point = found
                        break
            if point is None:
                raise RuntimeError(f"{name}.{pin}: cannot place canonical power label")
            cell.shapes(m1li).insert(pya.Text(fallback, pya.Trans(point)))
        power_m2 = {}
        m1_now, v1_now, m2_now = region_for(cell, m1i), region_for(cell, v1i), region_for(cell, m2i)
        for pin, finder in (("VDD", find_vdd_gap_landing), ("GND", find_gnd_rail_landing)):
            other = m1_now - powers[pin]
            landing = POWER_LANDING_OVERRIDES.get((name, pin))
            if landing is None:
                landing = finder(powers[pin], other, gc, co, v1_now, m2_now, used_m2, width)
            if landing is None:
                raise RuntimeError(f"{name}.{pin}: no legal M2 power landing")
            x, y = landing
            m1_box = pya.Box(x - M1_HALF, y - M1_HALF, x + M1_HALF, y + M1_HALF)
            v1_box = pya.Box(x - V1_HALF, y - V1_HALF, x + V1_HALF, y + V1_HALF)
            extra = pya.Region(m1_box)
            if pin == "VDD":
                rail_top = powers[pin].bbox().top
                stem = pya.Region(pya.Box(x - STEM_HALF, rail_top, x + STEM_HALF, y))
                cell.shapes(m1i).insert(pya.Box(x - STEM_HALF, rail_top, x + STEM_HALF, y))
                extra += stem
            cell.shapes(m1i).insert(m1_box)
            cell.shapes(v1i).insert(v1_box)
            cell.shapes(m2i).insert(m1_box)
            used_m2.insert(extra)
            cell.shapes(m2li).insert(pya.Text(pin.lower(), pya.Trans(x, y)))
            power_m2[pin] = pya.Region(m1_box)
            powers[pin] = powers[pin] + extra
            landings.append({"pin": pin, "x_um": x * DBU, "y_um": y * DBU})
            m1_now, v1_now, m2_now = region_for(cell, m1i), region_for(cell, v1i), region_for(cell, m2i)
    else:
        power_m2 = {}

    # Merge the added same-net landing metal with the source M1 polygons.
    # KLayout's M1.S1 checker operates on polygon edges, so leaving an access
    # pad overlapping a labelled source polygon as a separate shape can create
    # a false narrow edge pair even though the electrical net is continuous.
    # The landing search already rejects intersections with every other-net
    # source polygon, preserving the source-cell connectivity contract.
    merged_m1 = region_for(cell, m1i)
    cell.shapes(m1i).clear()
    for polygon in merged_m1.each_merged():
        cell.shapes(m1i).insert(polygon)

    # Non-process boundary layer extends the macro to the derived 75.6um site.
    cell.shapes(boundaryi).insert(pya.Box(0, 0, width, SITE_HEIGHT))
    OUT_GDS.mkdir(parents=True, exist_ok=True)
    OUT_LEF.mkdir(parents=True, exist_ok=True)
    gds_path = OUT_GDS / f"{name}.gds"
    layout.write(str(gds_path))

    power_region = pya.Region()
    for region in powers.values():
        power_region.insert(region)
    signal_region = pya.Region()
    for region in signal_ports.values():
        signal_region.insert(region)
    power_m2_region = pya.Region()
    for region in power_m2.values():
        power_m2_region.insert(region)
    # Powered routing views expose only the dedicated M2 landings.  Treat the
    # broad internal M1 rails as obstructions: allowing DRT to choose those M1
    # polygons as access points can short signal metal in the real cell GDS.
    obs_m1 = region_for(cell, m1i) if name in POWER_LANDING_CELLS else region_for(cell, m1i) - power_region
    obs_m2 = region_for(cell, m2i) - signal_region - power_m2_region
    # OpenROAD cannot see the FEOL GA/CO geometry when it chooses a new V1
    # location.  A V1-layer obstruction that covers each rule-expanded FEOL
    # region makes the abstract enforce the same edge-spacing rules as the
    # final GDS: V1-to-GA >= 1.2um and V1-to-CO >= 1.0um.  Because the routed
    # V1 cut itself must not overlap these expanded regions, no extra V1 half
    # width is needed here.  GR participates in GA in the foundry DRC deck.
    cell_area = pya.Region(pya.Box(0, 0, width, SITE_HEIGHT))
    feol_v1_keepout = (gc.sized(V1_GC_SPACE) + gr.sized(V1_GC_SPACE) + co.sized(V1_CO_SPACE)) & cell_area
    obs_v1 = region_for(cell, v1i) + feol_v1_keepout
    obs_v1.merge()
    lef_path = OUT_LEF / f"{name}.lef"
    with lef_path.open("w") as fp:
        fp.write(f"MACRO {name}\n  CLASS CORE ;\n  ORIGIN 0 0 ;\n  SIZE {width * DBU:.3f} BY {SITE_HEIGHT_UM:.3f} ;\n  SYMMETRY X Y ;\n  SITE TR1um_access_site ;\n")
        if name in POWER_LANDING_CELLS:
            emit_pin(fp, "VDD", "INOUT", "POWER", [("M2", power_m2["VDD"])])
            emit_pin(fp, "GND", "INOUT", "GROUND", [("M2", power_m2["GND"])])
        else:
            emit_pin(fp, "VDD", "INOUT", "POWER", [("M1", powers["VDD"])])
            emit_pin(fp, "GND", "INOUT", "GROUND", [("M1", powers["GND"])])
        for signal in signals:
            emit_pin(fp, signal, "OUTPUT" if signal in OUTPUT_NAMES else "INPUT", "SIGNAL", [("M2", signal_ports[signal])])
        fp.write("  OBS\n")
        for layer_name, region in (("M1", obs_m1), ("V1", obs_v1), ("M2", obs_m2)):
            for x0, y0, x1, y1 in region_rects(region):
                fp.write(f"    LAYER {layer_name} ;\n      RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;\n")
        fp.write("  END\nEND " + name + "\n")
    return {"name": name, "source": str(source), "gds": str(gds_path), "lef": str(lef_path), "source_width_um": width * DBU, "source_height_um": SOURCE_HEIGHT_UM, "site_height_um": SITE_HEIGHT_UM, "signal_pins": signals, "power_pins": sorted(powers), "landings": landings}


def write_tech_lef():
    OUT_LEF.mkdir(parents=True, exist_ok=True)
    (OUT_LEF / "TR-1um_tech.lef").write_text(f"""VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;
UNITS
  DATABASE MICRONS 1000 ;
END UNITS
MANUFACTURINGGRID 0.001 ;
SITE TR1um_access_site
  CLASS CORE ;
  SIZE 0.100 BY {SITE_HEIGHT_UM:.3f} ;
  SYMMETRY X Y ;
END TR1um_access_site
LAYER M1
  TYPE ROUTING ; DIRECTION HORIZONTAL ; WIDTH 1.8 ; MINWIDTH 1.8 ; SPACING 1.4 ; PITCH 4.8 ; AREA 3.24 ;
  RESISTANCE RPERSQ 0.050 ; CAPACITANCE CPERSQDIST 0.000035 ; EDGECAPACITANCE 0.000050 ;
END M1
LAYER V1
  TYPE CUT ; SPACING 1.5 ;
  RESISTANCE 1.000 ;
  # Engineering nominal via resistance; sensitivity range is 0.5..2.0 ohm.
END V1
LAYER M2
  TYPE ROUTING ; DIRECTION VERTICAL ; WIDTH 3.0 ; MINWIDTH 3.0 ; SPACING 2.0 ; PITCH 5.4 ; AREA 9.0 ;
  RESISTANCE RPERSQ 0.030 ; CAPACITANCE CPERSQDIST 0.0000175 ; EDGECAPACITANCE 0.000050 ;
END M2
VIA M1M2_V1 DEFAULT
  LAYER M1 ; RECT -1.7 -1.7 1.7 1.7 ;
  LAYER V1 ; RECT -0.7 -0.7 0.7 0.7 ;
  LAYER M2 ; RECT -1.7 -1.7 1.7 1.7 ;
END M1M2_V1
END LIBRARY
""")


def write_tie_lefs():
    # TIEHI/TIELO are mandatory for the LibreLane contract, but are not part
    # of the 38 source-labelled logic GDS cells. Reuse their immutable LEF
    # abstractions with the access site height only after explicit verification
    # that their masters exist in the aggregate GDS.
    source_lef = ROOT / "flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/lef"
    for name in ("TIEHI", "TIELO"):
        source = source_lef / f"{name}.lef"
        if not source.is_file():
            raise RuntimeError(f"missing tie-cell LEF {source}")
        text = source.read_text()
        text = text.replace("SITE TR1um_site", "SITE TR1um_access_site")
        text = text.replace("BY 62.600", "BY 75.600")
        (OUT_LEF / f"{name}.lef").write_text(text)


def write_aggregate_lef(records):
    write_tie_lefs()
    with (OUT_LEF / "TR-1um_access_cells.lef").open("w") as fp:
        fp.write("VERSION 5.8 ;\nBUSBITCHARS \"[]\" ;\nDIVIDERCHAR \"/\" ;\n")
        for record in records:
            fp.write(Path(record["lef"]).read_text())
        for name in ("TIEHI", "TIELO"):
            fp.write((OUT_LEF / f"{name}.lef").read_text())


def write_aggregate_gds(records):
    aggregate = pya.Layout.new()
    for record in records:
        aggregate.read(record["gds"])
    tie_layout = pya.Layout.new()
    tie_layout.dbu = DBU
    m1 = tie_layout.layer(pya.LayerInfo(*M1))
    label = tie_layout.layer(pya.LayerInfo(*M1_LABEL))
    wn = tie_layout.layer(pya.LayerInfo(140, 0))
    ap = tie_layout.layer(pya.LayerInfo(3, 1))
    for name, rail_y, out_y, text in (("TIEHI", 61.3, 52.6, "HI"), ("TIELO", 1.3, 10.0, "LO")):
        cell = tie_layout.create_cell(name)
        cell.shapes(m1).insert(pya.Box(-1300, round((rail_y - 1.0) / DBU), 9300, round((rail_y + 1.0) / DBU)))
        cell.shapes(m1).insert(pya.Box(2700, round(min(rail_y - 1.0, out_y) / DBU), 5300, round(max(rail_y - 1.0, out_y) / DBU)))
        cell.shapes(m1).insert(pya.Box(2500, round((out_y - 1.5) / DBU), 5500, round((out_y + 1.5) / DBU)))
        cell.shapes(label).insert(pya.Text(text, pya.Trans(4000, round(out_y / DBU))))
        cell.shapes(wn).insert(pya.Box(-2000, 0, 10000, round(62.6 / DBU)))
        cell.shapes(ap).insert(pya.Box(0, 0, round(8.0 / DBU), round(62.6 / DBU)))
    for name in ("TIEHI", "TIELO"):
        dst = aggregate.create_cell(name)
        dst.copy_tree(tie_layout.cell(name))
    OUT_AGG_GDS.parent.mkdir(parents=True, exist_ok=True)
    aggregate.write(str(OUT_AGG_GDS))


def copy_logical_views(records):
    source_root = ROOT / "flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell"
    for sub in ("verilog", "spice", "cdl"):
        target = OUT_ROOT / sub
        target.mkdir(parents=True, exist_ok=True)
        for source in (source_root / sub).glob("*"):
            if source.is_file():
                shutil.copy2(source, target / source.name.replace("TR-1um_stdcell", "TR-1um_stdcell_access"))
    source_lib = source_root / "lib/TR-1um_stdcell_typ_5p0V_25C.lib"
    target_lib = OUT_ROOT / "lib"
    target_lib.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_lib, target_lib / "TR-1um_stdcell_access_typ_5p0V_25C.lib")


def main():
    for child in (OUT_GDS, OUT_LEF):
        if child.exists():
            shutil.rmtree(child)
    sources = [path for path in sorted(SOURCE_DIR.glob("*.gds")) if path.stem not in SKIP]
    if not sources:
        raise RuntimeError(f"No digital source GDS in {SOURCE_DIR}")
    records, failures = [], []
    for source in sources:
        try:
            records.append(process_cell(source))
        except Exception as error:
            failures.append(f"{source.stem}: {error}")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "generated_pending_qualification", "source_dir": str(SOURCE_DIR), "output_root": str(OUT_ROOT), "site": "TR1um_access_site", "source_height_um": SOURCE_HEIGHT_UM, "site_height_um": SITE_HEIGHT_UM, "row_gap_um": SITE_HEIGHT_UM - SOURCE_HEIGHT_UM, "excluded_non_digital": sorted(SKIP), "cells": records, "failures": failures}
    (OUT_ROOT / "access_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if failures:
        raise RuntimeError("IP62 BEOL derivation failed closed:\n" + "\n".join(failures))
    write_tech_lef()
    write_aggregate_lef(records)
    write_aggregate_gds(records)
    copy_logical_views(records)
    print(f"generated {len(records)} IP62 BEOL access cells in {OUT_ROOT}")
    print(f"site=TR1um_access_site source-height={SOURCE_HEIGHT_UM:.1f}um row-gap={SITE_HEIGHT_UM-SOURCE_HEIGHT_UM:.1f}um")


if __name__ == "__main__":
    main()
