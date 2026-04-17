"""Gradient-based optimization of taper vertices via Tidy3D autograd.
Parameterize narrow segment by 8 control widths at fixed x, enforce monotonic.
Wide segment linear from (xb, W_last) to (L, W_out).
Budget: 10 iterations × 2 sims = 20 simulations.
"""

import autograd.numpy as anp
from autograd import grad, value_and_grad
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

xb_fixed = 5.9  # break point x
M = 8  # number of interior control points in narrow segment
x_interior = anp.linspace(TAPER_LENGTH / (M + 1), xb_fixed * M / (M + 1), M)


def widths_from_params(params):
    """Turn unconstrained params into monotonic widths at x_interior + x=xb.
    Baseline sqrt: W = 0.5 + 3.0 * (x/5.9)^0.5 at x in x_interior, last=(xb, 3.5)
    """
    # Enforce monotonic increments via softplus. Total interior + 1 deltas.
    deltas = anp.log(1 + anp.exp(params))  # softplus, all positive
    # Normalize so total delta = Wb_target - W_in (but we let last also vary)
    # Actually: let deltas be absolute widths at each position, enforced monotonic.
    # W[i] = W_in + sum(deltas[:i+1])
    Ws = WG_WIDTH_IN + anp.cumsum(deltas)
    return Ws  # length M+1, last is Wb


def build_vertices(widths_all):
    """widths_all: array of M+1 widths, at x_interior (M) and x=xb_fixed (1). Adds endpoints."""
    # Narrow segment x positions: [0, *x_interior, xb_fixed], widths [W_in, *widths_all]
    xs_narrow = anp.concatenate([anp.array([0.0]), x_interior, anp.array([xb_fixed])])
    ws_narrow = anp.concatenate([anp.array([WG_WIDTH_IN]), widths_all])
    # Then add (L, W_out) — step at xb_fixed → L
    # We use linear interp in the wide segment, so add (xb_fixed+eps, widths_all[-1]) is implicit; just connect with straight line.
    # Actually polygon needs closed shape: upper then lower.
    upper_xs = anp.concatenate([xs_narrow, anp.array([TAPER_LENGTH])])
    upper_ws = anp.concatenate([ws_narrow, anp.array([WG_WIDTH_OUT])])
    upper = anp.stack([upper_xs, upper_ws / 2.0], axis=1)
    lower = anp.stack([upper_xs[::-1], -upper_ws[::-1] / 2.0], axis=1)
    verts = anp.concatenate([upper, lower], axis=0)
    return verts


def make_sim_from_params(params):
    widths_all = widths_from_params(params)
    verts = build_vertices(widths_all)
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
    sim = make_sim_from_params(params)
    sim_data = web.run(sim, task_name="autodesign_opt", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)  # negative so minimization = maximize T


# Initialize params to reproduce the sqrt baseline:
# sqrt profile ws at x_interior (x = 0.655, 1.310, ..., 5.245):
# W(x) = 0.5 + 3.0 * (x/5.9)^0.5
def sqrt_W(x):
    return WG_WIDTH_IN + 3.0 * np.sqrt(x / xb_fixed)
target_ws = np.concatenate([sqrt_W(x_interior._value if hasattr(x_interior, '_value') else x_interior), [3.5]])
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], target_ws]))
# params from target: delta = softplus(p) → p = log(exp(delta)-1)
init_params = np.log(np.exp(target_deltas) - 1.0)

print("Initial widths:")
print(widths_from_params(init_params))

# Gradient descent
params = init_params.copy()
lr = 0.05
history = []
for step in range(9):
    vg = value_and_grad(loss_fn)
    loss, g = vg(params)
    T = -loss
    history.append((step, float(T), params.copy()))
    print(f"\nstep {step}: T = {T:.4f}  |grad| = {np.linalg.norm(g):.4f}")
    print(f"  widths = {widths_from_params(params)}")
    # Adam-ish update
    params = params - lr * g / (np.abs(g).max() + 1e-6)  # step-limited

# Final evaluation
final_sim = make_sim_from_params(params)
final_data = web.run(final_sim, task_name="autodesign_final", verbose=False)
final_T = float(np.abs(final_data["mode"].amps.sel(mode_index=0, direction="+").values)**2)
print(f"\nFINAL T = {final_T:.4f}")
print(f"Final widths: {widths_from_params(params)}")

# Save params
np.save("output/opt_params.npy", params)
print("Saved output/opt_params.npy")
