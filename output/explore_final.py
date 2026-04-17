"""Final fine sweep around best: W=2.1, L=3.65, Lt=1.4, wt=0.95."""

import sys
import numpy as np
import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, ".")
import design as d


def build_sim(mmi_width, mmi_length, in_taper_length, in_taper_exit_w):
    device_length = 10.0
    center_gap = 0.20
    x_ts = 0.0
    x_te = in_taper_length
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
    taper_verts = [(x_ts, -d.WG_WIDTH/2), (x_te, -in_taper_exit_w/2),
                   (x_te,  in_taper_exit_w/2), (x_ts,  d.WG_WIDTH/2)]
    structures.append(td.Structure(
        geometry=td.PolySlab(vertices=taper_verts, slab_bounds=(-d.WG_HEIGHT/2, d.WG_HEIGHT/2), axis=2),
        medium=d.Si))
    structures.append(td.Structure(
        geometry=td.Box.from_bounds(
            rmin=(x_ms, -mmi_width/2, -d.WG_HEIGHT/2),
            rmax=(x_me,  mmi_width/2,  d.WG_HEIGHT/2)),
        medium=d.Si))
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


# Sweep W and L jointly (W=2.08, 2.10, 2.12 × L=3.55, 3.65, 3.75)
combos = []
for w in [2.08, 2.10, 2.12]:
    for L in [3.55, 3.65, 3.75]:
        combos.append((w, L, 1.4, 0.95))
# Also explore Lt=1.3 and 1.5 at best W,L=2.1,3.65
for lt in [1.3, 1.5]:
    combos.append((2.10, 3.65, lt, 0.95))

sims = {f"W{w:.2f}_L{L:.2f}_Lt{lt:.1f}_wt{wt:.2f}": build_sim(w, L, lt, wt)
        for (w, L, lt, wt) in combos}
batch = web.Batch(simulations=sims, folder_name="final_sweep")
results = batch.run(path_dir="output/sim_data/final")
for name, sim_data in results.items():
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = 2 * float(np.abs(amp[0])**2)
    print(f"{name}: metric={T:.4f}")
