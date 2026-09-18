# Chapter 1: `01_Extract.lvs`

[`01_Extract.lvs`](../../libs.tech/klayout/tech/lvs/01_Extract.lvs) contains
MOS, ESD-MOS, diode, and global-node extraction. The layer aliases come from
[`00_Layers.drc`](../../libs.tech/klayout/tech/drc/00_Layers.drc) and
[`02_Device.drc`](../../libs.tech/klayout/tech/drc/02_Device.drc). The older
`AAMP`/`AAMN`/`SGG`/`NWMP`/`SDMP` vocabulary is not the active contract.

## 5 V CMOS MOS devices

The active runset recognizes normal PMOS and NMOS devices from `MP`/`MN`,
with `WN` and `BULK` as their backgate regions. Their source/drain contacts
are `SDP` and `SDN`:

```ruby
extract_devices(mos4("PMOS"),
  { "SD" => (MP - GC),
    "G"  => (MP & GC),
    "W"  => (MP & GC & WN),
    "tS" => (SDP),
    "tD" => (SDP),
    "tG" => (GC),
    "tB" => (WN) })

tolerance("PMOS", "W", :relative => 0.01)
tolerance("PMOS", "L", :relative => 0.0)

extract_devices(mos4("NMOS"),
  { "SD" => (MN - GC),
    "G"  => (MN & GC),
    "W"  => (MN & GC & BULK),
    "tS" => (SDN),
    "tD" => (SDN),
    "tG" => (GC),
    "tB" => (BULK) })

tolerance("NMOS", "W", :relative => 0.01)
tolerance("NMOS", "L", :relative => 0.0)
```

## ESD MOS devices

ESD diffusion is separated by `MPE`/`MNE`; the corresponding source/drain
contact layers are `SDPE`/`SDNE`. The active runset uses `PMOS` for the ESD
PMOS extraction and `NMOSE` for the ESD NMOS extraction:

```ruby
extract_devices(mos4("PMOS"),
  { "SD" => (MPE - GC),
    "G"  => (MPE & GC),
    "W"  => (MPE & GC & WN),
    "tS" => (SDPE),
    "tD" => (SDPE),
    "tG" => (GC),
    "tB" => (WN) })

extract_devices(mos4("NMOSE"),
  { "SD" => (MNE - GC),
    "G"  => (MNE & GC),
    "W"  => (MNE & GC & BULK),
    "tS" => (SDNE),
    "tD" => (SDNE),
    "tG" => (GC),
    "tB" => (BULK) })
```

`NMOSE` has the same 1% width and exact-length tolerance policy as the active
source. ESD protection behavior is not inferred from a device name alone;
placement and pad discharge paths remain separate signoff contracts.

## Diodes

`DP` and `DN` are intrinsic extracted devices. Their active terminal mappings
are:

```ruby
extract_devices(diode("DP"),
  { "P"  => (DP),
    "N"  => (DP & WN),
    "tA" => (DP),
    "tC" => (WN) })

tolerance("DP", "A", :relative => 0.05)
tolerance("DP", "P", :relative => 0.05)

extract_devices(diode("DN"),
  { "P"  => (DN & BULK),
    "N"  => (DN),
    "tA" => (BULK),
    "tC" => (DN) })

tolerance("DN", "A", :relative => 0.05)
tolerance("DN", "P", :relative => 0.05)
```

## Global nodes

The active source declares the well and substrate globals explicitly:

```ruby
connect_global(BULK, "VSS")
connect_global(WN,   "VDD")
```

The additional `GN` substrate-contact connection in `02_Extract.lvs` is
covered in Chapter 3. Do not replace these explicit power contracts with a
single historical `connect_global(BULK, ...)` example.
