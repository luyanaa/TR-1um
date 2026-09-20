* TR10-1 DCDC exact source topology with external measured clock.
* Model set: openrule1um_source
.include "/tmp/tr10-xschem/lib/TR10/mos.lib"
.include "/tmp/tr10-xschem/lib/TR10/passive.lib"
.include "/tmp/tr10-xschem/lib/TR10/diode.lib"
.option savecurrents
VIN_SRC vin 0 12
VDD_SRC VDD 0 5
VCLK net2 0 PULSE(0 5 0 4.95763454146e-07 4.95763454146e-07 2.42924092532e-05 4.95763454146e-05)
MM1 vin net2 net1 0 nchor1ex L=1u W=40u m=1
L1 net1 vout 100n
C1 vout 0 100p
MM2 vin 0 net1 0 nchor1ex L=3u W=40u m=1
MM3 net1 0 0 0 nchor1ex L=3u W=40u m=1
RLOAD vout 0 1000
.control
set noaskquit
tran 4.95763454146e-08 0.0001
wrdata /Users/yanlu/Documents/TR-1um/analysis/tr10_rcx_vco/final_characterization/openrule1um_dcdc/external/openrule1um_source/measured_vctrl_2p5V_r_1000/wave.txt v(vout) i(VIN_SRC) v(net2)
.endc
.end
