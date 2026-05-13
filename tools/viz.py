"""Visualization helpers for the PN auto-design agent.

Pure matplotlib + numpy. No Tidy3D dependency: these functions render the
doping profile and silicon mask straight from the `IMPLANTS` list, so they
can be called before any cloud simulation.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, SymLogNorm
from matplotlib.patches import Rectangle
import numpy as np

from .doping_builders import DopingRegion, render_net_doping, silicon_mask, geometry_bounds


def plot_net_doping(ax, regions: list[DopingRegion], y_grid, z_grid,
                    geom: dict, linthresh: float = 1e15,
                    vmin: float = -1e20, vmax: float = 1e20,
                    title: str = "Net doping  Nd − Na  (red = N, blue = P)",
                    equal_aspect: bool = False):
    """Pcolormesh of Nd - Na on a symmetric log scale (RdBu_r).

    Blue = net acceptors (P), red = net donors (N). White ~ intrinsic.
    """
    _, _, net = render_net_doping(regions, y_grid, z_grid)
    mask = silicon_mask(y_grid, z_grid, **geom)
    net_disp = np.where(mask, net, np.nan)

    im = ax.pcolormesh(
        y_grid, z_grid, net_disp, cmap="RdBu_r",
        norm=SymLogNorm(linthresh=linthresh, vmin=vmin, vmax=vmax),
        shading="auto",
    )
    _draw_geom_outline(ax, geom, equal_aspect=equal_aspect, color="k", lw=1.0)
    ax.set_xlabel("y (µm)"); ax.set_ylabel("z (µm)")
    ax.set_title(title)
    return im


def plot_silicon_mask_with_labels(ax, regions: list[DopingRegion], geom: dict,
                                  show_region_names: bool = True,
                                  y_range: tuple | None = None,
                                  equal_aspect: bool = False,
                                  title: str | None = None):
    """Outline of Si + each doping stripe with labels. No density mapping."""
    _draw_geom_outline(ax, geom, color="k", lw=1.0, equal_aspect=equal_aspect)

    # Draw each region rect; color by polarity, alpha by log10(concentration).
    for r in regions:
        w = r.ymax - r.ymin
        h = r.zmax - r.zmin
        logc = np.log10(max(r.concentration, 1.0))
        alpha = np.clip((logc - 16) / 4, 0.15, 0.85)   # 1e16..1e20 -> 0.15..0.85
        color = "tab:blue" if r.kind == "acceptor" else "tab:red"
        rect = Rectangle((r.ymin, r.zmin), w, h,
                         facecolor=color, alpha=alpha, edgecolor=color,
                         linewidth=0.6)
        ax.add_patch(rect)

    # Labels — place them outside the rectangles (above the silicon) with a
    # guide line, so text never overlaps tiny stripes.
    if show_region_names:
        _draw_region_labels(ax, regions, geom)

    b = geometry_bounds(**geom)
    if y_range is not None:
        ax.set_xlim(*y_range)
    else:
        ax.set_xlim(b["y_pp_L"] - 0.1, b["y_pp_R"] + 0.1)
    ax.set_ylim(-0.15, geom["h_core"] + 0.20)
    ax.set_xlabel("y (µm)"); ax.set_ylabel("z (µm)")
    if equal_aspect:
        ax.set_aspect("equal")
    if title is None:
        title = "Implant boxes  (red = N, blue = P; alpha ∝ log₁₀(N))"
    ax.set_title(title)


def _draw_region_labels(ax, regions, geom):
    """Stagger text labels above/below the silicon with leader lines."""
    h_core = geom["h_core"]
    # Sort by y-center so adjacent stripes alternate up/down to avoid overlap.
    sorted_r = sorted(regions, key=lambda r: (r.ymin + r.ymax) / 2)
    for i, r in enumerate(sorted_r):
        yc = (r.ymin + r.ymax) / 2
        zc = (r.zmin + r.zmax) / 2
        above = (i % 2 == 0)
        ytext = h_core + 0.10 if above else -0.06
        va = "bottom" if above else "top"
        ax.annotate(
            r.name, xy=(yc, zc), xytext=(yc, ytext),
            ha="center", va=va, fontsize=6,
            arrowprops=dict(arrowstyle="-", color="0.4", lw=0.3),
        )


def plot_carrier_density(ax, carrier_2d: np.ndarray, y_grid, z_grid,
                         geom: dict, title: str, cmap: str = "viridis",
                         vmin: float = 1e10, vmax: float = 1e20):
    """Log-scale pcolormesh of a carrier density (holes or electrons)."""
    im = ax.pcolormesh(
        y_grid, z_grid, carrier_2d, cmap=cmap,
        norm=LogNorm(vmin=vmin, vmax=vmax),
        shading="auto",
    )
    _draw_geom_outline(ax, geom)
    ax.set_xlabel("y (µm)"); ax.set_ylabel("z (µm)")
    ax.set_title(title)
    return im


def plot_mode_intensity(ax, E_abs: np.ndarray, y_grid, z_grid, geom: dict,
                        title: str = "|E|  baseline mode"):
    """Linear-scale pcolormesh of |E|, with silicon outline overlaid."""
    im = ax.pcolormesh(y_grid, z_grid, E_abs, cmap="magma", shading="auto")
    _draw_geom_outline(ax, geom, color="w")
    ax.set_xlabel("y (µm)"); ax.set_ylabel("z (µm)")
    ax.set_title(title)
    return im


# -------------------------------------------------------------------------
# Private helpers
# -------------------------------------------------------------------------

def _draw_geom_outline(ax, geom: dict, color: str = "k",
                       face_alpha: float = 0.0, lw: float = 0.8,
                       equal_aspect: bool = False):
    """Outline the silicon cross-section (core + slab + contact pads)."""
    b = geometry_bounds(**geom)
    h_core, h_slab = geom["h_core"], geom["h_slab"]
    w_core = geom["w_core"]

    # slab strip (across the whole device, h_slab tall)
    slab = Rectangle(
        (b["y_pp_L"], 0.0), b["y_pp_R"] - b["y_pp_L"], h_slab,
        fill=False, edgecolor=color, linewidth=lw,
    )
    ax.add_patch(slab)
    # rib (core)
    core = Rectangle(
        (-w_core / 2, 0.0), w_core, h_core,
        fill=False, edgecolor=color, linewidth=lw,
    )
    ax.add_patch(core)
    # contact pads (full-height silicon on the outer slab regions)
    for y_in, y_out in [(b["y_pp_L"], b["y_slab_L"]),
                        (b["y_slab_R"], b["y_pp_R"])]:
        pad = Rectangle(
            (y_in, 0.0), y_out - y_in, h_core,
            fill=False, edgecolor=color, linewidth=lw,
        )
        ax.add_patch(pad)

    if equal_aspect:
        ax.set_aspect("equal")


def preview_figure(regions: list[DopingRegion], geom: dict,
                   mode_E_abs: np.ndarray | None = None,
                   mode_y: np.ndarray | None = None,
                   mode_z: np.ndarray | None = None,
                   title: str = "",
                   zoom_um: float = 0.75) -> plt.Figure:
    """Four-panel geometric preview (no cloud data needed).

    Layout:
        row 0: full device (non-equal aspect, readable)
            (0,0) net doping on log scale
            (0,1) labeled implant boxes
        row 1: zoomed into the core (±zoom_um, equal aspect)
            (1,0) net doping  (1,1) labeled implant boxes

    Optional 3rd column: baseline |E| mode intensity if provided.
    """
    b = geometry_bounds(**geom)
    y_full = np.linspace(b["y_pp_L"] - 0.05, b["y_pp_R"] + 0.05, 800)
    z_full = np.linspace(-0.02, geom["h_core"] + 0.03, 200)
    y_zoom = np.linspace(-zoom_um, zoom_um, 500)
    z_zoom = np.linspace(-0.02, geom["h_core"] + 0.03, 200)

    ncols = 3 if mode_E_abs is not None else 2
    fig, axs = plt.subplots(2, ncols, figsize=(5.5 * ncols, 6.5),
                            constrained_layout=True)

    # --- Row 0: full device ----------------------------------------------
    im00 = plot_net_doping(
        axs[0, 0], regions, y_full, z_full, geom,
        title="Net doping  (full device)",
        equal_aspect=False,
    )
    fig.colorbar(im00, ax=axs[0, 0], label="Nd − Na (cm⁻³)",
                 shrink=0.85, aspect=30)
    axs[0, 0].set_xlim(b["y_pp_L"] - 0.1, b["y_pp_R"] + 0.1)

    plot_silicon_mask_with_labels(
        axs[0, 1], regions, geom,
        equal_aspect=False,
        title="Implant boxes  (full device)",
    )

    # --- Row 1: zoomed into core -----------------------------------------
    im10 = plot_net_doping(
        axs[1, 0], regions, y_zoom, z_zoom, geom,
        title=f"Net doping  (zoom ±{zoom_um:.2f} µm)",
        equal_aspect=True,
    )
    fig.colorbar(im10, ax=axs[1, 0], label="Nd − Na (cm⁻³)",
                 shrink=0.85, aspect=30)
    axs[1, 0].set_xlim(-zoom_um, zoom_um)

    plot_silicon_mask_with_labels(
        axs[1, 1], regions, geom,
        y_range=(-zoom_um, zoom_um),
        equal_aspect=True,
        title=f"Implant boxes  (zoom ±{zoom_um:.2f} µm)",
    )

    # --- Optional mode column --------------------------------------------
    if mode_E_abs is not None and ncols == 3:
        im02 = plot_mode_intensity(axs[0, 2], mode_E_abs, mode_y, mode_z, geom,
                                   title="|E|  baseline mode  (full)")
        fig.colorbar(im02, ax=axs[0, 2], label="|E| (a.u.)",
                     shrink=0.85, aspect=30)
        # Zoomed mode
        plot_mode_intensity(axs[1, 2], mode_E_abs, mode_y, mode_z, geom,
                            title=f"|E|  baseline mode  (zoom ±{zoom_um:.2f} µm)")
        axs[1, 2].set_xlim(-zoom_um, zoom_um)
        axs[1, 2].set_aspect("equal")

    if title:
        fig.suptitle(title, fontsize=12)

    return fig
