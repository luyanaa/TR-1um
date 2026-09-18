# tr1um_uarttx_big hierarchical macro bundle

Use `tr1um_uarttx_big.gds` and `tr1um_uarttx_big.lef` as the physical macro views. Use `tr1um_uarttx_big.blackbox.v` during parent synthesis. In xschem, place `tr1um_uarttx_big.sym` and add `.include tr1um_uarttx_big.strict.cir` to the parent SPICE netlist. For a hardened digital parent, pass the strict contract as an additional final argument to `flow/run_core_lvs.sh`. Supply net GND is normalized to VSS in the SPICE/LVS view.
