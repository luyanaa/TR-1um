* TR10-1 converted VCO pre controlled simulation
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/converted/rcx/vco.control.devices.sp"
VDD PWR 0 5
VCTRLN P17 0 2.5
VCTRLP P22 0 2.5
XU OUT PWR PWR 0 0 P17 P22 VCO
.options reltol=1e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-12 rshunt=1e12
.ic V(P2)=0 V(P3)=5 V(P4)=0 V(P5)=5 V(P6)=0 V(P7)=5 V(P8)=0 V(P18)=0 V(OUT)=0
.tran 1u 5m uic
.meas tran T1 WHEN v(OUT)=2.5 RISE=10
.meas tran T2 WHEN v(OUT)=2.5 RISE=11
.meas tran PERIOD PARAM='T2-T1'
.meas tran FREQ PARAM='1/PERIOD'
.end
