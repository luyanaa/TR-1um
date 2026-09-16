#!/usr/bin/env python3
from pathlib import Path
import argparse
import pya
parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

layout = pya.Layout()
layout.read(str(args.input))
top = layout.cell("tr1um_mixed_counter")
m2 = layout.layer(pya.LayerInfo(20, 0))


def erase_path(points):
    points = [(x, y) for x, y in points]
    for shape in list(top.shapes(m2).each()):
        if not shape.is_path() or shape.path.width != 3000:
            continue
        if [(point.x, point.y) for point in shape.path.each_point()] == points:
            top.shapes(m2).erase(shape)


# Remove stale copies when this post-streamout step is rerun.
old_bridge = [
    (67500, 3000),
    (24300, 3000),
    (24300, 386400),
    (261900, 386400),
    (261900, 271200),
    (283500, 271200),
    (283500, 252000),
    (306900, 252000),
    (306900, 282000),
    (310500, 282000),
]
erase_path(old_bridge)

# The router's ANA_DB jog enters the macro DB pin at an upstream-forbidden
# spacing. Replace the jog with an approach from below, preserving ANA_DB.
erase_path([(310500, 298400), (315900, 298400)])
erase_path([(310500, 298400), (310500, 305100)])

bridge = [
    (67500, 3000),
    (24300, 3000),
    (24300, 386400),
    (261900, 386400),
    (261900, 245000),
    (283500, 245000),
    (283500, 252000),
    (306900, 252000),
    (306900, 282000),
    (310500, 282000),
]
ana_db = [
    (310500, 305100),
    (315000, 305100),
    (315000, 298400),
]
for points in (bridge, ana_db):
    erase_path(points)

for points in (bridge, ana_db):
    top.shapes(m2).insert(
        pya.Path([pya.Point(x, y) for x, y in points], 3000)
    )

args.output.parent.mkdir(parents=True, exist_ok=True)
layout.write(str(args.output))
print(args.output)
