#!/usr/bin/env python3
"""Add deterministic empty-row-channel M1 power buses to a placed core DEF."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def lef_widths(path: Path) -> dict[str, int]:
    """Read macro widths from LEF and return integer DEF database units."""
    text = path.read_text()
    widths: dict[str, int] = {}
    for match in re.finditer(
        r"(?ms)^MACRO\s+(\S+)\s*$.*?^\s*SIZE\s+([0-9.]+)\s+BY\s+[0-9.]+\s*;",
        text,
    ):
        widths[match.group(1)] = round(float(match.group(2)) * 1000)
    if not widths:
        raise SystemExit(f"no MACRO widths found in {path}")
    return widths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_def", type=Path)
    parser.add_argument("output_def", type=Path)
    parser.add_argument("cell_lef", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    channel_config = {
        "gnd_row_offset_um": -7.0,
        "vdd_row_offset_um": 68.0,
        "min_row_pitch_um": 140.0,
        "vdd_trunk_inset_um": 60.0,
    }
    if args.config:
        channel_config.update(json.loads(args.config.read_text()))
    gnd_row_offset = round(float(channel_config["gnd_row_offset_um"]) * 1000)
    vdd_row_offset = round(float(channel_config["vdd_row_offset_um"]) * 1000)
    min_row_pitch = round(float(channel_config["min_row_pitch_um"]) * 1000)
    vdd_trunk_inset = round(float(channel_config["vdd_trunk_inset_um"]) * 1000)
    widths = lef_widths(args.cell_lef)
    text = args.input_def.read_text()

    die_match = re.search(
        r"(?m)^DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*"
        r"\(\s*(\d+)\s+(\d+)\s*\)\s*;",
        text,
    )
    if not die_match:
        raise SystemExit("missing rectangular DIEAREA")
    die_x0, die_y0, die_x1, die_y1 = map(int, die_match.groups())

    pin_block = re.search(r"(?ms)^PINS\b.*?^END PINS\s*$", text)
    if not pin_block:
        raise SystemExit("missing PINS block")

    def pin_location(name: str) -> tuple[int, int]:
        match = re.search(
            rf"(?ms)^\s*-\s+{re.escape(name)}\b.*?"
            r"\+\s+(?:PLACED|FIXED)\s+\(\s*(\d+)\s+(\d+)\s*\)",
            pin_block.group(0),
        )
        if not match:
            raise SystemExit(f"missing placed top-level pin {name}")
        return int(match.group(1)), int(match.group(2))

    gnd_pin_x, gnd_pin_y = pin_location("GND")
    vdd_pin_x, vdd_pin_y = pin_location("VDD")

    component_block = re.search(r"(?ms)^COMPONENTS\b.*?^END COMPONENTS\s*$", text)
    if not component_block:
        raise SystemExit("missing COMPONENTS block")
    rows: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
    for line in component_block.group(0).splitlines():
        match = re.search(
            r"^\s*-\s+(\S+)\s+(\S+).*\+\s+(?:FIXED|PLACED)\s+"
            r"\(\s*(\d+)\s+(\d+)\s*\)\s+(\S+)",
            line,
        )
        if match:
            master = match.group(2)
            x, y, orient = int(match.group(3)), int(match.group(4)), match.group(5)
            if orient != "N":
                raise SystemExit(f"side-rail prototype requires N orientation, found {orient}")
            if master not in widths:
                raise SystemExit(f"cell {master} is absent from {args.cell_lef}")
            rows[y].append((x, widths[master], master))
    if not rows:
        raise SystemExit("no placed component rows found")

    old_special = re.search(r"(?ms)^SPECIALNETS\b.*?^END SPECIALNETS\s*$", text)
    if not old_special:
        raise SystemExit("missing SPECIALNETS block")

    # All values are DEF database units (1 nm). The trunks live in empty side
    # channels. Opposite-supply row rails stop before reaching the other trunk.
    # Keep the left trunk one M2 routing pitch farther from the core. This
    # preserves cell/tap clearance and avoids a KLayout-only 1.2um M1 gap to
    # west-pin signal escapes (the drawing rule requires 1.4um).
    gnd_x = die_x0 + 54_000
    vdd_x = die_x1 - vdd_trunk_inset
    # Native M1 minimum width. A 3.4um strap intrudes 0.8um farther into the
    # source cells and reduces a legal 1.4um internal gap to 0.6um.
    width = 1_800
    # The source labels are at (6.3, 1.3) for GND and (6.3, 56.3) for VDD.
    # Escape left by 5um, outside the cell boundary, then rise/fall to buses
    # in the deliberately empty physical rows.
    gnd_rows = [y + gnd_row_offset for y in sorted(rows)]
    vdd_rows = [y + vdd_row_offset for y in sorted(rows)]
    half = width // 2

    occupied_y = sorted(rows)
    if gnd_rows[0] - half <= die_y0 or vdd_rows[-1] + half >= die_y1:
        raise SystemExit("power row channels do not fit inside DIEAREA")
    if any(right - left < min_row_pitch for left, right in zip(occupied_y, occupied_y[1:])):
        raise SystemExit(
            f"occupied rows are closer than configured {min_row_pitch / 1000:g}um minimum"
        )
    for row_y, cells in rows.items():
        ordered = sorted(cells)
        if ordered[0][0] - 5_000 <= gnd_x + half:
            raise SystemExit(f"no left trunk/tap clearance in row {row_y}")
        if ordered[-1][0] + ordered[-1][1] >= vdd_x - half:
            raise SystemExit(f"no right trunk clearance in row {row_y}")
        for (left_x, left_w, _), (right_x, _, _) in zip(ordered, ordered[1:]):
            if right_x - (left_x + left_w) < 10_000:
                raise SystemExit(
                    f"cell gap below qualified 10um minimum in row {row_y}: "
                    f"{left_x + left_w}..{right_x}"
                )

    gnd_landing_y = max(die_y0 + 30_000, gnd_pin_y)
    vdd_landing_y = max(die_y0 + 45_000, vdd_pin_y)
    if vdd_landing_y + half >= gnd_rows[0]:
        raise SystemExit("top-pin landing corridors collide with the first row channel")

    gnd_routes = [
        f"      + ROUTED M2 3000 + SHAPE STRIPE ( {gnd_pin_x} {gnd_pin_y} ) ( {gnd_pin_x} {gnd_landing_y} )",
        f"      NEW M1 0 + SHAPE STRIPE ( {gnd_pin_x} {gnd_landing_y} ) M1M2_V1",
        f"      NEW M1 {width} + SHAPE STRIPE ( {gnd_x-half} {gnd_landing_y} ) ( {gnd_pin_x+half} {gnd_landing_y} )",
        f"      NEW M1 {width} + SHAPE STRIPE ( {gnd_x} {gnd_landing_y-half} ) ( {gnd_x} {gnd_rows[-1]+half} )",
    ]
    for row_y, y in zip(sorted(rows), gnd_rows):
        cells = sorted(rows[row_y])
        taps = [x - 5_000 for x, _, _ in cells]
        gnd_routes.append(f"      NEW M1 {width} + SHAPE STRIPE ( {gnd_x-half} {y} ) ( {taps[-1]+half} {y} )")
        for (x, _, _), tap_x in zip(cells, taps):
            gnd_routes.append(
                f"      NEW M1 {width} + SHAPE STRIPE ( {tap_x} {y-half} ) ( {tap_x} {row_y+1_300+half} )"
            )
            gnd_routes.append(
                f"      NEW M1 {width} + SHAPE FOLLOWPIN ( {tap_x-half} {row_y+1_300} ) ( {x+6_300+half} {row_y+1_300} )"
            )
    gnd_routes[-1] += " ;"

    vdd_routes = [
        f"      + ROUTED M2 3000 + SHAPE STRIPE ( {vdd_pin_x} {vdd_pin_y} ) ( {vdd_pin_x} {vdd_landing_y} )",
        f"      NEW M1 0 + SHAPE STRIPE ( {vdd_pin_x} {vdd_landing_y} ) M1M2_V1",
        f"      NEW M1 {width} + SHAPE STRIPE ( {vdd_pin_x-half} {vdd_landing_y} ) ( {vdd_x+half} {vdd_landing_y} )",
        f"      NEW M1 {width} + SHAPE STRIPE ( {vdd_x} {vdd_landing_y-half} ) ( {vdd_x} {vdd_rows[-1]+half} )",
    ]
    for row_y, y in zip(sorted(rows), vdd_rows):
        cells = sorted(rows[row_y])
        taps = [x - 5_000 for x, _, _ in cells]
        vdd_routes.append(f"      NEW M1 {width} + SHAPE STRIPE ( {taps[0]-half} {y} ) ( {vdd_x+half} {y} )")
        for (x, _, _), tap_x in zip(cells, taps):
            vdd_routes.append(
                f"      NEW M1 {width} + SHAPE STRIPE ( {tap_x} {row_y+56_300-half} ) ( {tap_x} {y+half} )"
            )
            vdd_routes.append(
                f"      NEW M1 {width} + SHAPE FOLLOWPIN ( {tap_x-half} {row_y+56_300} ) ( {x+6_300+half} {row_y+56_300} )"
            )
    vdd_routes[-1] += " ;"

    replacement = "\n".join(
        [
            "SPECIALNETS 2 ;",
            "    - GND ( PIN GND ) ( * GND ) + USE GROUND",
            *gnd_routes,
            "    - VDD ( PIN VDD ) ( * VDD ) + USE POWER",
            *vdd_routes,
            "END SPECIALNETS",
        ]
    )
    result = text[: old_special.start()] + replacement + text[old_special.end() :]
    args.output_def.parent.mkdir(parents=True, exist_ok=True)
    args.output_def.write_text(result)
    print(f"wrote {args.output_def}: {len(rows)} rows, channel buses, left GND trunk, right VDD trunk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
