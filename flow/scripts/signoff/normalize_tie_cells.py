#!/usr/bin/env python3
"""Replace placeholder TR-1um tie-cell drawings with supply-connected metal."""

from __future__ import annotations

import argparse
from pathlib import Path

import pya


def replace_tie(layout: pya.Layout, name: str, high: bool) -> bool:
    cell = layout.cell(name)
    if cell is None:
        return False
    for layer_index in layout.layer_indices():
        cell.shapes(layer_index).clear()
    m1 = layout.layer(13, 0)
    # Retain routable landings for both supplies.  The selected output is an
    # ordinary M1 pin joined to its supply; the opposite landing stays
    # isolated so the standard power-connection machinery can contact it.
    cell.shapes(m1).insert(pya.Box(-1300, -1500, 9300, 2200))
    cell.shapes(m1).insert(pya.Box(-1300, 60600, 9300, 62600))
    if high:
        cell.shapes(m1).insert(pya.Box(2500, 45500, 5500, 62600))
    else:
        cell.shapes(m1).insert(pya.Box(2500, -1500, 5500, 17100))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    layout = pya.Layout()
    layout.read(str(args.input))
    if abs(layout.dbu - 0.001) > 1e-12:
        raise SystemExit(f"expected 0.001um GDS dbu, got {layout.dbu}")
    changed = [name for name, high in (("TIELO", False), ("TIEHI", True))
               if replace_tie(layout, name, high)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(args.output))
    print(f"normalized tie-cell physical views: {', '.join(changed) if changed else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
