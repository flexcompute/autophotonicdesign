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


def make_sim(tip_width, taper_power):
    xs = np.linspace(0.0, TAPER_LENGTH, 101)
    widths = tip_width + (WG_WIDTH - tip_width) * (xs / TAPER_LENGTH) ** taper_power
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
    tips = [0.200, 0.205, 0.210]
    powers = [2.25, 2.35, 2.50]
    sims = {
        f"tip{int(round(tip*1000)):03d}_p{power:.2f}": make_sim(tip, power)
        for tip in tips
        for power in powers
    }
    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore9_high_power",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} high-power taper candidates")
    data = batch.run(path_dir="output/explore9_high_power")

    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")

    rows.sort(reverse=True)
    Path("output/explore9_high_power_results.tsv").write_text(
        "rank\tname\tmetric\n"
        + "\n".join(
            f"{rank}\t{name}\t{metric:.9f}"
            for rank, (metric, name) in enumerate(rows, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nBest candidates")
    for rank, (metric, name) in enumerate(rows[:5], start=1):
        print(f"{rank}. {name}: {metric:.9f}")


if __name__ == "__main__":
    main()
