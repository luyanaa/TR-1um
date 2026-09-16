# tr1um_busdecode

This is one of the generic TR-1um RTL-to-GDS-to-LVS regression designs.
It uses only synthesizable RTL and the checked-in TR-1um standard cells.

Run the RTL test with `make -C src`. From the LibreLane nix shell, harden it
with `./flow/run_librelane_tr1um_access.sh flow/designs/tr1um_busdecode/config_access.yaml
--run-tag generic-1`. Then run strict connected-power signoff with
`./flow/run_digital_core_flow.sh <run-directory> tr1um_busdecode`.
