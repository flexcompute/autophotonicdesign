"""Plot transmission T vs experiment number from results.tsv."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import csv

xs, ys, statuses = [], [], []
with open("output/results.tsv") as f:
    reader = csv.DictReader(f, delimiter="\t")
    for row in reader:
        xs.append(int(row["experiment"]))
        ys.append(float(row["metric"]))
        statuses.append(row["status"])

# Running best
best = [ys[0]]
for y in ys[1:]:
    best.append(max(best[-1], y))

fig, ax = plt.subplots(figsize=(9, 5))
# Scatter all experiments, color by status
kept_x = [x for x, s in zip(xs, statuses) if s == "KEPT"]
kept_y = [y for y, s in zip(ys, statuses) if s == "KEPT"]
disc_x = [x for x, s in zip(xs, statuses) if s == "DISCARDED"]
disc_y = [y for y, s in zip(ys, statuses) if s == "DISCARDED"]

ax.plot(xs, best, "-", color="tab:blue", lw=2, label="Running best", zorder=3)
ax.scatter(kept_x, kept_y, color="tab:green", s=30, label="Kept", zorder=4)
ax.scatter(disc_x, disc_y, color="tab:red", marker="x", s=40, label="Discarded", zorder=4)

ax.set_xlabel("Experiment #")
ax.set_ylabel("Fundamental-mode transmission T")
ax.set_title(f"Optimization progress — final T = {max(ys):.4f}")
ax.axhline(max(ys), ls="--", color="gray", alpha=0.5)
ax.grid(alpha=0.3)
ax.legend(loc="lower right")
ax.set_ylim(0, 1.0)

plt.tight_layout()
plt.savefig("output/progress.png", dpi=150, bbox_inches="tight")
print("Saved output/progress.png")
