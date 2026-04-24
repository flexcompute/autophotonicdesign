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
from drc import run_drc


TIP = 0.20
POWER = 1.85
PITCH = 0.45


def width_at(x):
    x = np.asarray(x)
    return TIP + (WG_WIDTH - TIP) * (x / TAPER_LENGTH) ** POWER


def slab_slice(x0, x1):
    w0, w1 = width_at([x0, x1])
    return td.Structure(
        geometry=td.PolySlab(
            vertices=[
                (float(x0), float(-w0 / 2)),
                (float(x1), float(-w1 / 2)),
                (float(x1), float(w1 / 2)),
                (float(x0), float(w0 / 2)),
            ],
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )


def solid_taper(x_start, npts=101):
    xs = np.linspace(x_start, TAPER_LENGTH, npts)
    widths = width_at(xs)
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


def make_swg_taper(swg_length, fill):
    seg_len = PITCH * fill
    n_periods = int(np.floor(swg_length / PITCH))
    structures = []
    for k in range(n_periods):
        x0 = k * PITCH
        x1 = x0 + seg_len
        structures.append(slab_slice(x0, x1))
    solid_start = n_periods * PITCH
    structures.append(solid_taper(solid_start))
    return structures


def make_sim(swg_length, fill):
    return td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=18, wavelength=WAVELENGTH),
        structures=[
            si_substrate,
            chip_sio2,
            *make_swg_taper(swg_length, fill),
            output_waveguide,
        ],
        sources=[source],
        monitors=monitors,
        run_time=4e-12,
        medium=Air,
        symmetry=(0, -1, 0),
    )


def main():
    variants = []
    for swg_length in [4.5, 9.0, 13.5, 18.0, 22.5]:
        for fill in [0.55, 0.65, 0.75]:
            variants.append((swg_length, fill))

    sims = {}
    for i, (swg_length, fill) in enumerate(variants):
        name = f"swg{i:02d}_l{int(swg_length*10):03d}_f{int(fill*100):02d}"
        sim = make_sim(swg_length, fill)
        width_v, space_v, _ = run_drc(sim)
        if width_v.size() or space_v.size():
            print(
                f"{name} DRC_FAIL width={width_v.size()} space={space_v.size()}"
            )
            continue
        print(f"{name} DRC_PASS")
        sims[name] = sim

    if not sims:
        print("No DRC-passing SWG candidates")
        return

    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore6_swg",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} SWG candidates")
    data = batch.run(path_dir="output/explore6_swg")

    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")

    rows.sort(reverse=True)
    Path("output/explore6_swg_results.tsv").write_text(
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
