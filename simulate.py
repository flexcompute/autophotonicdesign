"""
simulate.py — Fixed evaluation harness for photonic device auto-design.

DO NOT MODIFY. The agent should only modify design.py.

Usage:
    python simulate.py > output/run.log 2>&1
"""

import sys
import time
import traceback


def plot_fields(sim_data):
    """Save field plots if a field monitor named 'field_xy' exists."""
    try:
        sim_data["field_xy"]
    except KeyError:
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    sim_data.plot_field("field_xy", "Hz", "real", ax=axes[0])
    axes[0].set_title("Hz (real)")

    sim_data.plot_field("field_xy", "E", "abs", ax=axes[1])
    axes[1].set_title("|E|")

    plt.tight_layout()
    plt.savefig("output/field.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved output/field.png")


def main():
    start = time.time()

    try:
        import tidy3d.web as web
        from design import create_simulation, evaluate

        # Build
        print("=== Building simulation ===")
        sim = create_simulation()
        print(f"  structures : {len(sim.structures)}")
        print(f"  monitors   : {len(sim.monitors)}")
        print(f"  sim size   : {tuple(round(s, 2) for s in sim.size)} μm")
        print(f"  run time   : {sim.run_time:.2e} s")

        # Run on Tidy3D cloud
        print("\n=== Submitting to Tidy3D ===")
        sim_data = web.run(sim, task_name="autodesign", path="output/sim_data/latest.hdf5")

        # Evaluate
        print("\n=== Results ===")
        result = evaluate(sim_data)

        # Support both dict and scalar return from evaluate()
        if isinstance(result, dict):
            for key, value in result.items():
                print(f"{key}: {value}")
        else:
            print(f"metric: {result}")

        elapsed = time.time() - start
        print(f"wall_time_s: {elapsed:.1f}")

        # Plot field intensity if monitor exists
        plot_fields(sim_data)

    except Exception:
        elapsed = time.time() - start
        print(f"\nCRASH after {elapsed:.1f}s", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
