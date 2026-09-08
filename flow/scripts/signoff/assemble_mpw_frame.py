#!/usr/bin/env python3
"""Assemble a single MPW-framed TR-1um submission GDS.

The frame is copied from the supplied MPW frame library. The selected core
GDS is inserted as a child centered at the 2500 um frame origin. The resulting
single top cell has the required tr_1um_ prefix and the frame cell remains in
its hierarchy; this script does not modify source or run artifacts.
"""
from pathlib import Path
import os
import pya

FRAME_GDS = Path(os.environ["TR1UM_FRAME_GDS"])
CORE_GDS = Path(os.environ["TR1UM_CORE_GDS"])
OUT_GDS = Path(os.environ["TR1UM_FRAMED_GDS"])
TOP_NAME = os.environ.get("TR1UM_FRAMED_TOP", "tr_1um_counter")
CORE_NAME = os.environ.get("TR1UM_FRAMED_CORE", "tr1um_counter_core")
CORE_TOP = os.environ.get("TR1UM_CORE_TOP", "tr1um_counter")
layout = pya.Layout.new()
frame_layout = pya.Layout.new()
frame_layout.read(str(FRAME_GDS))
core_layout = pya.Layout.new()
core_layout.read(str(CORE_GDS))

frame = frame_layout.cell("OSS_FRAME")
if frame is None:
    raise RuntimeError("OSS_FRAME is absent from frame GDS")
core = core_layout.cell(CORE_TOP)
if core is None:
    tops = list(core_layout.top_cells())
    if len(tops) == 1:
        core = tops[0]
    else:
        raise RuntimeError(f"core top cell {CORE_TOP!r} is absent and top cells are {[c.name for c in tops]}")

top = layout.create_cell(TOP_NAME)
frame_copy = layout.create_cell("OSS_FRAME")
frame_copy.copy_tree(frame)
core_copy = layout.create_cell(CORE_NAME)
core_copy.copy_tree(core)

top.insert(pya.CellInstArray(frame_copy.cell_index(), pya.Trans()))
core_bbox = core.dbbox()
core_center = core_bbox.center()
top.insert(pya.CellInstArray(core_copy.cell_index(), pya.Trans(pya.Vector(round(-core_center.x / layout.dbu), round(-core_center.y / layout.dbu)))))

OUT_GDS.parent.mkdir(parents=True, exist_ok=True)
layout.write(str(OUT_GDS))
print(f"wrote {OUT_GDS}")
print(f"top={TOP_NAME} bbox={top.dbbox()} dbu={layout.dbu}")
print(f"frame=OSS_FRAME core={CORE_NAME} source_top={core.name}")
raise SystemExit(0)
