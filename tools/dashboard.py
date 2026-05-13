"""dashboard.py — Regenerate output/dashboard.html after every iteration.

Self-contained static HTML: reads output/results.tsv, draws five time-series
PNGs into output/plots/, then writes dashboard.html that references them by
relative path. No JS, no server. Opens directly in a browser.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .journal import (
    OUTPUT_DIR, RESULTS_TSV, EXPERIMENTS_DIR, load_all_results,
)
from .literature_data import (
    LITERATURE_POINTS, PATEL_FIT, JUNCTION_COLORS,
    fit_curve_vpil, pF_per_mm_to_aF_per_um,
)

PLOTS_DIR     = OUTPUT_DIR / "plots"
DASHBOARD_HTML = OUTPUT_DIR / "dashboard.html"

# Baseline anchors (measured constant-doping SISCAP, experiment 0001).
# Reference lines on the time-series plots use these, and the Pareto
# "dotted crosshair" marks the baseline point.
_BASELINE_REF = dict(VpiL_Vcm=1.823, C_pF_mm=0.2605, loss_dB_cm=10.56)


# =========================================================================
# Plot helpers
# =========================================================================
def _metric_series(rows: list[dict], key: str) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for r in rows:
        try:
            v = float(r[key])
        except (ValueError, KeyError, TypeError):
            continue
        if np.isnan(v):
            continue
        xs.append(int(r["experiment"]))
        ys.append(v)
    return np.array(xs, dtype=int), np.array(ys, dtype=float)


def _plot_time_series(rows, key: str, ylabel: str, title: str,
                      baseline: float | None, lower_is_better: bool,
                      out_path: Path):
    xs, ys = _metric_series(rows, key)
    fig, ax = plt.subplots(figsize=(7, 3.5), constrained_layout=True)
    if len(xs) > 0:
        ax.plot(xs, ys, "o-", color="tab:blue", lw=1.6, label=ylabel)
        # running best
        if lower_is_better:
            running = np.minimum.accumulate(ys)
        else:
            running = np.maximum.accumulate(ys)
        ax.plot(xs, running, "--", color="tab:green", lw=1.4,
                label="best so far")
        # best marker
        idx = int(np.argmin(ys) if lower_is_better else np.argmax(ys))
        ax.plot(xs[idx], ys[idx], "*", color="tab:red", ms=14,
                label=f"best = {ys[idx]:.4g} @ exp {xs[idx]}")
    if baseline is not None:
        ax.axhline(baseline, color="0.5", ls=":", lw=1.0,
                   label=f"baseline = {baseline}")
    ax.set_xlabel("experiment")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_pareto(rows, out_path: Path):
    xs, Vpi = _metric_series(rows, "VpiL_Vcm")
    _,  C   = _metric_series(rows, "C_pF_mm")

    # Align on experiment number in case some rows lack one of the two fields
    Vpi_by = {e: v for e, v in zip(*_metric_series(rows, "VpiL_Vcm"))}
    C_by   = {e: v for e, v in zip(*_metric_series(rows, "C_pF_mm"))}
    common = sorted(set(Vpi_by).intersection(C_by))
    Vpi = np.array([Vpi_by[e] for e in common])
    C   = np.array([C_by[e]   for e in common])
    exp = np.array(common, dtype=int)

    fig, ax = plt.subplots(figsize=(6, 4.5), constrained_layout=True)
    if len(common) > 0:
        sc = ax.scatter(C, Vpi, c=exp, cmap="viridis", s=60,
                        edgecolors="k", linewidths=0.3)
        # Circle the best (lowest sum of normalized VπL and C)
        score = (Vpi / _BASELINE_REF["VpiL_Vcm"]) + (C / _BASELINE_REF["C_pF_mm"])
        best = int(np.argmin(score))
        ax.scatter(C[best], Vpi[best], s=260, facecolors="none",
                   edgecolors="tab:red", linewidths=2.0,
                   label=f"best exp {exp[best]}")
        for e, cx, vy in zip(exp, C, Vpi):
            ax.annotate(str(e), (cx, vy), fontsize=7,
                        xytext=(3, 3), textcoords="offset points")
        fig.colorbar(sc, ax=ax, label="experiment number")
    ax.axhline(_BASELINE_REF["VpiL_Vcm"], color="0.5", ls=":", lw=1.0)
    ax.axvline(_BASELINE_REF["C_pF_mm"],  color="0.5", ls=":", lw=1.0)
    ax.set_xlabel("C @ target bias  (pF/mm)")
    ax.set_ylabel("VπL @ target bias  (V·cm)")
    ax.set_title("Pareto: VπL  vs  C   (lower-left is better)")
    ax.grid(alpha=0.3)
    if len(common) > 0:
        ax.legend(fontsize=8, loc="upper right")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_pareto_vs_literature(rows, out_path: Path):
    """Reproduce Fig. 3 of Patel OFC'26 (linear axes) with our stars overlaid.

    Styled to match the paper: Cpn in aF/µm on a LINEAR x-axis up to
    ~4500, VπL in V·cm on a LINEAR y-axis up to ~2.25, grid lines,
    per-point labels, Patel fit as a dashed curve, fit-equation text box
    in the upper-right.
    """
    Vpi_by = {e: v for e, v in zip(*_metric_series(rows, "VpiL_Vcm"))}
    C_by   = {e: v for e, v in zip(*_metric_series(rows, "C_pF_mm"))}
    common = sorted(set(Vpi_by).intersection(C_by))

    # Figure dimensions / limits matching the paper
    fig, ax = plt.subplots(figsize=(9.5, 6.2), constrained_layout=True)

    # --- Patel fit curve (dashed, muted) -----------------------------
    cpn_x = np.linspace(200, 4500, 500)
    ax.plot(cpn_x, fit_curve_vpil(cpn_x), "--", color="0.4", lw=1.2,
            alpha=0.6, zorder=2, label="Patel fit")

    # --- Literature points grouped by junction type ------------------
    by_kind: dict[str, list] = {}
    for cpn, vpi, kind, label, is_open in LITERATURE_POINTS:
        by_kind.setdefault(kind, []).append((cpn, vpi, label, is_open))
    # Fixed legend order matching the paper
    legend_order = ["CAP", "LPN", "UPN", "VPN", "ZPN", "mPN"]
    for kind in legend_order:
        if kind not in by_kind:
            continue
        color = JUNCTION_COLORS.get(kind, "gray")
        pts = by_kind[kind]
        xs_f = [p[0] for p in pts if not p[3]]
        ys_f = [p[1] for p in pts if not p[3]]
        xs_o = [p[0] for p in pts if p[3]]
        ys_o = [p[1] for p in pts if p[3]]
        # filled = measured (muted with alpha)
        if xs_f:
            ax.scatter(xs_f, ys_f, c=color, s=65, label=kind,
                       edgecolors="none", alpha=0.35, zorder=3)
        # open = simulated
        if xs_o:
            ax.scatter(xs_o, ys_o, facecolors="none", edgecolors=color,
                       s=65, linewidths=1.3, alpha=0.45,
                       label=None if xs_f else kind, zorder=3)
        # Per-point labels (same mute treatment)
        for cpn, vpi, label, is_open in pts:
            ax.annotate(label, (cpn, vpi), fontsize=6.5, color=color,
                        alpha=0.55,
                        xytext=(4, 2), textcoords="offset points", zorder=4)

    # --- Our points: large bright stars, high contrast ---------------
    if common:
        ours_cpn = np.array([pF_per_mm_to_aF_per_um(C_by[e]) for e in common])
        ours_vpi = np.array([Vpi_by[e] for e in common])
        ours_exp = np.array(common, dtype=int)

        # Neon-green stars with thick black outline — stand out vs the
        # alpha-muted literature points behind them.
        ax.scatter(ours_cpn, ours_vpi, s=520, marker="*",
                   facecolors="#39FF14", edgecolors="black",
                   linewidths=2.4, zorder=6,
                   label="this work (★)")
        # "Lowest-VπL×Cpn" is the natural efficiency×speed Pareto champion.
        # That product has units of V·cm·aF/µm and is what the modulator
        # literature tracks as the combined-figure.
        product = ours_vpi * ours_cpn
        best_idx = int(np.argmin(product))
        ax.scatter(ours_cpn[best_idx], ours_vpi[best_idx], s=1200,
                   marker="*", facecolors="none", edgecolors="#FF00AA",
                   linewidths=3.0, zorder=7,
                   label=(f"lowest VπL·Cpn ≡ #{ours_exp[best_idx]} "
                          f"({product[best_idx]:.0f})"))

        for e, cx, vy in zip(ours_exp, ours_cpn, ours_vpi):
            # Skip labeling when off the paper's y range (keeps the plot clean)
            if vy > 2.25 or vy < 0.0:
                continue
            ax.annotate(f"#{e}", (cx, vy), fontsize=10, color="black",
                        weight="bold",
                        xytext=(10, -5), textcoords="offset points",
                        zorder=8,
                        bbox=dict(boxstyle="round,pad=0.15",
                                  facecolor="white", edgecolor="black",
                                  alpha=0.95, lw=0.6))

    # --- Axes to match Fig. 3 ----------------------------------------
    ax.set_xlim(0, 4500)
    ax.set_ylim(0, 2.25)
    ax.set_xticks(np.arange(0, 4501, 500))
    ax.set_yticks(np.arange(0, 2.26, 0.25))
    ax.set_xlabel("Cj  [aF/µm]")
    ax.set_ylabel("VπL  [V·cm]")
    ax.grid(True, which="major", alpha=0.35, color="0.6", lw=0.5)
    ax.set_axisbelow(True)

    # --- Legend (upper right inside the plot, like the paper) --------
    legend = ax.legend(fontsize=9, loc="center right", title="Junction",
                       frameon=True, facecolor="white", edgecolor="0.6")
    legend.get_title().set_fontsize(9)

    # --- Patel fit equation textbox in upper-right corner ------------
    fit_txt = (f"VπL = {PATEL_FIT['A']:.0f}·(1/Cpn) + {PATEL_FIT['B']:+.4f}\n"
               f"R² = {PATEL_FIT['r_squared']:.3f}\n"
               f"n_in = 13/18 (lit)")
    ax.text(0.97, 0.97, fit_txt, transform=ax.transAxes,
            fontsize=10, ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="black", lw=1.0))

    ax.set_title("Fig. 3 replica — this work (★) vs NVIDIA OFC'26 literature",
                 fontsize=11)

    fig.savefig(out_path, dpi=140)
    plt.close(fig)


# =========================================================================
# HTML renderer
# =========================================================================
_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       margin: 24px; color: #222; background: #fafafa; }
h1 { margin-bottom: 0; }
.subtitle { color: #666; margin-top: 4px; margin-bottom: 24px; }
.stats { display: flex; gap: 32px; margin-bottom: 20px; }
.stat { background: #fff; padding: 12px 16px; border-radius: 6px;
        border: 1px solid #e3e3e3; min-width: 120px; }
.stat .label { font-size: 11px; text-transform: uppercase; color: #888;
               letter-spacing: 0.04em; }
.stat .value { font-size: 22px; font-weight: 600; color: #111; }
.section { margin-bottom: 32px; }
.plot-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.plot-grid img { width: 100%; border: 1px solid #e3e3e3; border-radius: 6px;
                 background: #fff; }
table { border-collapse: collapse; width: 100%; background: #fff;
        font-size: 13px; }
th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid #e8e8e8; }
th { background: #f2f2f2; text-align: center; font-weight: 600; }
td.txt, th.txt { text-align: left; }
tr.best { background: #fff8e1; }
tr:hover { background: #f3f7ff; }
a.thumb img { height: 95px; border: 1px solid #ccc; border-radius: 3px;
               transition: transform 0.15s; }
a.thumb img:hover { transform: scale(4); transform-origin: left center;
                    position: relative; z-index: 10;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
.notice { color: #a00; font-style: italic; }
"""


def _card(label: str, value: str) -> str:
    return (f'<div class="stat"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(value)}</div></div>')


def _thumb_link(exp_num: int, kind: str) -> str:
    rel = f"experiments/{int(exp_num):04d}/{kind}.png"
    if not (OUTPUT_DIR / rel).exists():
        return "—"
    return f'<a class="thumb" href="{rel}"><img src="{rel}" alt="{kind}"></a>'


def _fmt_cell(val: str) -> str:
    try:
        f = float(val)
    except (ValueError, TypeError):
        return html.escape(val or "")
    if abs(f) >= 1000 or (abs(f) < 0.01 and f != 0):
        return f"{f:.3e}"
    return f"{f:.4g}"


def render_dashboard() -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_all_results()

    # --- draw the five time-series plots (always, so they refresh even when
    # the table itself is empty -- still nicer than a broken <img>).
    _plot_time_series(
        rows, "FOM", "FOM", "FOM over time",
        baseline=0.0, lower_is_better=False,
        out_path=PLOTS_DIR / "fom_over_time.png",
    )
    _plot_time_series(
        rows, "VpiL_Vcm", "VπL (V·cm)", "VπL at target bias",
        baseline=_BASELINE_REF["VpiL_Vcm"], lower_is_better=True,
        out_path=PLOTS_DIR / "vpil_over_time.png",
    )
    _plot_time_series(
        rows, "C_pF_mm", "C (pF/mm)", "Junction C at target bias",
        baseline=_BASELINE_REF["C_pF_mm"], lower_is_better=True,
        out_path=PLOTS_DIR / "c_over_time.png",
    )
    _plot_time_series(
        rows, "loss_dB_cm", "loss (dB/cm)", "Free-carrier loss at 0 V",
        baseline=_BASELINE_REF["loss_dB_cm"], lower_is_better=True,
        out_path=PLOTS_DIR / "loss_over_time.png",
    )
    _plot_pareto(rows, PLOTS_DIR / "vpil_vs_C_pareto.png")
    _plot_pareto_vs_literature(rows, PLOTS_DIR / "vpil_vs_C_literature.png")

    # --- summary stats -------------------------------------------------
    n_exp = len(rows)
    best_row = None
    for r in rows:
        try:
            f = float(r["FOM"])
        except Exception:
            continue
        if best_row is None or f > float(best_row["FOM"]):
            best_row = r

    best_fom = f"{float(best_row['FOM']):.4g}" if best_row else "—"
    best_exp = best_row["experiment"] if best_row else "—"
    best_vpi = _fmt_cell(best_row["VpiL_Vcm"]) if best_row else "—"
    best_c   = _fmt_cell(best_row["C_pF_mm"])  if best_row else "—"

    # --- per-experiment table -----------------------------------------
    rows_html = []
    header = ("<tr>"
              "<th>exp</th><th>when</th><th class='txt'>topology</th>"
              "<th>W_CORE</th><th>FOM</th>"
              "<th>VπL (V·cm)</th><th>C (pF/mm)</th><th>loss (dB/cm)</th>"
              "<th>t (s)</th><th class='txt'>status</th>"
              "<th>preview</th><th>fields</th>"
              "<th class='txt'>description</th>"
              "</tr>")
    rows_html.append(header)
    for r in reversed(rows):    # newest first
        cls = ""
        if best_row and r["experiment"] == best_row["experiment"]:
            cls = ' class="best"'
        rows_html.append(
            f"<tr{cls}>"
            f"<td>{html.escape(r['experiment'])}</td>"
            f"<td>{html.escape((r.get('timestamp') or '')[:19])}</td>"
            f"<td class='txt'>{html.escape(r.get('topology') or '')}</td>"
            f"<td>{_fmt_cell(r.get('W_CORE'))}</td>"
            f"<td>{_fmt_cell(r.get('FOM'))}</td>"
            f"<td>{_fmt_cell(r.get('VpiL_Vcm'))}</td>"
            f"<td>{_fmt_cell(r.get('C_pF_mm'))}</td>"
            f"<td>{_fmt_cell(r.get('loss_dB_cm'))}</td>"
            f"<td>{_fmt_cell(r.get('wall_time_s'))}</td>"
            f"<td class='txt'>{html.escape(r.get('status') or '')}</td>"
            f"<td>{_thumb_link(int(r['experiment']), 'preview')}</td>"
            f"<td>{_thumb_link(int(r['experiment']), 'fields')}</td>"
            f"<td class='txt'>{html.escape(r.get('description') or '')}</td>"
            "</tr>"
        )

    notice = ("" if n_exp else
              '<p class="notice">No experiments have been logged yet — '
              'run <code>python simulate.py</code>.</p>')

    html_doc = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>PN AutoDesign Dashboard</title>
<style>{_CSS}</style>
</head><body>
<h1>PN Junction AutoDesign — Dashboard</h1>
<div class="subtitle">{n_exp} experiment(s) logged.
 Regenerated from <code>output/results.tsv</code>.</div>

<div class="stats">
  {_card("Experiments", str(n_exp))}
  {_card("Best FOM", best_fom)}
  {_card("Best experiment", str(best_exp))}
  {_card("Best VπL (V·cm)", best_vpi)}
  {_card("Best C (pF/mm)", best_c)}
</div>

{notice}

<div class="section">
  <h2>vs. NVIDIA OFC'26 literature (Fig. 3)</h2>
  <p style="color:#666;margin-top:-8px;">Our designs overlaid on the published VπL-Cpn tradeoff.
     Points under the dashed Patel fit are better than the literature envelope.</p>
  <img src="plots/vpil_vs_C_literature.png" style="max-width:100%;border:1px solid #e3e3e3;border-radius:6px;background:#fff;">
</div>

<div class="section">
  <h2>Time-series</h2>
  <div class="plot-grid">
    <img src="plots/fom_over_time.png">
    <img src="plots/vpil_vs_C_pareto.png">
    <img src="plots/vpil_over_time.png">
    <img src="plots/c_over_time.png">
    <img src="plots/loss_over_time.png">
  </div>
</div>

<div class="section">
  <h2>Evolution across iterations</h2>
  <p style="color:#666;margin-top:-8px;">
    Net free-carrier density <b>Ne − Nh</b> at +1 V reverse bias,
    animated iteration by iteration. Red = electron-dominant (N-type),
    blue = hole-dominant (P-type), white = depletion / intrinsic.
    Axes fixed so frames are directly comparable.
  </p>
  <img src="plots/carriers_evolution.gif" alt="carrier evolution"
       style="width:100%;border:1px solid #e3e3e3;border-radius:6px;background:#fff;">
  <p style="color:#666;font-size:13px;margin-top:10px;">
    Doping-profile evolution (design only, no bias):
    <a href="plots/doping_evolution.gif">doping_evolution.gif</a>
    &nbsp;•&nbsp;
    Overview grid: <a href="plots/doping_evolution_grid.png">doping_evolution_grid.png</a>
  </p>
</div>

<div class="section">
  <h2>Experiments</h2>
  <table>
    {"".join(rows_html)}
  </table>
</div>

</body></html>
"""
    DASHBOARD_HTML.write_text(html_doc)
    return DASHBOARD_HTML
