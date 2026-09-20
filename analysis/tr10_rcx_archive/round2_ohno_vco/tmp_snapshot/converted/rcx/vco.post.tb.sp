* TR10-1 converted VCO post simulation
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/converted/rcx/vco.postlayout.sp"
VDD PWR 0 5
XU OUT PWR PWR 0 0 VCO
.options reltol=1e-3 abstol=1e-12 vntol=1e-6
.tran 1u 5m uic
.meas tran T1 WHEN v(OUT)=2.5 RISE=20
.meas tran T2 WHEN v(OUT)=2.5 RISE=21
.meas tran PERIOD PARAM='T2-T1'
.meas tran FREQ PARAM='1/PERIOD'
.end
