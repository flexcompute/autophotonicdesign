"""Sweep input taper (length, exit width) at fixed mmi_width=2.4, mmi_length=5.0.

Device occupies [0, 10]: taper [0,L_t], MMI [L_t, L_t+5], arms [L_t+5, 10].
"""

import sys
import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, ".")
import design as d


def build_sim(L_t, w_t):
    device_length = 10.0
    mmi_width = 2.4
    mmi_length = 5.0
    center_gap = 0.20

    x_ts = 0.0
    x_te = L_t
    x_ms = x_te
    x_me = x_ms + mmi_length
    x_as = x_me
    x_ae = device_length

    structures = []
    structures.append(td.Structure(
        geometry=td.Box.from_bounds(
            rmin=(-1e3, -d.WG_WIDTH/2, -d.WG_HEIGHT/2),
            rmax=(x_ts, d.WG_WIDTH/2, d.WG_HEIGHT/2)),
        medium=d.Si))
    # linear taper
    taper_verts = [
        (x_ts, -d.WG_WIDTH/2), (x_te, -w_t/2),
        (x_te,  w_t/2),        (x_ts,  d.WG_WIDTH/2),
    ]
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=taper_verts, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si))
    # MMI body
    structures.append(td.Structure(
        geometry=td.Box.from_bounds(
            rmin=(x_ms, -mmi_width/2, -d.WG_HEIGHT/2),
            rmax=(x_me,  mmi_width/2,  d.WG_HEIGHT/2)),
        medium=d.Si))
    # Access arms
    upper = d._cosine_arm_polygon(
        x0=x_as, x1=x_ae,
        y_outer_0=mmi_width/2, y_outer_1=d.OUTPUT_SEPARATION/2 + d.WG_WIDTH/2,
        y_inner_0=center_gap/2, y_inner_1=d.OUTPUT_SEPARATION/2 - d.WG_WIDTH/2,
    )
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=upper, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si))
    lower = [(x, -y) for (x, y) in upper]
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=lower, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si))
    # Output extension
    for sign in (+1, -1):
        structures.append(td.Structure(
            geometry=td.Box.from_bounds(
                rmin=(device_length, sign*d.OUTPUT_SEPARATION/2 - d.WG_WIDTH/2, -d.WG_HEIGHT/2),
                rmax=(1e3, sign*d.OUTPUT_SEPARATION/2 + d.WG_WIDTH/2, d.WG_HEIGHT/2)),
            medium=d.Si))

    buffer = 2
    source = td.ModeSource(
        center=(-buffer/2, 0, 0), size=(0, d.WG_WIDTH*4, d.WG_HEIGHT*6),
        source_time=td.GaussianPulse(freq0=d.FREQUENCY, fwidth=d.FREQUENCY/20),
        direction="+", mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
        mode_index=0, name="input_mode")
    monitor = td.ModeMonitor(
        center=(device_length+buffer/2, d.OUTPUT_SEPARATION/2, 0),
        size=source.size, freqs=[d.FREQUENCY],
        mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47), name="mode")
    sim_box = td.Box.from_bounds(
        rmin=(-buffer, -d.OUTPUT_SEPARATION/2 - buffer, -1),
        rmax=(device_length+buffer, d.OUTPUT_SEPARATION/2 + buffer, 1))

    return td.Simulation(
        center=sim_box.center, size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=d.WAVELENGTH),
        structures=structures, sources=[source], monitors=[monitor],
        run_time=2e-12, medium=d.SiO2, symmetry=(0, -1, 1))


# 3x3 grid, 9 sims (well under 20-budget since we've used ~5)
combos = [
    (0.5, 1.0), (1.0, 1.0), (1.5, 1.0),
    (0.5, 1.2), (1.0, 1.2), (1.5, 1.2),
    (1.0, 0.8), (1.0, 1.4),
]
sims = {f"Lt={Lt}_wt={wt}": build_sim(Lt, wt) for (Lt, wt) in combos}
batch = web.Batch(simulations=sims, folder_name="explore_taper")
results = batch.run(path_dir="output/sim_data/sweep_taper")
for name, sim_data in results.items():
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = 2 * float(np.abs(amp[0])**2)
    print(f"{name}: metric={T:.4f}")
