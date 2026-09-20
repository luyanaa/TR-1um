* TR10-1 converted VCO stabilized post simulation
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/converted/rcx/vco.control.post.sp"
VDDSRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
VCTRLNSRC CTRLN_SRC 0 2.5
RCTRLN CTRLN_SRC P17 10
VCTRLPSRC CTRLP_SRC 0 2.5
RCTRLP CTRLP_SRC P22 10
XU OUT PWR PWR 0 0 P17 P22 VCO
.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12 trtol=7 itl4=10000
.tran 10n 100u uic
.meas tran T1 WHEN v(OUT)=2.5 RISE=10
.meas tran T2 WHEN v(OUT)=2.5 RISE=11
.meas tran PERIOD PARAM='T2-T1'
.meas tran FREQ PARAM='1/PERIOD'
.end
