"""
drc.py — Geometric design-rule check for the segmented-CPW agent.

DO NOT MODIFY. The agent should only modify design.py.

Two classes of rule:

  • FAB rules — minimum metal feature & spacing of 100 nm anywhere a fab can
    print. Applies to T-rail dimensions, CPW gap, signal/ground widths,
    metal thickness.

  • PROCESS rules — TFLT/LTOI thicknesses are FIXED by the platform. The
    agent must not change `TLN0`, `TLN1`, `W0`, `THETA_LN_DEG`,
    `EPS_LN_O`, `EPS_LN_EO`. The cladding gap above LTOI (`TSIO21`)
    can only INCREASE from the baseline 0.20 μm.

Usage:
    python drc.py
Exit code 0 = pass, 1 = fail.  Failures print one line per violation.
"""
from __future__ import annotations

import sys

import design

# ============================================================
# Constants — kept here so the rules are visible in one place.
# ============================================================
MIN_FEATURE_UM = 0.100   # minimum metal feature / spacing
MIN_TM_UM      = 0.100   # minimum metal thickness
MIN_TSIO21_UM  = 0.200   # baseline cladding above LTOI; cannot decrease
PROCESS_FIXED  = {       # name -> (expected_value, tolerance_um)
    "TLN0":         (0.600, 1e-9),
    "TLN1":         (0.300, 1e-9),
    "W0":           (1.000, 1e-9),
    "THETA_LN_DEG": (30.0,  1e-9),
    "EPS_LN_O":     (44.0,  1e-9),
    "EPS_LN_EO":    (27.9,  1e-9),
    "EPS_QZ":       (4.5,   1e-9),
}


def _check_min(name: str, value: float, threshold: float, unit: str = "μm"):
    if value < threshold - 1e-9:
        return [f"FAIL  {name} = {value} {unit} < {threshold} {unit} (min feature)"]
    return []


def _check_process_fixed(name: str, value: float, expected: float, tol: float):
    if abs(value - expected) > tol:
        return [f"FAIL  {name} = {value} (must be fixed at {expected}; "
                f"process-determined, not editable)"]
    return []


def run_drc():
    violations = []

    # --- 1. Fab rules: minimum 100 nm metal features ---
    fab_features = {
        "T_S (T-top width)":          design.T_S,
        "T_T (T-neck width)":         design.T_T,
        "T_H (T-neck extension)":     design.T_H,
        "T_R (T-top length)":         design.T_R,
        "T_C (gap between Ts)":       design.T_C,
        "G  (residual CPW gap)":      design.G,
        "WS (signal trace width)":    design.WS,
        "WG (ground trace width)":    design.WG,
    }
    for name, val in fab_features.items():
        violations += _check_min(name, val, MIN_FEATURE_UM)

    # --- 2. Metal thickness ---
    violations += _check_min("TM (metal thickness)", design.TM, MIN_TM_UM)

    # --- 3. Cladding gap above LTOI (can only INCREASE from baseline 0.20) ---
    violations += _check_min("TSIO21 (cladding above LTOI)",
                             design.TSIO21, MIN_TSIO21_UM)

    # --- 4. Wide-segment ground rail width must remain ≥ 100 nm ---
    #     The wide CPW in the loaded section has ground width WG - (T_S + T_H).
    wide_ground = design.WG - (design.T_S + design.T_H)
    violations += _check_min("WG - (T_S + T_H) (loaded-section ground rail)",
                             wide_ground, MIN_FEATURE_UM)

    # --- 5. Period sanity: T_R must fit inside the period ---
    if design.T_R > design.P_T - MIN_FEATURE_UM:
        violations.append(
            f"FAIL  T_R = {design.T_R} μm leaves <100 nm gap inside period "
            f"P_T = {design.P_T} μm. Increase T_C or shrink T_R.")

    # --- 6. Process-fixed parameters must not be touched ---
    for name, (expected, tol) in PROCESS_FIXED.items():
        actual = getattr(design, name)
        violations += _check_process_fixed(name, actual, expected, tol)

    # --- 7. Sanity: the segmented section must have ≥ 5 unit cells ---
    #     Below that the S-parameter phase slope is too short to extract n_eff.
    if design.N_PERIODS < 5:
        violations.append(
            f"FAIL  N_PERIODS = {design.N_PERIODS} < 5; segmented section is "
            f"too short for reliable n_eff extraction.")

    return violations


def main():
    violations = run_drc()
    print("=" * 60)
    print("DRC — segmented CPW")
    print("=" * 60)
    print(f"  T-rail: T_S={design.T_S}  T_T={design.T_T}  "
          f"T_H={design.T_H}  T_R={design.T_R}  T_C={design.T_C}")
    print(f"  CPW   : G={design.G}   WS={design.WS}   WG={design.WG}")
    print(f"  Stack : TM={design.TM}  TSIO21={design.TSIO21}")
    print()
    if not violations:
        print("DRC PASSED")
        return 0
    print(f"DRC FAILED — {len(violations)} violation(s):")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
