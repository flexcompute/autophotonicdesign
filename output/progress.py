"""Plot experiment progress: metric vs experiment with best-so-far overlay."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

here = Path(__file__).resolve().parent
tsv = here / "results.tsv"

exps, metrics, statuses = [], [], []
for line in tsv.read_text().splitlines()[1:]:
    if not line.strip():
        continue
    parts = line.split("\t")
    exps.append(int(parts[0]))
    metrics.append(float(parts[1]))
    statuses.append(parts[3])
exps = np.array(exps)
metrics = np.array(metrics)
statuses = np.array(statuses)

running_best = np.maximum.accumulate(metrics)

fig, ax = plt.subplots(figsize=(9, 4.5))
kept = statuses == "KEPT"
ax.scatter(exps[~kept], metrics[~kept], s=28, c="#c44",
           marker="x", label="discarded", zorder=3)
ax.scatter(exps[kept], metrics[kept], s=36, c="#2a8",
           marker="o", edgecolors="k", linewidths=0.5,
           label="kept", zorder=4)
ax.plot(exps, running_best, "-", color="darkgreen", linewidth=2,
        label="best so far", zorder=2)

ax.set_xlabel("Experiment")
ax.set_ylabel("Mode transmission")
ax.set_title("Auto-design progress — 90° SiN bend (R = 12 µm)")
ax.set_ylim(0.3, 1.0)
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right")
fig.tight_layout()

out = here / "progress.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved {out}")
