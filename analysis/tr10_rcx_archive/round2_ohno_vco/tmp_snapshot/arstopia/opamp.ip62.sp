* Created by KLayout

* cell OPAMP_arstopia
.SUBCKT OPAMP_arstopia
* net 3 vinn
* net 5 vdd
* net 7 ib
* net 8 out
* net 9 vinp
* net 12 vss
* cell instance $1 r180 *1 281.3,-81.9
X$1 4 3 1 4 MP$3
* cell instance $2 r0 *1 316.9,-158.7
X$2 12 2 1 12 MN$4
* cell instance $3 r180 *1 270,-131.5
X$3 1 12 1 12 MN$4
* cell instance $4 r0 *1 456.9,-45.5
X$4 10 2 6 12 MN$2
* cell instance $5 r0 *1 433.5,-158.7
X$5 8 12 2 12 MN$3
* cell instance $8 r180 *1 490.2,-81.9
X$8 4 9 2 4 MP$3
* cell instance $11 r180 *1 248.9,-22
X$11 5 7 4 5 MP$5
* cell instance $14 r180 *1 82.8,-28.6
X$14 7 5 7 5 MP$2
* cell instance $15 r180 *1 424.3,-22.3
X$15 5 7 8 5 MP$4
* cell instance $16 r180 *1 128,-28.6
X$16 6 5 7 5 MP$2
* cell instance $19 r180 *1 75.8,-68.2
X$19 6 11 6 12 MN$5
* cell instance $24 r270 *1 579.6,-77.3
X$24 8 10 CSIO
* cell instance $30 r180 *1 75.8,-95.5
X$30 11 12 11 12 MN$5
.ENDS OPAMP_arstopia

* cell MN$3
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$3 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 3.8,13.6 NMOS
M$1 2 3 1 4 NMOS L=2U W=20U AS=56P AD=30P PS=45.6U PD=23U
* device instance $2 r0 *1 8.8,13.6 NMOS
M$2 1 3 2 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $3 r0 *1 13.8,13.6 NMOS
M$3 2 3 1 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $4 r0 *1 18.8,13.6 NMOS
M$4 1 3 2 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $5 r0 *1 23.8,13.6 NMOS
M$5 2 3 1 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $6 r0 *1 28.8,13.6 NMOS
M$6 1 3 2 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $7 r0 *1 33.8,13.6 NMOS
M$7 2 3 1 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $8 r0 *1 38.8,13.6 NMOS
M$8 1 3 2 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $9 r0 *1 43.8,13.6 NMOS
M$9 2 3 1 4 NMOS L=2U W=20U AS=30P AD=56P PS=23U PD=45.6U
.ENDS MN$3

* cell MP$5
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$5 1 2 3 4
* device instance $1 r0 *1 3.8,13.6 PMOS
M$1 1 2 3 4 PMOS L=2U W=20U AS=56P AD=30P PS=45.6U PD=23U
* device instance $2 r0 *1 8.8,13.6 PMOS
M$2 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $3 r0 *1 13.8,13.6 PMOS
M$3 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $4 r0 *1 18.8,13.6 PMOS
M$4 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $5 r0 *1 23.8,13.6 PMOS
M$5 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $6 r0 *1 28.8,13.6 PMOS
M$6 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $7 r0 *1 33.8,13.6 PMOS
M$7 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $8 r0 *1 38.8,13.6 PMOS
M$8 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $9 r0 *1 43.8,13.6 PMOS
M$9 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $10 r0 *1 48.8,13.6 PMOS
M$10 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $11 r0 *1 53.8,13.6 PMOS
M$11 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $12 r0 *1 58.8,13.6 PMOS
M$12 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $13 r0 *1 63.8,13.6 PMOS
M$13 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $14 r0 *1 68.8,13.6 PMOS
M$14 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $15 r0 *1 73.8,13.6 PMOS
M$15 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $16 r0 *1 78.8,13.6 PMOS
M$16 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $17 r0 *1 83.8,13.6 PMOS
M$17 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $18 r0 *1 88.8,13.6 PMOS
M$18 3 2 1 4 PMOS L=2U W=20U AS=30P AD=56P PS=23U PD=45.6U
.ENDS MP$5

* cell CSIO
* pin 
* pin 
.SUBCKT CSIO 1 2
* device instance $1 r0 *1 0,0 CSIO
C$1 1 2 8.856e-12 CSIO
.ENDS CSIO

* cell MN$2
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$2 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 3.8,9.1 NMOS
M$1 2 3 1 4 NMOS L=2U W=11U AS=30.8P AD=16.5P PS=27.6U PD=14U
* device instance $2 r0 *1 8.8,9.1 NMOS
M$2 1 3 2 4 NMOS L=2U W=11U AS=16.5P AD=30.8P PS=14U PD=27.6U
.ENDS MN$2

* cell MP$4
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$4 1 2 3 4
* device instance $1 r0 *1 3.8,13.6 PMOS
M$1 1 2 3 4 PMOS L=2U W=20U AS=56P AD=30P PS=45.6U PD=23U
* device instance $2 r0 *1 8.8,13.6 PMOS
M$2 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $3 r0 *1 13.8,13.6 PMOS
M$3 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $4 r0 *1 18.8,13.6 PMOS
M$4 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $5 r0 *1 23.8,13.6 PMOS
M$5 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $6 r0 *1 28.8,13.6 PMOS
M$6 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $7 r0 *1 33.8,13.6 PMOS
M$7 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $8 r0 *1 38.8,13.6 PMOS
M$8 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $9 r0 *1 43.8,13.6 PMOS
M$9 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $10 r0 *1 48.8,13.6 PMOS
M$10 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $11 r0 *1 53.8,13.6 PMOS
M$11 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $12 r0 *1 58.8,13.6 PMOS
M$12 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $13 r0 *1 63.8,13.6 PMOS
M$13 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $14 r0 *1 68.8,13.6 PMOS
M$14 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $15 r0 *1 73.8,13.6 PMOS
M$15 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $16 r0 *1 78.8,13.6 PMOS
M$16 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $17 r0 *1 83.8,13.6 PMOS
M$17 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $18 r0 *1 88.8,13.6 PMOS
M$18 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $19 r0 *1 93.8,13.6 PMOS
M$19 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $20 r0 *1 98.8,13.6 PMOS
M$20 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $21 r0 *1 103.8,13.6 PMOS
M$21 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $22 r0 *1 108.8,13.6 PMOS
M$22 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $23 r0 *1 113.8,13.6 PMOS
M$23 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $24 r0 *1 118.8,13.6 PMOS
M$24 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $25 r0 *1 123.8,13.6 PMOS
M$25 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $26 r0 *1 128.8,13.6 PMOS
M$26 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $27 r0 *1 133.8,13.6 PMOS
M$27 1 2 3 4 PMOS L=2U W=20U AS=30P AD=56P PS=23U PD=45.6U
.ENDS MP$4

* cell MN$4
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$4 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 3.8,13.6 NMOS
M$1 2 3 1 4 NMOS L=2U W=20U AS=56P AD=30P PS=45.6U PD=23U
* device instance $2 r0 *1 8.8,13.6 NMOS
M$2 1 3 2 4 NMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $3 r0 *1 13.8,13.6 NMOS
M$3 2 3 1 4 NMOS L=2U W=20U AS=30P AD=56P PS=23U PD=45.6U
.ENDS MN$4

* cell MP$3
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$3 1 2 3 4
* device instance $1 r0 *1 3.8,13.6 PMOS
M$1 1 2 3 4 PMOS L=2U W=20U AS=56P AD=30P PS=45.6U PD=23U
* device instance $2 r0 *1 8.8,13.6 PMOS
M$2 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $3 r0 *1 13.8,13.6 PMOS
M$3 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $4 r0 *1 18.8,13.6 PMOS
M$4 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $5 r0 *1 23.8,13.6 PMOS
M$5 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $6 r0 *1 28.8,13.6 PMOS
M$6 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $7 r0 *1 33.8,13.6 PMOS
M$7 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $8 r0 *1 38.8,13.6 PMOS
M$8 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $9 r0 *1 43.8,13.6 PMOS
M$9 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $10 r0 *1 48.8,13.6 PMOS
M$10 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $11 r0 *1 53.8,13.6 PMOS
M$11 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $12 r0 *1 58.8,13.6 PMOS
M$12 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $13 r0 *1 63.8,13.6 PMOS
M$13 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $14 r0 *1 68.8,13.6 PMOS
M$14 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $15 r0 *1 73.8,13.6 PMOS
M$15 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $16 r0 *1 78.8,13.6 PMOS
M$16 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $17 r0 *1 83.8,13.6 PMOS
M$17 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $18 r0 *1 88.8,13.6 PMOS
M$18 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $19 r0 *1 93.8,13.6 PMOS
M$19 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $20 r0 *1 98.8,13.6 PMOS
M$20 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $21 r0 *1 103.8,13.6 PMOS
M$21 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $22 r0 *1 108.8,13.6 PMOS
M$22 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $23 r0 *1 113.8,13.6 PMOS
M$23 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $24 r0 *1 118.8,13.6 PMOS
M$24 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $25 r0 *1 123.8,13.6 PMOS
M$25 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $26 r0 *1 128.8,13.6 PMOS
M$26 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $27 r0 *1 133.8,13.6 PMOS
M$27 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $28 r0 *1 138.8,13.6 PMOS
M$28 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $29 r0 *1 143.8,13.6 PMOS
M$29 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $30 r0 *1 148.8,13.6 PMOS
M$30 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $31 r0 *1 153.8,13.6 PMOS
M$31 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $32 r0 *1 158.8,13.6 PMOS
M$32 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $33 r0 *1 163.8,13.6 PMOS
M$33 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $34 r0 *1 168.8,13.6 PMOS
M$34 3 2 1 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $35 r0 *1 173.8,13.6 PMOS
M$35 1 2 3 4 PMOS L=2U W=20U AS=30P AD=30P PS=23U PD=23U
* device instance $36 r0 *1 178.8,13.6 PMOS
M$36 3 2 1 4 PMOS L=2U W=20U AS=30P AD=56P PS=23U PD=45.6U
.ENDS MP$3

* cell MP$2
* pin 
* pin 
* pin 
* pin 
.SUBCKT MP$2 1 2 3 4
* device instance $1 r0 *1 3.8,6.1 PMOS
M$1 2 3 1 4 PMOS L=2U W=5U AS=14P AD=7.5P PS=15.6U PD=8U
* device instance $2 r0 *1 8.8,6.1 PMOS
M$2 1 3 2 4 PMOS L=2U W=5U AS=7.5P AD=7.5P PS=8U PD=8U
* device instance $3 r0 *1 13.8,6.1 PMOS
M$3 2 3 1 4 PMOS L=2U W=5U AS=7.5P AD=14P PS=8U PD=15.6U
.ENDS MP$2

* cell MN$5
* pin 
* pin 
* pin 
* pin SUBSTRATE
.SUBCKT MN$5 1 2 3 4
* net 4 SUBSTRATE
* device instance $1 r0 *1 3.8,6.1 NMOS
M$1 2 3 1 4 NMOS L=2U W=5U AS=14P AD=14P PS=15.6U PD=15.6U
.ENDS MN$5
