"""50 narrow + 15 step widths = 65 params. Warm-start from exp 10."""

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

M_narrow = 50
M_step = 15
xb = 5.9
x_narrow = np.linspace(TAPER_LENGTH / (M_narrow + 1), xb * M_narrow / (M_narrow + 1), M_narrow)
x_step = np.linspace(xb + (TAPER_LENGTH - xb) / (M_step + 1), TAPER_LENGTH - (TAPER_LENGTH - xb) / (M_step + 1), M_step)


def make_from_params(params):
    deltas = anp.log(1 + anp.exp(params))
    widths = WG_WIDTH_IN + anp.cumsum(deltas)
    w_narrow = widths[:M_narrow + 1]
    w_step = widths[M_narrow + 1:]
    xs_all = anp.concatenate([anp.array([0.0]), x_narrow, anp.array([xb]), x_step, anp.array([TAPER_LENGTH])])
    ws_all = anp.concatenate([anp.array([WG_WIDTH_IN]), w_narrow, w_step, anp.array([WG_WIDTH_OUT])])
    upper = anp.stack([xs_all, ws_all / 2.0], axis=1)
    lower = anp.stack([xs_all[::-1], -ws_all[::-1] / 2.0], axis=1)
    verts = anp.concatenate([upper, lower], axis=0)
    taper = td.Structure(geometry=td.PolySlab(vertices=verts, slab_bounds=(-WG_HEIGHT / 2, WG_HEIGHT / 2), axis=2), medium=Si)
    return td.Simulation(center=sim_box.center, size=sim_box.size, grid_spec=td.GridSpec.auto(min_steps_per_wvl=20, wavelength=WAVELENGTH),
        structures=[input_wg, taper, output_wg], sources=[source], monitors=[mode_monitor], run_time=2e-12, medium=SiO2, symmetry=(0, -1, 1))


def loss_fn(params):
    sim = make_from_params(params)
    sim_data = web.run(sim, task_name="autodesign_opt6", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)


# Warm start from exp 10
x_exp10_narrow = np.linspace(TAPER_LENGTH / 31, xb * 30 / 31, 30)
x_exp10_step = np.linspace(xb + (TAPER_LENGTH - xb) / 8, TAPER_LENGTH - (TAPER_LENGTH - xb) / 8, 7)
x_exp10 = np.concatenate([[0.0], x_exp10_narrow, [xb], x_exp10_step, [TAPER_LENGTH]])
w_exp10 = np.array([0.5,
    1.16103, 1.46947, 1.49608, 1.54721, 1.60432, 1.67048, 1.74766, 1.82764,
    1.90977, 2.00280, 2.10565, 2.20705, 2.29902, 2.38018, 2.45592, 2.52651,
    2.61321, 2.71253, 2.81690, 2.91078, 3.00486, 3.10349, 3.19490, 3.28286,
    3.37099, 3.45497, 3.53201, 3.60119, 3.66024, 3.71407,
    3.76452,
    3.93402, 4.10404, 4.27447, 4.44495, 4.61530, 4.78557, 4.91989,
    5.0])
assert len(x_exp10) == len(w_exp10), (len(x_exp10), len(w_exp10))

xx = np.concatenate([[0.0], x_narrow, [xb], x_step, [TAPER_LENGTH]])
w_init = np.interp(xx, x_exp10, w_exp10)

widths_init = w_init[1:-1]
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], widths_init]))
target_deltas = np.maximum(target_deltas, 1e-3)
init_params = np.log(np.exp(target_deltas) - 1.0)
print(f"Total params: {len(init_params)}")

params = init_params.copy()
momentum = np.zeros_like(params)
lr = 0.01
mom_beta = 0.8

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

np.save("output/opt_params6.npy", best_params)
deltas = np.log(1 + np.exp(best_params))
Ws = WG_WIDTH_IN + np.cumsum(deltas)
print(f"\nBEST T = {best_T:.4f}")
print("narrow (51):")
print(','.join(f'{w:.5f}' for w in Ws[:M_narrow + 1]))
print("step (15):")
print(','.join(f'{w:.5f}' for w in Ws[M_narrow + 1:]))
