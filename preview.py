"""
preview.py — Generate geometry preview plot before running a simulation.

DO NOT MODIFY. The agent should only modify design.py.

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

    fig, ax = plt.subplots(figsize=(10, 5))
    sim.scene.plot_structures_eps(z=0, ax=ax)
    sim.plot_sources(z=0, ax=ax)
    sim.plot_monitors(z=0.001, ax=ax)
    ax.set_title("Top view (z = 0)")
    ax.set_aspect("equal")
    plt.tight_layout()

    # Always save to the standard location
    plt.savefig("output/preview.png", dpi=150, bbox_inches="tight")
    print("Saved output/preview.png")

    # Archive a copy if experiment number is provided
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
