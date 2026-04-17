"""Scale up to 80 narrow + 25 step = 105 params. Warm-start interpolated from exp 18."""
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

M_narrow = 80
M_step = 25
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
    sim_data = web.run(sim, task_name="autodesign_opt14", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)


# Warm start: interpolate exp 18 widths onto new grid
old_M_narrow = 50
old_M_step = 15
x_old_narrow = np.linspace(TAPER_LENGTH / 51, xb * 50 / 51, 50)
x_old_step = np.linspace(xb + (TAPER_LENGTH - xb) / 16, TAPER_LENGTH - (TAPER_LENGTH - xb) / 16, 15)
x_old = np.concatenate([[0.0], x_old_narrow, [xb], x_old_step, [TAPER_LENGTH]])
w_old = np.concatenate([[WG_WIDTH_IN],
    [0.93983, 1.25849, 1.44249, 1.51264, 1.52972, 1.55618, 1.58056, 1.60577,
     1.63387, 1.66379, 1.69874, 1.73623, 1.77607, 1.81769, 1.86609, 1.93658,
     2.01476, 2.09353, 2.15599, 2.20741, 2.25144, 2.29014, 2.32628, 2.36014,
     2.39373, 2.42726, 2.47101, 2.52868, 2.60565, 2.68563, 2.76095, 2.81738,
     2.86462, 2.91377, 2.98492, 3.06485, 3.12999, 3.17879, 3.22721, 3.29161,
     3.36501, 3.43599, 3.50460, 3.56811, 3.62782, 3.68479, 3.72888, 3.75837,
     3.78271, 3.80596, 3.82872,
     3.89183, 3.95496, 4.01830, 4.08175, 4.15416, 4.24436, 4.35786, 4.47157,
     4.58516, 4.69849, 4.80289, 4.87854, 4.93426, 4.98533, 5.00000],
    [WG_WIDTH_OUT]])
assert len(x_old) == len(w_old), (len(x_old), len(w_old))

x_new = np.concatenate([[0.0], x_narrow, [xb], x_step, [TAPER_LENGTH]])
w_new = np.interp(x_new, x_old, w_old)
widths_init = w_new[1:-1]
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], widths_init]))
target_deltas = np.maximum(target_deltas, 1e-3)
init_params = np.log(np.exp(target_deltas) - 1.0)
print(f"Total params: {len(init_params)}")

params = init_params.copy()
m = np.zeros_like(params)
v = np.zeros_like(params)
beta1, beta2, eps = 0.9, 0.999, 1e-8
lr = 0.01

best_T = 0.0
best_params = params.copy()
for step in range(9):
    loss, g = value_and_grad(loss_fn)(params)
    T = -loss
    if T > best_T:
        best_T = T
        best_params = params.copy()
    print(f"step {step}: T={T:.5f}  |g|={np.linalg.norm(g):.4f}  best={best_T:.5f}")
    m = beta1 * m + (1 - beta1) * g
    v = beta2 * v + (1 - beta2) * g * g
    m_hat = m / (1 - beta1 ** (step + 1))
    v_hat = v / (1 - beta2 ** (step + 1))
    params = params - lr * m_hat / (np.sqrt(v_hat) + eps)

np.save("output/opt_params14.npy", best_params)
deltas = np.log(1 + np.exp(best_params))
Ws = WG_WIDTH_IN + np.cumsum(deltas)
Ws[-1] = min(Ws[-1], 5.0)
print(f"\nBEST T = {best_T:.5f}")
print(f"# widths: {len(Ws)}")
print(','.join(f'{w:.5f}' for w in Ws))
