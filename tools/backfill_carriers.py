"""backfill_carriers.py — retrieve past CHARGE tasks from Tidy3D cloud,
render a single-panel carrier figure at +1V reverse bias per iteration,
and save into each experiment folder.

Matches cloud tasks to archived experiments by timestamp (each experiment's
results.json records its creation time; cloud tasks keep their created_at).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, SymLogNorm
import numpy as np

from .journal import EXPERIMENTS_DIR, OUTPUT_DIR
from .doping_builders import geometry_bounds, render_net_doping, silicon_mask

PLOTS_DIR = OUTPUT_DIR / "plots"
CACHE_DIR = OUTPUT_DIR / "_charge_cache"


def _list_cloud_tasks():
    import tidy3d.web as web
    tasks = web.get_tasks(num_tasks=500, order="new")
    ours = [t for t in tasks
            if t.get("taskName") == "pn_autodesign_charge"
            and t.get("status") == "success"]
    # Parse created_at to aware datetime
    for t in ours:
        ts = t["created_at"]
        if isinstance(ts, str):
            t["_ts"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            t["_ts"] = ts
    ours.sort(key=lambda t: t["_ts"])
    return ours


def _list_experiments():
    """Return sorted list of (exp_num, exp_dir, timestamp_utc)."""
    rows = []
    # Treat naive experiment timestamps as LOCAL time (that's how
    # datetime.now().isoformat() writes them in journal.py).
    local_tz = datetime.now().astimezone().tzinfo
    for d in sorted(EXPERIMENTS_DIR.iterdir()):
        if not d.is_dir() or not d.name.isdigit():
            continue
        rj = d / "results.json"
        if not rj.exists():
            continue
        try:
            payload = json.loads(rj.read_text())
            ts = datetime.fromisoformat(payload["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=local_tz)
            rows.append((int(d.name), d, ts.astimezone(timezone.utc)))
        except Exception:
            continue
    return rows


def _match_tasks_to_experiments(tasks, experiments,
                                max_delta_sec: int = 900):
    """For each experiment, find the cloud task with the closest created_at
    that's EARLIER than the experiment's timestamp (since archive happens
    after the run).

    Returns list of (exp_num, exp_dir, task_id) tuples.
    """
    import time
    matches = []
    used_tasks = set()
    for exp_num, exp_dir, exp_ts in experiments:
        best = None
        best_delta = None
        for t in tasks:
            tid = t["task_id"]
            if tid in used_tasks:
                continue
            delta = (exp_ts - t["_ts"]).total_seconds()
            # Only consider tasks that completed BEFORE the experiment timestamp
            if delta < 0 or delta > max_delta_sec:
                continue
            if best_delta is None or delta < best_delta:
                best = t
                best_delta = delta
        if best is not None:
            used_tasks.add(best["task_id"])
            matches.append((exp_num, exp_dir, best["task_id"], best_delta))
        else:
            matches.append((exp_num, exp_dir, None, None))
    return matches


_CMAP = "bwr"              # diverging blue-white-red
_Y_RANGE = (-3.5, 3.5)
_Z_RANGE = (-0.02, 0.25)


def _render_carriers_frame(
    iter_n: int, charge_data, implants, geom, meta: dict,
    out_path: Path, V_target: float = 1.0,
):
    """Render a two-panel frame: design doping on top, free carriers below.

    Same SymLogNorm on both axes so geometry and carrier response can be
    eyeballed side-by-side. No colorbar (keeps the thin, equal-aspect
    panels uncluttered) — the legend in the banner describes the colours.
    """
    from matplotlib.gridspec import GridSpec

    y = np.linspace(_Y_RANGE[0], _Y_RANGE[1], 1400)
    z = np.linspace(_Z_RANGE[0], _Z_RANGE[1], 180)

    # --- Design doping ------------------------------------------------
    from .doping_builders import render_net_doping as _dope_render
    _, _, net_dope = _dope_render(implants, y, z)
    mask_si = silicon_mask(y, z, **geom)
    dope_disp = np.where(mask_si, net_dope, np.nan)

    # --- Carriers at V_target ----------------------------------------
    cm = charge_data["carriers"]
    el = cm.electrons.sel(voltage=float(V_target))
    ho = cm.holes.sel(voltage=float(V_target))

    def _resample(field):
        # Linear interpolation avoids nearest-neighbour zigzag artefacts
        # at the silicon edge (unstructured triangular mesh).
        vals = field.interp(x=0.0, y=y, z=z, method="linear",
                            fill_value=0.0).values
        arr = np.squeeze(vals)
        if arr.shape == (len(y), len(z)):
            arr = arr.T
        return arr

    Ne = _resample(el)
    Nh = _resample(ho)
    net_free = Ne - Nh
    carrier_disp = np.where(mask_si, net_free, np.nan)

    # --- Figure --------------------------------------------------------
    fig = plt.figure(figsize=(14, 2.9))
    gs = GridSpec(
        nrows=2, ncols=1, figure=fig,
        left=0.05, right=0.98, bottom=0.14, top=0.82,
        hspace=0.55,
    )
    ax_d = fig.add_subplot(gs[0, 0])
    ax_c = fig.add_subplot(gs[1, 0], sharex=ax_d)

    norm = SymLogNorm(linthresh=1e15, vmin=-1e20, vmax=1e20)

    ax_d.pcolormesh(y, z, dope_disp, cmap=_CMAP, norm=norm,
                    shading="auto", rasterized=True)
    _overlay_silicon(ax_d, geom)
    ax_d.set_xlim(*_Y_RANGE); ax_d.set_ylim(*_Z_RANGE)
    ax_d.set_aspect("equal")
    ax_d.set_ylabel("z (µm)")
    ax_d.set_title("Design doping   Nd − Na    (red = donor / N,  blue = acceptor / P)",
                   fontsize=9)
    plt.setp(ax_d.get_xticklabels(), visible=False)

    ax_c.pcolormesh(y, z, carrier_disp, cmap=_CMAP, norm=norm,
                    shading="auto", rasterized=True)
    _overlay_silicon(ax_c, geom)
    ax_c.set_xlim(*_Y_RANGE); ax_c.set_ylim(*_Z_RANGE)
    ax_c.set_aspect("equal")
    ax_c.set_xlabel("y (µm)"); ax_c.set_ylabel("z (µm)")
    ax_c.set_title(
        f"Net free carriers  Ne − Nh  @  +{V_target:.1f} V reverse   "
        "(white = depletion)",
        fontsize=9,
    )

    # Title banner
    V = meta.get("VpiL"); C = meta.get("C"); L = meta.get("loss"); F = meta.get("FOM")
    metrics_line = ""
    try:
        metrics_line = (
            f"VπL = {float(V):.3g} V·cm   |   C = {float(C):.3g} pF/mm   |   "
            f"loss = {float(L):.3g} dB/cm   |   FOM = {float(F):.3g}"
        )
    except Exception:
        pass
    fig.suptitle(
        f"Iter {iter_n}  —  W_CORE={geom['w_core']:.3f} µm  —  "
        f"{meta.get('topology','?')}" +
        (f"\n{metrics_line}" if metrics_line else ""),
        fontsize=10, y=0.98,
    )

    fig.savefig(out_path, dpi=110)
    plt.close(fig)


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


def backfill_all(V_target: float = 1.0, max_delta_sec: int = 900,
                 limit: Optional[int] = None):
    """Download carrier data for every archived experiment and render a
    single-panel electrons+holes plot at +V_target reverse bias.
    """
    from tools.evolution import _load_iter_design, _load_result_meta
    import tidy3d.web as web
    import tidy3d as td

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    tasks = _list_cloud_tasks()
    experiments = _list_experiments()
    matches = _match_tasks_to_experiments(
        tasks, experiments, max_delta_sec=max_delta_sec
    )
    print(f"[backfill] {len(experiments)} experiments, {len(tasks)} cloud tasks, "
          f"{sum(1 for m in matches if m[2])} matched")

    count = 0
    for exp_num, exp_dir, task_id, delta in matches:
        if task_id is None:
            print(f"  iter {exp_num}: no matching task — skipped")
            continue
        if limit is not None and count >= limit:
            break

        out_png = exp_dir / "carriers_at_target.png"
        # Always re-render (format may have changed since last backfill).

        loaded = _load_iter_design(exp_dir)
        if loaded is None:
            print(f"  iter {exp_num}: couldn't load design — skipping")
            continue
        implants, geom = loaded
        meta = _load_result_meta(exp_dir)

        # Download (or use cached) HDF5
        hdf5_path = CACHE_DIR / f"{task_id}.hdf5"
        try:
            if not hdf5_path.exists():
                print(f"  iter {exp_num}: downloading task {task_id[:12]}... "
                      f"(\u0394={delta:.0f}s)")
                web.load(task_id, path=str(hdf5_path), verbose=False)
            charge_data = td.HeatChargeSimulationData.from_file(str(hdf5_path))
        except Exception as e:
            print(f"  iter {exp_num}: download failed — {e}")
            continue

        try:
            _render_carriers_frame(
                exp_num, charge_data, implants, geom, meta,
                out_path=out_png, V_target=V_target,
            )
            count += 1
            print(f"  iter {exp_num}: saved {out_png.name}")
        except Exception as e:
            print(f"  iter {exp_num}: render failed — {e}")

    print(f"[backfill] done — {count} frames generated")


if __name__ == "__main__":
    backfill_all()
