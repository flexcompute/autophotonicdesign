"""Randomized search around current best, using PCHIP-interpolated narrow segment
with 4 free interior control points + linear wide step."""

import numpy as np
import tidy3d as td
import tidy3d.web as web
from scipy.interpolate import PchipInterpolator

WAVELENGTH = 1.55
FREQUENCY = td.C_0 / WAVELENGTH
WG_WIDTH_IN = 0.5
WG_WIDTH_OUT = 5.0
WG_HEIGHT = 0.22
TAPER_LENGTH = 6.0
BUFFER = 1.0
Si = td.Medium.from_nk(n=3.47, k=0, freq=FREQUENCY)
SiO2 = td.Medium.from_nk(n=1.44, k=0, freq=FREQUENCY)
input_wg = td.Structure(geometry=td.Box.from_bounds(rmin=(-1e3, -WG_WIDTH_IN/2, -WG_HEIGHT/2), rmax=(0, WG_WIDTH_IN/2, WG_HEIGHT/2)), medium=Si)
output_wg = td.Structure(geometry=td.Box.from_bounds(rmin=(TAPER_LENGTH, -WG_WIDTH_OUT/2, -WG_HEIGHT/2), rmax=(1e3, WG_WIDTH_OUT/2, WG_HEIGHT/2)), medium=Si)
source = td.ModeSource(center=(-BUFFER/2, 0, 0), size=(0, WG_WIDTH_IN*4, WG_HEIGHT*6), source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY/20), direction="+", mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47), mode_index=0, name="input_mode")
mode_monitor = td.ModeMonitor(center=(TAPER_LENGTH+BUFFER/2, 0, 0), size=(0, WG_WIDTH_OUT+2, WG_HEIGHT*6), freqs=[FREQUENCY], mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47), name="mode")
sim_box = td.Box.from_bounds(rmin=(-BUFFER, -WG_WIDTH_OUT/2-BUFFER, -1), rmax=(TAPER_LENGTH+BUFFER, WG_WIDTH_OUT/2+BUFFER, 1))


def make_sim(xs, ws):
    upper = [(float(x), float(w/2)) for x, w in zip(xs, ws)]
    lower = [(float(x), float(-w/2)) for x, w in zip(xs[::-1], ws[::-1])]
    taper = td.Structure(geometry=td.PolySlab(vertices=upper+lower, slab_bounds=(-WG_HEIGHT/2, WG_HEIGHT/2), axis=2), medium=Si)
    return td.Simulation(center=sim_box.center, size=sim_box.size, grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=[input_wg, taper, output_wg], sources=[source], monitors=[mode_monitor], run_time=2e-12, medium=SiO2, symmetry=(0, -1, 1))


def profile_from_knots(knots, xb=5.9, W_out=5.0):
    """knots: list of (x, W) interior control points including endpoints (0, 0.5) and (xb, Wb)."""
    x_ctrl = np.array([k[0] for k in knots])
    w_ctrl = np.array([k[1] for k in knots])
    # enforce monotonic W (sort by x, ensure W increasing)
    order = np.argsort(x_ctrl)
    x_ctrl, w_ctrl = x_ctrl[order], w_ctrl[order]
    for i in range(1, len(w_ctrl)):
        w_ctrl[i] = max(w_ctrl[i], w_ctrl[i-1] + 1e-3)
    pchip = PchipInterpolator(x_ctrl, w_ctrl, extrapolate=False)
    N = 201
    xs = np.linspace(0.0, TAPER_LENGTH, N)
    ws = np.zeros_like(xs)
    ws[xs <= xb] = pchip(xs[xs <= xb])
    Wb = w_ctrl[-1]
    ws[xs > xb] = Wb + (W_out - Wb) * (xs[xs > xb] - xb) / (TAPER_LENGTH - xb)
    return xs, ws


# Baseline knots from sqrt profile: W(x) = 0.5 + 3.0 * (x/5.9)^0.5 evaluated at x = [1, 2, 3, 4, 5]
# baseline_knots = [(0, 0.5), (1, 1.73), (2, 2.24), (3, 2.64), (4, 2.97), (5, 3.26), (5.9, 3.5)]
baseline_ws_at_x = {1: 1.734, 2: 2.236, 3: 2.637, 4: 2.970, 5: 3.258}

np.random.seed(42)
configs = {}
# baseline (should reproduce T~0.92)
knots = [(0.0, 0.5)] + [(x, baseline_ws_at_x[x]) for x in [1, 2, 3, 4, 5]] + [(5.9, 3.5)]
configs["baseline_pchip"] = profile_from_knots(knots)

# Random perturbations: ±0.3 at each interior knot, keep monotonic
for i in range(19):
    knots = [(0.0, 0.5)]
    prev_w = 0.5
    for x in [1, 2, 3, 4, 5]:
        w = baseline_ws_at_x[x] + np.random.uniform(-0.3, 0.3)
        w = max(w, prev_w + 0.05)
        knots.append((x, w))
        prev_w = w
    Wb = 3.5 + np.random.uniform(-0.1, 0.1)
    Wb = max(Wb, prev_w + 0.05)
    knots.append((5.9, Wb))
    configs[f"rand_{i:02d}"] = profile_from_knots(knots)

print(f"Running {len(configs)} simulations")
batch = web.Batch(simulations=dict((k, make_sim(*profile_from_knots(v) if isinstance(v, list) else v)) for k, v in configs.items()), verbose=False) if False else None

# Actually the above is messy. Simpler:
sims = {}
for name, (xs, ws) in configs.items():
    sims[name] = make_sim(xs, ws)

batch = web.Batch(simulations=sims, verbose=False)
results = batch.run(path_dir="output/sim_data/sweep10")

rows = []
for key, data in results.items():
    amp = data["mode"].amps.sel(mode_index=0, direction="+").values
    T = float(np.array(np.abs(amp)**2).flatten()[0])
    rows.append((key, T))
    print(f"{key:<22} T = {T:.4f}")

rows.sort(key=lambda r: -r[1])
print("\nTop 5:")
for key, T in rows[:5]:
    print(f"  {key}: {T:.4f}")
