"""view_pcells.py  ──  show the device library (the DUT PCells) in the LiveViewer (port 8765).

A vertical catalog of every device the DoE loop can pack, each labelled, so the PCells can be
inspected before launching the autonomous loop.
"""
import time
import sys
import pathlib
import warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

import photonforge as pf
from photonforge.live_viewer import LiveViewer
from tools import components as C, library

C.technology()
lib = library.default_library()

# (label, DUT) in catalog order; a couple of variants show the swept axes.
items = [
    ("straight  (width 0.5 um)", lib["straight"].instantiate(length=160, width=0.5)),
    ("straight  (width 2.0 um, tapered)", lib["straight"].instantiate(length=160, width=2.0)),
    ("spiral  (2000 um folded)", lib["spiral"].instantiate(length=2000)),
    ("directional coupler  (s-bend)", lib["dcoupler"].instantiate(coupling_gap=0.3, coupling_length=12)),
    ("crossing  (added_width 1.4 um)", lib["crossing"].instantiate(added_width=1.4, arm_length=6)),
    ("Y-branch  (ingested from GDS)", lib["ybranch_gds"].instantiate()),
    ("thermo-optic heater", lib["heater"].instantiate(length=200)),
    ("segmented-CPS modulator  (unbalanced MZI, 500 um)",
     lib["modulator"].instantiate(length=500, imbalance=30)),
]

show = pf.Component("PCell_Library")
gap, label_h = 70.0, 26.0
y = 0.0
try:
    from photonforge.stencil import as_component
except Exception:  # noqa: BLE001
    as_component = None
for label, dut in items:
    (x0, y0), (x1, y1) = dut.bounds()
    h = y1 - y0
    r = show.add_reference(dut)
    r.origin = (-x0, y - y1)            # left-align at x=0; top edge at y
    if as_component is not None:
        try:
            lbl = show.add_reference(as_component(layer="Text", stencil="text",
                                                  text_string=label, size=18.0))
            lbl.origin = (-x0, y + 8.0)
        except Exception:  # noqa: BLE001
            pass
    y -= (h + label_h + gap)

print(f"PCell library: {len(items)} devices")
viewer = LiveViewer(port=8765)
viewer(show)
while True:
    time.sleep(60)
