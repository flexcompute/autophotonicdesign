"""simulate.py — Run the CHARGE sim + per-bias mode solves + compute the FOM.

After each run the experiment is archived in output/experiments/NNNN/ and
the dashboard (output/dashboard.html) is regenerated.

Usage:
    python simulate.py                              # full run
    python simulate.py --charge-only                # skip mode-solver batch
    python simulate.py --preflight                  # build sim; no cloud call
    python simulate.py --description "U-shape center"
    python simulate.py --topology ushape_center

Exit codes:
    0  success
    1  exception during build / run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--charge-only", action="store_true",
                        help="Skip the per-bias mode-solver batch.")
    parser.add_argument("--preflight", action="store_true",
                        help="Build the sim objects and exit (no cloud call).")
    parser.add_argument("--topology", default="constant",
                        help="Short tag for the topology being tried.")
    parser.add_argument("--description", default="",
                        help="Free-text note to log in results.tsv.")
    parser.add_argument("--experiment", type=int, default=None,
                        help="Override the auto-incremented experiment number.")
    parser.add_argument("--no-archive", action="store_true",
                        help="Don't archive this run (useful for debugging).")
    args = parser.parse_args()

    start = time.time()
    os.makedirs("output", exist_ok=True)

    try:
        from design import (
            IMPLANTS, V_SWEEP, WAVELENGTH_UM, TARGET_BIAS_V,
            geometry, evaluate, snapshot_header,
        )
        from tools.charge_sim import build_charge_simulation

        print("=== Building CHARGE simulation ===")
        print(snapshot_header())
        charge_sim, handles = build_charge_simulation(
            implants=IMPLANTS,
            geometry=geometry(),
            v_sweep=V_SWEEP,
            wavelength_um=WAVELENGTH_UM,
        )
        print(f"  structures : {len(charge_sim.structures)}")
        print(f"  monitors   : {len(charge_sim.monitors)}")
        print(f"  sim size   : {tuple(round(s, 2) for s in charge_sim.size)} µm")
        print(f"  V_SWEEP    : {V_SWEEP}")
        print(f"  target bias: {TARGET_BIAS_V} V")

        if args.preflight:
            print("\nPREFLIGHT OK — sim object built cleanly, not submitted.")
            elapsed = time.time() - start
            print(f"wall_time_s: {elapsed:.1f}")
            return 0

        print("\n=== Submitting CHARGE job to Tidy3D ===")
        import tidy3d.web as web
        charge_data = web.run(
            charge_sim,
            task_name="pn_autodesign_charge",
            path="output/charge_latest.hdf5",
        )

        mode_results = None
        if not args.charge_only:
            print("\n=== Running per-bias mode solver batch ===")
            from tools.modesolve import run_mode_solver_batch
            mode_results = run_mode_solver_batch(
                charge_sim_data=charge_data,
                implants=IMPLANTS,
                geometry=geometry(),
                v_sweep=V_SWEEP,
                wavelength_um=WAVELENGTH_UM,
            )

        print("\n=== Results ===")
        result = evaluate(charge_data, mode_results)

        # Print one `metric:` line per field so the agent can grep.
        for k, v in result.items():
            if isinstance(v, (list, dict)):
                continue
            print(f"metric: {k}={v}")

        # Save a post-sim figure with the carrier maps and C(V) overlay.
        _save_post_sim_plots(charge_data, mode_results, result)

        # Also save a standalone carrier map at the target reverse bias
        # so we can later build an "evolution" GIF across iterations.
        try:
            _save_carrier_map_at_target(charge_data)
        except Exception as e:
            print(f"[carrier map] failed: {e}")

        elapsed = time.time() - start
        print(f"wall_time_s: {elapsed:.1f}")

        # Archive this iteration and regenerate dashboard.
        if not args.no_archive:
            _finalize(experiment_n=args.experiment, result=result,
                      topology=args.topology, description=args.description,
                      wall_time_s=elapsed, status="ok")
        return 0

    except Exception:
        elapsed = time.time() - start
        print(f"\nCRASH after {elapsed:.1f}s", file=sys.stderr)
        traceback.print_exc()
        # Archive the crash too, with status="crash" and empty metrics.
        if not args.no_archive and not args.preflight:
            try:
                _finalize(experiment_n=args.experiment,
                          result={"FOM": float("nan")},
                          topology=args.topology,
                          description=(args.description or "crashed"),
                          wall_time_s=elapsed, status="crash")
            except Exception:
                traceback.print_exc()
        return 1


def _finalize(experiment_n, result, topology, description, wall_time_s, status):
    """Archive the run + regenerate dashboard + promote if new best."""
    from tools.journal import (
        archive_run, promote_best, next_experiment_number,
    )
    from tools.dashboard import render_dashboard
    from tools.evolution import build_doping_evolution, build_carrier_evolution

    n = experiment_n if experiment_n is not None else next_experiment_number()
    exp_dir = archive_run(
        experiment_n=n, results=result,
        topology=topology, description=description,
        wall_time_s=wall_time_s, status=status,
    )
    print(f"\nArchived -> {exp_dir}")

    if status == "ok" and promote_best(n, result):
        print(f"NEW BEST  FOM={result.get('FOM')} — "
              "output/best_design.py updated.")

    dash = render_dashboard()
    print(f"Dashboard refreshed -> {dash}")

    try:
        info = build_doping_evolution()
        print(f"Doping evolution GIF refreshed ({info['n_iters']} frames)")
    except Exception as e:
        print(f"[evolution] doping GIF build failed: {e}")
    try:
        gif = build_carrier_evolution()
        if gif is not None:
            print(f"Carrier evolution GIF refreshed -> {gif}")
    except Exception as e:
        print(f"[evolution] carrier GIF build failed: {e}")


def _save_carrier_map_at_target(charge_data):
    """Save a single-panel net-carriers figure at TARGET_BIAS_V.

    Layout matches tools/backfill_carriers so every iteration's frame is
    stylistically consistent for the evolution GIF. One wide, short panel
    showing Ne − Nh on a diverging symmetric-log scale (RdBu): red =
    electron-dominant, blue = hole-dominant, white = depletion.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import SymLogNorm
    import numpy as np

    from design import TARGET_BIAS_V, IMPLANTS, geometry
    from tools.doping_builders import silicon_mask
    from tools.backfill_carriers import _overlay_silicon

    V_target = float(TARGET_BIAS_V)
    geom = geometry()

    y = np.linspace(-3.5, 3.5, 900)
    z = np.linspace(-0.02, 0.25, 130)

    cm = charge_data["carriers"]
    el = cm.electrons.sel(voltage=V_target)
    ho = cm.holes.sel(voltage=V_target)

    def _resample(field):
        vals = field.interp(x=0.0, y=y, z=z, method="nearest").values
        arr = np.squeeze(vals)
        if arr.shape != (len(y), len(z)) and arr.T.shape == (len(z), len(y)):
            return arr.T
        return arr.T

    Ne = _resample(el)
    Nh = _resample(ho)
    net_free = Ne - Nh
    mask = silicon_mask(y, z, **geom)

    fig, ax = plt.subplots(figsize=(14, 2.2), constrained_layout=True)
    im = ax.pcolormesh(
        y, z, np.where(mask, net_free, np.nan), cmap="RdBu_r",
        norm=SymLogNorm(linthresh=1e12, vmin=-1e20, vmax=1e20),
        shading="auto",
    )
    _overlay_silicon(ax, geom)
    ax.set_xlim(-3.5, 3.5)
    ax.set_ylim(-0.02, 0.25)
    ax.set_xlabel("y (µm)")
    ax.set_ylabel("z (µm)")
    ax.set_title(
        f"Net free carriers Ne − Nh  @  +{V_target:.1f} V reverse   "
        "(red = electrons, blue = holes, white = depletion)",
        fontsize=10,
    )
    cb = fig.colorbar(im, ax=ax, shrink=0.85, aspect=10)
    cb.set_label("cm⁻³")
    fig.savefig("output/carriers_at_target.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("Saved output/carriers_at_target.png")


def _save_post_sim_plots(charge_data, mode_results, result):
    """Write output/fields.png : carrier maps at 0 V and target bias, plus C(V) / VπL(V)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from design import IMPLANTS, TARGET_BIAS_V, geometry
    from tools.viz import plot_carrier_density

    geom = geometry()
    V_c = np.asarray(result["V_sweep"])
    C_pF = np.asarray(result["C_pF_mm_sweep"])

    # Carrier maps need the structured interpolation helper from the Yong
    # campaign; for the scaffolding we skip and plot C(V) + VπL(V) only.
    ncols = 2 if mode_results is None else 3
    fig, axs = plt.subplots(1, ncols, figsize=(5.5 * ncols, 4),
                            constrained_layout=True)

    # C(V)  — V_SWEEP is already positive reverse-bias magnitudes
    axs[0].plot(V_c, C_pF, "o-", lw=2, color="tab:blue")
    axs[0].set_xlabel("Reverse bias V (V)")
    axs[0].set_ylabel("C (pF/mm)")
    axs[0].set_title("Junction capacitance")
    axs[0].grid(alpha=0.3)

    # FOM summary text
    axs[1].axis("off")
    def _fmt(v, digits=4):
        try:
            fv = float(v)
            return f"{fv:.{digits}g}"
        except Exception:
            return str(v)
    lines = [
        f"W_CORE = {geom['w_core']:.3f} µm",
        f"H_CORE = {geom['h_core']:.3f} µm",
        f"H_SLAB = {geom['h_slab']:.3f} µm",
        f"Target bias = +{TARGET_BIAS_V:.2f} V (reverse)",
        "",
        f"C(V_target)   = {_fmt(result['C_pF_mm'], 4)} pF/mm",
        f"VπL(V_target) = {_fmt(result['VpiL_Vcm'], 4)} V·cm",
        f"loss(0V)      = {_fmt(result['loss_dB_cm'], 4)} dB/cm",
        "",
        f"FOM = {_fmt(result['FOM'], 4)}",
    ]
    axs[1].text(0.05, 0.95, "\n".join(lines), va="top", ha="left",
                family="monospace", fontsize=10)
    axs[1].set_title("Summary")

    # VπL(V)
    if mode_results is not None:
        V_m = np.asarray(mode_results["V"])
        VpiL = np.asarray(mode_results["VpiL_Vcm"])
        axs[2].plot(V_m, VpiL, "o-", lw=2, color="tab:green")
        axs[2].set_xlabel("Reverse bias V (V)")
        axs[2].set_ylabel("VπL (V·cm)")
        axs[2].set_title("Half-wave voltage-length product")
        axs[2].grid(alpha=0.3)

    fig.savefig("output/fields.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved output/fields.png")


if __name__ == "__main__":
    sys.exit(main())
