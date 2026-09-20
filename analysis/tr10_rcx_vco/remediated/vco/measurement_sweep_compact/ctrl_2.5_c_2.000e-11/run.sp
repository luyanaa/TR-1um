* TR-1um canonical VCO post-layout transient testbench.
* Device compact models are included by the merged post-layout deck.
.include "/Users/yanlu/Documents/TR-1um/analysis/tr10_rcx_vco/remediated/vco/vco.post.sp"

VDDSRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
VCTRLNSRC CTRLN_SRC 0 2.5
RCTRLN CTRLN_SRC P17 10
VCTRLPSRC CTRLP_SRC 0 2.5
RCTRLP CTRLP_SRC P22 10

XU OUT PWR PWR 0 0 P17 P22 VCO

CLOAD OUT 0 2e-11

.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12 trtol=7 itl4=10000
.save v(OUT) v(PWR) v(P17) v(P22)
.tran 50n 250u uic
.meas tran T1 WHEN v(OUT)=2.5 RISE=20
.meas tran T2 WHEN v(OUT)=2.5 RISE=21
.meas tran PERIOD PARAM='T2-T1'
.meas tran FREQ PARAM='1/PERIOD'
.meas tran VOUT_MIN MIN v(OUT) FROM=100u TO=250u
.meas tran VOUT_MAX MAX v(OUT) FROM=100u TO=250u
.end
