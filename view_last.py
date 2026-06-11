"""view_last.py  ──  serve the LAST archived loop step in the LiveViewer (port 8765).

Loads the most recent output/experiments/NNNN/chip.gds (the final, void-filled packed die) so you
can pan/zoom the real result and read the Text-layer probe codes. Set PF_STEP=NN to view a
specific step instead of the last one.
"""
import os
import sys
import glob
import time
import pathlib
import warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import photonforge as pf
from photonforge.live_viewer import LiveViewer
from tools import components

components.technology()
exp_dir = ROOT / "output" / "experiments"
step = os.environ.get("PF_STEP")
if step is not None:
    gds = exp_dir / f"{int(step):04d}" / "chip.gds"
else:
    gds = sorted(glob.glob(str(exp_dir / "*" / "chip.gds")))[-1]
print(f"loading {gds}")
comps = pf.load_layout(str(gds))
try:
    chip = pf.find_top_level(*comps.values())[0]
except Exception:  # noqa: BLE001
    chip = max(comps.values(), key=lambda c: c.bounds()[1][0] - c.bounds()[0][0])
(x0, y0), (x1, y1) = chip.bounds()
print(f"top cell '{chip.name}'  {x1-x0:.0f} x {y1-y0:.0f} um  refs={len(chip.references)}")

viewer = LiveViewer(port=8765)
viewer(chip)
while True:
    time.sleep(60)
