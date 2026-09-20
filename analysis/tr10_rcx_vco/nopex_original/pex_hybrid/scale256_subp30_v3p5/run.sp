* Historical ISHI-KAI MOS/passive models plus distributed engineering PEX.
.include "../../models/mos.f8862f775cad.lib"
.include "../../models/passive.f8862f775cad.lib"
.include "vco.nopex.pex.sp"

VDD PWR 0 5
VCTRL CTRL 0 3.5
XU OUT PWR PWR 0 0 CTRL CTRL VCO

.options reltol=2e-3 abstol=1e-12 vntol=1e-6 method=gear gmin=1e-10 rshunt=1e12 trtol=7 itl4=10000
.save v(OUT) v(PWR) v(CTRL) v(P2) v(P3) v(P8)
.tran 1n 600u uic
.meas tran T1 WHEN v(OUT)=2.5 RISE=8
.meas tran T2 WHEN v(OUT)=2.5 RISE=9
.meas tran PERIOD PARAM='T2-T1'
.meas tran FREQ PARAM='1/PERIOD'
.meas tran VOUT_MIN MIN v(OUT) FROM=20u TO=600u
.meas tran VOUT_MAX MAX v(OUT) FROM=20u TO=600u
.end
