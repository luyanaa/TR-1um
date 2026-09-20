* TR10-1 exact OpenRule1um source-level integrated DCDC/VCO reference.
.include "/Users/yanlu/Documents/TR-1um/analysis/tr10_rcx_vco/final_characterization/openrule1um_dcdc/dcdc_down_full_tb.clean.sp"
XTB dcdc_down_full_tb
.control
set noaskquit
tran 1n 100u
wrdata /Users/yanlu/Documents/TR-1um/analysis/tr10_rcx_vco/final_characterization/openrule1um_dcdc/integrated_openrule1um_vctrl_5V/wave.txt v(xtb.vout) v(xtb.net2)
.endc
.end
