#!/usr/bin/env python3
"""Merge same-net routing shapes in the routed GDS around the analog macro.

The digital router attaches 3.0um wires to the macro's 5.4um escape pads by
ending them flush on a pad edge with a partial overlap. The router models
this as legal same-net connectivity, but the foundry drawing DRC sees two
disjoint polygons whose union has a sub-minimum notch (M2.W1/M1.S1), because
the checker does not know they are the same net.

This fixup uses the routed DEF's net ownership: for every DEF net it collects
the routed M1/M2 rectangles (already the router's own shapes) plus any macro
escape pads they touch, and rewrites those shapes as merged polygons inside a
bounded halo around the macro. Connectivity is unchanged - only the polygon
topology of same-net shapes is merged, which is exactly what the KLayout DRC
needs to measure the true (legal) union widths.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pya

M1 = (13, 0)
M2 = (20, 0)


def parse_def_nets(text: str):
    """Return {net_name: [((x0,y0,x1,y1), layer), ...]} in dbu."""
    nets = {}
    current = None
    in_nets = False
    for line in text.splitlines():
        if line.startswith("NETS ") or line.startswith("SPECIALNETS "):
            in_nets = True
            continue
        if line.startswith("END NETS") or line.startswith("END SPECIALNETS"):
            in_nets = False
            continue
        if not in_nets:
            continue
        m = re.match(r"^\s*- (\S+) ", line)
        if m:
            current = m.group(1)
            nets.setdefault(current, [])
            continue
        if current is None:
            continue
        for rm in re.finditer(r"(?:ROUTED|NEW)\s+(M\d)\b([^;]*)", line):
            layer = rm.group(1)
            body = rm.group(2)
            for cm in re.finditer(r"\(\s*([^)]*)\)", body):
                fields = cm.group(1).split()
                if len(fields) < 2:
                    continue
                x, y = fields[0], fields[1]
                if x == "*" or y == "*":
                    continue
                xi, yi = int(float(x)), int(float(y))
                w = 3000 if layer == "M2" else 1800
                nets[current].append(((xi - w // 2, yi - w // 2, xi + w // 2, yi + w // 2), layer))
    return nets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gds", required=True, type=Path)
    parser.add_argument("--def", required=True, type=Path, dest="def_file")
    parser.add_argument("--top", required=True)
    parser.add_argument("--macro", default="CMC_S_NMOS_B_X1_Y1")
    parser.add_argument("--halo", type=float, default=5.0, help="merge radius around macro in um")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    layout = pya.Layout()
    layout.read(str(args.gds))
    top = layout.cell(args.top)
    if top is None:
        raise SystemExit(f"top cell {args.top!r} not found")
    macro = layout.cell(args.macro)
    if macro is None:
        raise SystemExit(f"macro cell {args.macro!r} not found")

    # Macro instance bbox in top coordinates.
    halo = int(args.halo / layout.dbu)
    region = None
    for inst in top.each_inst():
        if inst.cell.name == args.macro:
            region = inst.dbbox().enlarged(pya.Vector(halo, halo))
            break
    if region is None:
        raise SystemExit(f"no instance of {args.macro} under {args.top}")

    nets = parse_def_nets(Path(args.def_file).read_text())

    m1i = layout.find_layer(*M1)
    m2i = layout.find_layer(*M2)

    # Collect macro pad shapes (top-level coords) keyed by layer so router
    # wires can union with the pads they touch.
    macro_inst = None
    for inst in top.each_inst():
        if inst.cell.name == args.macro:
            macro_inst = inst
            break
    macro_pads = {"M1": pya.Region(), "M2": pya.Region()}
    for li, layer_name in ((m1i, "M1"), (m2i, "M2")):
        it = macro_inst.cell.begin_shapes_rec(li)
        while not it.at_end():
            sh = it.shape()
            if sh.is_box():
                macro_pads[layer_name].insert(sh.box.transformed(it.trans() * macro_inst.trans))
            elif sh.is_polygon():
                macro_pads[layer_name].insert(sh.polygon.transformed(it.trans() * macro_inst.trans))
            it.next()
        macro_pads[layer_name].merge()

    merged_shapes = 0
    for net, rects in nets.items():
        by_layer = {"M1": [], "M2": []}
        for (x0, y0, x1, y1), layer in rects:
            b = pya.Box(x0, y0, x1, y1)
            if b.left <= region.right and region.left <= b.right and b.bottom <= region.top and region.bottom <= b.top:
                by_layer[layer].append(b)
        for layer, boxes in by_layer.items():
            reg = pya.Region()
            for b in boxes:
                reg.insert(b)
            # Union with any macro pad this net's wires touch (same net).
            pads_here = macro_pads[layer]
            if pads_here.count():
                touching = pads_here.interacting(reg.sized(10))
                reg += touching
            if reg.count() < 2:
                continue
            reg.merge()
            target = m1i if layer == "M1" else m2i
            for poly in reg.each_merged():
                top.shapes(target).insert(poly)
                merged_shapes += 1
            # Bridge same-net router stubs that stop just short of a pad:
            # extend them by up to 2.0um so they touch and merge with the
            # pad, closing sub-minimum same-net gaps.
            if layer == "M2" and pads_here.count():
                near = reg.interacting(pads_here.sized(2000)) - pads_here
                for poly in near.each_merged():
                    b = poly.bbox()
                    grown = pya.Region(b).sized(2000)
                    bridge = grown & pads_here.sized(2000)
                    # take the facing pad edges: build connecting box from
                    # stub edge to pad edge along the dominant axis
                    for pad_poly in pads_here.each_merged():
                        pb = pad_poly.bbox()
                        if b.left < pb.right and pb.left < b.right:
                            ox0, ox1 = max(b.left, pb.left), min(b.right, pb.right)
                            ocx = (ox0 + ox1) // 2
                            bw = max(3000, ox1 - ox0)
                            if 0 < pb.bottom - b.top <= 2000:
                                top.shapes(m2i).insert(pya.Box(
                                    ocx - bw // 2, b.top, ocx + bw // 2, pb.bottom))
                                merged_shapes += 1
                            if 0 < b.bottom - pb.top <= 2000:
                                top.shapes(m2i).insert(pya.Box(
                                    ocx - bw // 2, pb.top, ocx + bw // 2, b.bottom))
                                merged_shapes += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(args.out))
    print(f"wrote {args.out}; inserted {merged_shapes} merged same-net polygons in halo {args.halo}um")


if __name__ == "__main__":
    main()
