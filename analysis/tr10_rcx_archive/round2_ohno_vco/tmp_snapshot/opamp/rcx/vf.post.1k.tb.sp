* TR10-2 Shuntaro OPAMP voltage follower post
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/opamp/rcx/opamp.postlayout.sim.sp"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 11.8u
VSIG SIG 0 SIN(2.5 0.5 1000)
RSIG SIG INP 1
RFB OUT INN 1
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
CL OUT 0 100p
.options reltol=5e-3 abstol=1e-12 vntol=1e-6 gmin=1e-12 method=gear
.tran 5e-06 0.008
.meas tran VMAX MAX v(OUT) FROM=0.002 TO=0.0075
.meas tran VMIN MIN v(OUT) FROM=0.002 TO=0.0075
.meas tran VPP PARAM='VMAX-VMIN'
.meas tran IMAX MAX i(VDD_SRC) FROM=0.002 TO=0.0075
.end
