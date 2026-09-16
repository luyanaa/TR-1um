#!/usr/bin/env python3
"""Stamp DEF top pins onto the matching GDS label layers for LVS/hierarchy."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pya


LABEL_LAYERS = {"M1": (48, 0), "M2": (49, 0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-gds", required=True, type=Path)
    parser.add_argument("--def", dest="def_file", required=True, type=Path)
    parser.add_argument("--top", required=True)
    parser.add_argument("--output-gds", required=True, type=Path)
    args = parser.parse_args()

    text = args.def_file.read_text()
    pins = re.search(r"(?ms)^PINS\b.*?^END PINS\s*$", text)
    if not pins:
        raise SystemExit("ERROR: DEF has no PINS block")

    parsed: list[tuple[str, str, int, int]] = []
    for match in re.finditer(
        # Do not use a regex word boundary after the pin name: `]` is a
        # non-word character, so a name such as data[0] was truncated to
        # data[0.  DEF separates the name from its body with whitespace.
        r"(?ms)^\s*-\s+(\S+)[ \t]+(.*?)(?=^\s*-\s+\S+[ \t]+|^END PINS\s*$)",
        pins.group(0),
    ):
        name, body = match.group(1), match.group(2)
        layer_match = re.search(r"\+\s+LAYER\s+(\S+)\b", body)
        place_match = re.search(
            r"\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", body
        )
        if not layer_match or not place_match:
            raise SystemExit(f"ERROR: pin {name} lacks one placed routing-layer port")
        layer = layer_match.group(1)
        if layer not in LABEL_LAYERS:
            raise SystemExit(f"ERROR: no LVS label-layer mapping for {name} on {layer}")
        parsed.append((name, layer, int(place_match.group(1)), int(place_match.group(2))))

    declared = re.search(r"(?m)^PINS\s+(\d+)\s*;", pins.group(0))
    if not declared or int(declared.group(1)) != len(parsed):
        raise SystemExit("ERROR: failed to parse every declared DEF pin")

    layout = pya.Layout()
    layout.read(str(args.input_gds))
    top = layout.cell(args.top)
    if top is None:
        raise SystemExit(f"ERROR: GDS has no top cell {args.top}")
    if abs(layout.dbu - 0.001) > 1e-12:
        raise SystemExit(f"ERROR: expected 0.001um GDS dbu, got {layout.dbu}")

    aliases = {"GND": "VSS", "VSS": "VSS", "VDD": "VDD", "VCC": "VDD"}
    for name, layer, x, y in parsed:
        label = aliases.get(name.upper(), name)
        layer_index = layout.layer(*LABEL_LAYERS[layer])
        top.shapes(layer_index).insert(pya.Text(label, pya.Trans(x, y)))
        print(f"label {label} on {layer} at ({x * layout.dbu:g}, {y * layout.dbu:g})um")

    args.output_gds.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(args.output_gds))
    print(f"wrote {args.output_gds}: {len(parsed)} top-level labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
