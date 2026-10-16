"""Show design/chip.py in the PhotonForge LiveViewer (http://localhost:8765). Restart after a code change.

    lsof -ti:8765 | xargs kill -9; python tools/view.py &      # then open http://localhost:8765
"""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import noclouds  # noqa: F401,E402
from tools.measure import load_design  # noqa: E402
from photonforge.live_viewer import LiveViewer  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--design", default=None)
ap.add_argument("--port", type=int, default=8765)
a = ap.parse_args()
chip = load_design(a.design).build()
viewer = LiveViewer(port=a.port)
viewer(chip)
print(f"LiveViewer on http://localhost:{a.port}", flush=True)
while True:
    time.sleep(60)
