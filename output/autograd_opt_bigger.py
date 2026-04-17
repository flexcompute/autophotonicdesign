"""Scale up to 120 narrow + 40 step = 161 params, warm-start from exp 24."""
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

M_narrow = 120
M_step = 40
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
    sim_data = web.run(sim, task_name="autodesign_big", verbose=False)
    amp = sim_data["mode"].amps.sel(mode_index=0, direction="+").values
    T = anp.abs(amp) ** 2
    return -anp.sum(T)


# Warm-start: interpolate exp 24 widths (80+25 -> 120+40)
old_xb = 5.9
old_x = np.concatenate([[0.0], np.linspace(TAPER_LENGTH / 81, old_xb * 80 / 81, 80),
                        [old_xb], np.linspace(old_xb + (TAPER_LENGTH - old_xb) / 26, TAPER_LENGTH - (TAPER_LENGTH - old_xb) / 26, 25),
                        [TAPER_LENGTH]])
old_w = np.concatenate([[WG_WIDTH_IN], np.load("output/opt_params19.npy")[:0], # placeholder
                        np.load("output/opt_params19.npy")[:0], [WG_WIDTH_OUT]])

# Just rebuild from params
old_params = np.load("output/opt_params19.npy")
old_deltas = np.log(1 + np.exp(old_params))
old_ws = WG_WIDTH_IN + np.cumsum(old_deltas)  # 106 values
old_ws[-1] = min(old_ws[-1], 5.0)
assert len(old_x) == 1 + 80 + 1 + 25 + 1 == 108, len(old_x)
old_w = np.concatenate([[WG_WIDTH_IN], old_ws, [WG_WIDTH_OUT]])
assert len(old_w) == 108, len(old_w)

new_x = np.concatenate([[0.0], x_narrow, [xb], x_step, [TAPER_LENGTH]])
new_w = np.interp(new_x, old_x, old_w)
widths_init = new_w[1:-1]
target_deltas = np.diff(np.concatenate([[WG_WIDTH_IN], widths_init]))
target_deltas = np.maximum(target_deltas, 1e-3)
init_params = np.log(np.exp(target_deltas) - 1.0)
print(f"Total params: {len(init_params)}")

params = init_params.copy()
m = np.zeros_like(params)
v = np.zeros_like(params)
beta1, beta2, eps = 0.9, 0.999, 1e-8
lr = 0.005

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

np.save("output/opt_params_big.npy", best_params)
deltas = np.log(1 + np.exp(best_params))
Ws = WG_WIDTH_IN + np.cumsum(deltas)
Ws[-1] = min(Ws[-1], 5.0)
print(f"\nBEST T = {best_T:.5f}")
print(f"# widths: {len(Ws)}")
