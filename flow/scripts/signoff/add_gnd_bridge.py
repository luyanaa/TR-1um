#!/usr/bin/env python3
from pathlib import Path
import argparse
import pya
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
l=pya.Layout();l.read(str(a.input)); t=l.cell('tr1um_mixed_counter'); m2=l.layer(pya.LayerInfo(20,0))
pts=[
    pya.Point(67500, 3000),
    pya.Point(24300, 3000),
    pya.Point(24300, 386400),
    pya.Point(261900, 386400),
    pya.Point(261900, 271200),
    pya.Point(283500, 271200),
    pya.Point(283500, 252000),
    pya.Point(306900, 252000),
    pya.Point(306900, 282000),
    pya.Point(310500, 282000),
]
t.shapes(m2).insert(pya.Path(pts,3000));a.output.parent.mkdir(parents=True,exist_ok=True);l.write(str(a.output));print(a.output)
