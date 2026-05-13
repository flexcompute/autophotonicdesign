"""preview.py — Geometric / visual sanity check before any cloud call.

Reads `design.IMPLANTS` + `design.geometry()`, renders a 2-panel figure
(net doping log-scale + labeled implant boxes), and saves it to
`output/preview.png`. Optionally archives a per-experiment copy to
`output/previews/experiment_N.png`.

Usage:
    python preview.py          # no archive
    python preview.py 7        # archive as experiment_7.png
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from design import IMPLANTS, V_SWEEP, geometry, snapshot_header
from tools.viz import preview_figure


def main():
    geom = geometry()
    title = (
        f"PN doping preview  —  W_CORE={geom['w_core']:.3f} µm, "
        f"{len(IMPLANTS)} regions, V_SWEEP={V_SWEEP}"
    )
    fig = preview_figure(IMPLANTS, geom, title=title)

    os.makedirs("output", exist_ok=True)
    out_path = "output/preview.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved {out_path}")

    if len(sys.argv) > 1:
        os.makedirs("output/previews", exist_ok=True)
        archive = f"output/previews/experiment_{sys.argv[1]}.png"
        fig.savefig(archive, dpi=200, bbox_inches="tight")
        print(f"Saved {archive}")

    plt.close(fig)

    print("\n" + snapshot_header())
    print(f"\n  {'region':18s} {'kind':9s} {'N (cm⁻³)':>10s}  "
          f"{'y (µm)':>16s}  {'z (µm)':>16s}")
    print("  " + "-" * 74)
    for r in IMPLANTS:
        print(f"  {r.name:18s} {r.kind:9s} {r.concentration:10.2e}  "
              f"({r.ymin:+6.3f},{r.ymax:+6.3f})  "
              f"({r.zmin:+6.3f},{r.zmax:+6.3f})")


if __name__ == "__main__":
    main()
