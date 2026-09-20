* TR10 inverter frequency/load reproduction surrogate
.include "/Users/yanlu/Documents/TR-1um/flow/char/fixed_models.sp"
.subckt INV_TR10 IN OUT VDD VSS
XM1 OUT IN VSS VSS NMOS w=20u l=10u
XM2 OUT IN VDD VDD PMOS w=60u l=10u
.ends INV_TR10
VDD VDD 0 5
VIN IN 0 PULSE(0 5 0 2e-08 2e-08 1e-06 2e-06)
XINV IN OUT VDD 0 INV_TR10
CLOAD OUT 0 1e-12
.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12
.tran 4e-09 6e-06
.meas tran vout_min MIN v(OUT) FROM=3e-06 TO=6e-06
.meas tran vout_max MAX v(OUT) FROM=3e-06 TO=6e-06
.meas tran trise TRIG v(OUT) VAL=0.83 RISE=2 TARG v(OUT) VAL=4.17 RISE=2
.meas tran tfall TRIG v(OUT) VAL=4.17 FALL=2 TARG v(OUT) VAL=0.83 FALL=2
.control
run
.endc
.end
