# TR-1um 24-character UART transmitter

This macro continuously transmits `SYMBIOTIC@YG@CKDUR@ROBIN@@@@@@@@` at 115200
baud from a 14.7456 MHz input clock. Each byte occupies sixteen baud slots
(start, eight data, stop, and six idle slots). The 24-character message is
followed by eight `@` characters, so one cycle naturally occupies 32 character
times.

The RTL uses one free-running 16-bit counter. Message characters are stored as
five-bit alphabet codes (`A=1` through `Z=26`, `@` is zero), and only the
current ASCII output bit is decoded. ASCII bits 5 and 6 are constants for both
uppercase letters and `@`. There is no shift register, character register,
modulo-24 rewind comparator, reduction operator, or unused-slot gate.

The physical target is 1000 by 1000 um in seven site-aligned rows with 10 um
horizontal cell gaps. The core is [50, 75.6]-[950, 982.8] um, retaining a
50 um side margin for ordinary pin access instead of extending the core to the
die boundary. Five row intervals retain an empty 75.6 um site row; the final
pair is adjacent, putting the cell stack between y=75.6 and 982.8 um.
`manual_place_access.tcl` uses an exact linear partition to balance contiguous
synthesis-order groups, keeping related logic nearby, and applies small
track-relative row offsets. Synthesis contains 103 cells: 102 logic/sequential
cells plus one physical TIELO. The extracted transistor hierarchy contains the
102 functional cells after the design-local TIELO metal is merged into VSS.
The powered route is about 89.9 mm long. `postprocess_gds.py` joins all
rectangular WN bands into one common WN region. These customizations are local
to this design.

The powered routing stage uses a generated run-local technology LEF with a
2.1 um M2 spacing margin (versus the 2.0 um drawing rule). This avoids
router/stream-out correlation errors without modifying the PDK or the final
GDS rules. `power_channels.json` places each row's M1 buses only 4.0 um from
the GND/VDD pin centerline, places the GND trunk at x=54 um, and uses a 50 um
right-edge inset for VDD. All cell supplies are connected through these M1
channels.

From the LibreLane development shell, run:

```bash
./flow/designs/run_digital_tests.sh \
  --tag uart-big-1000x1000-run tr1um_uarttx_big
```

The verified hierarchical bundle is written below
`flow/designs/artifacts/<tag>/tr1um_uarttx_big/`. It contains GDS, LEF,
powered gate-level Verilog, black-box Verilog, xschem symbol, and the strict
SPICE/LVS contract. `clk` is on the west edge, `tx` on the east edge, and both
supplies are on the south edge.

The qualified reference run is `uart-big-generic-signoff-3`: OpenROAD detailed
routing has zero violations, KLayout drawing DRC has zero hard items, all 102
extracted instances connect to top-level VDD/VSS, and strict LVS matches. The
official `run_IP62.drc` deck, run with
`TR1UM_OFFICIAL_EDA_IMAGE=<official-ip62-docker-image>`, also reports zero
items. Strict extraction preserves the seven-terminal DFFR model and all 16
RST terminals are connected to VSS through the routed TIELO net.

Timing constraints remain deliberately relaxed because the current TR-1um
Liberty data is placeholder characterization. DRC/LVS success is not timing,
IR-drop, electromigration, or frame/pad signoff.
