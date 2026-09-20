* TR10 inverter triangle-drive/load reproduction surrogate
.include "/Users/yanlu/Documents/TR-1um/flow/char/fixed_models.sp"
.subckt INV_TR10 IN OUT VDD VSS
XM1 OUT IN VSS VSS NMOS w=20u l=10u
XM2 OUT IN VDD VDD PMOS w=60u l=10u
.ends INV_TR10
VDD VDD 0 5
VTRI IN 0 PWL(0 0 0.0005 5 0.001 0 0.001 0 0.0015 5 0.002 0 0.002 0 0.0025 5 0.003 0)
XINV IN OUT VDD 0 INV_TR10
CLOAD OUT 0 5e-11
.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12
.tran 2e-09 0.003
.meas tran vout_min MIN v(OUT) FROM=0.001 TO=0.003
.meas tran vout_max MAX v(OUT) FROM=0.001 TO=0.003
.meas tran trise TRIG v(OUT) VAL=0.83 RISE=2 TARG v(OUT) VAL=4.17 RISE=2
.meas tran tfall TRIG v(OUT) VAL=4.17 FALL=2 TARG v(OUT) VAL=0.83 FALL=2
.control
run
.endc
.end
