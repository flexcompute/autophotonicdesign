"""view_doe.py  ──  serve a representative packed DoE die in the LiveViewer (port 8765).

Builds a mid-fill packed chip from the current plan (blackboard/doe_plan.json) and shows it, so you
can pan/zoom the same-direction layout. Set PF_MULT to change the replicate multiplier (fill).
"""
import os
import sys
import time
import json
import pathlib
import warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from photonforge.live_viewer import LiveViewer
from tools import components, library, test_structures, floorplan

VIEWER_PORT = 8765
MULT = int(os.environ.get("PF_MULT", "8"))

components.technology()
lib = library.default_library()
plan = json.loads((ROOT / "blackboard" / "doe_plan.json").read_text())
structs, _ = test_structures.build_from_plan(plan, lib, replicates=MULT)
chip, m = floorplan.pack_into_die(
    structs, die_w=plan["die"]["DIE_W"], die_h=plan["die"]["DIE_H"],
    gap=plan.get("pack", {}).get("GAP", 20.0), method="blsf", sorting="area",
    allow_rotation=False)
print(f"packed {m['n_placed']} structures on "
      f"{plan['die']['DIE_W']/1000:.0f}x{plan['die']['DIE_H']/1000:.0f}mm "
      f"(fill {m['fill_fraction']*100:.0f}%), allow_rotation=False")

viewer = LiveViewer(port=VIEWER_PORT)
viewer(chip)
while True:
    time.sleep(60)
