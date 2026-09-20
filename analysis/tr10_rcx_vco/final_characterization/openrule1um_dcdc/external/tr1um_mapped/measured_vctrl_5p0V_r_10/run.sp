* TR10-1 DCDC exact source topology with external measured clock.
* Model set: tr1um_mapped
.include "/Users/yanlu/Documents/TR-1um/flow/char/fixed_models.sp"
.option savecurrents
VIN_SRC vin 0 12
VDD_SRC VDD 0 5
VCLK net2 0 PULSE(0 5 0 2.96413377385e-07 2.96413377385e-07 1.45242554919e-05 2.96413377385e-05)
XM1 vin net2 net1 0 NMOS L=1u W=40u m=1
L1 net1 vout 100n
C1 vout 0 100p
XM2 vin 0 net1 0 NMOS L=3u W=40u m=1
XM3 net1 0 0 0 NMOS L=3u W=40u m=1
RLOAD vout 0 10
.control
set noaskquit
tran 2.96413377385e-08 0.0001
wrdata /Users/yanlu/Documents/TR-1um/analysis/tr10_rcx_vco/final_characterization/openrule1um_dcdc/external/tr1um_mapped/measured_vctrl_5p0V_r_10/wave.txt v(vout) i(VIN_SRC) v(net2)
.endc
.end
