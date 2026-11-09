"""Draw the planted chip with each plant marked by its kind (and, after a run, found or missed).

    python tools/red/plant_map.py ../runs/siepic_s7/red docs/img/siepic_plants.png
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import review as rv   # noqa: E402

KIND = {"mistake": "#e5484d", "easy": "#8b8d98", "harmless": "#3e63dd"}


def main(red, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MP
    red = Path(red)
    key = json.loads((red / "answer_key.json").read_text())
    score = json.loads((red / "score.json").read_text()) if (red / "score.json").exists() else None
    found = {r["id"]: r["found"] for r in score["plants"]} if score else {}
    rv.configure(red / "haystack.gds", key["top"], key["pdk"], cache=red / "cache_map")
    x0, y0, x1, y1 = rv.summary()["bbox"]
    w, h = x1 - x0, y1 - y0
    fig = plt.figure(figsize=(12, max(4.0, 12 * h / w)), dpi=130)
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    colors = rv.pdk().COLORS
    for layer in rv.pdk().CORE + rv.pdk().ALT_CORE:
        for p in rv.flat().get(layer, []):
            for g in getattr(p, "geoms", [p]):
                ax.add_patch(MP(np.asarray(g.exterior.coords), closed=True, fc=colors.get(layer, "#888"),
                                ec=colors.get(layer, "#888"), lw=0.3, alpha=0.9 if layer in rv.pdk().CORE else 0.25))
    for p in key["plants"]:
        bx = p["bbox"]
        cx, cy = 0.5 * (bx[0] + bx[2]), 0.5 * (bx[1] + bx[3])
        c = KIND[p["kind"]]
        hollow = score is not None and not found.get(p["id"], False)
        ax.plot([cx], [cy], "o", ms=15, mfc="none" if hollow else c, mec=c, mew=2.5, alpha=0.9)
        ax.annotate(p["id"], (cx, cy), xytext=(9, 9), textcoords="offset points", fontsize=10, color=c, weight="bold")
    ax.set_xlim(x0 - 0.03 * w, x1 + 0.03 * w)
    ax.set_ylim(y0 - 0.03 * h, y1 + 0.03 * h)
    ax.set_aspect("equal")
    ax.axis("off")
    for k, c in KIND.items():
        ax.plot([], [], "o", ms=10, color=c, label={"mistake": "real mistake", "easy": "easy (DRC or LVS flags it)",
                                                     "harmless": "harmless change"}[k])
    ax.legend(loc="lower right", fontsize=10, frameon=False)
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
