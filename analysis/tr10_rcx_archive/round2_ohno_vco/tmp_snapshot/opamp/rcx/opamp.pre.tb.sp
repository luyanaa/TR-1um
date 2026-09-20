* TR10-2 Shuntaro OPAMP pre AC simulation
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/opamp/rcx/opamp.devices.sp"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 11.8u
VINP_SRC INP_SRC 0 DC 2.5 AC 1
RINP INP_SRC INP 1
VINN_SRC INN_SRC 0 DC 2.5 AC 0
RINN INN_SRC INN 1
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
CL OUT 0 100p
.options reltol=1e-2 abstol=1e-12 vntol=1e-6 gmin=1e-12 method=gear
.save all
.ac dec 20 1e3 1e8
.meas ac GAIN1K FIND vm(OUT) AT=1e3
.meas ac UGF WHEN vm(OUT)=1 CROSS=1
.meas ac PHASE_2M FIND vp(OUT) AT=2.23487e6
.end
