"""
preview.py — Generate geometry preview plots before running a simulation.

Plots two slices:
  - xz cross-section at y = 0 (side view through the focal axis)
  - xy top view at z = 0.1 µm (through the grating teeth / tops of the 220 nm Si)

Usage:
    python preview.py [experiment_number]

Outputs:
    output/preview.png — always overwritten (agent inspects this)
    output/previews/experiment N.png — archived copy if experiment number given
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from design import create_simulation


def main():
    sim = create_simulation()

    fig, (ax_xz, ax_xy) = plt.subplots(1, 2, figsize=(18, 6))

    # Side view (xz) at y = 0
    sim.scene.plot_structures_eps(y=0, ax=ax_xz)
    sim.plot_sources(y=0, ax=ax_xz)
    sim.plot_monitors(y=0, ax=ax_xz)
    ax_xz.set_title("Side view (y = 0)")
    ax_xz.set_aspect("equal")

    # Top view (xy) at z = 0.1 µm — inside the 220 nm Si device layer, above
    # the slab-etch plane (z_slab_top = -0.11 + 0.15 = 0.04 µm), so this cut
    # shows tooth/gap structure and the strip waveguide.
    z_top = 0.1
    sim.scene.plot_structures_eps(z=z_top, ax=ax_xy)
    sim.plot_sources(z=z_top, ax=ax_xy)
    sim.plot_monitors(z=z_top, ax=ax_xy)
    ax_xy.set_title(f"Top view (z = {z_top} μm)")
    ax_xy.set_aspect("equal")

    plt.tight_layout()

    plt.savefig("output/preview.png", dpi=150, bbox_inches="tight")
    print("Saved output/preview.png")

    if len(sys.argv) > 1:
        import os

        os.makedirs("output/previews", exist_ok=True)
        name = f"output/previews/experiment {sys.argv[1]}.png"
        plt.savefig(name, dpi=300, bbox_inches="tight")
        print(f"Saved {name}")

    plt.close()

    print(f"  Simulation domain: {tuple(round(s, 2) for s in sim.size)} μm")
    print(f"  Structures: {len(sim.structures)}")
    print(f"  Sources: {len(sim.sources)}")
    print(f"  Monitors: {len(sim.monitors)}")


if __name__ == "__main__":
    main()
