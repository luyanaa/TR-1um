#!/usr/bin/env python3
"""Run the MPW structural pre-check inside KLayout's Python runtime.

The template pre-check uses Click for its command-line decorator, while the
KLayout runtime provides the authoritative ``pya`` bindings.  This small
adapter keeps the same structural checks without requiring Click in the
KLayout interpreter.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pya

FRAME_CELL_NAMES = {"OSS_FRAME", "OSS_FRAME_TEG"}
CHIP_SIZE_WIDTH = 2500.00
CHIP_SIZE_HEIGHT = 2500.00
EXPECTED_DBU = 0.001
EPS = 1e-6


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def same_float(a: float, b: float) -> bool:
    return abs(a - b) <= EPS


def main() -> None:
    layout_file = Path(globals().get("input", ""))
    expected_top_name = str(globals().get("top_cell", ""))
    if not layout_file.is_file():
        fail(f"missing layout '{layout_file}'.")
    if not expected_top_name:
        fail("top_cell was not supplied.")

    layout = pya.Layout()
    layout.read(str(layout_file))
    top_cells = list(layout.top_cells())
    if not top_cells:
        fail(f"No top-level cell found in '{layout_file}'.")
    if len(top_cells) != 1:
        fail(
            f"More than one top-level cell found in '{layout_file}': "
            + ", ".join(cell.name for cell in top_cells)
        )
    top_cell = top_cells[0]

    if top_cell.name != expected_top_name:
        fail(
            f"Top-level cell name '{top_cell.name}' does not match expected "
            f"name '{expected_top_name}'."
        )
    print(f"OK: Top-level cell name '{expected_top_name}' matches.")

    if not same_float(layout.dbu, EXPECTED_DBU):
        fail(f"Database unit (dbu) is {layout.dbu:.12g}, but expected {EXPECTED_DBU:.12g}.")
    print(f"OK: Database unit (dbu) is {layout.dbu:.3f} um.")

    bbox = top_cell.dbbox()
    expected_p1 = pya.DPoint(-CHIP_SIZE_WIDTH / 2.0, -CHIP_SIZE_HEIGHT / 2.0)
    expected_p2 = pya.DPoint(CHIP_SIZE_WIDTH / 2.0, CHIP_SIZE_HEIGHT / 2.0)
    if (
        not same_float(bbox.p1.x, expected_p1.x)
        or not same_float(bbox.p1.y, expected_p1.y)
        or not same_float(bbox.p2.x, expected_p2.x)
        or not same_float(bbox.p2.y, expected_p2.y)
    ):
        fail(
            "Layout area does not match expected die area: "
            f"expected ({expected_p1.x:.2f},{expected_p1.y:.2f})"
            f"({expected_p2.x:.2f},{expected_p2.y:.2f}), "
            f"got ({bbox.p1.x:.2f},{bbox.p1.y:.2f})"
            f"({bbox.p2.x:.2f},{bbox.p2.y:.2f})."
        )
    print(
        "OK: Layout area matches expected die area "
        f"({expected_p1.x:.2f},{expected_p1.y:.2f})"
        f"({expected_p2.x:.2f},{expected_p2.y:.2f})."
    )

    if not any(cell.name in FRAME_CELL_NAMES for cell in layout.each_cell()):
        fail(
            f"No required OpenSUSI frame/TEG cell found under top cell '{top_cell.name}'. "
            f"Expected one of: {', '.join(sorted(FRAME_CELL_NAMES))}"
        )
    print(f"OK: Design '{top_cell.name}' passed pre-check with required OpenSUSI frame/TEG cell.")


main()
