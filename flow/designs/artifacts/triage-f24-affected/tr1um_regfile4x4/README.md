# tr1um_regfile4x4 hierarchical macro bundle

Use `tr1um_regfile4x4.gds` and `tr1um_regfile4x4.lef` as the physical macro views. Use `tr1um_regfile4x4.blackbox.v` during parent synthesis. In xschem, place `tr1um_regfile4x4.sym` and add `.include tr1um_regfile4x4.strict.cir` to the parent SPICE netlist. For a hardened digital parent, pass the strict contract as an additional final argument to `flow/run_core_lvs.sh`. Supply net GND is normalized to VSS in the SPICE/LVS view.
