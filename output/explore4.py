"""Bilinear taper sweep: two linear segments meeting at (xb, Wb).
9-point sweep to identify best asymmetric split."""

import numpy as np
import tidy3d as td
import tidy3d.web as web

WAVELENGTH = 1.55
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH_IN = 0.5
WG_WIDTH_OUT = 5.0
WG_HEIGHT = 0.22
TAPER_LENGTH = 6.0
BUFFER = 1.0

Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)

input_wg = td.Structure(
    geometry=td.Box.from_bounds(rmin=(-1e3, -WG_WIDTH_IN / 2, -WG_HEIGHT / 2),
                                rmax=(0, WG_WIDTH_IN / 2, WG_HEIGHT / 2)),
    medium=Si,
)
output_wg = td.Structure(
    geometry=td.Box.from_bounds(rmin=(TAPER_LENGTH, -WG_WIDTH_OUT / 2, -WG_HEIGHT / 2),
                                rmax=(1e3, WG_WIDTH_OUT / 2, WG_HEIGHT / 2)),
    medium=Si,
)
source = td.ModeSource(
    center=(-BUFFER / 2, 0, 0), size=(0, WG_WIDTH_IN * 4, WG_HEIGHT * 6),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+", mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    mode_index=0, name="input_mode",
)
mode_monitor = td.ModeMonitor(
    center=(TAPER_LENGTH + BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH_OUT + 2, WG_HEIGHT * 6),
    freqs=[FREQUENCY], mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    name="mode",
)
sim_box = td.Box.from_bounds(
    rmin=(-BUFFER, -WG_WIDTH_OUT / 2 - BUFFER, -1),
    rmax=(TAPER_LENGTH + BUFFER, WG_WIDTH_OUT / 2 + BUFFER, 1),
)


def make_sim(xb, Wb):
    N = 80
    xs = np.linspace(0.0, TAPER_LENGTH, N)
    ws = np.where(
        xs <= xb,
        WG_WIDTH_IN + (Wb - WG_WIDTH_IN) * (xs / xb),
        Wb + (WG_WIDTH_OUT - Wb) * (xs - xb) / (TAPER_LENGTH - xb),
    )
    upper = [(float(x), float(w / 2)) for x, w in zip(xs, ws)]
    lower = [(float(x), float(-w / 2)) for x, w in zip(xs[::-1], ws[::-1])]
    taper = td.Structure(
        geometry=td.PolySlab(vertices=upper + lower, slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2), axis=2),
        medium=Si,
    )
    return td.Simulation(
        center=sim_box.center, size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=[input_wg, taper, output_wg],
        sources=[source], monitors=[mode_monitor],
        run_time=2e-12, medium=SiO2, symmetry=(0, -1, 1),
    )


# 9 combinations, xb ∈ {2, 3, 4}, Wb ∈ {1.5, 2.5, 3.5}
configs = []
for xb in [2.0, 3.0, 4.0]:
    for Wb in [1.5, 2.5, 3.5]:
        configs.append((xb, Wb))

sims = {f"xb={xb:.1f}_Wb={Wb:.1f}": make_sim(xb, Wb) for xb, Wb in configs}
batch = web.Batch(simulations=sims, verbose=False)
results = batch.run(path_dir="output/sim_data/sweep_bilinear")

rows = []
for key, data in results.items():
    amp = data["mode"].amps.sel(mode_index=0, direction="+").values
    T = float(np.array(np.abs(amp) ** 2).flatten()[0])
    rows.append((key, T))
    print(f"{key:<22} T = {T:.4f}")

rows.sort(key=lambda r: -r[1])
print("\nTop 3:")
for key, T in rows[:3]:
    print(f"  {key}: {T:.4f}")
