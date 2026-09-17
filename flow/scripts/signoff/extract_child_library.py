#!/usr/bin/env python3
"""Extract child-cell definitions from a known-good hierarchical GDS."""

import argparse
import pya

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("top")
parser.add_argument("output")
args = parser.parse_args()
layout = pya.Layout()
layout.read(args.source)
top = layout.cell(args.top)
if top is None:
    raise SystemExit(f"missing top {args.top}")
layout.delete_cell(top.cell_index())
layout.write(args.output)
