#!/usr/bin/env python3
"""Normalize ALIGN top-level macro names for hard-macro handoff."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pya


def main() -> None:
    gds_in = Path(os.environ["TR1UM_GDS_IN"])
    gds_out = Path(os.environ["TR1UM_GDS_OUT"])
    lef_in = Path(os.environ["TR1UM_LEF_IN"])
    lef_out = Path(os.environ["TR1UM_LEF_OUT"])
    desired = os.environ["TR1UM_MACRO_NAME"]

    layout = pya.Layout.new()
    layout.read(str(gds_in))
    top = layout.top_cell()
    old = top.name
    if old != desired:
        top.name = desired
    gds_out.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(gds_out))

    lef = lef_in.read_text(encoding="utf-8")
    if old != desired:
        lef = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", desired, lef)
    lef_out.parent.mkdir(parents=True, exist_ok=True)
    lef_out.write_text(lef, encoding="utf-8")
    print(f"Normalized ALIGN macro {old} -> {desired}")


if __name__ == "__main__":
    main()
