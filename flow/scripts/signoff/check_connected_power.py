#!/usr/bin/env python3
"""Verify that every labelled TR-1um supply shape is physically connected."""

from __future__ import annotations

import argparse
from collections import defaultdict

import pya

M1 = (13, 0)
V1 = (19, 0)
M2 = (20, 0)
M1_LABEL = (48, 0)
M2_LABEL = (49, 0)
SUPPLY_GROUPS = {"ground": {"GND", "VSS"}, "power": {"VDD", "VCC"}}


def point_in_polygon(poly: pya.Polygon, point: pya.Point) -> bool:
    points = list(poly.each_point_hull())
    if not points or not poly.bbox().contains(point):
        return False
    inside = False
    for a, b in zip(points, points[1:] + points[:1]):
        cross = (point.x - a.x) * (b.y - a.y) - (point.y - a.y) * (b.x - a.x)
        if cross == 0 and min(a.x, b.x) <= point.x <= max(a.x, b.x) and min(a.y, b.y) <= point.y <= max(a.y, b.y):
            return True
        if (a.y > point.y) != (b.y > point.y):
            edge_x = a.x + (b.x - a.x) * (point.y - a.y) / (b.y - a.y)
            if point.x < edge_x:
                inside = not inside
    return inside


def region(cell: pya.Cell, layer_index: int) -> pya.Region:
    result = pya.Region()
    if layer_index < 0:
        return result
    for shape in cell.shapes(layer_index):
        if shape.is_box():
            result.insert(shape.box)
        elif shape.is_polygon():
            result.insert(shape.polygon)
        elif shape.is_path():
            result.insert(shape.path.polygon())
    result.merge()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gds")
    parser.add_argument("top")
    args = parser.parse_args()

    layout = pya.Layout()
    layout.read(args.gds)
    top = layout.cell(args.top)
    if top is None:
        raise SystemExit(f"ERROR: missing top cell {args.top}")
    top.flatten(True)

    specs = (M1, V1, M2, M1_LABEL, M2_LABEL)
    indices = {spec: layout.find_layer(*spec) for spec in specs}
    m1 = list(region(top, indices[M1]).each_merged())
    m2 = list(region(top, indices[M2]).each_merged())
    vias = list(region(top, indices[V1]).each_merged())
    conductors = m1 + m2
    parent = list(range(len(conductors)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for via in vias:
        point = via.bbox().center()
        hits = [index for index, poly in enumerate(conductors) if point_in_polygon(poly, point)]
        for hit in hits[1:]:
            union(hits[0], hit)

    label_roots: dict[str, set[int]] = defaultdict(set)
    label_counts: dict[str, int] = defaultdict(int)
    missing: list[tuple[str, float, float]] = []
    for spec, offset, polygons in (
        (M1_LABEL, 0, m1),
        (M2_LABEL, len(m1), m2),
    ):
        layer_index = indices[spec]
        if layer_index < 0:
            continue
        for shape in top.shapes(layer_index):
            if not shape.is_text():
                continue
            name = shape.text.string.strip().upper()
            if name not in {alias for aliases in SUPPLY_GROUPS.values() for alias in aliases}:
                continue
            point = pya.Point(shape.text.x, shape.text.y)
            hits = [offset + index for index, poly in enumerate(polygons) if point_in_polygon(poly, point)]
            if hits:
                label_roots[name].add(find(hits[0]))
                label_counts[name] += 1
            else:
                missing.append((name, point.x * layout.dbu, point.y * layout.dbu))

    print(
        f"top={args.top} dbu={layout.dbu} M1_components={len(m1)} "
        f"M2_components={len(m2)} V1_shapes={len(vias)}"
    )
    failures: list[str] = []
    group_roots: dict[str, set[int]] = {}
    for group, aliases in SUPPLY_GROUPS.items():
        roots = {find(root) for alias in aliases for root in label_roots[alias]}
        group_roots[group] = roots
        count = sum(label_counts[alias] for alias in aliases)
        print(f"{group}: labels={count} distinct_conductive_components={len(roots)}")
        if count == 0:
            failures.append(f"no {group} labels found")
        elif len(roots) != 1:
            failures.append(f"{group} labels occupy {len(roots)} conductive components")

    if missing:
        failures.append(f"{len(missing)} power labels are not on M1/M2 metal")
        for name, x, y in missing[:10]:
            print(f"missing-metal: {name} at ({x:.3f},{y:.3f})")
    if group_roots["ground"] & group_roots["power"]:
        failures.append("power and ground are shorted")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("PASS: every labelled power terminal is connected to its supply network")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
