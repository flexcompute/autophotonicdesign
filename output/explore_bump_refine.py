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


TIP = 0.21
POWER = 2.25


def make_sim(mid_bump, late_bump):
    xs = np.linspace(0.0, TAPER_LENGTH, 141)
    t = xs / TAPER_LENGTH
    base = t**POWER
    g_mid = np.exp(-((t - 0.45) / 0.18) ** 2)
    g_late = np.exp(-((t - 0.78) / 0.14) ** 2)
    s = base * (1.0 + mid_bump * g_mid + late_bump * g_late)
    s /= s[-1]
    if np.any(np.diff(s) < -1e-6) or np.min(s) < -1e-9 or np.max(s) > 1.02:
        return None
    widths = TIP + (WG_WIDTH - TIP) * s
    vertices = [(float(x), float(w / 2)) for x, w in zip(xs, widths)]
    vertices += [(float(x), float(-w / 2)) for x, w in zip(xs[::-1], widths[::-1])]
    taper = td.Structure(
        geometry=td.PolySlab(
            vertices=vertices,
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )
    return td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=18, wavelength=WAVELENGTH),
        structures=[si_substrate, chip_sio2, taper, output_waveguide],
        sources=[source],
        monitors=monitors,
        run_time=4e-12,
        medium=Air,
        symmetry=(0, -1, 0),
    )


def safe_name(mid, late):
    return f"bref_m{mid:+.2f}_l{late:+.2f}".replace("+", "p").replace("-", "n")


def main():
    mids = [-0.34, -0.28, -0.22, -0.18, -0.14]
    lates = [-0.02, 0.06, 0.14, 0.22, 0.30]
    sims = {}
    for mid in mids:
        for late in lates:
            sim = make_sim(mid, late)
            name = safe_name(mid, late)
            if sim is None:
                print(f"{name} SKIP nonmonotonic")
                continue
            sims[name] = sim

    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore12_bump_refine",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} refined bump candidates")
    data = batch.run(path_dir="output/explore12_bump_refine")

    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")

    rows.sort(reverse=True)
    Path("output/explore12_bump_refine_results.tsv").write_text(
        "rank\tname\tmetric\n"
        + "\n".join(
            f"{rank}\t{name}\t{metric:.9f}"
            for rank, (metric, name) in enumerate(rows, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nBest candidates")
    for rank, (metric, name) in enumerate(rows[:8], start=1):
        print(f"{rank}. {name}: {metric:.9f}")


if __name__ == "__main__":
    main()
