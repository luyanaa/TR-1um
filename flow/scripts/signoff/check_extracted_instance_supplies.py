#!/usr/bin/env python3
"""Cross-check placed instances and their extracted top-level supply pins."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("placed_def", type=Path)
    parser.add_argument("extracted_spice", type=Path)
    parser.add_argument("top")
    args = parser.parse_args()

    def_text = args.placed_def.read_text()
    block = re.search(r"(?ms)^COMPONENTS\b.*?^END COMPONENTS\s*$", def_text)
    if not block:
        raise SystemExit("ERROR: missing COMPONENTS block")
    metal_ties = {"TIEHI", "TIELO"}
    placed_all = Counter(
        match.group(1)
        for match in re.finditer(r"(?m)^\s*-\s+\S+\s+(\S+)\b", block.group(0))
    )
    placed = Counter(
        {master: count for master, count in placed_all.items() if master.upper() not in metal_ties}
    )

    # Join ordinary SPICE continuation lines before selecting the top subckt.
    statements: list[str] = []
    for line in args.extracted_spice.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("+") and statements:
            statements[-1] += " " + stripped[1:].strip()
        elif stripped and not stripped.startswith("*"):
            statements.append(stripped)

    start = next(
        (i for i, line in enumerate(statements)
         if re.match(rf"(?i)^\.subckt\s+{re.escape(args.top)}(?:\s|$)", line)),
        None,
    )
    if start is None:
        raise SystemExit(f"ERROR: extracted netlist has no .SUBCKT {args.top}")

    header = statements[start].split()
    top_pins = [pin.upper() for pin in header[2:]]
    if top_pins.count("VDD") != 1 or top_pins.count("VSS") != 1:
        raise SystemExit(
            f"ERROR: extracted top pins are {header[2:]}, expected one VDD and one VSS"
        )

    extracted: Counter[str] = Counter()
    missing_supplies: list[str] = []
    for line in statements[start + 1:]:
        if re.match(rf"(?i)^\.ends(?:\s+{re.escape(args.top)})?(?:\s|$)", line):
            break
        if not line[:1].upper() == "X":
            continue
        words = line.split()
        if len(words) < 4:
            raise SystemExit(f"ERROR: malformed extracted instance: {line}")
        master = words[-1]
        if master.upper() in metal_ties:
            continue
        extracted[master] += 1
        if [word.upper() for word in words[-3:-1]] != ["VDD", "VSS"]:
            missing_supplies.append(line)
    else:
        raise SystemExit(f"ERROR: unterminated extracted .SUBCKT {args.top}")

    if placed != extracted:
        print(f"placed masters:   {dict(sorted(placed.items()))}")
        print(f"extracted masters: {dict(sorted(extracted.items()))}")
        raise SystemExit("ERROR: placed/extracted instance populations differ")
    if missing_supplies:
        for line in missing_supplies[:10]:
            print(f"missing-supply: {line}")
        raise SystemExit(
            f"ERROR: {len(missing_supplies)} extracted instances do not end in VDD VSS"
        )

    print(
        f"PASS: {sum(extracted.values())} extracted instances match the DEF and "
        "all connect to top-level VDD/VSS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
