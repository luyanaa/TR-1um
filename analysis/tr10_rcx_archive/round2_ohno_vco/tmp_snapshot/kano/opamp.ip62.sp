* Created by KLayout

* cell OPAMP_kano
.SUBCKT OPAMP_kano
* net 2 ib
* net 4 out
* net 6 vinn
* net 7 vdd
* net 9 vinp
* net 12 vss
* cell instance $1 r0 *1 -161.9,-13.4
X$1 1 8 1 12 MN$6
* cell instance $2 m90 *1 132.6,27.2
X$2 3 5 1 12 MN$7
* cell instance $7 m0 *1 4.9,57.1
X$7 7 4 2 7 MP$7
* cell instance $8 r0 *1 -143.2,213.1
X$8 7 11 2 7 MP$4
* cell instance $18 r90 *1 49.3,251
X$18 4 3 CSIO
* cell instance $19 r270 *1 118.4,19.4
X$19 12 4 5 12 MN$9
* cell instance $32 m90 *1 156.6,89
X$32 5 9 11 11 MP
* cell instance $42 r0 *1 -143.2,89
X$42 10 6 11 11 MP
* cell instance $57 m90 *1 -138.3,-13.4
X$57 12 8 8 12 MN$6
* device instance $1 r0 *1 -153.6,37.1 PMOS
M$1 7 2 1 7 PMOS L=5U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $2 r0 *1 -145.6,37.1 PMOS
M$2 2 2 7 7 PMOS L=5U W=30U AS=45P AD=84P PS=33U PD=65.6U
* device instance $3 r0 *1 -93.6,18.6 NMOS
M$3 10 10 12 12 NMOS L=5U W=30U AS=84P AD=45P PS=65.6U PD=33U
* device instance $4 r0 *1 -85.6,18.6 NMOS
M$4 12 10 10 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $5 r0 *1 -77.6,18.6 NMOS
M$5 10 10 12 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $6 r0 *1 -69.6,18.6 NMOS
M$6 12 10 10 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $7 r0 *1 -61.6,18.6 NMOS
M$7 5 10 12 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $8 r0 *1 -53.6,18.6 NMOS
M$8 12 10 5 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $9 r0 *1 -45.6,18.6 NMOS
M$9 5 10 12 12 NMOS L=5U W=30U AS=45P AD=45P PS=33U PD=33U
* device instance $10 r0 *1 -37.6,18.6 NMOS
M$10 12 10 5 12 NMOS L=5U W=30U AS=45P AD=84P PS=33U PD=65.6U
.ENDS OPAMP_kano

* cell MP
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP 1 2 3 4
* device instance $1 r0 *1 5.3,33.6 PMOS
M$1 1 2 3 4 PMOS L=5U W=60U AS=168P AD=90P PS=125.6U PD=63U
* device instance $2 r0 *1 13.3,33.6 PMOS
M$2 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $3 r0 *1 21.3,33.6 PMOS
M$3 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $4 r0 *1 29.3,33.6 PMOS
M$4 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $5 r0 *1 37.3,33.6 PMOS
M$5 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $6 r0 *1 45.3,33.6 PMOS
M$6 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $7 r0 *1 53.3,33.6 PMOS
M$7 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $8 r0 *1 61.3,33.6 PMOS
M$8 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $9 r0 *1 69.3,33.6 PMOS
M$9 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $10 r0 *1 77.3,33.6 PMOS
M$10 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $11 r0 *1 85.3,33.6 PMOS
M$11 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $12 r0 *1 93.3,33.6 PMOS
M$12 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $13 r0 *1 101.3,33.6 PMOS
M$13 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $14 r0 *1 109.3,33.6 PMOS
M$14 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $15 r0 *1 117.3,33.6 PMOS
M$15 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $16 r0 *1 125.3,33.6 PMOS
M$16 3 2 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $17 r0 *1 133.3,33.6 PMOS
M$17 1 2 3 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $18 r0 *1 141.3,33.6 PMOS
M$18 3 2 1 4 PMOS L=5U W=60U AS=90P AD=168P PS=63U PD=125.6U
.ENDS MP

* cell MP$7
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$7 1 2 3 4
* device instance $1 r0 *1 5.3,28.6 PMOS
M$1 2 3 1 4 PMOS L=5U W=50U AS=140P AD=75P PS=105.6U PD=53U
* device instance $2 r0 *1 13.3,28.6 PMOS
M$2 1 3 2 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $3 r0 *1 21.3,28.6 PMOS
M$3 2 3 1 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $4 r0 *1 29.3,28.6 PMOS
M$4 1 3 2 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $5 r0 *1 37.3,28.6 PMOS
M$5 2 3 1 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $6 r0 *1 45.3,28.6 PMOS
M$6 1 3 2 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $7 r0 *1 53.3,28.6 PMOS
M$7 2 3 1 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $8 r0 *1 61.3,28.6 PMOS
M$8 1 3 2 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $9 r0 *1 69.3,28.6 PMOS
M$9 2 3 1 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $10 r0 *1 77.3,28.6 PMOS
M$10 1 3 2 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $11 r0 *1 85.3,28.6 PMOS
M$11 2 3 1 4 PMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $12 r0 *1 93.3,28.6 PMOS
M$12 1 3 2 4 PMOS L=5U W=50U AS=75P AD=140P PS=53U PD=105.6U
.ENDS MP$7

* cell MN$7
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$7 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 5.3,11.1 NMOS
M$1 2 3 1 4 NMOS L=5U W=15U AS=42P AD=42P PS=35.6U PD=35.6U
.ENDS MN$7

* cell CSIO
* pin 
* pin 
.SUBCKT CSIO 1 2
* device instance $1 r0 *1 0,0 CSIO
C$1 1 2 8.856e-12 CSIO
.ENDS CSIO

* cell MN$9
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$9 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 5.3,28.6 NMOS
M$1 2 3 1 4 NMOS L=5U W=50U AS=140P AD=75P PS=105.6U PD=53U
* device instance $2 r0 *1 13.3,28.6 NMOS
M$2 1 3 2 4 NMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $3 r0 *1 21.3,28.6 NMOS
M$3 2 3 1 4 NMOS L=5U W=50U AS=75P AD=75P PS=53U PD=53U
* device instance $4 r0 *1 29.3,28.6 NMOS
M$4 1 3 2 4 NMOS L=5U W=50U AS=75P AD=140P PS=53U PD=105.6U
.ENDS MN$9

* cell MN$6
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$6 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 5.3,8.6 NMOS
M$1 2 3 1 4 NMOS L=5U W=10U AS=28P AD=28P PS=25.6U PD=25.6U
.ENDS MN$6

* cell MP$4
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$4 1 2 3 4
* device instance $1 r0 *1 5.3,33.6 PMOS
M$1 2 3 1 4 PMOS L=5U W=60U AS=168P AD=90P PS=125.6U PD=63U
* device instance $2 r0 *1 13.3,33.6 PMOS
M$2 1 3 2 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $3 r0 *1 21.3,33.6 PMOS
M$3 2 3 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $4 r0 *1 29.3,33.6 PMOS
M$4 1 3 2 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $5 r0 *1 37.3,33.6 PMOS
M$5 2 3 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $6 r0 *1 45.3,33.6 PMOS
M$6 1 3 2 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $7 r0 *1 53.3,33.6 PMOS
M$7 2 3 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $8 r0 *1 61.3,33.6 PMOS
M$8 1 3 2 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $9 r0 *1 69.3,33.6 PMOS
M$9 2 3 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $10 r0 *1 77.3,33.6 PMOS
M$10 1 3 2 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $11 r0 *1 85.3,33.6 PMOS
M$11 2 3 1 4 PMOS L=5U W=60U AS=90P AD=90P PS=63U PD=63U
* device instance $12 r0 *1 93.3,33.6 PMOS
M$12 1 3 2 4 PMOS L=5U W=60U AS=90P AD=168P PS=63U PD=125.6U
.ENDS MP$4
