* TR-1um telescopic OTA for ALIGN (drawing-layer process, 1um/5V CMOS)
* Device models: nmos5v/pmos5v (see pdks/TR1um/models.sp)
* W in um (3.4-60), L in um (1-30), NF = fingers, M = multiplier
.subckt TELESCOPIC_OTA vbiasn vbiasp1 vbiasp2 vinn vinp voutn voutp id vdd 0
m1 id id 0 0 nmos5v w=10u l=2u nf=2 m=1
m2 net10 id 0 0 nmos5v w=10u l=2u nf=2 m=1
m5 voutn vbiasn net8 0 nmos5v w=10u l=2u nf=2 m=1
m6 voutp vbiasn net014 0 nmos5v w=10u l=2u nf=2 m=1
m8 voutp vbiasp1 net012 vdd pmos5v w=10u l=2u nf=2 m=1
m7 voutn vbiasp1 net06 vdd pmos5v w=10u l=2u nf=2 m=1
m10 net012 vbiasp2 vdd vdd pmos5v w=10u l=2u nf=2 m=1
m9 net06 vbiasp2 vdd vdd pmos5v w=10u l=2u nf=2 m=1
m4 net014 vinn net10 0 nmos5v w=10u l=2u nf=2 m=1
m3 net8 vinp net10 0 nmos5v w=10u l=2u nf=2 m=1
.ends TELESCOPIC_OTA
