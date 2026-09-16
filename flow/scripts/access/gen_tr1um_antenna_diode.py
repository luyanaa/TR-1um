#!/usr/bin/env python3
"""Generate the TR-1um N-diffusion antenna diode cell.

The cell is the minimum-size native ``diode_n`` PCell geometry: one CO
contact inside AN, with an M1 landing on the routed net.  The substrate is
implicit VSS in the TR-1um extraction contract, so no second routed pin is
needed.

Run this script with KLayout's Python runtime, for example::

    klayout -b -r flow/scripts/access/gen_tr1um_antenna_diode.py

The output directory can be overridden with ``--output-root``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pya


CELL_NAME = "DIODE_N_X1"
DBU = 0.001
DIFF_WIDTH = 6.0
DIFF_HEIGHT = 3.6
X0 = 10.8
PIN_X0 = X0 - 3.6
Y0 = 30.0
CONTACT = (X0 + 2.4, Y0 + 1.2, X0 + 3.6, Y0 + 2.4)

def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root / "flow/pdk_root/TR-1um/libs.ref/TR-1um_antenna",
    )
    args = parser.parse_args()

    gds_path = args.output_root / "gds" / f"{CELL_NAME}.gds"
    gds_path.parent.mkdir(parents=True, exist_ok=True)

    layout = pya.Layout()
    layout.dbu = DBU
    cell = layout.create_cell(CELL_NAME)

    def box(layer: int, datatype: int, x0: float, y0: float, x1: float, y1: float) -> None:
        cell.shapes(layout.layer(layer, datatype)).insert(
            pya.DBox(x0, y0, x1, y1)
        )

    # Keep the 3.6um-tall diode 10.8um from the source-cell-facing edge.
    # The right-shifted contact leaves room for the row's final V1 access.
    # The M1 landing extension gives the router access away from CO.
    box(11, 0, *CONTACT)  # CO
    box(3, 2, X0, Y0, X0 + DIFF_WIDTH, Y0 + DIFF_HEIGHT)  # AN
    box(13, 0, PIN_X0, Y0, X0 + DIFF_WIDTH, Y0 + DIFF_HEIGHT)  # M1 landing
    cell.shapes(layout.layer(48, 0)).insert(
        pya.Text("DIODE", pya.DTrans(X0 + 3.0, Y0 + 1.8))
    )

    layout.write(str(gds_path))
    print(f"wrote {gds_path}")


if __name__ == "__main__":
    main()
