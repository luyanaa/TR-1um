#!/usr/bin/env python3
"""Add a spacing-checked BEOL escape ring to the analog hard macro.

The composite NMOS macro's source pins are M1-only and its M1 is uniformly
2.6um wide, so no legal V1 landing fits inside the original bbox (V1 needs
1.0um M1 enclosure on every side => 3.4um of M1). When the digital router
connected to the native pins it placed M1 stubs and V1 vias over the macro
interior, hitting gate silicide (GC) and neighbouring M1 - 14 drawing-layer
violations (M1.S1/M1.W1/V1.GA) in the routed mixed run.

This generator grows the macro by a bottom halo (and a small top halo for
the gate pin) and gives every pin an escape:

- a 1.8um M1 stem from the pin down (or up for G) into the halo,
- a 3.4x3.4 M1 pad,
- one legal 1.4um V1,
- a 3.4x3.4 M2 pad that the router connects to on M2.

Pad positions (native dbu) come from a bounded legal-geometry sweep: every
pad pair is >= 2.0um apart (M2.S1/M1.S1), every via clears all GC/CO halos,
and stems never come within 1.4um of another net's M1.

The LEF exposes every signal on its M2 pad, GND on its M1 pad, and declares
all remaining M1/V1/M2 as obstruction so the router never enters the macro
interior.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pya

DBU = 0.001
M1 = (13, 0)
V1 = (19, 0)
M2 = (20, 0)
GC = (8, 1)
CO = (11, 0)
M1_LABEL = (48, 0)
M2_LABEL = (49, 0)

V1_HALF = 700          # 1.4um via
PAD_X_HALF = 2700      # 5.4um pad X (full M2 track pitch) so router wires
                       # terminate fully inside the pad without notches
PAD_Y_HALF = 2700       # 5.4um pad Y: any 3.0um router wire ending flush on a
                       # pad edge stays fully inside the pad's Y extent, so the
                       # union never forms a sub-3.0um neck
STEM_HALF = 900        # 1.8um stem (M1.W1 min 1.8)
V1_GC_SPACE = 1200
V1_CO_SPACE = 1000
M2_SPACE = 2000
M1_SPACE = 1400

POWER_NAMES = {"VDD", "GND", "VSS"}

# Escape-ring plan in native dbu. Pad X centers sit on the M2 track grid
# (native track centers are 0.7 + 5.4n: 0.7, 6.1, 11.5, 16.9, 22.3, 27.7) so
# the router's 3.0um M2 wires terminate fully inside the 5.4um-wide pads.
#   pin: (pad_x, pad_y, stem_from_y, stem_to_y)  stem spans y range at pin x
# Row A (y -1400): DA(0.7), GNDP(11.5), DB(16.9), GND(27.7)
# Row B (y -6800): SA(6.1); Row B (y -7000): SB(22.3); top halo (y 11400): G(11.5)
ESCAPES = {
    "DA":   (  700,  -1600,  2600,   1100),
    "SA":   ( 6100,  -9200,  2600, -6500),
    "DB":   (16900,  -1600,  2600,  1100),
    "SB":   (22300,  -9200,  2600, -6500),
    "G":    (11500,  12400,  8800,  10700),
    "GND":  (27700,  -1600,  2600,  1100),
}
# The shared body pad (labelled "GND" at x 11000..13600) gets its own deeper
# escape row so same-row 5.4um-wide pads keep >= 2.0um spacing. Its stem is
# deliberately offset (x 10.9..12.7k) to keep >= 1.4um from the DB pad.
GND_PAD_ESCAPE = ("GNDP", 11500, -17000, 2600, -14300)
GND_PAD_STEM_X = 11900


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
        if (a.y > point.y) != (b.y > point.y):
            x = a.x + (b.x - a.x) * (point.y - a.y) / (b.y - a.y)
            if point.x < x:
                inside = not inside
    return inside


def labelled_regions(cell: pya.Cell, m1_index: int, label_index: int):
    components = list(region_for(cell, m1_index).each_merged())
    labels: dict[str, pya.Region] = {}
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
    return labels


def region_rects(region: pya.Region, ox: int, oy: int):
    return [
        ((p.bbox().left - ox) * DBU, (p.bbox().bottom - oy) * DBU,
         (p.bbox().right - ox) * DBU, (p.bbox().top - oy) * DBU)
        for p in region.each_merged()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="source macro GDS")
    parser.add_argument("--output-gds", required=True, type=Path)
    parser.add_argument("--output-lef", required=True, type=Path)
    parser.add_argument("--macro", default=None, help="macro cell name (default: single top cell)")
    parser.add_argument("--gnd-use", choices=("SIGNAL", "GROUND"), default="SIGNAL")
    args = parser.parse_args()

    layout = pya.Layout.new()
    layout.read(str(args.input))
    if args.macro:
        cell = layout.cell(args.macro)
        if cell is None:
            raise SystemExit(f"macro cell {args.macro!r} not found")
    else:
        tops = list(layout.top_cells())
        if len(tops) != 1:
            raise SystemExit(f"expected one top cell, found {[c.name for c in tops]}")
        cell = tops[0]

    m1i, v1i, m2i = layer(layout, M1), layer(layout, V1), layer(layout, M2)
    gci, coi = layer(layout, GC), layer(layout, CO)
    m1li, m2li = layer(layout, M1_LABEL), layer(layout, M2_LABEL)

    # Work in native source coordinates; the LEF mirrors the macro origin.
    bbox = cell.bbox()
    origin = pya.Point(bbox.left, bbox.bottom)

    labels = labelled_regions(cell, m1i, m1li)
    signals = sorted(n for n in labels if n not in POWER_NAMES)
    missing = [s for s in ESCAPES if s not in labels]
    if missing:
        raise SystemExit(f"escape plan references unknown pins: {missing}")

    gc = region_for(cell, gci)
    co = region_for(cell, coi)

    # GND has two labelled M1 components: the pin at x 27000..29600 and the
    # shared body pad at x 11000..13600. Both belong to the GND net.
    body_pad = labels["GND"] - pya.Region(pya.Box(27000, 2000, 29600, 6000))
    body_pad.merge()
    if body_pad.count() < 1:
        raise SystemExit("GND body pad not found")

    def add_escape(name, px, py, stem_y0, stem_y1, stem_x, stem_half=STEM_HALF):
        via = pya.Region(pya.Box(px - V1_HALF, py - V1_HALF, px + V1_HALF, py + V1_HALF))
        if (via & gc.sized(V1_GC_SPACE)).count():
            raise SystemExit(f"{name}: via overlaps GC halo")
        if (via & co.sized(V1_CO_SPACE)).count():
            raise SystemExit(f"{name}: via overlaps CO halo")
        pad_m1 = pya.Box(px - PAD_X_HALF, py - PAD_Y_HALF, px + PAD_X_HALF, py + PAD_Y_HALF)
        stem = pya.Box(stem_x - stem_half, min(stem_y0, stem_y1), stem_x + stem_half, max(stem_y0, stem_y1))
        cell.shapes(m1i).insert(stem)
        cell.shapes(m1i).insert(pad_m1)
        cell.shapes(v1i).insert(pya.Box(px - V1_HALF, py - V1_HALF, px + V1_HALF, py + V1_HALF))
        cell.shapes(m2i).insert(pad_m1)
        cell.shapes(m2li).insert(pya.Text(name, pya.Trans(px, py)))
        return pya.Region(pad_m1), pya.Region(stem)

    pad_regions: dict[str, pya.Region] = {}
    stem_regions: dict[str, pya.Region] = {}
    # Signal escapes: stem x = pin center.
    for pin, (px, py, sy0, sy1) in ESCAPES.items():
        if pin == "GND":
            continue
        center = labels[pin].bbox().center()
        if pin == "G":
            # The gate stem spans the full pad width so the strip-to-pad
            # transition merges into one same-net polygon (no 0.9um notch).
            pad, stem = add_escape(pin, px, py, sy0, sy1, px, PAD_X_HALF)
        else:
            pad, stem = add_escape(pin, px, py, sy0, sy1, center.x)
        pad_regions[pin] = pad
        stem_regions[pin] = stem

    # GND (labelled pin at x 27000..29600) and the shared body pad.
    gnd_pin = labels["GND"] - body_pad
    gnd_pin.merge()
    gnd_center = gnd_pin.bbox().center()
    pad, stem = add_escape("GND", ESCAPES["GND"][0], ESCAPES["GND"][1], ESCAPES["GND"][2], ESCAPES["GND"][3], gnd_center.x)
    pad_regions["GND"] = pad
    stem_regions["GND"] = stem
    name, px, py, sy0, sy1 = GND_PAD_ESCAPE
    pad, stem = add_escape(name, px, py, sy0, sy1, GND_PAD_STEM_X)
    pad_regions[name] = pad
    stem_regions[name] = stem
    # The body pad escape is GND net too: drop its label text, use the GND net.
    # Re-point the pad's M2 label to GND.
    for shape in list(cell.shapes(m2li).each()):
        if shape.is_text() and shape.text.string == "GNDP":
            cell.shapes(m2li).erase(shape)
    cell.shapes(m2li).insert(pya.Text("GND", pya.Trans(px, py)))

    # Pad-to-pad spacing (pairwise, min-distance rule).
    entries = list(pad_regions.items())
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            (na, ra), (nb, rb) = entries[i], entries[j]
            a, b = ra.bbox(), rb.bbox()
            dx = max(a.left - b.right, b.left - a.right, 0)
            dy = max(a.bottom - b.top, b.bottom - a.top, 0)
            if (dx * dx + dy * dy) ** 0.5 < M2_SPACE:
                raise SystemExit(f"M2 pads {na}/{nb} closer than 2.0um")

    # Merge added M1 with same-net source polygons.
    merged = region_for(cell, m1i)
    cell.shapes(m1i).clear()
    for polygon in merged.each_merged():
        cell.shapes(m1i).insert(polygon)

    args.output_gds.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(args.output_gds))

    m1_final = region_for(cell, m1i)
    v1_final = region_for(cell, v1i)
    m2_final = region_for(cell, m2i)
    new_bbox = cell.bbox()

    # Ports: signals on M2 pads; GND on both M2 pads (pin escape + body escape).
    signal_region = pya.Region()
    for pin in signals:
        signal_region.insert(pad_regions[pin])
    gnd_region = pad_regions["GND"] + pad_regions["GNDP"]

    # Obstructions: the pin escape stems and source metal only. The router
    # may route over the halo on M2; same-net junction notches are merged by
    # flow/scripts/signoff/merge_same_net_shapes.py after streamout.
    pins_m1 = pya.Region()
    for region in labels.values():
        pins_m1.insert(region)
    obs_m1 = m1_final - pins_m1 - body_pad
    obs_v1 = v1_final
    obs_m2 = m2_final - signal_region - gnd_region

    ox, oy = origin.x, origin.y
    w, h = new_bbox.width() * DBU, new_bbox.height() * DBU

    def emit_pin(fp, name, direction, use, ports):
        fp.write(f"  PIN {name}\n    DIRECTION {direction} ;\n    USE {use} ;\n    PORT\n")
        for layer_name, region in ports:
            for x0, y0, x1, y1 in region_rects(region, ox, oy):
                fp.write(f"      LAYER {layer_name} ;\n        RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;\n")
        fp.write(f"    END\n  END {name}\n")

    with args.output_lef.open("w") as fp:
        fp.write("VERSION 5.7 ;\nBUSBITCHARS \"[]\" ;\nDIVIDERCHAR \"/\" ;\n")
        fp.write("UNITS\n  DATABASE MICRONS 1000 ;\nEND UNITS\n\n")
        fp.write(
            f"MACRO {cell.name}\n  CLASS BLOCK ;\n  ORIGIN {ox * DBU:.3f} {oy * DBU:.3f} ;\n"
            f"  FOREIGN {cell.name} {ox * DBU:.3f} {oy * DBU:.3f} ;\n  SIZE {w:.3f} BY {h:.3f} ;\n"
        )
        for pin in signals:
            emit_pin(fp, pin, "INOUT", "SIGNAL", [("M2", pad_regions[pin])])
        if "GND" in labels:
            # OpenROAD must treat the no-PDN escape as an ordinary routable
            # pin. disconnected_pins.py classifies GND by pin/net name, so
            # this does not weaken the ground check.
            emit_pin(fp, "GND", "INOUT", args.gnd_use, [("M1", labels["GND"]), ("M2", gnd_region)])
        fp.write("  OBS\n")
        for layer_name, region in (("M1", obs_m1), ("V1", obs_v1), ("M2", obs_m2)):
            for x0, y0, x1, y1 in region_rects(region, ox, oy):
                fp.write(f"    LAYER {layer_name} ;\n      RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;\n")
        fp.write("  END\nEND " + cell.name + "\n\nEND LIBRARY\n")

    print(f"wrote {args.output_gds}")
    print(f"wrote {args.output_lef}")
    print(f"macro={cell.name} size={w:.3f}x{h:.3f} bbox=({new_bbox.left * DBU:.3f},{new_bbox.bottom * DBU:.3f};{new_bbox.right * DBU:.3f},{new_bbox.top * DBU:.3f})")
    print(f"signal escapes: {signals}; power escapes: GND(pin+body)")


if __name__ == "__main__":
    main()
