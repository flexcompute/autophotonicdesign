"""The chip layout. The layout agent owns this file. The other agents only read it.

Requirements (tools/verify.py does a check of each one):
    build() -> pf.Component
      - The top-level optical ports and heater terminals have the names in spec.md (layout section of the numbers).
      - The chip is in layout.max_size. It is DRC clean and LVS clean on the PDK of the spec.
      - The chip has a CircuitModel, and each reference has a model. Then the post-layout circuit
        simulation runs on this computer. (tools/pdks/<pdk>.py: fast_models gives a model to the route pieces.)
      - Route the optical nets with tools/routing.py (one route_auto call, one LVS wire for each net).

Use PDK cells (tools/pdks/<pdk>.py: library). Use design/components/ only for new cells.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import photonforge as pf  # noqa: E402,F401


def build() -> "pf.Component":
    raise NotImplementedError("design/chip.py: the layout agent writes build()")
