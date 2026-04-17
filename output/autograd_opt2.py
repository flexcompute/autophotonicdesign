"""Continue optimization: 10 interior widths + variable xb,
warm-start from exp 6 results. Budget: ~9 iters x 2 = 18 sims + 1 eval."""

import autograd.numpy as anp
from autograd import value_and_grad
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
input_wg = td.Structure(geometry=td.Box.from_bounds(rmin=(-1e3, -WG_WIDTH_IN/2, -WG_HEIGHT/2), rmax=(0, WG_WIDTH_IN/2, WG_HEIGHT/2)), medium=Si)
output_wg = td.Structure(geometry=td.Box.from_bounds(rmin=(TAPER_LENGTH, -WG_WIDTH_OUT/2, -WG_HEIGHT/2), rmax=(1e3, WG_WIDTH_OUT/2, WG_HEIGHT/2)), medium=Si)
source = td.ModeSource(center=(-BUFFER/2, 0, 0), size=(0, WG_WIDTH_IN*4, WG_HEIGHT*6), source_time=td.GaussianPulse(freq0=FREQUENCY, fwidth=FREQUENCY/20), direction="+", mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47), mode_index=0, name="input_mode")
mode_monitor = td.ModeMonitor(center=(TAPER_LENGTH+BUFFER/2, 0, 0), size=(0, WG_WIDTH_OUT+2, WG_HEIGHT*6), freqs=[FREQUENCY], mode_spec=td.ModeSpec(num_modes=1, target_neff=3.47), name="mode")
sim_box = td.Box.from_bounds(rmin=(-BUFFER, -WG_WIDTH_OUT/2-BUFFER, -1), rmax=(TAPER_LENGTH+BUFFER, WG_WIDTH_OUT/2+BUFFER, 1))

M = 10  # interior control points


def make_from_params(params):
    """params: M+1 log-delta params (softplus → monotonic widths)
    Returns Tidy3D simulation with taper PolySlab.
    x_interior fixed at equispaced in [0.5, 5.4] (inside [0, 5.9]).
    """
    xb = 5.9  # keep fixed for now
    x_interior = anp.linspace(TAPER_LENGTH / (M + 1), xb * M / (M + 1), M)
    deltas = anp.log(1 + anp.exp(params))
    widths = WG_WIDTH_IN + anp.cumsum(deltas)  # length M+1: interior + last at xb
    # Build vertices
    xs_all = anp.concatenate([anp.array([0.0]), x_interior, anp.array([xb, TAPER_LENGTH])])
    ws_all = anp.concatenate([anp.array([WG_WIDTH_IN]), widths, anp.array([WG_WIDTH_OUT])])
    upper = anp.stack([xs_all, ws_all / 2.0], axis=1)
    lower = anp.stack([xs_all[::-1], -ws_all[::-1] / 2.0], axis=1)
    verts = anp.concatenate([upper, lower], axis=0)
    taper = td.Structure(
        geometry=td.PolySlab(vertices=verts, slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2), axis=2),
        medium=Si,
    )
    return td.Simulation(
        center=sim_box.center, size=sim_box.size,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=[input_wg, taper, output_wg],
        sources=[source], monitors=[mode_monitor],
        run_time=2e-12, medium=SiO2, symmetry=(0, -1, 1),
    )


def loss_fn(params):
    sim = make_from_params(params)
    sim_data = web.run(sim, task_name="autodesign_opt2", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)


# Warm-start from exp 6: interpolate from 8-point to 10-point
xb = 5.9
x_interior_new = np.linspace(TAPER_LENGTH / (M + 1), xb * M / (M + 1), M)
x_exp6 = np.concatenate([np.linspace(TAPER_LENGTH / 9, xb * 8 / 9, 8), [xb]])
w_exp6 = np.array([1.46557, 1.80637, 2.09088, 2.38575, 2.63128, 2.86518, 3.07526, 3.26801, 3.44018])
widths_new = np.interp(np.concatenate([x_interior_new, [xb]]), x_exp6, w_exp6)
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], widths_new]))
target_deltas = np.maximum(target_deltas, 1e-3)
init_params = np.log(np.exp(target_deltas) - 1.0)
print("Warm-start widths:", widths_new)

# Run optimization with small lr + momentum
params = init_params.copy()
momentum = np.zeros_like(params)
lr = 0.015
mom_beta = 0.7

best_T = 0.0
best_params = params.copy()

for step in range(9):
    loss, g = value_and_grad(loss_fn)(params)
    T = -loss
    if T > best_T:
        best_T = T
        best_params = params.copy()
    print(f"step {step}: T={T:.4f}  |g|={np.linalg.norm(g):.4f}  best_so_far={best_T:.4f}")
    # Momentum update with step-limiting
    momentum = mom_beta * momentum - lr * g / (np.abs(g).max() + 1e-6)
    params = params + momentum

np.save("output/opt_params2.npy", best_params)
deltas = np.log(1 + np.exp(best_params))
Ws = WG_WIDTH_IN + np.cumsum(deltas)
print(f"\nBEST T = {best_T:.4f}")
print(f"Best widths: {Ws}")
