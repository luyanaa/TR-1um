* TR10-2 OPAMP DC diagnostic
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/opamp/rcx/opamp.devices.sp"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 11.8u
VINP_SRC INP_SRC 0 DC 2.5
RINP INP_SRC INP 1
VINN_SRC INN_SRC 0 DC 2.5
RINN INN_SRC INN 1
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
CL OUT 0 100p
.options reltol=1e-3 abstol=1e-14 vntol=1e-8 gmin=1e-12 rshunt=1e-12 method=gear
.op
.print op v(OUT) v(PWR) v(BIAS) v(INP) v(INN) v(XU.P1) v(XU.P2) v(XU.P3) v(XU.P4) v(XU.P5) v(XU.P6) v(XU.P7) v(XU.P8) v(XU.P9) v(XU.P10) v(XU.P11) v(XU.P12)
.end
