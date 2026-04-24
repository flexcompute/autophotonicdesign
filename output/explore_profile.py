from pathlib import Path
import sys

import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import (
    Air,
    FREQUENCY,
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


def make_profile_taper(tip_width: float, taper_power: float, npts: int = 81):
    xs = np.linspace(0.0, TAPER_LENGTH, npts)
    s = (xs / TAPER_LENGTH) ** taper_power
    widths = tip_width + (WG_WIDTH - tip_width) * s
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


def make_sim(tip_width: float, taper_power: float):
    taper = make_profile_taper(tip_width, taper_power)
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
    tips = [0.15, 0.16, 0.18]
    powers = [1.2, 1.7, 2.2]
    sims = {
        f"tip{int(tip * 1000):03d}_p{power:.1f}": make_sim(tip, power)
        for tip in tips
        for power in powers
    }

    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore2",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} profile candidates")
    data = batch.run(path_dir="output/explore2")

    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")

    rows.sort(reverse=True)
    result_path = Path("output/explore2_results.tsv")
    result_path.write_text(
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
