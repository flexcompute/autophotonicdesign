from pathlib import Path
import sys

import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import (
    Air,
    TAPER_LENGTH,
    WG_WIDTH,
    WAVELENGTH,
    Z_SIN_BOT,
    Z_SIN_TOP,
    chip_sio2,
    evaluate,
    monitors,
    output_waveguide,
    si_substrate,
    sim_box,
    source,
    SiN,
)


CTRL_X = np.array([0.0, 5.0, 15.0, 30.0, 42.0, TAPER_LENGTH])


def smooth_widths(ctrl_w, npts=151):
    xs = np.linspace(0.0, TAPER_LENGTH, npts)
    widths = np.empty_like(xs)
    for i in range(len(CTRL_X) - 1):
        lo, hi = CTRL_X[i], CTRL_X[i + 1]
        mask = (xs >= lo) & (xs <= hi)
        t = (xs[mask] - lo) / (hi - lo)
        ease = 0.5 - 0.5 * np.cos(np.pi * t)
        widths[mask] = ctrl_w[i] + (ctrl_w[i + 1] - ctrl_w[i]) * ease
    return xs, widths


def make_taper(ctrl_w):
    xs, widths = smooth_widths(ctrl_w)
    top = [(float(x), float(w / 2)) for x, w in zip(xs, widths)]
    bottom = [(float(x), float(-w / 2)) for x, w in zip(xs[::-1], widths[::-1])]
    return td.Structure(
        geometry=td.PolySlab(
            vertices=top + bottom,
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )


def make_sim(ctrl_w):
    return td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=18, wavelength=WAVELENGTH),
        structures=[si_substrate, chip_sio2, make_taper(ctrl_w), output_waveguide],
        sources=[source],
        monitors=monitors,
        run_time=4e-12,
        medium=Air,
        symmetry=(0, -1, 0),
    )


def random_controls(seed=23, count=20):
    rng = np.random.default_rng(seed)
    controls = []
    # Current best power-law taper, sampled at the control points.
    current = 0.20 + (WG_WIDTH - 0.20) * (CTRL_X / TAPER_LENGTH) ** 1.85
    controls.append(current)
    for _ in range(count - 1):
        w5 = rng.uniform(0.20, 0.27)
        w15 = rng.uniform(max(w5 + 0.02, 0.25), 0.42)
        w30 = rng.uniform(max(w15 + 0.05, 0.43), 0.72)
        w42 = rng.uniform(max(w30 + 0.08, 0.68), 0.95)
        controls.append(np.array([0.20, w5, w15, w30, w42, 1.00]))
    return controls


def main():
    controls = random_controls()
    sims = {f"spline{i:02d}": make_sim(ctrl) for i, ctrl in enumerate(controls)}
    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore4_spline",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} spline profile candidates")
    for i, ctrl in enumerate(controls):
        print(f"spline{i:02d} controls " + " ".join(f"{w:.4f}" for w in ctrl))

    data = batch.run(path_dir="output/explore4_spline")
    metrics = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        idx = int(name.replace("spline", ""))
        metrics.append((metric, name, controls[idx]))
        print(f"{name}\t{metric:.9f}")

    metrics.sort(reverse=True, key=lambda row: row[0])
    lines = ["rank\tname\tmetric\tw0\tw5\tw15\tw30\tw42\tw50"]
    for rank, (metric, name, ctrl) in enumerate(metrics, start=1):
        lines.append(
            f"{rank}\t{name}\t{metric:.9f}\t"
            + "\t".join(f"{w:.6f}" for w in ctrl)
        )
    Path("output/explore4_spline_results.tsv").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\nBest candidates")
    for rank, (metric, name, ctrl) in enumerate(metrics[:5], start=1):
        ctrl_s = " ".join(f"{w:.4f}" for w in ctrl)
        print(f"{rank}. {name}: {metric:.9f} controls {ctrl_s}")


if __name__ == "__main__":
    main()
