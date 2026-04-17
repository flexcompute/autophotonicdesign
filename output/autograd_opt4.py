"""Optimize 20 interior narrow-segment widths + 3 step-region widths.
Total: 23 free params. Warm-start from exp 8."""

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

# 20 interior widths in narrow segment (x from 0.286 to 5.714, xb=5.9)
# + 3 step-region widths (x from 5.92 to 5.98)
M_narrow = 20
M_step = 3
xb = 5.9
x_narrow = np.linspace(TAPER_LENGTH / (M_narrow + 1), xb * M_narrow / (M_narrow + 1), M_narrow)
x_step = np.linspace(xb + 0.02, TAPER_LENGTH - 0.02, M_step)  # 5.92, 5.95, 5.98


def make_from_params(params):
    """params: M_narrow + 1 (Wb) + M_step softplus deltas → all cumulative.
    Total widths count = M_narrow + 1 + M_step = 24, all monotonic."""
    deltas = anp.log(1 + anp.exp(params))
    widths = WG_WIDTH_IN + anp.cumsum(deltas)  # 24 monotonic values
    # Split: narrow gets first 21 (interior + Wb), step gets next 3
    w_narrow = widths[:M_narrow + 1]  # 21
    w_step = widths[M_narrow + 1:]    # 3

    xs_all = anp.concatenate([
        anp.array([0.0]),
        x_narrow,
        anp.array([xb]),
        x_step,
        anp.array([TAPER_LENGTH]),
    ])
    ws_all = anp.concatenate([
        anp.array([WG_WIDTH_IN]),
        w_narrow,
        w_step,
        anp.array([WG_WIDTH_OUT]),
    ])
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
    sim_data = web.run(sim, task_name="autodesign_opt4", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)


# Warm start: narrow from exp 8 via interpolation; step: linear 3.64 → 4.66 → 4.83 → 4.93 → 5.0
x_exp8 = np.concatenate([np.linspace(TAPER_LENGTH / 17, xb * 16 / 17, 16), [xb]])
w_exp8 = np.array([1.46478, 1.52436, 1.65600, 1.80738, 1.96048, 2.12116, 2.29960,
                   2.46601, 2.60549, 2.75994, 2.91740, 3.05966, 3.19627, 3.32550,
                   3.44285, 3.54609, 3.63872])
w_narrow_new = np.interp(np.concatenate([x_narrow, [xb]]), x_exp8, w_exp8)
# step widths: linear interp from Wb=3.639 to W_out=5
w_step_new = 3.639 + (5.0 - 3.639) * (x_step - xb) / (TAPER_LENGTH - xb)

widths_init = np.concatenate([w_narrow_new, w_step_new])
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], widths_init]))
target_deltas = np.maximum(target_deltas, 1e-3)
init_params = np.log(np.exp(target_deltas) - 1.0)
print(f"Total params: {len(init_params)}")

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
    print(f"step {step}: T={T:.4f}  |g|={np.linalg.norm(g):.4f}  best={best_T:.4f}")
    momentum = mom_beta * momentum - lr * g / (np.abs(g).max() + 1e-6)
    params = params + momentum

np.save("output/opt_params4.npy", best_params)
deltas = np.log(1 + np.exp(best_params))
Ws = WG_WIDTH_IN + np.cumsum(deltas)
print(f"\nBEST T = {best_T:.4f}")
print("Narrow widths (21):")
print(','.join(f'{w:.5f}' for w in Ws[:21]))
print("Step widths (3):")
print(','.join(f'{w:.5f}' for w in Ws[21:]))
