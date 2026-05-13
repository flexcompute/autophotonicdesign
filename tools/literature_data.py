"""literature_data.py — VπL-vs-Cpn Pareto points from the NVIDIA OFC 2026 review.

Source: D. Patel, "Si Microring Resonator Modulators at >200Gb/s," OFC 2026,
paper M2A.7, Fig. 3. The author scaled each paper's reported values by radius,
estimated fill factor, and wavelength to place them on a common Cpn (aF/µm)
vs VπL (V·cm) axis, and fit the overall trend with

    VπL ≈ 673 / Cpn − 0.0705    (R² = 0.879, n = 13/18)

Points below / to the left of this fit are favorable (high phase-shifter
efficiency at low junction capacitance).

Legend:
    CAP  — SISCAP / MOSCAP (metal-oxide-semiconductor capacitor)
    LPN  — lateral PN
    VPN  — vertical PN
    UPN  — U-shaped PN
    ZPN  — Z-shaped PN
    mPN  — meandered PN
"""

# Each entry: (Cpn_aF_per_um, VpiL_Vcm, junction_type, label, is_open_marker)
# Positions read off Fig. 3 — accuracy ~5%. Open markers in the paper
# indicate simulation-only (not measurement).
LITERATURE_POINTS = [
    # CAP (SISCAP / MOSCAP)
    (350,  2.13, "CAP", "CAP-JLT.2020.3026945",      False),
    (3400, 0.20, "CAP", "CAP-OFC.2015.W4H.3",        False),
    (4250, 0.13, "CAP", "CAP-PRJ.438047",            False),
    # LPN (lateral PN)
    (480,  1.05, "LPN", "LPN-JLT.2025.3561153",      False),
    (830,  0.82, "LPN", "LPN-PRJ.441791",            False),
    (870,  0.71, "LPN", "LPN-LPT.2022.3170554",      False),
    (1670, 0.69, "LPN", "LPN-OFC.2025.Th1E.3",       False),
    # UPN (U-shape)
    (350,  0.47, "UPN", "UPN-OE.25.008425 (sim)",    True),
    (2200, 0.26, "UPN", "UPN-OE.25.008425 (meas)",   False),
    # VPN (vertical PN)
    (970,  0.55, "VPN", "VPN-OFC.2022.M2D.4",        False),
    (1100, 0.48, "VPN", "VPN-CLEO_SI.2021.SF1C.3",   False),
    (1200, 0.36, "VPN", "VPN-JLT.2024.3483313",      False),
    (1120, 0.28, "VPN", "VPN-JLT.2024.3483313 (b)",  False),
    # ZPN (Z-shape)
    (350,  0.53, "ZPN", "ZPN-s41467-024-45301-3",    False),
    (830,  0.65, "ZPN", "ZPN-LPT.2022.3170554",      False),
    # mPN (meandered PN)
    (350,  1.05, "mPN", "mPN-OE.560256",             True),
    (860,  2.00, "mPN", "mPN-LPT.2012.2213244",      True),
]

# Fit reported in Fig. 3 inset
PATEL_FIT = dict(A=673.0, B=-0.0705, r_squared=0.879)

# Color map matching the paper (Fig. 3 legend)
JUNCTION_COLORS = {
    "CAP": "#1f77b4",   # blue
    "LPN": "#ff7f0e",   # orange
    "UPN": "#2ca02c",   # green
    "VPN": "#d62728",   # red
    "ZPN": "#9467bd",   # purple
    "mPN": "#8c564b",   # brown
}


def fit_curve_vpil(cpn_aF_per_um, *, A=PATEL_FIT["A"], B=PATEL_FIT["B"]):
    """Evaluate the Fig. 3 trend line at any Cpn (aF/µm)."""
    return A / cpn_aF_per_um + B


def pF_per_mm_to_aF_per_um(c_pf_mm: float) -> float:
    """Convert our internal C (pF/mm) to the paper's axis units (aF/µm).

    1 pF/mm = 10⁻⁹ F/m = 10³ aF/µm.
    """
    return c_pf_mm * 1000.0
