"""Evaluate the autograd-optimized params; print final widths."""
import numpy as np

params = np.load("output/opt_params.npy")
deltas = np.log(1 + np.exp(params))
W_in = 0.5
Ws = W_in + np.cumsum(deltas)

TAPER_LENGTH = 6.0
xb_fixed = 5.9
M = 8
x_interior = np.linspace(TAPER_LENGTH / (M + 1), xb_fixed * M / (M + 1), M)
xs_ctrl = np.concatenate([[0.0], x_interior, [xb_fixed]])
ws_ctrl = np.concatenate([[W_in], Ws])
print("Control points:")
for x, w in zip(xs_ctrl, ws_ctrl):
    print(f"  x={x:.4f}  W={w:.4f}")
print()
print("interior widths (M=8):", Ws[:-1])
print("Wb at xb:", Ws[-1])
