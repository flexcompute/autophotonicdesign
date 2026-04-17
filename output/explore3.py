"""Sweep power-law exponent p in W(x) = W0 + (W1-W0)(x/L)^p via Tidy3D batch.
Only 6 FDTDs — well under the 20-FDTD exploration budget.
"""

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
    geometry=td.Box.from_bounds(
        rmin=(-1e3, -WG_WIDTH_IN / 2, -WG_HEIGHT / 2),
        rmax=(0, WG_WIDTH_IN / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)
output_wg = td.Structure(
    geometry=td.Box.from_bounds(
        rmin=(TAPER_LENGTH, -WG_WIDTH_OUT / 2, -WG_HEIGHT / 2),
        rmax=(1e3, WG_WIDTH_OUT / 2, WG_HEIGHT / 2),
    ),
    medium=Si,
)
source = td.ModeSource(
    center=(-BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH_IN * 4, WG_HEIGHT * 6),
    source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY / 20),
    direction="+",
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    mode_index=0,
    name="input_mode",
)
mode_monitor = td.ModeMonitor(
    center=(TAPER_LENGTH + BUFFER / 2, 0, 0),
    size=(0, WG_WIDTH_OUT + 2, WG_HEIGHT * 6),
    freqs=[FREQUENCY],
    mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47),
    name="mode",
)
sim_box = td.Box.from_bounds(
    rmin=(-BUFFER, -WG_WIDTH_OUT / 2 - BUFFER, -1),
    rmax=(TAPER_LENGTH + BUFFER, WG_WIDTH_OUT / 2 + BUFFER, 1),
)


def make_sim(p):
    N = 80
    xs = np.linspace(0.0, TAPER_LENGTH, N)
    ws = WG_WIDTH_IN + (WG_WIDTH_OUT - WG_WIDTH_IN) * (xs / TAPER_LENGTH) ** p
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


ps = [0.7, 1.0, 1.3, 1.7, 2.0, 2.5]
sims = {f"p={p:.2f}": make_sim(p) for p in ps}
batch = web.Batch(simulations=sims, verbose=False)
results = batch.run(path_dir="output/sim_data/sweep_p")

print(f"\n{'Profile':<10} {'T':>8}")
for key, data in results.items():
    amp = data["mode"].amps.sel(mode_index=0, direction="+").values
    T_arr = np.abs(amp) ** 2
    T = float(np.array(T_arr).flatten()[0])
    print(f"{key:<10} {T:8.4f}")
