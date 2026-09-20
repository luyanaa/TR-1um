* Created by mapped OpenRule1um bridge

* cell VCO
.SUBCKT VCO P19 P28 P29 P1 P30 P17 P22
* net 1 GND
* net 19 Vout
* net 28 VDD
* net 29 VDD
* net 30 VSS
* device instance $1 r0 *1 205.3,84.1 pchor1ex
M$1 P28 P22 P22 P29 pchor1ex L=10U W=6U AS=12P AD=6P PS=16U PD=8U
* device instance $2 r0 *1 217.3,84.1 pchor1ex
M$2 P22 P22 P28 P29 pchor1ex L=10U W=6U AS=6P AD=12P PS=8U PD=16U
* device instance $3 r0 *1 476.3,83.1 pchor1ex
M$3 P27 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $4 r0 *1 483.3,83.1 pchor1ex
M$4 P28 P22 P27 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $5 r0 *1 490.3,83.1 pchor1ex
M$5 P27 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $6 r0 *1 497.3,83.1 pchor1ex
M$6 P28 P22 P27 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $7 r0 *1 437.3,83.1 pchor1ex
M$7 P26 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $8 r0 *1 444.3,83.1 pchor1ex
M$8 P28 P22 P26 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $9 r0 *1 451.3,83.1 pchor1ex
M$9 P26 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $10 r0 *1 458.3,83.1 pchor1ex
M$10 P28 P22 P26 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $11 r0 *1 398.3,83.1 pchor1ex
M$11 P21 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $12 r0 *1 405.3,83.1 pchor1ex
M$12 P28 P22 P21 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $13 r0 *1 412.3,83.1 pchor1ex
M$13 P21 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $14 r0 *1 419.3,83.1 pchor1ex
M$14 P28 P22 P21 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $15 r0 *1 320.3,83.1 pchor1ex
M$15 P24 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $16 r0 *1 327.3,83.1 pchor1ex
M$16 P28 P22 P24 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $17 r0 *1 334.3,83.1 pchor1ex
M$17 P24 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $18 r0 *1 341.3,83.1 pchor1ex
M$18 P28 P22 P24 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $19 r0 *1 332.4,66.1 pchor1ex
M$19 P4 P3 P24 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $20 r0 *1 281.3,83.1 pchor1ex
M$20 P23 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $21 r0 *1 288.3,83.1 pchor1ex
M$21 P28 P22 P23 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $22 r0 *1 295.3,83.1 pchor1ex
M$22 P23 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $23 r0 *1 302.3,83.1 pchor1ex
M$23 P28 P22 P23 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $24 r0 *1 359.3,83.1 pchor1ex
M$24 P25 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $25 r0 *1 366.3,83.1 pchor1ex
M$25 P28 P22 P25 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $26 r0 *1 373.3,83.1 pchor1ex
M$26 P25 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $27 r0 *1 380.3,83.1 pchor1ex
M$27 P28 P22 P25 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $28 r0 *1 530.5,66.1 pchor1ex
M$28 P19 P18 P28 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $29 r0 *1 242.3,83.1 pchor1ex
M$29 P20 P22 P28 P29 pchor1ex L=5U W=3U AS=6P AD=3P PS=10U PD=5U
* device instance $30 r0 *1 249.3,83.1 pchor1ex
M$30 P28 P22 P20 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $31 r0 *1 256.3,83.1 pchor1ex
M$31 P20 P22 P28 P29 pchor1ex L=5U W=3U AS=3P AD=3P PS=5U PD=5U
* device instance $32 r0 *1 263.3,83.1 pchor1ex
M$32 P28 P22 P20 P29 pchor1ex L=5U W=3U AS=3P AD=6P PS=5U PD=10U
* device instance $33 r0 *1 516.5,66.1 pchor1ex
M$33 P18 P8 P28 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $34 r0 *1 449.4,66.1 pchor1ex
M$34 P7 P6 P26 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $35 r0 *1 410.4,66.1 pchor1ex
M$35 P6 P5 P21 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $36 r0 *1 371.4,66.1 pchor1ex
M$36 P5 P4 P25 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $37 r0 *1 488.4,66.1 pchor1ex
M$37 P8 P7 P27 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $38 r0 *1 254.4,66.1 pchor1ex
M$38 P2 P8 P20 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $39 r0 *1 293.4,66.1 pchor1ex
M$39 P3 P2 P23 P29 pchor1ex L=1U W=3U AS=6P AD=6P PS=10U PD=10U
* device instance $40 r0 *1 205.4,40.9 nchor1ex
M$40 P9 P17 P1 P30 nchor1ex L=10U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $41 r0 *1 217.4,40.9 nchor1ex
M$41 P1 P17 P9 P30 nchor1ex L=10U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $42 r0 *1 242.2,41.6 nchor1ex
M$42 P10 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $43 r0 *1 249.2,41.6 nchor1ex
M$43 P1 P17 P10 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $44 r0 *1 256.2,41.6 nchor1ex
M$44 P10 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $45 r0 *1 263.2,41.6 nchor1ex
M$45 P1 P17 P10 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $46 r0 *1 281.2,41.6 nchor1ex
M$46 P11 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $47 r0 *1 288.2,41.6 nchor1ex
M$47 P1 P17 P11 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $48 r0 *1 295.2,41.6 nchor1ex
M$48 P11 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $49 r0 *1 302.2,41.6 nchor1ex
M$49 P1 P17 P11 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $50 r0 *1 320.2,41.6 nchor1ex
M$50 P12 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $51 r0 *1 327.2,41.6 nchor1ex
M$51 P1 P17 P12 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $52 r0 *1 334.2,41.6 nchor1ex
M$52 P12 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $53 r0 *1 341.2,41.6 nchor1ex
M$53 P1 P17 P12 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $54 r0 *1 359.2,41.6 nchor1ex
M$54 P13 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $55 r0 *1 366.2,41.6 nchor1ex
M$55 P1 P17 P13 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $56 r0 *1 373.2,41.6 nchor1ex
M$56 P13 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $57 r0 *1 380.2,41.6 nchor1ex
M$57 P1 P17 P13 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $58 r0 *1 398.2,41.6 nchor1ex
M$58 P14 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $59 r0 *1 405.2,41.6 nchor1ex
M$59 P1 P17 P14 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $60 r0 *1 412.2,41.6 nchor1ex
M$60 P14 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $61 r0 *1 419.2,41.6 nchor1ex
M$61 P1 P17 P14 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $62 r0 *1 437.2,41.6 nchor1ex
M$62 P15 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $63 r0 *1 444.2,41.6 nchor1ex
M$63 P1 P17 P15 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $64 r0 *1 451.2,41.6 nchor1ex
M$64 P15 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $65 r0 *1 458.2,41.6 nchor1ex
M$65 P1 P17 P15 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $66 r0 *1 476.2,41.6 nchor1ex
M$66 P16 P17 P1 P30 nchor1ex L=5U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $67 r0 *1 483.2,41.6 nchor1ex
M$67 P1 P17 P16 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $68 r0 *1 490.2,41.6 nchor1ex
M$68 P16 P17 P1 P30 nchor1ex L=5U W=2U AS=2P AD=2P PS=4U PD=4U
* device instance $69 r0 *1 497.2,41.6 nchor1ex
M$69 P1 P17 P16 P30 nchor1ex L=5U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $70 r0 *1 205.3,63.2 nchor1ex
M$70 P22 P22 P9 P30 nchor1ex L=10U W=2U AS=4P AD=2P PS=8U PD=4U
* device instance $71 r0 *1 217.3,63.2 nchor1ex
M$71 P9 P22 P22 P30 nchor1ex L=10U W=2U AS=2P AD=4P PS=4U PD=8U
* device instance $72 r0 *1 254.4,54.6 nchor1ex
M$72 P2 P8 P10 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $73 r0 *1 293.4,54.6 nchor1ex
M$73 P3 P2 P11 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $74 r0 *1 332.4,54.6 nchor1ex
M$74 P4 P3 P12 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $75 r0 *1 371.4,54.6 nchor1ex
M$75 P5 P4 P13 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $76 r0 *1 410.4,54.6 nchor1ex
M$76 P6 P5 P14 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $77 r0 *1 449.4,54.6 nchor1ex
M$77 P7 P6 P15 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $78 r0 *1 488.4,54.6 nchor1ex
M$78 P8 P7 P16 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $79 r0 *1 516.5,54.6 nchor1ex
M$79 P18 P8 P1 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* device instance $80 r0 *1 530.5,54.6 nchor1ex
M$80 P19 P18 P1 P30 nchor1ex L=1U W=2U AS=4P AD=4P PS=8U PD=8U
* Legacy OpenRule1um poly-cap markers retained as explicit simulation caps.
CLEG1 P2 P1 poly_cap W=20 L=20
CLEG2 P3 P1 poly_cap W=20 L=20
CLEG3 P4 P1 poly_cap W=20 L=20
CLEG4 P5 P1 poly_cap W=20 L=20
CLEG5 P6 P1 poly_cap W=20 L=20
CLEG6 P7 P1 poly_cap W=20 L=20
CLEG7 P8 P1 poly_cap W=20 L=20
.ENDS VCO
