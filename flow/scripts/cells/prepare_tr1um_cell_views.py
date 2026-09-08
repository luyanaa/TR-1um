#!/usr/bin/env python3
"""Build flow-only TR-1um cell views from immutable STDLIB GDS.

The STDLIB and openIP62 trees are source-of-truth inputs and are never edited.
The generated `flow_gds` directory is a derived compatibility view used by
the LibreLane PDK package. Translation is an origin normalization only; no
layer, polygon, device, or pin geometry is changed relative to the source.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import pya

SOURCE = Path(os.environ.get("TR1UM_STDLIB_SOURCE_GDS", Path(__file__).resolve().parents[3] / "STDLIB/LogicCells/gds"))
OUT_DIR = Path(os.environ.get("TR1UM_FLOW_CELL_GDS_DIR", Path(__file__).resolve().parents[3] / "flow/pdk_root/TR-1um/libs.ref/TR-1um_stdcell/flow_gds"))
SHIFT = pya.Trans(pya.Vector(6300, 1300))  # +6.3um, +1.3um; 1nm dbu
SKIP = {"RR$1", "RS", "TOP"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.gds"):
        old.unlink()

    count = 0
    for source in sorted(SOURCE.glob("*.gds")):
        name = source.stem
        if name in SKIP:
            continue
        layout = pya.Layout.new()
        layout.read(str(source))
        top = layout.top_cell()
        top.transform(SHIFT)
        layout.write(str(OUT_DIR / source.name))
        count += 1

    print(f"prepared {count} flow-only cell GDS views in {OUT_DIR}")


if __name__ == "__main__":
    main()
