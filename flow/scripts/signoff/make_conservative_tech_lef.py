#!/usr/bin/env python3
"""Create a run-local TR-1um routing tech LEF with a small M2 safety margin."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_lef", type=Path)
    parser.add_argument("output_lef", type=Path)
    args = parser.parse_args()

    text = args.input_lef.read_text()
    pattern = re.compile(
        r"(?ms)(^LAYER\s+M2\s*$.*?^\s*TYPE\s+ROUTING\s*;.*?)"
        r"(\bSPACING\s+)2\.0(\s*;)"
    )
    result, count = pattern.subn(r"\g<1>\g<2>2.1\g<3>", text, count=1)
    if count != 1:
        raise SystemExit("expected exactly one 2.0um M2 routing spacing rule")
    args.output_lef.parent.mkdir(parents=True, exist_ok=True)
    args.output_lef.write_text(result)
    print(f"wrote {args.output_lef}: route-only M2 spacing 2.1um")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
