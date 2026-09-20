* Ohno OPAMP quantitative silicon-anchor experiment: op
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.sim.sp"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 1.18e-05
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
VBIASP INP 0 2.5
VBIASN INN 0 2.5
CL OUT 0 100p
.op
.print op v(P7) v(P2) v(P5) v(P8) v(P3) v(P6) i(VDD_SRC) i(IBIAS) i(XU.X$1) i(XU.X$34) i(XU.X$53) i(XU.X$77) i(XU.C$52)
.end
