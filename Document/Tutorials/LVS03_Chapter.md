# Chapter 3: passive extraction and device combination

[`02_Extract.lvs`](../../libs.tech/klayout/tech/lvs/02_Extract.lvs) defines the
active CSIO, RR, and RS extraction contracts. The model names below are the
same names consumed by [`04_Custom.lvs`](../../libs.tech/klayout/tech/lvs/04_Custom.lvs).

## CSIO capacitor

The active CSIO extractor uses `GC` as the top plate, `AC` as the bottom
plate, `WC` as the well plate, and `BULK` as the bulk terminal:

```ruby
class LWCapacitorWithBulk < RBA::DeviceClassCapacitorWithBulk
  def initialize
    super
    enable_parameter("A", true)
    enable_parameter("P", true)
    add_parameter(RBA::DeviceParameterDefinition.new('W', 'Width', 0, false))
    add_parameter(RBA::DeviceParameterDefinition.new('L', 'Length', 0, false))
    add_parameter(RBA::DeviceParameterDefinition.new('m', 'multiplier', 1, true))
    enable_parameter("m", true)
    self.combiner = CAPDeviceCombiner.new
    self.supports_serial_combination = false
    self.supports_parallel_combination = true
    clear_equivalent_terminal_ids
  end
end

extract_devices(capacitor_with_bulk("F_CSIO", 0.6e-15, LWCapacitorWithBulk),
  { "P1" => (GC),
    "P2" => (AC),
    "W"  => (WC),
    "tA" => (GC),
    "tB" => (WC),
    "tW" => (BULK) })

tolerance("F_CSIO", "A", :relative => 0.01)
tolerance("F_CSIO", "P", :relative => 0.01)
ignore_parameter("F_CSIO", "C")
ignore_parameter("F_CSIO", "W")
ignore_parameter("F_CSIO", "L")
```

The `C` model parameter is intentionally ignored for LVS; area/perimeter are
the active structural comparison parameters. The voltage-dependent compact
model remains a circuit-simulation concern.

## RR and RS resistors

`LWResistor` and `LWResistorWithBulk` enable `W`, `L`, and multiplier
comparison. The active recognition mappings are:

```ruby
class LWResistor < RBA::DeviceClassResistor
  def initialize
    super
    enable_parameter("W", true)
    enable_parameter("L", true)
    add_parameter(RBA::DeviceParameterDefinition.new('m', 'multiplier', 1, true))
    enable_parameter("m", true)
    self.combiner = RESDeviceCombiner.new
    self.supports_serial_combination = true
    self.supports_parallel_combination = true
  end
end

class LWResistorWithBulk < RBA::DeviceClassResistorWithBulk
  def initialize
    super
    enable_parameter("W", true)
    enable_parameter("L", true)
    add_parameter(RBA::DeviceParameterDefinition.new('m', 'multiplier', 1, true))
    enable_parameter("m", true)
    self.combiner = RESDeviceCombiner.new
    self.supports_serial_combination = true
    self.supports_parallel_combination = true
  end
end

extract_devices(resistor("F_RS", 1, LWResistor),
  { "R" => (RS), "C" => (RSC), "tA" => (RSC), "tB" => (RSC) })

extract_devices(resistor_with_bulk("F_RR", 1, LWResistorWithBulk),
  { "R" => (RR), "C" => (ARC), "W" => (AR),
    "tA" => (ARC), "tB" => (ARC), "tW" => (WR) })

tolerance("F_RS", "W", :relative => 0.01)
tolerance("F_RS", "L", :relative => 0.01)
ignore_parameter("F_RS", "R")
tolerance("F_RR", "W", :relative => 0.01)
tolerance("F_RR", "L", :relative => 0.01)
ignore_parameter("F_RR", "R")
equivalent_pins("F_RS", "A", "B")
equivalent_pins("F_RR", "A", "B")
```

The supported RR widths are classified in `02_Device.drc` as 2.8, 4, 6, 12,
and 20 um. The model parser and runtime branches must agree with these
values; LVS itself compares the extracted `W`/`L` contract rather than the
compact-model resistance value.

## Combiner contract (reference-only)

[`03_Combiner.lvs`](../../libs.tech/klayout/tech/lvs/03_Combiner.lvs) is an
active include but has no standalone tutorial fixture. Its behavior is:

- `CAPDeviceCombiner` combines parallel `F_CSIO` devices only when A/P and
  all A/B/W nets match; it sums `m` and disconnects the second device.
- `RESDeviceCombiner` first requires matching substrate nets for three-terminal
  devices. Parallel resistors require matching `W` and `L` and matching or
  swapped A/B nets; it sums `m`. Series resistors require matching `W` and
  `m`, exactly one shared node, and sum `L`.
- A second device is never silently merged when the net topology is ambiguous;
  the combiner returns false instead.

This is a structural reference contract, not a qualified analog equivalence
claim. A future regression fixture should exercise parallel/series cases
through the active KLayout runset before this section is treated as a tested
signoff guarantee.
