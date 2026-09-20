* TR10-1 DCDC schematic-level surrogate.
* The source Xschem deck references missing mos.lib/passive.lib/diode.lib wrappers;
* this uses the repository calibrated PMOS/NMOS compact-model subcircuits and explicit topology.
.include "/Users/yanlu/Documents/TR-1um/flow/char/fixed_models.sp"
V VIN 0 12
VCLK CLK 0 PULSE(0 5 0 1e-08 1e-08 0.0148206688692 0.0296413377385)
XM1 SW CLK VIN 0 NMOS w=40u l=1u
XM2 SW CLK VIN 0 NMOS w=40u l=3u
XM3 SW 0 0 0 NMOS w=40u l=3u
VCLKN CLK_N 0 0
L1 SW OUT 100n
C1 OUT 0 100p
RLOAD OUT 0 10000
.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12
.tran 1e-08 0.592826754769 uic
.meas tran vout_final FIND v(OUT) AT=0.592826754769
.meas tran vout_min MIN v(OUT) FROM=0.296413377385 TO=0.592826754769
.meas tran vout_max MAX v(OUT) FROM=0.296413377385 TO=0.592826754769
.meas tran iin_avg AVG i(V) FROM=0.296413377385 TO=0.592826754769
.control
run
.endc
.end
