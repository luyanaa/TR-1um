* Ohno quantitative anchor: follower, bias=1.18e-05, f=160000, amp=0.5
.include "/Users/yanlu/Documents/TR-1um/libs.tech/spice/models/ip62_models_calibrated"
.include "/tmp/tr10-rcx/opamp/rcx_cfine/c1.2/opamp.postlayout.renamed.sp"
VDD_SRC PWR_SRC 0 5
RVDD PWR_SRC PWR 1
IBIAS BIAS 0 1.18e-05
VSIG SIG 0 SIN(2.5 0.5 160000)
RSIG SIG INP 1
RFB OUT INN 1
CL OUT 0 100p
XU OUT PWR 0 INP INN BIAS OPAMP_OHNO
.options reltol=5e-3 abstol=1e-12 vntol=1e-6 gmin=1e-12 method=gear
.tran 1.5625e-08 5e-05
.control
run
wrdata /tmp/tr10-rcx/opamp/rcx_cfine/c1.2/c1.2_vf_160k_1vpp.raw time v(sig) v(inp) v(inn) v(out) v(xu.p2) @m.xu.x_1.m1[id] @m.xu.x_34.m1[id] @m.xu.x_53.m1[id] @m.xu.x_77.m1[id] @c.xu.c_52[i]
.endc
.end
