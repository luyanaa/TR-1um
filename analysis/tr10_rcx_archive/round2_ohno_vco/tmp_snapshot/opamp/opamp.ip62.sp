* Created by KLayout

* cell OPAMP_OHNO
.SUBCKT OPAMP_OHNO
* net 7 OUT
* net 9 VDD
* net 12 VSS
* cell instance $1 m135 *1 -201.2,13
X$1 9 1 1 9 MP$6
* cell instance $2 m90 *1 -204.5,39.5
X$2 9 3 1 9 MP$1
* cell instance $3 r0 *1 -167,39.5
X$3 9 6 1 9 MP$5
* cell instance $4 r0 *1 117,39.5
X$4 9 7 1 9 MP$3
* cell instance $5 m0 *1 117,32.7
X$5 9 7 1 9 MP$3
* cell instance $32 r0 *1 271.8,23.3
X$32 7 2 CSIO
* cell instance $34 m135 *1 -45.2,-63.6
X$34 2 5 3 12 MN$3
* cell instance $38 r0 *1 -196.4,-77.6
X$38 4 3 3 12 MN$2
* cell instance $51 r0 *1 -232,-77.6
X$51 12 4 4 12 MN$2
* cell instance $58 r0 *1 117,-66.8
X$58 12 7 5 12 MN$4
* cell instance $59 m90 *1 78.8,39.5
X$59 6 5 10 6 MP
* cell instance $60 r270 *1 -149.3,-25.5
X$60 12 5 8 12 MN$2
* cell instance $80 m0 *1 -78.8,5.8
X$80 6 5 10 6 MP
* cell instance $96 r180 *1 78.8,5.8
X$96 6 8 11 6 MP
* cell instance $97 r0 *1 -78.8,39.5
X$97 6 8 11 6 MP
* cell instance $200 m45 *1 -149.3,-4.7
X$200 12 8 8 12 MN$2
.ENDS OPAMP_OHNO

* cell MN$4
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$4 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 4.3,18.6 NMOS
M$1 2 3 1 4 NMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 NMOS
M$2 1 3 2 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 NMOS
M$3 2 3 1 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $4 r0 *1 22.3,18.6 NMOS
M$4 1 3 2 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $5 r0 *1 28.3,18.6 NMOS
M$5 2 3 1 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $6 r0 *1 34.3,18.6 NMOS
M$6 1 3 2 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $7 r0 *1 40.3,18.6 NMOS
M$7 2 3 1 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $8 r0 *1 46.3,18.6 NMOS
M$8 1 3 2 4 NMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $9 r0 *1 52.3,18.6 NMOS
M$9 2 3 1 4 NMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MN$4

* cell MN$3
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$3 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 4.3,18.6 NMOS
M$1 2 3 1 4 NMOS L=3U W=30U AS=84P AD=84P PS=65.6U PD=65.6U
.ENDS MN$3

* cell MP$1
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$1 1 2 3 4
* device instance $1 r0 *1 4.3,18.6 PMOS
M$1 2 3 1 4 PMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 PMOS
M$2 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 PMOS
M$3 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $4 r0 *1 22.3,18.6 PMOS
M$4 1 3 2 4 PMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MP$1

* cell MP$5
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$5 1 2 3 4
* device instance $1 r0 *1 4.3,18.6 PMOS
M$1 2 3 1 4 PMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 PMOS
M$2 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 PMOS
M$3 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $4 r0 *1 22.3,18.6 PMOS
M$4 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $5 r0 *1 28.3,18.6 PMOS
M$5 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $6 r0 *1 34.3,18.6 PMOS
M$6 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $7 r0 *1 40.3,18.6 PMOS
M$7 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $8 r0 *1 46.3,18.6 PMOS
M$8 1 3 2 4 PMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MP$5

* cell MN$2
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$2 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 4.3,18.6 NMOS
M$1 2 3 1 4 NMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 NMOS
M$2 1 3 2 4 NMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MN$2

* cell MP$6
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$6 1 2 3 4
* device instance $1 r0 *1 4.3,18.6 PMOS
M$1 2 3 1 4 PMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 PMOS
M$2 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 PMOS
M$3 2 3 1 4 PMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MP$6

* cell MP$3
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$3 1 2 3 4
* device instance $1 r0 *1 4.3,18.6 PMOS
M$1 2 3 1 4 PMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 PMOS
M$2 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 PMOS
M$3 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $4 r0 *1 22.3,18.6 PMOS
M$4 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $5 r0 *1 28.3,18.6 PMOS
M$5 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $6 r0 *1 34.3,18.6 PMOS
M$6 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $7 r0 *1 40.3,18.6 PMOS
M$7 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $8 r0 *1 46.3,18.6 PMOS
M$8 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $9 r0 *1 52.3,18.6 PMOS
M$9 2 3 1 4 PMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MP$3

* cell CSIO
* pin 
* pin 
.SUBCKT CSIO 1 2
* device instance $1 r0 *1 0,0 CSIO
C$1 1 2 8.856e-12 CSIO
.ENDS CSIO

* cell MP
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP 1 2 3 4
* device instance $1 r0 *1 4.3,18.6 PMOS
M$1 2 3 1 4 PMOS L=3U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 10.3,18.6 PMOS
M$2 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $3 r0 *1 16.3,18.6 PMOS
M$3 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $4 r0 *1 22.3,18.6 PMOS
M$4 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $5 r0 *1 28.3,18.6 PMOS
M$5 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $6 r0 *1 34.3,18.6 PMOS
M$6 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $7 r0 *1 40.3,18.6 PMOS
M$7 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $8 r0 *1 46.3,18.6 PMOS
M$8 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $9 r0 *1 52.3,18.6 PMOS
M$9 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $10 r0 *1 58.3,18.6 PMOS
M$10 1 3 2 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $11 r0 *1 64.3,18.6 PMOS
M$11 2 3 1 4 PMOS L=3U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $12 r0 *1 70.3,18.6 PMOS
M$12 1 3 2 4 PMOS L=3U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS MP
