#!/usr/bin/env python3
"""Compose a clean mixed-signal core from verified digital and analog views.

The digital core comes from the qualified access-cell LibreLane streamout. The
analog hard macro is inserted as a non-overlapping fixed child in an enlarged
core area. This is an assembly artifact, not a replacement for top-level LVS
contract generation.
"""
from __future__ import annotations

import os
from pathlib import Path
import pya

root = Path(__file__).resolve().parents[3]
def path(name: str, default: str) -> Path:
    value = os.environ.get(name, default)
    p = Path(value)
    return p if p.is_absolute() else root / p

DIGITAL_GDS = path("TR1UM_DIGITAL_GDS", "flow/designs/tr1um_counter/runs/access-canonical-final/final/gds/tr1um_counter.gds")
ANALOG_GDS = path("TR1UM_ANALOG_GDS", "flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds")
OUT_GDS = path("TR1UM_MIXED_CORE_GDS", "flow/signoff/tr1um_mixed_counter_core.gds")
TOP_NAME = os.environ.get("TR1UM_MIXED_CORE_TOP", "tr1um_mixed_counter")
DIGITAL_TOP = os.environ.get("TR1UM_DIGITAL_TOP", "tr1um_counter")
ANALOG_TOP = os.environ.get("TR1UM_ANALOG_TOP", "CMC_S_NMOS_B_X1_Y1")
ANALOG_X_UM = float(os.environ.get("TR1UM_ANALOG_X_UM", "1000"))
ANALOG_Y_UM = float(os.environ.get("TR1UM_ANALOG_Y_UM", "1000"))

for required in (DIGITAL_GDS, ANALOG_GDS):
    if not required.is_file():
        raise SystemExit(f"missing input GDS: {required}")

out = pya.Layout.new()
digital_layout = pya.Layout.new()
digital_layout.read(str(DIGITAL_GDS))
analog_layout = pya.Layout.new()
analog_layout.read(str(ANALOG_GDS))

def get_top(layout: pya.Layout, name: str, label: str):
    cell = layout.cell(name)
    if cell is not None:
        return cell
    tops = list(layout.top_cells())
    if len(tops) == 1:
        return tops[0]
    raise SystemExit(f"missing {label} cell {name!r}; top cells={[c.name for c in tops]}")

digital = get_top(digital_layout, DIGITAL_TOP, "digital")
analog = get_top(analog_layout, ANALOG_TOP, "analog")
top = out.create_cell(TOP_NAME)
digital_copy = out.create_cell(f"{DIGITAL_TOP}_core")
digital_copy.copy_tree(digital)
analog_copy = out.create_cell(ANALOG_TOP)
analog_copy.copy_tree(analog)
top.insert(pya.CellInstArray(digital_copy.cell_index(), pya.Trans()))
top.insert(pya.CellInstArray(analog_copy.cell_index(), pya.Trans(pya.Trans.R0, pya.Point(round(ANALOG_X_UM / out.dbu), round(ANALOG_Y_UM / out.dbu)))))

out.write(str(OUT_GDS))
print(f"wrote {OUT_GDS}")
print(f"top={TOP_NAME} bbox={top.dbbox()} dbu={out.dbu}")
print(f"digital={DIGITAL_TOP} analog={ANALOG_TOP} analog_origin=({ANALOG_X_UM},{ANALOG_Y_UM})")
