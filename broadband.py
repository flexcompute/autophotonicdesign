"""
broadband.py — run the best 3D design with a broadband mode monitor
(1500-1600 nm, 31 points) and plot insertion loss vs. wavelength.

Usage:
    python broadband.py
Outputs:
    output/insertion_loss.png — IL [dB] vs. wavelength [nm]
    output/sim_data/broadband.hdf5 — raw simulation data
"""

import sys
import time
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import tidy3d as td
import tidy3d.web as web

sys.path.insert(0, "output")
from best_design import create_simulation  # noqa: E402


def main():
    start = time.time()

    sim = create_simulation()
    print("=== Building broadband simulation ===")
    print(f"  structures : {len(sim.structures)}")
    print(f"  monitors   : {len(sim.monitors)}")
    print(f"  sim size   : {tuple(round(s, 2) for s in sim.size)} μm")

    # Mode monitor freqs (set inside best_design.py)
    mode_freqs = np.array(sim.monitors[0].freqs)
    wavelengths_nm = 1000.0 * td.C_0 / mode_freqs  # um -> nm
    print(
        f"  mode freqs : {len(mode_freqs)} points, "
        f"{wavelengths_nm.min():.1f}-{wavelengths_nm.max():.1f} nm"
    )

    print("\n=== Submitting to Tidy3D ===")
    sim_data = web.run(
        sim,
        task_name="broadband_3d_fgc",
        path="output/sim_data/broadband.hdf5",
    )

    # Coupling into the backward TE mode at each frequency
    amps = sim_data["mode"].amps.sel(mode_index=0, direction="-").values
    coupling = np.abs(amps) ** 2  # power coupling, 0..1
    insertion_loss_db = -10.0 * np.log10(np.maximum(coupling, 1e-12))

    # Sort by wavelength (ascending) for plotting
    order = np.argsort(wavelengths_nm)
    wl_sorted = wavelengths_nm[order]
    il_sorted = insertion_loss_db[order]
    coup_sorted = coupling[order]

    peak_idx = int(np.argmin(il_sorted))
    print("\n=== Results ===")
    print(f"  peak coupling : {coup_sorted[peak_idx]:.4f} "
          f"at {wl_sorted[peak_idx]:.1f} nm (IL = {il_sorted[peak_idx]:.2f} dB)")
    # 3 dB bandwidth (crude: width where IL <= IL_min + 3)
    il_min = il_sorted.min()
    below_3db = il_sorted <= il_min + 3.0
    if below_3db.any():
        i0 = int(np.argmax(below_3db))
        i1 = len(below_3db) - int(np.argmax(below_3db[::-1])) - 1
        print(f"  3-dB bandwidth (approx): {wl_sorted[i0]:.1f}–{wl_sorted[i1]:.1f} nm "
              f"({wl_sorted[i1] - wl_sorted[i0]:.1f} nm wide)")

    # Plot
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(wl_sorted, il_sorted, "o-", color="C0", lw=1.5, ms=4)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Insertion loss (dB)")
    ax.set_title("3D focusing grating coupler: insertion loss vs. wavelength")
    ax.grid(True, alpha=0.3)
    # ymax = 0 dB at the top of the plot, ymin at the bottom (auto-scaled).
    ax.set_ylim(bottom=float(il_sorted.max()) * 1.1, top=0.0)
    ax.axvline(1550, color="gray", lw=0.8, ls="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig("output/insertion_loss.png", dpi=150, bbox_inches="tight")
    print("\nSaved output/insertion_loss.png")

    elapsed = time.time() - start
    print(f"wall_time_s: {elapsed:.1f}")


if __name__ == "__main__":
    main()
