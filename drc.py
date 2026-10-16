"""
drc.py — Design Rule Check using KLayout.

DO NOT MODIFY. The agent should only modify design.py.

Usage:
    python drc.py

Exits 0 if DRC passes, 1 if violations found.
On failure, saves output/drc.png showing violation locations.
"""

import sys

import klayout.db as pya

from design import create_simulation

# Must match the constraint in program.md
MIN_WIDTH_UM = 0.15  # 150 nm minimum width
MIN_SPACE_UM = 0.15  # 150 nm minimum spacing

GDS_PATH = "output/layout.gds"


def run_drc(sim):
    """Export simulation to GDS and run width/space checks.

    Returns (width_violations, space_violations, layout, dbu).
    """
    sim.to_gds_file(fname=GDS_PATH, z=0, gds_cell_name="MAIN")

    layout = pya.Layout()
    layout.read(GDS_PATH)

    cell = layout.top_cell()
    dbu = layout.dbu

    min_width_dbu = int(MIN_WIDTH_UM / dbu)
    min_space_dbu = int(MIN_SPACE_UM / dbu)

    # Merge all layers (all exported structures are silicon)
    region = pya.Region()
    for li in layout.layer_indices():
        region += pya.Region(cell.begin_shapes_rec(li))
    region.merge()

    width_violations = region.width_check(min_width_dbu)
    space_violations = region.space_check(min_space_dbu)

    return width_violations, space_violations, dbu


def print_violations(width_violations, space_violations, dbu):
    """Print violation details in human-readable coordinates (μm)."""
    for i in range(width_violations.size()):
        ep = width_violations[i]
        e1, e2 = ep.first, ep.second
        print(
            f"  Width: ({e1.p1.x*dbu:.3f}, {e1.p1.y*dbu:.3f})-"
            f"({e1.p2.x*dbu:.3f}, {e1.p2.y*dbu:.3f}) <-> "
            f"({e2.p1.x*dbu:.3f}, {e2.p1.y*dbu:.3f})-"
            f"({e2.p2.x*dbu:.3f}, {e2.p2.y*dbu:.3f})"
        )
    for i in range(space_violations.size()):
        ep = space_violations[i]
        e1, e2 = ep.first, ep.second
        print(
            f"  Space: ({e1.p1.x*dbu:.3f}, {e1.p1.y*dbu:.3f})-"
            f"({e1.p2.x*dbu:.3f}, {e1.p2.y*dbu:.3f}) <-> "
            f"({e2.p1.x*dbu:.3f}, {e2.p1.y*dbu:.3f})-"
            f"({e2.p2.x*dbu:.3f}, {e2.p2.y*dbu:.3f})"
        )


def save_violation_plot(sim, width_violations, space_violations, dbu):
    """Save a plot of the device with violation locations marked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    fig, ax = plt.subplots(figsize=(10, 5))
    sim.scene.plot_structures_eps(z=0, ax=ax)
    sim.plot_sources(z=0, ax=ax)

    for violations, color, label in [
        (width_violations, "red", f"Width violations ({width_violations.size()})"),
        (space_violations, "blue", f"Space violations ({space_violations.size()})"),
    ]:
        lines = []
        for i in range(violations.size()):
            ep = violations[i]
            for edge in [ep.first, ep.second]:
                x1, y1 = edge.p1.x * dbu, edge.p1.y * dbu
                x2, y2 = edge.p2.x * dbu, edge.p2.y * dbu
                lines.append([(x1, y1), (x2, y2)])
        if lines:
            lc = LineCollection(lines, colors=color, linewidths=2, label=label)
            ax.add_collection(lc)

    ax.legend()
    ax.set_aspect("equal")
    ax.set_title("DRC Violations")
    plt.tight_layout()
    plt.savefig("output/drc.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved output/drc.png")


def main():
    sim = create_simulation()
    width_violations, space_violations, dbu = run_drc(sim)

    n_width = width_violations.size()
    n_space = space_violations.size()

    print(f"Width violations: {n_width}")
    print(f"Space violations: {n_space}")

    if n_width == 0 and n_space == 0:
        print("DRC PASSED")
        return 0

    print_violations(width_violations, space_violations, dbu)
    save_violation_plot(sim, width_violations, space_violations, dbu)
    print("DRC FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
