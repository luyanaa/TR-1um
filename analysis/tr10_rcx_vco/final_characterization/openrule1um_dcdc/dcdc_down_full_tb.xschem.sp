** sch_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/dcdc_down_full_tb.sch
.subckt dcdc_down_full_tb

vin vin GND 12.0
M1 vin net2 net1 GND nchor1ex L=1.0u W=40.0u m=1
L1 net1 vout 100n m=1
vdd VDD GND 5.0
C1 vout GND 100p m=1
M2 vin GND net1 GND nchor1ex L=3.0u W=40.0u m=1
M3 net1 GND GND GND nchor1ex L=3.0u W=40.0u m=1
vcntl vcntl GND 5.0
x1 VDD net2 vcntl GND vco
**** begin user architecture code
 .include /tmp/tr10-xschem/lib/TR10/mos.lib
.include /tmp/tr10-xschem/lib/TR10/passive.lib
.include /tmp/tr10-xschem/lib/TR10/diode.lib

.option savecurrent
.control
save all

* Tran analysis
tran 1n 100u
plot vout
wrdata ~/dcdc_down_full_tb.txt v(vout)
write dcdc_down_full_tb.raw
.endc

**** end user architecture code
.ends

* expanding   symbol:  vco.sym # of pins=4
** sym_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/vco.sym
** sch_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/vco.sch
.subckt vco vdd vout vctrl gnd
*.PININFO vdd:B vout:O gnd:B vctrl:I
M4 vdd net1 net1 vdd pchor1ex L=10u W=12u m=1
M6 net2 vctrl gnd gnd nchor1ex L=10u W=4u m=1
x2 vdd net1 net3 net8 vctrl gnd inverter
x3 vdd net1 net4 net3 vctrl gnd inverter
x4 vdd net1 net6 net4 vctrl gnd inverter
x5 vdd net1 net5 net6 vctrl gnd inverter
x1 vdd vout net6 gnd buffer
x9 vdd net1 net7 net5 vctrl gnd inverter
x6 vdd net1 net9 net7 vctrl gnd inverter
x7 vdd net1 net8 net9 vctrl gnd inverter
M1 net1 net1 net2 gnd nchor1ex L=10u W=4u m=1
.ends


* expanding   symbol:  inverter.sym # of pins=6
** sym_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/inverter.sym
** sch_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/inverter.sch
.subckt inverter vdd vvctrl vout vin vctrl gnd
*.PININFO vin:I vout:O vdd:B gnd:B vctrl:I vvctrl:I
M1 vout vin net1 vdd pchor1ex L=1u W=3u m=1
M2 vout vin net2 gnd nchor1ex L=1u W=2u m=1
M3 net2 vctrl gnd gnd nchor1ex L=5u W=8u m=1
M4 net1 vvctrl vdd vdd pchor1ex L=5u W=12u m=1
C2 vout gnd poly_cap W=20 L=20
.ends


* expanding   symbol:  buffer.sym # of pins=4
** sym_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/buffer.sym
** sch_path: /tmp/TR10-1/member_project/DCDC_DOWN/xschem/buffer.sch
.subckt buffer vdd vout vin gnd
*.PININFO vdd:B vin:I vout:O gnd:B
M1 net1 vin gnd gnd nchor1ex L=1u W=2u m=1
M2 net1 vin vdd vdd pchor1ex L=1u W=3u m=1
M3 vout net1 gnd gnd nchor1ex L=1u W=2u m=1
M4 vout net1 vdd vdd pchor1ex L=1u W=3u m=1
.ends

.GLOBAL GND
.GLOBAL VDD
