"""evolution.py — cross-iteration visualizations.

Two products:
  (1) doping_evolution.gif/.png — reads each archived `design.py` under
      output/experiments/NNNN/ and renders the doping geometry with a
      FIXED axis range so viewers can see how the topology evolves.
  (2) carriers_evolution.gif   — stitches together each iteration's
      `carriers_at_target.png` (saved by simulate.py post-sim).

Both use the same y/z bounds set by the widest-ever W_CORE / H_CORE so
frame-to-frame comparison is straightforward.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .doping_builders import (
    DopingRegion, geometry_bounds, render_net_doping, silicon_mask,
)
from .journal import EXPERIMENTS_DIR, OUTPUT_DIR

PLOTS_DIR = OUTPUT_DIR / "plots"

# Fixed render domain — covers the widest geometry we've tried (W=0.70 rib
# + 1 µm contact + 2 µm clearance → ~4.4 µm total). Using ±3.5 µm keeps
# the full cross-section in view while zooming into core details at ±0.5.
_FULL_Y = (-3.5, 3.5)
_ZOOM_Y = (-0.5, 0.5)
_Z_RANGE = (-0.02, 0.25)


# =========================================================================
# Loading archived designs
# =========================================================================
def _load_iter_design(exp_dir: Path):
    """Dynamically import a frozen design.py. Return (implants, geom) or None."""
    design_py = exp_dir / "design.py"
    if not design_py.exists():
        return None
    import sys
    mod_name = f"_archived_design_{exp_dir.name}"
    # Make sure the parent 'tools' is importable
    proj_root = Path(__file__).resolve().parent.parent
    if str(proj_root) not in sys.path:
        sys.path.insert(0, str(proj_root))
    spec = importlib.util.spec_from_file_location(mod_name, design_py)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"[evolution] failed to import {design_py}: {exc}")
        return None
    try:
        implants = list(mod.IMPLANTS)
        geom = mod.geometry()
    except Exception as exc:
        print(f"[evolution] missing IMPLANTS/geometry in {design_py}: {exc}")
        return None
    return implants, geom


def _load_result_meta(exp_dir: Path) -> dict:
    """Return per-iteration metadata needed for frame headers."""
    rj = exp_dir / "results.json"
    if not rj.exists():
        return {}
    try:
        payload = json.loads(rj.read_text())
    except Exception:
        return {}
    r = payload.get("results", {})
    return dict(
        topology=payload.get("topology", ""),
        description=payload.get("description", ""),
        VpiL=r.get("VpiL_Vcm"),
        C=r.get("C_pF_mm"),
        loss=r.get("loss_dB_cm"),
        FOM=r.get("FOM"),
    )


# =========================================================================
# Per-iteration doping frame — fixed axes
# =========================================================================
def _render_doping_frame(implants, geom, iter_n, meta, out_path: Path,
                         zoom: bool = False, title: str | None = None,
                         figsize=(9, 5)):
    """Render one frame (doping profile + zoom + metadata banner)."""
    from matplotlib.colors import SymLogNorm

    fig, (ax_full, ax_zoom) = plt.subplots(
        1, 2, figsize=figsize, constrained_layout=True,
        gridspec_kw={"width_ratios": [2, 1]},
    )

    y_full = np.linspace(_FULL_Y[0], _FULL_Y[1], 700)
    z_full = np.linspace(_Z_RANGE[0], _Z_RANGE[1], 160)
    y_zoom = np.linspace(_ZOOM_Y[0], _ZOOM_Y[1], 500)
    z_zoom = np.linspace(_Z_RANGE[0], _Z_RANGE[1], 200)

    # Full-device view
    _, _, net_full = render_net_doping(implants, y_full, z_full)
    mask_full = silicon_mask(y_full, z_full, **geom)
    disp_full = np.where(mask_full, net_full, np.nan)
    im = ax_full.pcolormesh(
        y_full, z_full, disp_full, cmap="RdBu_r",
        norm=SymLogNorm(linthresh=1e15, vmin=-1e20, vmax=1e20),
        shading="auto",
    )
    _overlay_silicon(ax_full, geom)
    ax_full.set_xlim(*_FULL_Y)
    ax_full.set_ylim(*_Z_RANGE)
    ax_full.set_xlabel("y (µm)"); ax_full.set_ylabel("z (µm)")
    ax_full.set_title("Net doping  Nd − Na")

    # Zoom view
    _, _, net_zoom = render_net_doping(implants, y_zoom, z_zoom)
    mask_zoom = silicon_mask(y_zoom, z_zoom, **geom)
    disp_zoom = np.where(mask_zoom, net_zoom, np.nan)
    ax_zoom.pcolormesh(
        y_zoom, z_zoom, disp_zoom, cmap="RdBu_r",
        norm=SymLogNorm(linthresh=1e15, vmin=-1e20, vmax=1e20),
        shading="auto",
    )
    _overlay_silicon(ax_zoom, geom)
    ax_zoom.set_xlim(*_ZOOM_Y)
    ax_zoom.set_ylim(*_Z_RANGE)
    ax_zoom.set_aspect("equal")
    ax_zoom.set_xlabel("y (µm)")
    ax_zoom.set_title("Core zoom ±0.5 µm")

    # Colorbar attached to full view
    cbar = fig.colorbar(im, ax=[ax_full, ax_zoom], shrink=0.7, aspect=30,
                        location="right")
    cbar.set_label("Nd − Na (cm⁻³)")

    # Title banner
    V = meta.get("VpiL"); C = meta.get("C"); L = meta.get("loss"); F = meta.get("FOM")
    banner = (
        f"Iter {iter_n:d}  —  W_CORE={geom['w_core']:.3f} µm  —  "
        f"topology: {meta.get('topology','?')}"
    )
    metrics_line = ""
    if V is not None and C is not None:
        try:
            metrics_line = (
                f"VπL = {float(V):.3g} V·cm   |   "
                f"C = {float(C):.3g} pF/mm   |   "
                f"loss = {float(L):.3g} dB/cm   |   "
                f"FOM = {float(F):.3g}"
            )
        except Exception:
            pass
    fig.suptitle(
        (title or banner) + (f"\n{metrics_line}" if metrics_line else ""),
        fontsize=11,
    )

    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def _overlay_silicon(ax, geom):
    """Thin black outline of core + slab + contact pads on top of the pcolormesh."""
    from matplotlib.patches import Rectangle
    b = geometry_bounds(**geom)
    h_core, h_slab, w_core = geom["h_core"], geom["h_slab"], geom["w_core"]
    # Slab
    ax.add_patch(Rectangle((b["y_pp_L"], 0), b["y_pp_R"] - b["y_pp_L"],
                           h_slab, fill=False, ec="k", lw=0.7))
    # Core rib
    ax.add_patch(Rectangle((-w_core / 2, 0), w_core, h_core,
                           fill=False, ec="k", lw=0.7))
    # Contact pads
    for y0, y1 in [(b["y_pp_L"], b["y_slab_L"]),
                   (b["y_slab_R"], b["y_pp_R"])]:
        ax.add_patch(Rectangle((y0, 0), y1 - y0, h_core,
                               fill=False, ec="k", lw=0.7))


# =========================================================================
# GIF builder
# =========================================================================
def _frames_to_gif(frame_paths: list[Path], out_path: Path,
                   duration_ms: int = 900) -> Path:
    """Stitch frame PNGs into an animated GIF (pillow only, no ffmpeg)."""
    if not frame_paths:
        print("[evolution] no frames to stitch")
        return out_path
    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    # Pad all frames to the largest size so the GIF has a consistent canvas
    max_w = max(im.width for im in imgs)
    max_h = max(im.height for im in imgs)
    padded = []
    for im in imgs:
        if im.size != (max_w, max_h):
            bg = Image.new("RGB", (max_w, max_h), "white")
            bg.paste(im, ((max_w - im.width) // 2, (max_h - im.height) // 2))
            padded.append(bg)
        else:
            padded.append(im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    padded[0].save(
        out_path, save_all=True, append_images=padded[1:],
        duration=duration_ms, loop=0, optimize=True,
    )
    return out_path


# =========================================================================
# Public entry points
# =========================================================================
def build_doping_evolution(
    gif_out: Path | None = None,
    grid_out: Path | None = None,
    duration_ms: int = 900,
) -> dict:
    """Render per-iteration doping frames, stitch into GIF + grid.

    Returns a dict {"frames": [...], "gif": path, "grid": path}.
    """
    gif_out = gif_out or (PLOTS_DIR / "doping_evolution.gif")
    grid_out = grid_out or (PLOTS_DIR / "doping_evolution_grid.png")

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = PLOTS_DIR / "doping_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    iter_meta: list[dict] = []
    for exp_dir in sorted(EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.isdigit():
            continue
        iter_n = int(exp_dir.name)
        loaded = _load_iter_design(exp_dir)
        if loaded is None:
            continue
        implants, geom = loaded
        meta = _load_result_meta(exp_dir)
        meta["iter"] = iter_n
        frame_p = frames_dir / f"iter_{iter_n:04d}.png"
        _render_doping_frame(implants, geom, iter_n, meta, frame_p)
        frame_paths.append(frame_p)
        iter_meta.append(meta)

    gif_path = _frames_to_gif(frame_paths, gif_out, duration_ms=duration_ms)

    # Also build a grid (8 columns, as many rows as needed) for at-a-glance
    grid_path = _build_grid(frame_paths, grid_out)

    return dict(frames=frame_paths, gif=gif_path, grid=grid_path,
                n_iters=len(frame_paths))


def build_carrier_evolution(
    gif_out: Path | None = None,
    duration_ms: int = 900,
) -> Path | None:
    """Stitch each experiment's `carriers_at_target.png` into a GIF.

    Only iterations that ran simulate.py AFTER the carrier-save feature was
    added will have the PNG — older experiments are skipped.
    """
    gif_out = gif_out or (PLOTS_DIR / "carriers_evolution.gif")
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    frame_paths: list[Path] = []
    for exp_dir in sorted(EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.isdigit():
            continue
        p = exp_dir / "carriers_at_target.png"
        if p.exists():
            frame_paths.append(p)
    if not frame_paths:
        return None
    return _frames_to_gif(frame_paths, gif_out, duration_ms=duration_ms)


def _build_grid(frame_paths: list[Path], out_path: Path,
                ncols: int = 4) -> Path | None:
    """Grid of all frames (downscaled thumbnails) — overview.png."""
    if not frame_paths:
        return None
    imgs = [Image.open(p).convert("RGB") for p in frame_paths]
    # downscale each frame uniformly
    target_w = 700
    thumbs = []
    for im in imgs:
        ratio = target_w / im.width
        new_h = int(im.height * ratio)
        thumbs.append(im.resize((target_w, new_h)))
    w = thumbs[0].width
    h = thumbs[0].height
    n = len(thumbs)
    ncols = min(ncols, n)
    nrows = (n + ncols - 1) // ncols
    grid = Image.new("RGB", (w * ncols, h * nrows), "white")
    for i, t in enumerate(thumbs):
        r, c = divmod(i, ncols)
        grid.paste(t, (c * w, r * h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path)
    return out_path
