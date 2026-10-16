"""The chip. The layout agent owns this file; the others read it.

Contract (tools/verify.py checks it):
    build() -> pf.Component
      - top-level optical ports and heater terminals named as in spec.yaml (layout section)
      - fits layout.max_size; DRC clean and LVS clean on the spec's PDK
      - a CircuitModel on the chip, and a model on every reference, so post-layout circuit
        simulation runs offline (tools/pdks/<pdk>.py: fast_models gives route pieces analytic models)
      - route optical nets with tools/routing.py (one route_auto call, added per net), so LVS sees
        one wire per net

Build from PDK cells (tools/pdks/<pdk>.py: library) and from design/components/ for new cells.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import photonforge as pf  # noqa: E402,F401


def build() -> "pf.Component":
    raise NotImplementedError("design/chip.py: the layout agent writes build()")
