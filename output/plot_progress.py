"""Plot metric (in dB) vs experiment number from results.tsv."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv

experiments = []
metrics = []
with open("output/results.tsv", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        experiments.append(int(row["experiment"]))
        metrics.append(float(row["metric"]))

experiments = np.array(experiments)
metrics = np.array(metrics)
metrics_db = 10 * np.log10(metrics)

# Running best
best_so_far = np.maximum.accumulate(metrics)
best_db = 10 * np.log10(best_so_far)

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(experiments, metrics_db, "o-", color="#1f77b4", alpha=0.6, label="experiment")
ax.plot(experiments, best_db, "-", color="#d62728", linewidth=2, label="best-so-far")
ax.set_xlabel("Experiment number")
ax.set_ylabel("Metric (dB) = 10·log10(transmission)")
ax.set_title("1x2 Splitter Auto-Design Progress")
ax.grid(True, alpha=0.3)
ax.legend()
plt.tight_layout()
plt.savefig("output/progress.png", dpi=150, bbox_inches="tight")
print(f"Saved output/progress.png ({len(experiments)} experiments, best={best_db[-1]:.3f} dB)")
