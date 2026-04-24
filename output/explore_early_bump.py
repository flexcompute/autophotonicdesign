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


def make_sim(early_bump, early_center):
    xs = np.linspace(0.0, TAPER_LENGTH, 141)
    t = xs / TAPER_LENGTH
    base = t**2.20
    g_early = np.exp(-((t - early_center) / 0.10) ** 2)
    g_mid = np.exp(-((t - 0.52) / 0.18) ** 2)
    g_late = np.exp(-((t - 0.72) / 0.14) ** 2)
    s = base * (1.0 + early_bump * g_early - 0.46 * g_mid + 0.18 * g_late)
    s /= s[-1]
    if np.any(np.diff(s) < -1e-6) or np.min(s) < -1e-9 or np.max(s) > 1.02:
        return None
    widths = 0.20 + (WG_WIDTH - 0.20) * s
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


def main():
    amps = [-0.30, -0.15, 0.0, 0.15, 0.30]
    centers = [0.20, 0.30, 0.40]
    sims = {}
    for amp in amps:
        for center in centers:
            name = f"eb_a{amp:+.2f}_c{int(center*100):02d}".replace("+", "p").replace("-", "n")
            sim = make_sim(amp, center)
            if sim is None:
                print(f"{name} SKIP nonmonotonic")
                continue
            sims[name] = sim
    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore20_early_bump",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} early-bump candidates")
    data = batch.run(path_dir="output/explore20_early_bump")
    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")
    rows.sort(reverse=True)
    Path("output/explore20_early_bump_results.tsv").write_text(
        "rank\tname\tmetric\n"
        + "\n".join(
            f"{rank}\t{name}\t{metric:.9f}"
            for rank, (metric, name) in enumerate(rows, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nBest candidates")
    for rank, (metric, name) in enumerate(rows, start=1):
        print(f"{rank}. {name}: {metric:.9f}")


if __name__ == "__main__":
    main()
