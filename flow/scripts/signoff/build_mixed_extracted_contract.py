from pathlib import Path
import os, shutil, subprocess
root=Path(__file__).resolve().parents[3]
physical=Path(os.environ['TR1UM_PHYSICAL_EXTRACTED'])
out=Path(os.environ['TR1UM_MIXED_LVS_CONTRACT'])
text=physical.read_text()
# This contract intentionally preserves the extracted hierarchy and is suitable
# for validation/debugging; the frame wrappers remain authoritative.
required=['tr_1um_mixed_counter','tr1um_counter_core','tr1um_counter_core$1','CMC_S_NMOS_B_X1_Y1','OSS_FRAME']
missing=[x for x in required if f'.SUBCKT {x} ' not in text and f'.SUBCKT {x}\n' not in text]
if missing: raise SystemExit(f'missing extracted circuits: {missing}')
out.parent.mkdir(parents=True,exist_ok=True);out.write_text('* Generated from current physical extraction.\n'+text)
print(out)
