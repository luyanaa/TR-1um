# Compare: `04_Custom.lvs` and `05_Compare.lvs`

The active comparison flow is split between
[`04_Custom.lvs`](../../libs.tech/klayout/tech/lvs/04_Custom.lvs) and
[`05_Compare.lvs`](../../libs.tech/klayout/tech/lvs/05_Compare.lvs). The
historical delegate example in this chapter was incomplete: it did not cover
the active parameter conversion, writer prefixes, explicit file overrides,
finite standard-cell flattening, or strict top-level ports.

## Input files

`05_Compare.lvs` accepts explicit paths through KLayout runtime variables:

```ruby
if $extracted
  Lay_file = $extracted
else
  Lay_file = source.cell_name + ".extracted"
end

if $circuit
  Sch_file = $circuit
else
  Sch_file = "simulation/" + source.cell_name + ".spice"
end
```

The extracted layout netlist and schematic are therefore not required to use
only the historical `<cell>.extracted` and `<cell>.cir` names. Pass
`-rd extracted=... -rd circuit=...` when the release artifact names differ.

## Schematic reader translation

The schematic contains `X` instances for `F_RR`, `F_RS`, and `F_CSIO`, while
the extracted netlist contains resistor/capacitor device records. The active
`MyReader` handles exactly those three subcircuits:

```ruby
class MyReader < RBA::NetlistSpiceReaderDelegate
  def wants_subcircuit(name)
    name == "F_RR" || name == "F_RS" || name == "F_CSIO"
  end

  def element(circuit, el, name, model, value, nets, params)
    return super if el != "X"

    cls = circuit.netlist.device_class_by_name(model)
    if !cls
      cls = LWResistor.new if model == "F_RS"
      cls = LWResistorWithBulk.new if model == "F_RR"
      cls = LWCapacitorWithBulk.new if model == "F_CSIO"
      cls.name = model
      circuit.netlist.add(cls)
    end

    device = circuit.create_device(cls, name)
    if nets.size == 2
      ["A", "B"].each_with_index do |terminal, index|
        device.connect_terminal(terminal, nets[index])
      end
    elsif nets.size == 3
      ["A", "B", "W"].each_with_index do |terminal, index|
        device.connect_terminal(terminal, nets[index])
      end
    else
      error("Subcircuit #{model} not enough nodes")
    end

    params.each do |parameter, value|
      case parameter
      when "L", "W" then device.set_parameter(parameter, value * 1e6)
      when "A"      then device.set_parameter(parameter, value * 1e12)
      when "P"      then device.set_parameter(parameter, value * 1e6)
      when "C"      then device.set_parameter(parameter, value)
      when "M"      then device.set_parameter("m", value)
      end
    end
  end
end
```

The full implementation is authoritative. It maps `L/W` to micrometers,
`A` to square-micrometers, `P` to micrometers, preserves `C`, and maps the
schematic `M` parameter to the extracted lowercase `m` parameter.

## Extracted-netlist writer

Before comparison, the active flow writes the extracted netlist with
`MyWriter`:

```ruby
writer = RBA::NetlistSpiceWriter.new(MyWriter.new)
writer.use_net_names = true
target_netlist(Lay_file, writer, "Created by KLayout")
```

The writer uses prefixes that remain parseable on a second SPICE read:

```ruby
PREFIX_MAP = {
  "NMOS" => "M", "NMOSE" => "M", "PMOS" => "M",
  "DP" => "D", "F_CSIO" => "XC", "F_RR" => "XR", "F_RS" => "XR"
}
```

This is why an extracted resistor is emitted as `XR... F_RR/F_RS` and an
extracted CSIO as `XC... F_CSIO`, rather than as an opaque generated prefix.

## Finite standard-cell flattening

The active flow flattens the finite standard-cell boundary before comparison:

```ruby
["AND4_X1", "DFFR", "NAND2", "NAND3", "XNOR2", "XOR2"].each do |cell|
  schematic.flatten_circuit(cell)
  netlist.flatten_circuit(cell)
end
```

This is an explicit interoperability boundary, not a request to flatten the
entire design hierarchy.

## Strict top-level comparison

The default is strict top-level port checking. The opt-out is explicit:

```ruby
if IGNORE_TOP_PORTS_MISMATCH
  success = compare
else
  compare_result = compare
  port_check_result = flag_missing_ports
  success = compare_result && port_check_result
end
```

A successful device comparison with a missing, extra, or misnamed top-level
port is therefore a failure unless `ignore_top_ports_mismatch` was deliberately
set. The final result emits `INFO : Congratulations! Netlists match.` only
when the selected comparison mode succeeds.
