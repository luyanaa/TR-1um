#!/usr/bin/env python3
"""Build conservative routing obstructions for the FEOL access cells."""

from __future__ import annotations

import argparse
from pathlib import Path


EXTRA_OBS = {
    # Foundry drawing-DRC correlation found gate edges not fully represented
    # by the generated V1-only FEOL abstraction. Block both routing metals at
    # the two safe Steiner-via corridors, and V1 at NAND2's left gate edge.
    "NAND2": [("V1", 4.0, 10.0, 9.0, 36.0)],
    "NAND3": [("M1", 25.0, 25.0, 31.0, 34.0), ("M2", 25.0, 25.0, 31.0, 34.0)],
    "NAND4": [
        ("M1", 5.0, 31.0, 12.0, 39.0), ("M2", 5.0, 31.0, 12.0, 39.0),
        ("V1", 4.0, 20.0, 11.0, 29.0),
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_lef", type=Path)
    parser.add_argument("output_lef", type=Path)
    args = parser.parse_args()
    lines = args.input_lef.read_text().splitlines()
    output: list[str] = []
    power_rects: list[str] = []
    pin = ""
    layer = ""
    in_obs = False
    macro = ""
    macro_width = 0.0
    macro_height = 0.0

    for line in lines:
        words = line.strip().rstrip(";").split()
        if len(words) >= 2 and words[0] == "MACRO":
            macro = words[1]
            power_rects = []
            macro_width = 0.0
            macro_height = 0.0
        elif len(words) >= 4 and words[0] == "SIZE" and words[2] == "BY":
            macro_width = float(words[1])
            macro_height = float(words[3])
        if len(words) >= 2 and words[0] == "PIN":
            pin = words[1]
            layer = ""
        elif pin and len(words) >= 2 and words[0] == "LAYER":
            layer = words[1]
        elif pin in {"VDD", "GND"} and layer == "M1" and words and words[0] == "RECT":
            power_rects.append("      " + line.strip())
        elif pin and len(words) >= 2 and words[0] == "END" and words[1] == pin:
            pin = ""
            layer = ""

        if words and words[0] == "OBS":
            in_obs = True
        if in_obs and words == ["END"]:
            if power_rects:
                output.append("    LAYER M1 ;")
                output.extend(power_rects)
            for obs_layer, x0, y0, x1, y1 in EXTRA_OBS.get(macro, []):
                output.append(f"    LAYER {obs_layer} ;")
                output.append(f"      RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;")
            in_obs = False
        output.append(line)

    args.output_lef.write_text("\n".join(output) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
