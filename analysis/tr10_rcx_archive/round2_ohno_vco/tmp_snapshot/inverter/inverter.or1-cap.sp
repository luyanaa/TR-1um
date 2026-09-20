* Created by KLayout

* cell TOP
.SUBCKT TOP
* net 1 Q
* net 2 A
* net 3 VDD
* net 4 VSS
* cell instance $1 r0 *1 -8,-5
X$1 3 1 2 3 Pch
* cell instance $2 r0 *1 -8,-35
X$2 4 1 2 4 Nch
.ENDS TOP

* cell Nch
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT Nch 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 7,13 NMOS
M$1 2 3 1 4 NMOS L=10U W=20U AS=40P AD=40P PS=44U PD=44U
.ENDS Nch

* cell Pch
* pin 
* pin 
* pin 
* pin 
.SUBCKT Pch 1 2 3 4
* device instance $1 r0 *1 7,33 PMOS
M$1 2 3 1 4 PMOS L=10U W=60U AS=120P AD=120P PS=124U PD=124U
.ENDS Pch
