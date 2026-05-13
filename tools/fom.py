"""fom.py — Figure-of-merit extraction from CHARGE + mode-solver results.

Composes a single scalar FOM from (V\u03c0L, C, \u03b1) so the agent's keep/discard
decision is unambiguous. Higher FOM is better. Defaults are set so the
constant-doping SISCAP baseline gives FOM \u2248 0 — improvements push it positive.
"""
from __future__ import annotations

import numpy as np


def capacitance_pF_per_mm(charge_data, monitor_name: str = "capacitance_mnt"):
    """Return (V, C) with C in pF/mm.

    Tidy3D's SteadyCapacitanceMonitor already reports per-mm in this 2D-
    cross-section convention; the half-sum of electron / hole contributions
    with a sign flip gives the positive junction capacitance. Matches the
    Yong 2017 campaign's `capacitance_pF_per_mm` helper exactly.
    """
    mnt = charge_data[monitor_name]
    V = np.asarray(mnt.electron_capacitance.coords["v"].data, dtype=float)
    C_e = np.asarray(mnt.electron_capacitance.data, dtype=float)
    C_h = np.asarray(mnt.hole_capacitance.data, dtype=float)
    C_pF_mm = -0.5 * (C_e + C_h)
    # sort ascending in V (Tidy3D sometimes returns descending)
    order = np.argsort(V)
    return V[order], C_pF_mm[order]


def compute_fom(
    sim_data,
    mode_results: dict | None,
    target_bias_v: float = 1.0,
    wavelength_um: float = 1.31,
    # Normalization anchors = measured constant-doping SISCAP baseline
    # (experiment 0001). Future designs are scored relative to this so
    # baseline FOM = 0, improvements > 0, regressions < 0.
    baseline_VpiL_Vcm: float = 1.823,
    baseline_C_pF_mm: float = 0.2605,
    baseline_loss_dB_cm: float = 10.56,
    lambda_C: float = 1.0,
    lambda_alpha: float = 0.2,
) -> dict:
    """FOM = -log10(VpiL/b_VpiL) - \u03bb_C \u00b7 (C/b_C - 1) - \u03bb_\u03b1 \u00b7 (loss/b_loss - 1)

    Each term is zero at the baseline, positive when the design improves
    that metric (lower is better for all three), negative when it regresses.
    """
    V_c, C_pF_mm = capacitance_pF_per_mm(sim_data)
    i_c = int(np.argmin(np.abs(V_c - target_bias_v)))
    C = float(C_pF_mm[i_c])

    out = dict(
        V_sweep=list(map(float, V_c)),
        C_pF_mm_sweep=list(map(float, C_pF_mm)),
        C_pF_mm=C,
    )

    if mode_results is not None:
        V_m = np.asarray(mode_results["V"], dtype=float)
        i_m = int(np.argmin(np.abs(V_m - target_bias_v)))
        VpiL = float(mode_results["VpiL_Vcm"][i_m])
        loss = float(mode_results["loss_dB_cm"][0])   # 0 V point
        out["VpiL_Vcm"] = VpiL
        out["loss_dB_cm"] = loss
    else:
        # CHARGE-only run: FOM skips VpiL / loss (used for first-pass check).
        out["VpiL_Vcm"] = float("nan")
        out["loss_dB_cm"] = float("nan")

    # Score: higher = better, zero at baseline.
    VpiL_term = (
        -np.log10(max(out["VpiL_Vcm"], 1e-6) / baseline_VpiL_Vcm)
        if np.isfinite(out["VpiL_Vcm"]) else 0.0
    )
    C_term = -lambda_C * (C / baseline_C_pF_mm - 1.0)
    loss_term = (
        -lambda_alpha * (out["loss_dB_cm"] / baseline_loss_dB_cm - 1.0)
        if np.isfinite(out["loss_dB_cm"]) else 0.0
    )
    out["FOM"] = float(VpiL_term + C_term + loss_term)
    out["FOM_breakdown"] = dict(
        VpiL_term=float(VpiL_term),
        C_term=float(C_term),
        loss_term=float(loss_term),
    )
    return out
