"""
preview.py — Render the projector circuit + bondpads with the current routing
strategy applied. Saves output/preview.svg. Free, no cloud spend, no DRC scoring.

Usage:
    python preview.py
"""
from __future__ import annotations

import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))


def main():
    from runners import run_manhattan, run_grid
    import design

    mode = design.get_mode()
    cfg = design.get_config()

    if mode == "manhattan_indep":
        run_manhattan(cfg, mode="indep")
    elif mode == "manhattan_seq":
        run_manhattan(cfg, mode="seq")
    elif mode == "grid":
        run_grid(cfg)
    else:
        raise SystemExit(f"Unknown MODE {mode!r}")

    # The runners have side-effected the circuit. Save it to SVG (PhotonForge
    # components don't expose matplotlib but they do export SVG cleanly).
    from projector_circuit_setup import projector_circuit

    out_dir = os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    svg_path = os.path.join(out_dir, "preview.svg")
    with open(svg_path, "w") as f:
        f.write(projector_circuit._repr_svg_())
    print(f"Saved {svg_path}")
    print(design.snapshot_header())


if __name__ == "__main__":
    main()
