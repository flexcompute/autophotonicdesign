"""Sweep mmi_length for the current 2.4 um MMI, find empirical optimum.

Runs 5 FDTD sims (under the 20 exploration budget).
"""

import sys
import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, ".")
import design as d


def build_sim(mmi_length):
    d_mod = d
    # Reuse everything from design.create_simulation but override mmi_length
    # by building the simulation ourselves (copy the relevant logic).
    device_length = 10.0
    mmi_width = 2.4
    center_gap = 0.20

    structures = []
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(-1e3, -d.WG_WIDTH / 2, -d.WG_HEIGHT / 2),
                rmax=(0, d.WG_WIDTH / 2, d.WG_HEIGHT / 2),
            ),
            medium=d.Si,
        )
    )
    structures.append(
        td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(0, -mmi_width / 2, -d.WG_HEIGHT / 2),
                rmax=(mmi_length, mmi_width / 2, d.WG_HEIGHT / 2),
            ),
            medium=d.Si,
        )
    )

    upper = d._cosine_arm_polygon(
        x0=mmi_length,
        x1=device_length,
        y_outer_0=mmi_width / 2,
        y_outer_1=d.OUTPUT_SEPARATION / 2 + d.WG_WIDTH / 2,
        y_inner_0=center_gap / 2,
        y_inner_1=d.OUTPUT_SEPARATION / 2 - d.WG_WIDTH / 2,
    )
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=upper, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si,
    ))
    lower = [(x, -y) for (x, y) in upper]
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=lower, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si,
    ))

    for sign in (+1, -1):
        structures.append(
            td.Structure(
                geometry=td.Box.from_bounds(
                    rmin=(device_length, sign * d.OUTPUT_SEPARATION / 2 - d.WG_WIDTH / 2, -d.WG_HEIGHT / 2),
                    rmax=(1e3, sign * d.OUTPUT_SEPARATION / 2 + d.WG_WIDTH / 2, d.WG_HEIGHT / 2),
                ),
                medium=d.Si,
            )
        )

    buffer = 2
    source = td.ModeSource(
        center=(-buffer / 2, 0, 0),
        size=(0, d.WG_WIDTH * 4, d.WG_HEIGHT * 6),
        source_time=td.GaussianPulse(freq0=d.FREQUENCY, fwidth=d.FREQUENCY / 20),
        direction="+",
        mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
        mode_index=0,
        name="input_mode",
    )
    monitor = td.ModeMonitor(
        center=(device_length + buffer / 2, d.OUTPUT_SEPARATION / 2, 0),
        size=source.size,
        freqs=[d.FREQUENCY],
        mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
        name="mode",
    )
    sim_box = td.Box.from_bounds(
        rmin=(-buffer, -d.OUTPUT_SEPARATION / 2 - buffer, -1),
        rmax=(device_length + buffer, d.OUTPUT_SEPARATION / 2 + buffer, 1),
    )
    return td.Simulation(
        center=sim_box.center,
        size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=d.WAVELENGTH),
        structures=structures,
        sources=[source],
        monitors=[monitor],
        run_time=2e-12,
        medium=d.SiO2,
        symmetry=(0, -1, 1),
    )


lengths = [4.6, 5.0, 5.3, 5.6, 6.0]
sims = {f"L={L:.1f}": build_sim(L) for L in lengths}
batch = web.Batch(simulations=sims, folder_name="explore_mmi_length")
results = batch.run(path_dir="output/sim_data/sweep_L")

for name, sim_data in results.items():
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = 2 * float(np.abs(amp[0])**2)
    print(f"{name}: metric={T:.4f}")
