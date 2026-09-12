#!/usr/bin/env python3
"""Run the macro BEOL generator inside KLayout's pya runtime.

Usage from the LibreLane nix-shell:
  python3 flow/scripts/signoff/run_macro_beol_access.py \
    --input flow/align_macro/CMC_S_NMOS_B_X1_Y1.source.gds \
    --output-gds flow/align_macro/CMC_S_NMOS_B_X1_Y1.gds \
    --output-lef flow/align_macro/CMC_S_NMOS_B_X1_Y1.lef

The wrapper is intentionally checked in so reproduction does not depend on a
transient /tmp/run_gen_macro.py file.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-gds", required=True, type=Path)
    parser.add_argument("--output-lef", required=True, type=Path)
    parser.add_argument("--macro", default=None)
    args = parser.parse_args()

    generator = Path(__file__).with_name("gen_macro_beol_access.py")
    argv = [str(generator), "--input", str(args.input), "--output-gds", str(args.output_gds), "--output-lef", str(args.output_lef)]
    if args.macro:
        argv.extend(["--macro", args.macro])
    sys.argv = argv
    runpy.run_path(str(generator), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
