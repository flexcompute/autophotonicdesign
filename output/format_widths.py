"""Format the widths array from a .npy file as a Python literal."""
import sys
import numpy as np

params = np.load(sys.argv[1])
deltas = np.log(1 + np.exp(params))
Ws = 0.5 + np.cumsum(deltas)
Ws[-1] = min(Ws[-1], 5.0)
M_narrow = int(sys.argv[2]) if len(sys.argv) > 2 else 120

# Format: M_narrow+1 narrow (up to and incl Wb at xb), then step widths
print("    w_narrow_step = np.array([")
narrow_ws = Ws[:M_narrow + 1]
step_ws = Ws[M_narrow + 1:]
for i in range(0, len(narrow_ws), 8):
    row = narrow_ws[i:i+8]
    print("        " + ", ".join(f"{v:.5f}" for v in row) + ",")
# separator blank line
# step
for i in range(0, len(step_ws), 8):
    row = step_ws[i:i+8]
    if i == 0:
        print("        " + ", ".join(f"{v:.5f}" for v in row) + ",")
    elif i + 8 >= len(step_ws):
        print("        " + ", ".join(f"{v:.5f}" for v in row) + "])")
    else:
        print("        " + ", ".join(f"{v:.5f}" for v in row) + ",")
# if only 1 row, close
if len(step_ws) <= 8:
    print("        ])")
