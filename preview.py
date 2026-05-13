"""
preview.py — Visualize the segmented-CPW geometry before paying for a 3-D run.

DO NOT MODIFY. The agent should only modify design.py.

Usage:
    python preview.py [experiment_number]

Outputs:
    output/preview.png             — multi-panel pre-sim view (always overwritten)
    output/previews/experiment N   — archived copy if N is provided
"""

from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import design
from design import (
    GW, WS, WG, G, TLN0, TLN1, TSIO21, TM, LTL, L_IN, L_OUT, P_T, W_CPW,
    create_simulation,
)


def _plot_top(sim, ax):
    """Top-down view of the metal plane — shows the T-rail repetition."""
    sim.plot(z=TLN0 - TLN1 + TSIO21 + TM / 2.0, ax=ax)
    ax.set_xlim(-(GW + WS), GW + WS)
    ax.set_ylim(-LTL / 2 - L_IN, LTL / 2 + L_OUT)
    ax.set_aspect(0.3)
    ax.set_title("Top view — metal plane")


def _plot_cross(sim, ax):
    """Cross-section at y=0 (mid-segmented section)."""
    sim.plot(y=0, ax=ax)
    ax.set_xlim(-(G + WS), G + WS)
    ax.set_ylim(-3.0, 5.0)
    ax.set_aspect(1.0)
    ax.set_title("Cross-section at y = 0")


def _plot_zoom(sim, ax):
    """Zoom on a single CPW gap to verify T-rail vertices/sidewalls/rib."""
    sim.plot(z=TLN0 - TLN1 + TSIO21 + TM / 2.0, ax=ax)
    x0 = (WS + GW) / 2.0
    ax.set_xlim(x0 - GW / 2.0 - 5, x0 + GW / 2.0 + 5)
    ax.set_ylim(-LTL / 2 - 5, -LTL / 2 + 3 * P_T + 5)
    ax.set_aspect(1.0)
    ax.set_title("Zoom — right gap, 3 unit cells")


def _plot_gap_grid(sim, ax):
    """Cross-section + grid in the active CPW gap (where the rib sits)."""
    sim.plot(y=0, ax=ax)
    sim.plot_grid(y=0, ax=ax,
                  hlim=(WS / 2 - 1, WS / 2 + GW + 1),
                  vlim=(-1.0, 2.5))
    ax.set_xlim(WS / 2 - 1, WS / 2 + GW + 1)
    ax.set_ylim(-1.0, 2.5)
    ax.set_aspect(1.0)
    ax.set_title("Active gap + grid (y=0)")


def main():
    sim = create_simulation()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    _plot_top(sim, axes[0, 0])
    _plot_cross(sim, axes[0, 1])
    _plot_zoom(sim, axes[1, 0])
    _plot_gap_grid(sim, axes[1, 1])
    fig.suptitle(f"Segmented CPW — {design.snapshot_header()}", fontsize=10)
    plt.tight_layout()

    os.makedirs("output", exist_ok=True)
    plt.savefig("output/preview.png", dpi=150, bbox_inches="tight")
    print("Saved output/preview.png")

    if len(sys.argv) > 1:
        os.makedirs("output/previews", exist_ok=True)
        name = f"output/previews/experiment {sys.argv[1]}.png"
        plt.savefig(name, dpi=200, bbox_inches="tight")
        print(f"Saved {name}")
    plt.close(fig)

    # Build summary
    print(f"  Simulation size : {tuple(round(s, 2) for s in sim.size)} μm")
    print(f"  Structures      : {len(sim.structures)}")
    print(f"  Monitors        : {len(sim.monitors)}")
    print(f"  T-rail period   : {P_T:.2f} μm")
    print(f"  Segmented length: {LTL:.2f} μm  (=> {round(LTL/P_T)} cells)")
    print(f"  Total y-span    : {LTL + L_IN + L_OUT:.2f} μm")
    print(f"  CPW span        : {W_CPW:.2f} μm")


if __name__ == "__main__":
    main()
