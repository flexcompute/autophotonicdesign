"""test_carrier_frame.py — single-frame prototype for the new
doping+carriers stacked figure used by carriers_evolution.gif.

Usage:  .venv/bin/python tools/test_carrier_frame.py [ITER] [MODE]
  ITER default = 32
  MODE in {linear, nearest, tripcolor} — how we render the carriers.
"""
from __future__ import annotations
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tidy3d as td

from tools.doping_builders import (
    geometry_bounds, render_net_doping, silicon_mask,
)
from tools.evolution import _load_iter_design, _load_result_meta
from tools.backfill_carriers import (
    _list_cloud_tasks, _list_experiments, _match_tasks_to_experiments,
)
from tools.journal import EXPERIMENTS_DIR, OUTPUT_DIR

CACHE_DIR = OUTPUT_DIR / "_charge_cache"

# Shared frame axes — fixed so iteration-to-iteration comparison is fair.
_Y_RANGE = (-3.5, 3.5)
_Z_RANGE = (-0.02, 0.25)


def _overlay_silicon(ax, geom, color="k", lw=0.7):
    from matplotlib.patches import Rectangle
    b = geometry_bounds(**geom)
    h_core, h_slab, w_core = geom["h_core"], geom["h_slab"], geom["w_core"]
    ax.add_patch(Rectangle((b["y_pp_L"], 0), b["y_pp_R"] - b["y_pp_L"],
                           h_slab, fill=False, ec=color, lw=lw))
    ax.add_patch(Rectangle((-w_core / 2, 0), w_core, h_core,
                           fill=False, ec=color, lw=lw))
    for y0, y1 in [(b["y_pp_L"], b["y_slab_L"]),
                   (b["y_slab_R"], b["y_pp_R"])]:
        ax.add_patch(Rectangle((y0, 0), y1 - y0, h_core,
                               fill=False, ec=color, lw=lw))


def _resolve_task(iter_n: int) -> str | None:
    tasks = _list_cloud_tasks()
    exps = _list_experiments()
    m = _match_tasks_to_experiments(tasks, exps, max_delta_sec=900)
    for exp_num, _dir, tid, _delta in m:
        if exp_num == iter_n:
            return tid
    return None


def render_test_frame(iter_n: int = 32, mode: str = "linear",
                      out_path: Path | None = None) -> Path:
    exp_dir = EXPERIMENTS_DIR / f"{iter_n:04d}"
    loaded = _load_iter_design(exp_dir)
    assert loaded is not None, f"could not load iter {iter_n}"
    implants, geom = loaded
    meta = _load_result_meta(exp_dir)

    task_id = _resolve_task(iter_n)
    hdf5 = CACHE_DIR / f"{task_id}.hdf5"
    assert hdf5.exists(), f"hdf5 not cached: {hdf5}"
    charge_data = td.HeatChargeSimulationData.from_file(str(hdf5))

    # Fine rectangular grid for both panels so aspect matches.
    y = np.linspace(_Y_RANGE[0], _Y_RANGE[1], 1400)
    z = np.linspace(_Z_RANGE[0], _Z_RANGE[1], 180)

    # Doping
    _, _, net_dope = render_net_doping(implants, y, z)
    mask_si = silicon_mask(y, z, **geom)
    dope_disp = np.where(mask_si, net_dope, np.nan)

    # Carriers at +1 V reverse
    el = charge_data["carriers"].electrons.sel(voltage=1.0)
    ho = charge_data["carriers"].holes.sel(voltage=1.0)

    if mode in ("linear", "nearest"):
        def _resample(field):
            vals = field.interp(x=0.0, y=y, z=z, method=mode,
                                fill_value=0.0).values
            arr = np.squeeze(vals)
            # interp may return (Ny, Nz) or (Nz, Ny); want (Nz, Ny)
            if arr.shape == (len(y), len(z)):
                arr = arr.T
            return arr
        Ne = _resample(el)
        Nh = _resample(ho)
        net_free = Ne - Nh
        carrier_disp = np.where(mask_si, net_free, np.nan)
    elif mode == "tripcolor":
        carrier_disp = None  # handled below with ax.tripcolor
    else:
        raise ValueError(mode)

    # -----------------------------------------------------------------
    # Build figure — doping on top, carriers below, same x/z, equal aspect.
    # Custom gridspec: 2 thin plot rows + a right-hand colorbar column
    # sized to match the plot height (not the full figure height).
    # -----------------------------------------------------------------
    from matplotlib.gridspec import GridSpec
    fig = plt.figure(figsize=(14, 3.2))
    gs = GridSpec(
        nrows=2, ncols=2, figure=fig,
        width_ratios=[60, 1], height_ratios=[1, 1],
        left=0.05, right=0.95, bottom=0.14, top=0.82,
        hspace=0.55, wspace=0.02,
    )
    ax_d = fig.add_subplot(gs[0, 0])
    ax_c = fig.add_subplot(gs[1, 0], sharex=ax_d)
    cax = fig.add_subplot(gs[:, 1])

    cmap_dope = "RdBu_r"
    norm_dope = SymLogNorm(linthresh=1e15, vmin=-1e20, vmax=1e20)

    ax_d.pcolormesh(
        y, z, dope_disp, cmap=cmap_dope, norm=norm_dope,
        shading="auto", rasterized=True,
    )
    _overlay_silicon(ax_d, geom)
    ax_d.set_xlim(*_Y_RANGE); ax_d.set_ylim(*_Z_RANGE)
    ax_d.set_aspect("equal")
    ax_d.set_ylabel("z (µm)")
    ax_d.set_title("Design doping   Nd − Na   (red = donor / N, blue = acceptor / P)",
                   fontsize=10)
    plt.setp(ax_d.get_xticklabels(), visible=False)

    # Carriers — same symlog range so both panels share one colorbar cleanly.
    norm_car = SymLogNorm(linthresh=1e15, vmin=-1e20, vmax=1e20)
    if mode == "tripcolor":
        net_ds = el - ho
        im_c = net_ds.plot(ax=ax_c, cmap=cmap_dope)
    else:
        im_c = ax_c.pcolormesh(
            y, z, carrier_disp, cmap=cmap_dope, norm=norm_car,
            shading="auto", rasterized=True,
        )
    _overlay_silicon(ax_c, geom)
    ax_c.set_xlim(*_Y_RANGE); ax_c.set_ylim(*_Z_RANGE)
    ax_c.set_aspect("equal")
    ax_c.set_xlabel("y (µm)"); ax_c.set_ylabel("z (µm)")
    ax_c.set_title("Net free carriers  Ne − Nh  @  +1.0 V reverse",
                   fontsize=10)

    cb = fig.colorbar(im_c, cax=cax, extend="both")
    cb.set_label("cm⁻³")

    # Banner
    V = meta.get("VpiL"); C = meta.get("C"); L = meta.get("loss"); F = meta.get("FOM")
    banner = (f"Iter {iter_n}  —  W_CORE={geom['w_core']:.3f} µm  —  "
              f"{meta.get('topology','?')}   [mode={mode}]")
    try:
        banner += (f"\nVπL = {float(V):.3g} V·cm   |   C = {float(C):.3g} pF/mm"
                   f"   |   loss = {float(L):.3g} dB/cm   |   FOM = {float(F):.3g}")
    except Exception:
        pass
    fig.suptitle(banner, fontsize=10, y=0.98)

    out_path = out_path or (OUTPUT_DIR / "plots" / f"test_frame_iter{iter_n:04d}_{mode}.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"[test] wrote {out_path}")
    return out_path


if __name__ == "__main__":
    iter_n = int(sys.argv[1]) if len(sys.argv) > 1 else 32
    mode = sys.argv[2] if len(sys.argv) > 2 else "linear"
    render_test_frame(iter_n=iter_n, mode=mode)
