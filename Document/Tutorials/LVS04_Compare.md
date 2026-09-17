# Compare: 05_Compare.lvs

## [05_Compare.lvs](../../libs.tech/klayout/tech/lvs/05_Compare.lvs)

In **run.lvs**, there are couple of LVS preparation and definition to handle TR-1um spice file. 

### LVS preparation 

First, defined net file names which would be extracted from GDSII and be compared spice file to compare.

```
# ----- ------ ----- ----- ------ ----- ----- ------ ----- 
# LVS preparation
# 
# cell_name + ".extracted" is extracted circuit file 
# cell_name + ".cir"       is circuit file to compare
# cell_name + ".spice"     is circuit file to compare (alternative)
#
Lay_file = source.cell_name + ".extracted"
Sch_file = source.cell_name + ".cir"
#
target_netlist(Lay_file, write_spice, "Created by KLayout")
#
# ----- ------ ----- ----- ------ ----- ----- ------ ----- 
# netlist extraction
#
netlist.simplify
#
```

### .subckt device models

Heer is "How to handle **.subckt** device models such as **F_RR**,**F_RS**, and **F_CSIO**. Those elements are described as **X...** in the reference **cir** file as below.

```
XC1 IN GND GND F_CSIO c=0.4875p x=1u y=1u m=1
XR1 net1 IN VDD F_RR w=6u R=1 l=6.6u tc1=0 tc2=0
XR2 VDD net1 F_RS w=6u R=1 l=17u tc1=0 tc2=0
```

Yet in **extracted**, those are **R** and **C** devices as below.

```
* device instance $6 r0 *1 101.5,108.4 F_RS
R$6 4 3 2.83333333333 F_RS L=17U W=6U
* device instance $7 r0 *1 -7,100 F_RR
R$7 2 4 3 1.1 F_RR L=6.6U W=6U
* device instance $8 r90 *1 -46,18 F_CSIO
C$8 2 5 5 4.8735e-13 F_CSIO
```

So in LVS, Schematic netlist **reader** have to traslate **X..** to **C/R** device as front-end process. So new **reader** class was delegated from **NetlistSpiceReaderDelegate** as below.

```
# ----- ------ ----- ----- ------ ----- ----- ------ ----- 
# Translate Xres/cap to Rres or Ccap
# 
class MyDelegate < RBA::NetlistSpiceReaderDelegate
    def wants_subcircuit(name)
        name == "F_RR" || name == "F_RS" || name == "F_CSIO" 
    end
    #
    # translate the element from Xsubckt
    #
    def element(circuit, el, name, model, value, nets, params)
        #
        if el != "X"
            # all other elements are left to the standard implementation
            return super
        end
        # ----- ------ ----- 
        # provide a device class
        cls = circuit.netlist.device_class_by_name(model)
        # ----- ------ ----- 
        if ! cls && model == "F_RS" 
            cls = RBA::DeviceClassResistor::new
        elsif ! cls && model == "F_RR" 
            cls = RBA::DeviceClassResistorWithBulk::new
        elsif ! cls && model == "F_CSIO" 
            cls = RBA::DeviceClassCapacitorWithBulk::new
        end
        cls.name = model
        circuit.netlist.add(cls)
        # ----- ------ ----- 
        # create a device
        #
        device = circuit.create_device(cls, name)
        if nets.size == 2
            [ "A", "B" ].each_with_index do |t,index|
                device.connect_terminal(t, nets[index])
            end
        elsif nets.size == 3
            [ "A", "B", "W" ].each_with_index do |t,index|
            device.connect_terminal(t, nets[index])
            end
        else
            error("Subcircuit #{model} not enough nodes")
        end
        params.each do |p,value|    
            if p == "L" || p == "W"             # compare L/W * 1e6 
                device.set_parameter(p, value * 1e6)
            elsif p == "C"                      # compare C asis
                device.set_parameter(p, value)
            end
        end
    end
end
#
reader = RBA::NetlistSpiceReader::new(MyDelegate::new)
#
schematic(Sch_file, reader)
#
```

In the last, LVS comparison was executed.

```
align
#
compare
#
```