"""topology_evolution — build animated GIFs showing how the AI is changing
the segmented-CPW design across iterations.

For each archived experiment:
  • Load the snapshotted design.py (fresh module, no cache)
  • Build the Tidy3D Simulation
  • Render a frame: top-down at the metal plane + transverse cross-section
  • Title the frame with exp #, topology family, FOM, key knobs

Stitch frames into:
  output/plots/topology_evolution.gif        (animated)
  output/plots/topology_evolution_grid.png   (static grid)

Usage:
    python -m tools.evolution
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
EXPERIMENTS_DIR = OUTPUT_DIR / "experiments"
PLOTS_DIR = OUTPUT_DIR / "plots"
RESULTS_TSV = OUTPUT_DIR / "results.tsv"


# --------------------------------------------------------------------
# Per-experiment design loading
# --------------------------------------------------------------------
def _load_design_snapshot(design_py: Path):
    """Import an experiment's snapshotted design.py as a fresh, isolated module."""
    mod_name = f"design_iter_{design_py.parent.name}"
    spec = importlib.util.spec_from_file_location(mod_name, design_py)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"  [load-fail {design_py.parent.name}]: {exc}")
        sys.modules.pop(mod_name, None)
        return None
    return mod


def _load_results_index() -> dict[int, dict]:
    """Index every TSV row by experiment number for title overlays."""
    if not RESULTS_TSV.exists():
        return {}
    out = {}
    with RESULTS_TSV.open() as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                out[int(row["experiment"])] = row
            except (ValueError, KeyError, TypeError):
                continue
    return out


# --------------------------------------------------------------------
# Frame renderer
# --------------------------------------------------------------------
# Per-topology color (matches dashboard.py)
TOPO_COLORS = {
    "T-rail":         "#1f77b4",
    "asym-T":         "#2ca02c",
    "slotted-signal": "#d62728",
    "mushroom-T":     "#9467bd",
    "T+U":            "#ff7f0e",
    "asym-mushroom":  "#e377c2",
    "half-T":         "#8c564b",
}

# Internal topology name → display label. The underlying TSV / journal /
# best_design.py all keep the historical name (back-compat with archives);
# only the rendered titles + legends use the friendlier label.
TOPO_DISPLAY = {
    "mushroom-T":    "wide-cap T",
    "asym-mushroom": "asym wide-cap T",
}


# Keep axis limits fixed across all frames so the animation doesn't jitter.
# Worst-case-design values from our 37 experiments:
#   GW reaches ~33 μm, P_T reaches ~73 μm. Show ~5 unit cells in the top view.
TOP_XLIM = (-105.0, 105.0)      # μm — signal trace + both gaps + grounds
TOP_YLIM = (-130.0, 130.0)      # μm — fewer cells, larger per-cell detail
# Cross-section zooms on the RIGHT active gap (where the rib waveguide lives)
# — much narrower x range so the metal stack is visible at proper scale.
CROSS_XLIM = (35.0, 90.0)       # μm — signal edge through right ground rail
CROSS_ZLIM = (-0.5, 2.5)        # μm — TFLT at z=0..0.3, metal at z~1.2..2.2


def _render_frame(mod, exp_num: int, meta: dict, out_path: Path) -> bool:
    """Render a single frame: top-down view + transverse cross-section, stacked."""
    try:
        sim = mod.create_simulation()
    except Exception as exc:
        print(f"  [build-fail exp {exp_num}]: {exc}")
        return False

    # 2 panels: a much taller top-down + a thin cross-section underneath
    fig, axes = plt.subplots(2, 1, figsize=(11, 13),
                             gridspec_kw={"height_ratios": [5, 1]})

    # Top-down at metal plane — plot_structures shows just the geometry without
    # the PML / symmetry-plane overlay grid.
    z_metal = mod.TLN0 - mod.TLN1 + mod.TSIO21 + mod.TM / 2.0
    sim.plot_structures(z=z_metal, ax=axes[0])
    axes[0].set_xlim(*TOP_XLIM)
    axes[0].set_ylim(*TOP_YLIM)
    axes[0].set_aspect("equal")
    axes[0].set_title(f"Top-down @ metal plane (z = {z_metal:.2f} μm) — "
                      f"showing T-rail layout in ~5 unit cells",
                      fontsize=10)
    axes[0].set_xlabel("")  # save vertical space

    # G / S / G labels — exact x-position depends on the geometry knobs.
    gw = mod.GW                           # full gap (incl T-rails) at metal plane
    label_y = TOP_YLIM[1] - 14            # 14 μm below the top of the panel
    sig_x = 0.0
    left_gnd_x = -mod.WS / 2 - gw - mod.WG / 2
    right_gnd_x = +mod.WS / 2 + gw + mod.WG / 2
    label_kw = dict(ha="center", va="center", fontsize=18, fontweight="bold",
                    color="white",
                    bbox=dict(boxstyle="round,pad=0.45",
                              facecolor="#222", edgecolor="white", lw=1.2))
    # Clamp to visible x range so labels don't fly off-screen
    for x, txt in [(max(left_gnd_x, TOP_XLIM[0] + 12), "G"),
                   (sig_x, "S"),
                   (min(right_gnd_x, TOP_XLIM[1] - 12), "G")]:
        axes[0].text(x, label_y, txt, **label_kw)

    # Transverse cross-section at y=0, zoomed on the active RIGHT gap (where
    # the rib waveguide lives). Auto aspect so the panel fills its allocated
    # space — z is intentionally exaggerated relative to x so the sub-μm metal
    # thickness is visible.
    sim.plot_structures(y=0, ax=axes[1])
    axes[1].set_xlim(*CROSS_XLIM)
    axes[1].set_ylim(*CROSS_ZLIM)
    axes[1].set_aspect("auto")
    axes[1].set_title("Cross-section @ y=0, zoom on active gap "
                      "(z-axis exaggerated)", fontsize=10)
    # S / G labels for the cross-section (signal edge at +WS/2, ground at +WS/2+GW)
    label_kw_x = dict(ha="center", va="center", fontsize=11, fontweight="bold",
                      color="white",
                      bbox=dict(boxstyle="round,pad=0.2",
                                facecolor="#444", edgecolor="white", lw=0.6))
    cross_label_z = CROSS_ZLIM[1] - 0.25
    sig_edge_x = mod.WS / 2 - 5         # just inside signal trace
    gnd_edge_x = mod.WS / 2 + gw + 5    # just inside right ground rail
    if CROSS_XLIM[0] <= sig_edge_x <= CROSS_XLIM[1]:
        axes[1].text(sig_edge_x, cross_label_z, "S", **label_kw_x)
    if CROSS_XLIM[0] <= gnd_edge_x <= CROSS_XLIM[1]:
        axes[1].text(gnd_edge_x, cross_label_z, "G", **label_kw_x)

    # ------- Title block with experiment metadata -------
    topo = meta.get("topology", "?")
    topo_display = TOPO_DISPLAY.get(topo, topo)
    fom = meta.get("FOM", "?")
    color = TOPO_COLORS.get(topo, "#444")

    # Per-topology key knobs
    knob_str = (
        f"T_R={mod.T_R}  T_H={mod.T_H}  T_T={mod.T_T}  T_C={mod.T_C}  "
        f"G={mod.G}  WS={mod.WS}  TM={mod.TM}"
    )
    if topo in ("asym-T", "asym-mushroom"):
        sig_R = mod.T_R_SIG if mod.T_R_SIG > 0 else mod.T_R
        gnd_R = mod.T_R_GND if mod.T_R_GND > 0 else mod.T_R
        knob_str += f"\nT_R_SIG={sig_R}  T_R_GND={gnd_R}"
    if topo in ("mushroom-T",):
        knob_str += f"\nCAP_W={mod.CAP_W}  CAP_OVERHANG={mod.CAP_OVERHANG}"
    if topo in ("asym-mushroom",):
        knob_str += (f"\nSIG_CAP_W={mod.SIG_CAP_W}  SIG_OVH={mod.SIG_CAP_OVERHANG}"
                     f"  GND_CAP_W={mod.GND_CAP_W}  GND_OVH={mod.GND_CAP_OVERHANG}")
    if topo == "T+U":
        knob_str += (f"\nU_PERIOD_RATIO={mod.U_PERIOD_RATIO}  "
                     f"U_W={mod.U_W}  U_REACH={mod.U_REACH}")
    if topo == "slotted-signal":
        knob_str += f"\nSLOT_W={mod.SLOT_W}  SLOT_GAP={mod.SLOT_GAP}"

    try:
        fom_str = f"FOM = {float(fom):+.3f}"
    except (ValueError, TypeError):
        fom_str = f"FOM = {fom}"

    fig.suptitle(
        f"Iteration {exp_num}  ·  {topo_display}    {fom_str}",
        fontsize=15, color=color, fontweight="bold", y=0.995,
    )
    n_lines = knob_str.count("\n") + 1
    fig.text(0.5, 0.955 - 0.010 * (n_lines - 1), knob_str,
             ha="center", fontsize=8.5, color="#333", linespacing=1.2)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return True


# --------------------------------------------------------------------
# GIF + grid stitchers
# --------------------------------------------------------------------
def _frames_to_gif(frame_paths: list[Path], out_path: Path,
                   duration_ms: int = 200) -> Path:
    if not frame_paths:
        print("  [evolution] no frames to stitch")
        return out_path
    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    max_w = max(im.width for im in imgs)
    max_h = max(im.height for im in imgs)
    padded = []
    for im in imgs:
        if im.size != (max_w, max_h):
            bg = Image.new("RGB", (max_w, max_h), "white")
            bg.paste(im, ((max_w - im.width) // 2,
                          (max_h - im.height) // 2))
            padded.append(bg)
        else:
            padded.append(im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    padded[0].save(
        out_path, save_all=True, append_images=padded[1:],
        duration=duration_ms, loop=0, optimize=True,
    )
    print(f"  saved {out_path} ({len(padded)} frames)")
    return out_path


def _frames_to_grid(frame_paths: list[Path], out_path: Path,
                    cols: int = 6) -> Path:
    """Static thumbnail grid of all frames — easier to scan than a GIF."""
    if not frame_paths:
        return out_path
    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    # Downscale each thumbnail
    thumb_w = 380
    thumbs = []
    for im in imgs:
        scale = thumb_w / im.width
        thumbs.append(im.resize((thumb_w, int(im.height * scale))))
    th_w, th_h = thumbs[0].size
    rows = (len(thumbs) + cols - 1) // cols
    grid = Image.new("RGB", (cols * th_w, rows * th_h), "white")
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        grid.paste(t, (c * th_w, r * th_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path, optimize=True)
    print(f"  saved {out_path} ({len(thumbs)} thumbs, {rows}×{cols} grid)")
    return out_path


# --------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------
def build_topology_evolution(duration_ms: int = 200,
                             gif_out: Path | None = None,
                             grid_out: Path | None = None) -> dict:
    """Render per-iteration topology frames, stitch into GIF + grid."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = PLOTS_DIR / "topology_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    gif_out = gif_out or (PLOTS_DIR / "topology_evolution.gif")
    grid_out = grid_out or (PLOTS_DIR / "topology_evolution_grid.png")

    results = _load_results_index()
    exp_dirs = sorted(d for d in EXPERIMENTS_DIR.iterdir()
                      if d.is_dir() and d.name.isdigit())

    frame_paths: list[Path] = []
    for exp_dir in exp_dirs:
        n = int(exp_dir.name)
        design_py = exp_dir / "design.py"
        if not design_py.exists():
            continue
        mod = _load_design_snapshot(design_py)
        if mod is None:
            continue
        meta = results.get(n, {})
        meta["experiment"] = n
        frame_p = frames_dir / f"iter_{n:04d}.png"
        if _render_frame(mod, n, meta, frame_p):
            frame_paths.append(frame_p)

    gif_path = _frames_to_gif(frame_paths, gif_out, duration_ms=duration_ms)
    grid_path = _frames_to_grid(frame_paths, grid_out)
    return {"frames": frame_paths, "gif": gif_path, "grid": grid_path,
            "n_iters": len(frame_paths)}


if __name__ == "__main__":
    print("Building topology_evolution.gif and grid …")
    r = build_topology_evolution(duration_ms=200)
    print(f"  Total frames: {r['n_iters']}")
    print(f"  GIF: {r['gif']}")
    print(f"  Grid: {r['grid']}")
