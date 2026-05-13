"""
simulate.py — Submit the segmented-CPW TerminalComponentModeler to Tidy3D,
extract n_eff(f), α(f), Z0(f), and a scalar FOM, then archive the run and
refresh the dashboard.

DO NOT MODIFY. The agent should only modify design.py.

Usage:
    python simulate.py                 # full 3-D run, log + dashboard
    python simulate.py --build-only    # build modeler, print cost estimate, exit
    python simulate.py --mode2d        # cheap 2-D conventional-CPW mode solver
    python simulate.py --no-log        # 3-D run, but don't archive (debug)
    python simulate.py --description "raised T_H to push n_eff up"
                                       # description goes into journal stub
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _ensure_output():
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/data", exist_ok=True)


def _plot_summary(metrics, savepath):
    """4×2 panel summary: |S|, n_eff, α+fit, Z0, R, L, G, C — all vs frequency."""
    freqs = metrics["_freqs_Hz"]
    f_GHz = freqs / 1e9
    f_ref = metrics["F_ref_GHz"]

    fig, ax = plt.subplots(2, 4, figsize=(18, 7), tight_layout=True)

    # Row 1: S-mag, n_eff, α+fit, Z0
    ax[0, 0].plot(f_GHz, np.abs(metrics["_S11"]), label="|S11|")
    ax[0, 0].plot(f_GHz, np.abs(metrics["_S21"]), label="|S21|")
    ax[0, 0].set_xlabel("f (GHz)"); ax[0, 0].set_ylabel("|S|")
    ax[0, 0].set_title("S-parameter magnitudes")
    ax[0, 0].legend(); ax[0, 0].grid()

    ax[0, 1].plot(f_GHz, metrics["_n_eff"])
    ax[0, 1].axhline(2.20, color="gray", ls="--", label="target 2.20")
    ax[0, 1].set_xlabel("f (GHz)"); ax[0, 1].set_ylabel("n_eff (RF)")
    ax[0, 1].set_title(f"n_eff — n_eff({f_ref:.0f}) = {metrics['n_eff_at_Fref']:.3f}")
    ax[0, 1].legend(); ax[0, 1].grid()

    sqrt_f = np.sqrt(f_GHz)
    fit = metrics["alpha_0_dBcm_per_sqrtGHz"] * sqrt_f + metrics["alpha_offset_dBcm"]
    ax[0, 2].plot(f_GHz, metrics["_alpha_dBcm"], label="α(f)")
    ax[0, 2].plot(f_GHz, fit, ls="--", color="tab:red",
                  label=f"fit: {metrics['alpha_0_dBcm_per_sqrtGHz']:.3f}·√f")
    ax[0, 2].set_xlabel("f (GHz)"); ax[0, 2].set_ylabel("α (dB/cm)")
    ax[0, 2].set_title("RF loss")
    ax[0, 2].legend(); ax[0, 2].grid()

    Z0 = metrics["_Z0"]
    ax[0, 3].plot(f_GHz, np.real(Z0), label="Re(Z0)")
    ax[0, 3].plot(f_GHz, np.imag(Z0), label="Im(Z0)")
    ax[0, 3].axhline(50, color="gray", ls="--", label="target 50 Ω")
    ax[0, 3].set_xlabel("f (GHz)"); ax[0, 3].set_ylabel("Z0 (Ω)")
    ax[0, 3].set_title(f"Z0 — Re(Z0)({f_ref:.0f}) = {metrics['Z0_real_at_Fref']:.1f} Ω")
    ax[0, 3].legend(); ax[0, 3].grid()

    # Row 2: RLCG distributed-line params (per mm)
    R_mm = metrics["_R_per_mm"]
    L_mm_nH = metrics["_L_per_mm"] * 1e9     # H/mm → nH/mm
    G_mm = metrics["_G_per_mm"]
    C_mm_pF = metrics["_C_per_mm"] * 1e12    # F/mm → pF/mm

    ax[1, 0].plot(f_GHz, R_mm, color="tab:blue")
    ax[1, 0].set_xlabel("f (GHz)"); ax[1, 0].set_ylabel("R (Ω/mm)")
    ax[1, 0].set_title(f"R — R({f_ref:.0f}) = {metrics['R_Ohm_per_mm_at_Fref']:.3f} Ω/mm")
    ax[1, 0].grid()

    ax[1, 1].plot(f_GHz, L_mm_nH, color="tab:green")
    ax[1, 1].set_xlabel("f (GHz)"); ax[1, 1].set_ylabel("L (nH/mm)")
    ax[1, 1].set_title(f"L — L({f_ref:.0f}) = {metrics['L_nH_per_mm_at_Fref']:.3f} nH/mm")
    ax[1, 1].grid()

    ax[1, 2].plot(f_GHz, G_mm, color="tab:red")
    ax[1, 2].set_xlabel("f (GHz)"); ax[1, 2].set_ylabel("G (S/mm)")
    ax[1, 2].set_title(f"G — G({f_ref:.0f}) = {metrics['G_S_per_mm_at_Fref']:.3e} S/mm")
    ax[1, 2].grid()

    ax[1, 3].plot(f_GHz, C_mm_pF, color="tab:purple")
    ax[1, 3].set_xlabel("f (GHz)"); ax[1, 3].set_ylabel("C (pF/mm)")
    ax[1, 3].set_title(f"C — C({f_ref:.0f}) = {metrics['C_pF_per_mm_at_Fref']:.4f} pF/mm")
    ax[1, 3].grid()

    plt.savefig(savepath, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {savepath}")


def _print_metrics(metrics):
    print("=== Headline metrics ===")
    print(f"FOM                              : {metrics['FOM']:+.4f}")
    print(f"α₀  (dB/cm/√GHz, fitted)         : {metrics['alpha_0_dBcm_per_sqrtGHz']:.4f}")
    f_ref = metrics['F_ref_GHz']
    print(f"α   at {f_ref:.0f} GHz (dB/cm)            : {metrics['alpha_at_Fref_dBcm']:.3f}")
    print(f"Re(Z0) at {f_ref:.0f} GHz (Ω)             : {metrics['Z0_real_at_Fref']:.2f}")
    print(f"Im(Z0) at {f_ref:.0f} GHz (Ω)             : {metrics['Z0_imag_at_Fref']:.2f}")
    print(f"n_eff  at {f_ref:.0f} GHz                 : {metrics['n_eff_at_Fref']:.4f}")
    print(f"R     at {f_ref:.0f} GHz (Ω/mm)           : {metrics['R_Ohm_per_mm_at_Fref']:.4f}")
    print(f"L     at {f_ref:.0f} GHz (nH/mm)          : {metrics['L_nH_per_mm_at_Fref']:.4f}")
    print(f"G     at {f_ref:.0f} GHz (S/mm)           : {metrics['G_S_per_mm_at_Fref']:.4e}")
    print(f"C     at {f_ref:.0f} GHz (pF/mm)          : {metrics['C_pF_per_mm_at_Fref']:.5f}")


# -----------------------------------------------------------------
# 2-D mode-solver branch — cheap sanity check on the conventional CPW
# -----------------------------------------------------------------
def run_mode2d(submit=True):
    import tidy3d as td  # noqa: F401
    import tidy3d.web as web
    from design import create_2d_mode_solver, FREQS

    _ensure_output()
    ms = create_2d_mode_solver()

    if not submit:
        print("(--build-only) Skipping cloud submission.")
        return None

    print("=== 2-D mode solver on the conventional CPW ===")
    data = web.run(ms, task_name="cpwrf_mode2d", path="output/data/mode_data.hdf5")

    f_GHz = FREQS / 1e9
    n_eff = data.modes_info["n eff"].squeeze()
    alpha_dBcm = data.modes_info["loss (dB/cm)"].squeeze()
    Z0 = np.conjugate(data.transmission_line_data.Z0.isel(mode_index=0)).squeeze()
    # data.alpha and data.beta are in 1/μm in tidy3d.
    alpha_per_um = data.alpha.isel(mode_index=0).values
    beta_per_um = data.beta.isel(mode_index=0).values
    gamma_per_um = alpha_per_um + 1j * beta_per_um
    omega = 2 * np.pi * FREQS
    R = np.real(gamma_per_um * Z0.values)            # Ω/μm
    L = np.imag(gamma_per_um * Z0.values) / omega    # H/μm
    G = np.real(gamma_per_um / Z0.values)            # S/μm
    C = np.imag(gamma_per_um / Z0.values) / omega    # F/μm

    print(f"n_eff (40 GHz)        : {float(np.interp(40e9, FREQS, np.real(n_eff))):.3f}")
    print(f"α     (40 GHz, dB/cm) : {float(np.interp(40e9, FREQS, np.real(alpha_dBcm))):.3f}")
    print(f"Z0    (40 GHz, Ω)     : {float(np.interp(40e9, FREQS, np.real(Z0.values))):.2f}")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), tight_layout=True)
    axes[0, 0].plot(f_GHz, n_eff); axes[0, 0].set_title("n_eff")
    axes[0, 1].plot(f_GHz, alpha_dBcm); axes[0, 1].set_title("α (dB/cm)")
    axes[1, 0].plot(f_GHz, np.real(Z0)); axes[1, 0].set_title("Re(Z0) (Ω)")
    axes[1, 1].plot(f_GHz, R * 1e3); axes[1, 1].set_title("R (Ω/mm)")
    for a in axes.ravel():
        a.set_xlabel("f (GHz)"); a.grid()
    plt.savefig("output/mode2d.png", dpi=150, bbox_inches="tight"); plt.close(fig)
    print("Saved output/mode2d.png")
    return data


# -----------------------------------------------------------------
# 3-D segmented CPW branch
# -----------------------------------------------------------------
def run_segmented(submit=True, log=True, description=""):
    import tidy3d.web as web
    from design import create_modeler, evaluate

    _ensure_output()
    print("=== Building segmented-CPW TerminalComponentModeler ===")
    tcm = create_modeler()

    sim = tcm.simulation
    print(f"  sim size      : {tuple(round(s, 2) for s in sim.size)} μm")
    print(f"  structures    : {len(sim.structures)}")
    print(f"  monitors      : {len(sim.monitors)}")
    print(f"  ports         : {[p.name for p in tcm.ports]}")
    print(f"  freqs         : {len(tcm.freqs)} pts, {tcm.freqs[0]/1e9:.1f}–{tcm.freqs[-1]/1e9:.1f} GHz")

    if not submit:
        print("(--build-only) Skipping cloud submission.")
        return None

    # Refresh preview before cloud submission so the archive captures the
    # current geometry even if the agent forgot to run preview.py manually.
    try:
        from preview import main as _preview_main
        _preview_main()
    except Exception as e:
        print(f"(preview render failed: {e}; continuing)")

    print("\n=== Submitting to Tidy3D RF solver ===")
    start = time.time()
    tcm_data = web.run(
        tcm,
        task_name="autodesign_rf_segmented",
        path="output/data/segmented.hdf5",
    )
    elapsed = time.time() - start
    print(f"Wall time: {elapsed:.1f} s")

    print("\n=== Extracting transmission-line parameters ===")
    metrics = evaluate(tcm_data)
    _print_metrics(metrics)

    _plot_summary(metrics, "output/segmented_summary.png")

    # ---- archive + dashboard refresh -------------------------------
    if log:
        from tools.journal import (
            next_experiment_number, archive_run, promote_best,
        )
        from tools.dashboard import render_dashboard

        n = next_experiment_number()
        exp_dir = archive_run(
            experiment_n=n,
            results=metrics,
            status="ok",
            topology="T-rail",
            description=description,
            wall_time_s=elapsed,
            extra_files={"segmented.hdf5_path": "output/data/segmented.hdf5"},
        )
        promoted = promote_best(n, metrics)
        dash = render_dashboard()
        print(f"\n=== Archived experiment {n} -> {exp_dir} ===")
        print(f"  promoted to best_design.py : {promoted}")
        print(f"  dashboard refreshed        : {dash}")
        print("  (open output/dashboard.html in a browser)")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true",
                        help="Construct the modeler but do not submit to the cloud.")
    parser.add_argument("--mode2d", action="store_true",
                        help="Run the cheap 2-D conventional-CPW mode solver only.")
    parser.add_argument("--no-log", action="store_true",
                        help="Run 3-D but skip archive/dashboard (debug only).")
    parser.add_argument("--description", default="",
                        help="One-line note appended to the journal stub.")
    args = parser.parse_args()

    try:
        if args.mode2d:
            run_mode2d(submit=not args.build_only)
        else:
            run_segmented(submit=not args.build_only,
                          log=not args.no_log,
                          description=args.description)
    except Exception:
        print("CRASH", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
