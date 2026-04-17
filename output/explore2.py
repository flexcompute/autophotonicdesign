"""Compute the optimal adiabatic taper profile from mode-solver data.
Uses Hamerly-style dW/dz ∝ (β_TE0 - β_TE2)."""

import numpy as np

arr = np.load("output/neff_vs_W.npy")
W = arr[:, 0]
# From inspection: mode order varies with W. Need to identify TE2 (2nd even mode).
# At W=0.5, only one guided mode (n0≈2.41). Others are cladding.
# At W>=1.0, modes are sorted by neff: TE0, TE1, TE2, TE3, ...
# TE2 is at column 3 (index 2 after W column → arr column 3) for W>=1.
# For W<1: TE2 not guided; use SiO2 index (1.44) as floor (worst-case coupling far below).

n0 = arr[:, 1]
n2 = arr[:, 3]  # TE2 column
# Floor n2 at 1.44 (where it approaches cladding); below that TE2 isn't confined
n2 = np.maximum(n2, 1.44)
dn = n0 - n2
dn = np.maximum(dn, 0.03)  # clamp minimum to avoid division blow-up

L = 6.0
W0, W1 = 0.5, 5.0

# z(W) = L * ∫_W0^W (1/dn) dW' / ∫_W0^W1 (1/dn) dW'
integrand = 1.0 / dn
# cumulative trapezoid integral
cum = np.zeros_like(W)
for i in range(1, len(W)):
    cum[i] = cum[i-1] + 0.5 * (integrand[i] + integrand[i-1]) * (W[i] - W[i-1])

z_of_W = L * cum / cum[-1]

# Invert: sample at uniform z and interpolate W
N = 80
zs = np.linspace(0, L, N)
ws = np.interp(zs, z_of_W, W)

# Diagnostics
print(f"{'W':>6} {'n0':>7} {'n2':>7} {'Δn':>6} {'1/Δn':>7} {'z(W)':>6}")
for i in range(len(W)):
    print(f"{W[i]:6.3f} {n0[i]:7.4f} {n2[i]:7.4f} {dn[i]:6.4f} {integrand[i]:7.2f} {z_of_W[i]:6.3f}")

# Peak slope
dW_dz = np.gradient(ws, zs)
print(f"\npeak dW/dz = {max(abs(dW_dz)):.3f} µm/µm")
print(f"linear slope = {(W1-W0)/L:.3f} µm/µm")

# Save the profile
np.save("output/hamerly_profile.npy", np.column_stack([zs, ws]))
print("Saved hamerly profile")
print(f"W at x=0.5: {np.interp(0.5, zs, ws):.3f}")
print(f"W at x=1.0: {np.interp(1.0, zs, ws):.3f}")
print(f"W at x=2.0: {np.interp(2.0, zs, ws):.3f}")
print(f"W at x=3.0: {np.interp(3.0, zs, ws):.3f}")
print(f"W at x=4.0: {np.interp(4.0, zs, ws):.3f}")
print(f"W at x=5.0: {np.interp(5.0, zs, ws):.3f}")
