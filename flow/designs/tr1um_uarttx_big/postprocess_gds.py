#!/usr/bin/env python3
"""Join the UART standard-cell PMOS wells after placement/streamout."""

from __future__ import annotations

import argparse
from pathlib import Path

import pya


WN = (140, 0)
MIN_WELL_WIDTH = 8_000  # 8um at the required 0.001um GDS dbu
CELL_CLEARANCE = 12_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top", required=True)
    args = parser.parse_args()

    layout = pya.Layout()
    layout.read(str(args.input))
    if abs(layout.dbu - 0.001) > 1e-12:
        raise SystemExit(f"expected 0.001um GDS dbu, got {layout.dbu}")
    top = layout.cell(args.top)
    if top is None:
        raise SystemExit(f"input GDS has no top cell {args.top}")
    wn_index = layout.layer(*WN)

    # Each qualified access cell has one rectangular PMOS well band. Group
    # transformed bands by row, then span each row and join the rows with a
    # left-side 8um well spine outside all cell active regions.
    well_boxes: list[pya.Box] = []
    for instance in top.each_inst():
        region = pya.Region()
        iterator = instance.cell.begin_shapes_rec(wn_index)
        while not iterator.at_end():
            shape = iterator.shape()
            transform = iterator.trans() * instance.trans
            if shape.is_box():
                region.insert(shape.box.transformed(transform))
            elif shape.is_polygon():
                region.insert(shape.polygon.transformed(transform))
            iterator.next()
        if region.is_empty():
            continue
        region.merge()
        box = region.bbox()
        if region.count() != 1 or region.area() != int(box.area()):
            raise SystemExit(
                f"refusing to bridge non-rectangular WN in {instance.cell.name}"
            )
        well_boxes.append(box)

    if not well_boxes:
        raise SystemExit("no placed standard-cell WN shapes found")

    # Most cells have the same WN vertical interval, but tie cells legitimately
    # extend their well farther down while overlapping the row's common WN
    # band. Group by vertical overlap and bridge only the intersection. This
    # joins the wells without expanding the ordinary cells' well toward AP.
    rows: list[tuple[int, int, list[pya.Box]]] = []
    for box in sorted(well_boxes, key=lambda item: (item.bottom, item.top)):
        for index, (bottom, top_y, boxes) in enumerate(rows):
            overlap_bottom = max(bottom, box.bottom)
            overlap_top = min(top_y, box.top)
            if overlap_bottom < overlap_top:
                rows[index] = (overlap_bottom, overlap_top, [*boxes, box])
                break
        else:
            rows.append((box.bottom, box.top, [box]))

    if any(len(boxes) < 2 for _, _, boxes in rows):
        raise SystemExit("refusing unexpected row containing fewer than two WN cells")

    leftmost = min(box.left for _, _, boxes in rows for box in boxes)
    spine_right = leftmost - CELL_CLEARANCE
    spine_left = spine_right - MIN_WELL_WIDTH
    if spine_left <= top.bbox().left:
        raise SystemExit("not enough left margin for the common WN spine")

    added = pya.Region()
    row_bottom = min(bottom for bottom, _, _ in rows)
    row_top = max(top_y for _, top_y, _ in rows)
    added.insert(pya.Box(spine_left, row_bottom, spine_right, row_top))
    for bottom, top_y, boxes in sorted(rows):
        rightmost = max(box.right for box in boxes)
        added.insert(pya.Box(spine_left, bottom, rightmost, top_y))
    added.merge()
    for polygon in added.each_merged():
        top.shapes(wn_index).insert(polygon)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(args.output))
    print(
        f"joined {sum(len(boxes) for _, _, boxes in rows)} cell wells across {len(rows)} rows "
        f"into one WN network in {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
