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


CENTER_TIP = 0.20
CENTER_POWER = 1.85


def center_width(x):
    x = np.asarray(x)
    return CENTER_TIP + (WG_WIDTH - CENTER_TIP) * (x / TAPER_LENGTH) ** CENTER_POWER


def make_center_taper(npts=101):
    xs = np.linspace(0.0, TAPER_LENGTH, npts)
    widths = center_width(xs)
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


def make_top_rail(gap, side_tip, side_width, bridge_x, absorb_x=46.0):
    pre_x = np.linspace(0.0, bridge_x, 31)
    pre_w = side_tip + (side_width - side_tip) * (pre_x / bridge_x) ** 1.2
    pre_inner = center_width(pre_x) / 2 + gap
    pre_outer = pre_inner + pre_w

    post_x = np.linspace(bridge_x, absorb_x, 31)[1:]
    t = (post_x - bridge_x) / (absorb_x - bridge_x)
    ease = 0.5 - 0.5 * np.cos(np.pi * t)
    outer_start = center_width(bridge_x) / 2 + gap + side_width
    outer_end = center_width(absorb_x) / 2 + 0.18
    post_outer = outer_start + (outer_end - outer_start) * ease

    # After the bridge point, the rail lower edge is inside the center taper;
    # before it, the open gap is constant and DRC-safe.
    post_inner = center_width(post_x) / 2 - 0.18

    outer = [(float(x), float(y)) for x, y in zip(pre_x, pre_outer)]
    outer += [(float(x), float(y)) for x, y in zip(post_x, post_outer)]

    inner = [(float(absorb_x), float(center_width(absorb_x) / 2 - 0.18))]
    inner += [(float(x), float(y)) for x, y in zip(post_x[::-1], post_inner[::-1])]
    inner += [
        (float(bridge_x), float(center_width(bridge_x) / 2 - 0.18)),
        (float(bridge_x), float(center_width(bridge_x) / 2 + gap)),
    ]
    inner += [(float(x), float(y)) for x, y in zip(pre_x[-2::-1], pre_inner[-2::-1])]

    return td.Structure(
        geometry=td.PolySlab(
            vertices=outer + inner,
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )


def mirror_y(structure):
    vertices = [(float(x), float(-y)) for x, y in structure.geometry.vertices]
    return td.Structure(
        geometry=td.PolySlab(
            vertices=vertices[::-1],
            slab_bounds=(Z_SIN_BOT, Z_SIN_TOP),
            axis=2,
        ),
        medium=SiN,
    )


def make_sim(gap, side_tip, bridge_x):
    top_rail = make_top_rail(gap, side_tip, side_width=0.22, bridge_x=bridge_x)
    bottom_rail = mirror_y(top_rail)
    return td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=18, wavelength=WAVELENGTH),
        structures=[
            si_substrate,
            chip_sio2,
            make_center_taper(),
            top_rail,
            bottom_rail,
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
    for gap in [0.25, 0.45, 0.65]:
        for side_tip in [0.16, 0.20]:
            for bridge_x in [18.0, 28.0]:
                variants.append((gap, side_tip, bridge_x))

    sims = {}
    for i, (gap, side_tip, bridge_x) in enumerate(variants):
        name = f"tri{i:02d}_g{int(gap*100):02d}_t{int(side_tip*1000):03d}_b{int(bridge_x):02d}"
        sim = make_sim(gap, side_tip, bridge_x)
        width_v, space_v, _ = run_drc(sim)
        if width_v.size() or space_v.size():
            print(
                f"{name} DRC_FAIL width={width_v.size()} space={space_v.size()}"
            )
            continue
        print(f"{name} DRC_PASS")
        sims[name] = sim

    if not sims:
        print("No DRC-passing trident candidates")
        return

    batch = web.Batch(
        simulations=sims,
        folder_name="autophotonicdesign_explore5_trident",
        num_workers=len(sims),
    )
    print(f"Running {len(sims)} trident candidates")
    data = batch.run(path_dir="output/explore5_trident")

    rows = []
    for name, sim_data in data.items():
        metric = evaluate(sim_data)
        rows.append((metric, name))
        print(f"{name}\t{metric:.9f}")

    rows.sort(reverse=True)
    Path("output/explore5_trident_results.tsv").write_text(
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
