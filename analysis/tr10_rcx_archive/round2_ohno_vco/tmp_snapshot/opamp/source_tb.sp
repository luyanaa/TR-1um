* TR10-2 ShuntaroOhno source-level smoke deck
.include /Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models
.include /tmp/TR10-2/member_project/OPAMP/ShuntaroOhno/xschem/simulation/opamp.spice
VDD vdd 0 5
VINP vinp 0 DC 2.5 AC 1
VINN vinn 0 DC 2.5
VBIAS ib 0 3.5
CL out 0 100p
XU vinp vinn ib out vdd 0 opamp
.op
.ac dec 10 1e3 1e8
.print ac vdb(out) vp(out)
.end
