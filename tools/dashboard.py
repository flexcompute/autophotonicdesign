"""dashboard.py — Regenerate output/dashboard.html after every iteration.

Self-contained static HTML: reads output/results.tsv, draws time-series PNGs
and a tradeoff scatter into output/plots/, then writes dashboard.html that
references them by relative path. No JS, no server.
"""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .journal import OUTPUT_DIR, RESULTS_TSV, load_all_results

PLOTS_DIR     = OUTPUT_DIR / "plots"
DASHBOARD_HTML = OUTPUT_DIR / "dashboard.html"

# Baseline anchors — frozen reference (CPWRFPhotonics2.ipynb defaults).
BASELINE = dict(
    FOM=-1.122,
    alpha_0_dBcm_per_sqrtGHz=0.5726,
    alpha_at_Fref_dBcm=2.818,
    Z0_real_at_Fref=39.42,
    n_eff_at_Fref=2.0225,
)
TARGET_Z = 50.0
TARGET_N = 2.20

# Outliers / known-broken experiments to exclude from the tradeoff scatters.
# Rows still appear in the per-experiment table for full transparency.
#   exp 15: slotted-signal port-mode mismatch (α₀ ≈ 21, off-scale)
#   exps 14, 18, 19, 25, 26, 28, 29, 30, 32, 33: pre-fix asymmetric topologies
#     where adjacent T-tops overlapped along propagation due to a period-
#     calculation bug. The post-fix re-runs (34-37, 42, 44) replace them.
TRADEOFF_EXCLUDE = {15, 14, 18, 19, 25, 26, 28, 29, 30, 32, 33}


# ------------------------------------------------------------------
# Plot helpers
# ------------------------------------------------------------------
def _series(rows, key):
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


def _plot_time_series(rows, key, ylabel, title, baseline,
                      lower_is_better, target=None, out_path=None):
    xs, ys = _series(rows, key)
    fig, ax = plt.subplots(figsize=(7, 3.5), constrained_layout=True)
    if len(xs):
        ax.plot(xs, ys, "o-", color="tab:blue", lw=1.6, label=ylabel)
        running = (np.minimum.accumulate(ys) if lower_is_better
                   else np.maximum.accumulate(ys))
        ax.plot(xs, running, "--", color="tab:green", lw=1.4, label="best so far")
        idx = int(np.argmin(ys) if lower_is_better else np.argmax(ys))
        ax.plot(xs[idx], ys[idx], "*", color="tab:red", ms=14,
                label=f"best = {ys[idx]:.4g} @ exp {xs[idx]}")
    if baseline is not None:
        ax.axhline(baseline, color="0.5", ls=":", lw=1.0,
                   label=f"baseline = {baseline:.4g}")
    if target is not None:
        ax.axhline(target, color="tab:orange", ls="--", lw=1.0,
                   label=f"target = {target:.4g}")
    ax.set_xlabel("experiment")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


# Topology → color map (used by all tradeoff scatters)
TOPO_COLORS = {
    "T-rail":         "tab:blue",
    "asym-T":         "tab:green",
    "slotted-signal": "tab:red",
    "mushroom-T":     "tab:purple",
    "T+U":            "tab:orange",
    "asym-mushroom":  "tab:pink",
    "half-T":         "tab:brown",
}

# Internal name → friendlier label used in legends/titles. Underlying TSV
# rows still use the historical internal names for back-compat.
TOPO_DISPLAY = {
    "mushroom-T":    "wide-cap T",
    "asym-mushroom": "asym wide-cap T",
}


def _topo_display(name: str) -> str:
    return TOPO_DISPLAY.get(name, name)


def _topology_of_row(r):
    return (r.get("topology") or "T-rail").strip()


def _plot_tradeoff_alpha_vs_neff(rows, out_path):
    """Microwave loss α₀ vs effective RF index n_eff — the central tradeoff.
    Lower-left is best (low loss, n_eff close to target line). Color = topology.
    """
    fig, ax = plt.subplots(figsize=(7.5, 5.5), constrained_layout=True)
    by_topo = {}
    for r in rows:
        t = _topology_of_row(r)
        try:
            e = int(r["experiment"])
            if e in TRADEOFF_EXCLUDE:
                continue
            n = float(r["n_eff_at_Fref"])
            a = float(r["alpha_0_dBcm_per_sqrtGHz"])
        except (ValueError, KeyError, TypeError):
            continue
        by_topo.setdefault(t, []).append((e, n, a))
    for t, pts in by_topo.items():
        e_arr = np.array([p[0] for p in pts])
        n_arr = np.array([p[1] for p in pts])
        a_arr = np.array([p[2] for p in pts])
        ax.scatter(n_arr, a_arr, c=TOPO_COLORS.get(t, "gray"),
                   s=80, edgecolors="k", linewidths=0.5, label=_topo_display(t))
        for e, nx, ay in zip(e_arr, n_arr, a_arr):
            ax.annotate(str(e), (nx, ay), fontsize=7,
                        xytext=(3, 3), textcoords="offset points")
    ax.axvline(TARGET_N, color="tab:orange", ls="--", lw=1.2,
               label=f"target n_eff = {TARGET_N}")
    ax.scatter([BASELINE["n_eff_at_Fref"]], [BASELINE["alpha_0_dBcm_per_sqrtGHz"]],
               s=260, marker="x", c="black", lw=2.5,
               label="baseline")
    ax.set_xlabel("n_eff at F_ref (RF index)")
    ax.set_ylabel("α₀ (dB/cm/√GHz)")
    ax.set_title("Microwave loss vs effective RF index — colored by topology")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_tradeoff_Z0_vs_neff(rows, out_path):
    """Impedance vs n_eff — colored by topology, gold star = target."""
    fig, ax = plt.subplots(figsize=(7.5, 5.5), constrained_layout=True)
    by_topo = {}
    for r in rows:
        t = _topology_of_row(r)
        try:
            e = int(r["experiment"])
            if e in TRADEOFF_EXCLUDE:
                continue
            n = float(r["n_eff_at_Fref"])
            z = float(r["Z0_real_at_Fref"])
        except (ValueError, KeyError, TypeError):
            continue
        by_topo.setdefault(t, []).append((e, n, z))
    for t, pts in by_topo.items():
        e_arr = np.array([p[0] for p in pts])
        n_arr = np.array([p[1] for p in pts])
        z_arr = np.array([p[2] for p in pts])
        ax.scatter(n_arr, z_arr, c=TOPO_COLORS.get(t, "gray"),
                   s=80, edgecolors="k", linewidths=0.5, label=_topo_display(t))
        for e, nx, zy in zip(e_arr, n_arr, z_arr):
            ax.annotate(str(e), (nx, zy), fontsize=7,
                        xytext=(3, 3), textcoords="offset points")
    ax.axvline(TARGET_N, color="tab:orange", ls="--", lw=1.2,
               label=f"target n_eff = {TARGET_N}")
    ax.axhline(TARGET_Z, color="tab:red", ls="--", lw=1.2,
               label=f"target Z₀ = {TARGET_Z} Ω")
    ax.scatter([TARGET_N], [TARGET_Z], s=320, marker="*",
               c="gold", edgecolors="k", lw=1.5, zorder=10,
               label="target sweet spot")
    ax.scatter([BASELINE["n_eff_at_Fref"]], [BASELINE["Z0_real_at_Fref"]],
               s=260, marker="x", c="black", lw=2.5,
               label="baseline")
    ax.set_xlabel("n_eff at F_ref (RF index)")
    ax.set_ylabel("Re(Z₀) at F_ref (Ω)")
    ax.set_title("Impedance vs effective RF index — colored by topology")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_tradeoff_alpha_vs_Z0(rows, out_path):
    fig, ax = plt.subplots(figsize=(7.5, 5.5), constrained_layout=True)
    by_topo = {}
    for r in rows:
        t = _topology_of_row(r)
        try:
            e = int(r["experiment"])
            if e in TRADEOFF_EXCLUDE:
                continue
            z = float(r["Z0_real_at_Fref"])
            a = float(r["alpha_0_dBcm_per_sqrtGHz"])
        except (ValueError, KeyError, TypeError):
            continue
        by_topo.setdefault(t, []).append((e, z, a))
    for t, pts in by_topo.items():
        e_arr = np.array([p[0] for p in pts])
        z_arr = np.array([p[1] for p in pts])
        a_arr = np.array([p[2] for p in pts])
        ax.scatter(z_arr, a_arr, c=TOPO_COLORS.get(t, "gray"),
                   s=80, edgecolors="k", linewidths=0.5, label=_topo_display(t))
        for e, zx, ay in zip(e_arr, z_arr, a_arr):
            ax.annotate(str(e), (zx, ay), fontsize=7,
                        xytext=(3, 3), textcoords="offset points")
    ax.axvline(TARGET_Z, color="tab:red", ls="--", lw=1.2,
               label=f"target Z₀ = {TARGET_Z} Ω")
    ax.scatter([BASELINE["Z0_real_at_Fref"]], [BASELINE["alpha_0_dBcm_per_sqrtGHz"]],
               s=260, marker="x", c="black", lw=2.5,
               label="baseline")
    ax.set_xlabel("Re(Z₀) at F_ref (Ω)")
    ax.set_ylabel("α₀ (dB/cm/√GHz)")
    ax.set_title("Microwave loss vs impedance — colored by topology")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------
_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       margin: 24px; color: #222; background: #fafafa; }
h1 { margin-bottom: 0; }
.subtitle { color: #666; margin-top: 4px; margin-bottom: 24px; }
.stats { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.stat { background: #fff; padding: 12px 16px; border-radius: 6px;
        border: 1px solid #e3e3e3; min-width: 130px; }
.stat .label { font-size: 11px; text-transform: uppercase; color: #888;
               letter-spacing: 0.04em; }
.stat .value { font-size: 22px; font-weight: 600; color: #111; }
.section { margin-bottom: 32px; }
.plot-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.plot-grid img { width: 100%; border: 1px solid #e3e3e3; border-radius: 6px;
                 background: #fff; }
table { border-collapse: collapse; width: 100%; background: #fff; font-size: 12px; }
th, td { padding: 5px 8px; text-align: right; border-bottom: 1px solid #e8e8e8;
         white-space: nowrap; }
th { background: #f2f2f2; text-align: center; font-weight: 600; }
td.txt, th.txt { text-align: left; }
tr.best { background: #fff8e1; }
tr:hover { background: #f3f7ff; }
a.thumb img { height: 80px; border: 1px solid #ccc; border-radius: 3px;
              transition: transform 0.15s; }
a.thumb img:hover { transform: scale(4); transform-origin: left center;
                    position: relative; z-index: 10;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
.notice { color: #a00; font-style: italic; }
"""


def _card(label, value):
    return (f'<div class="stat"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(str(value))}</div></div>')


def _thumb(exp_num, kind):
    rel = f"experiments/{int(exp_num):04d}/{kind}.png"
    if not (OUTPUT_DIR / rel).exists():
        return "—"
    return f'<a class="thumb" href="{rel}"><img src="{rel}" alt="{kind}"></a>'


def _fmt_cell(val):
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

    # Time-series
    _plot_time_series(rows, "FOM", "FOM", "FOM over time",
                      baseline=BASELINE["FOM"], lower_is_better=False,
                      out_path=PLOTS_DIR / "fom_over_time.png")
    _plot_time_series(rows, "alpha_0_dBcm_per_sqrtGHz", "α₀ (dB/cm/√GHz)",
                      "Microwave loss coefficient",
                      baseline=BASELINE["alpha_0_dBcm_per_sqrtGHz"],
                      lower_is_better=True,
                      out_path=PLOTS_DIR / "alpha0_over_time.png")
    _plot_time_series(rows, "Z0_real_at_Fref", "Re(Z₀) (Ω)",
                      "Characteristic impedance @ F_ref",
                      baseline=BASELINE["Z0_real_at_Fref"],
                      lower_is_better=False, target=TARGET_Z,
                      out_path=PLOTS_DIR / "Z0_over_time.png")
    _plot_time_series(rows, "n_eff_at_Fref", "n_eff (RF)",
                      "Effective RF index @ F_ref",
                      baseline=BASELINE["n_eff_at_Fref"],
                      lower_is_better=False, target=TARGET_N,
                      out_path=PLOTS_DIR / "neff_over_time.png")

    # Tradeoffs
    _plot_tradeoff_alpha_vs_neff(rows, PLOTS_DIR / "alpha_vs_neff.png")
    _plot_tradeoff_Z0_vs_neff(rows, PLOTS_DIR / "Z0_vs_neff.png")
    _plot_tradeoff_alpha_vs_Z0(rows, PLOTS_DIR / "alpha_vs_Z0.png")

    # Best row
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
    best_n = _fmt_cell(best_row.get("n_eff_at_Fref")) if best_row else "—"
    best_z = _fmt_cell(best_row.get("Z0_real_at_Fref")) if best_row else "—"
    best_a = _fmt_cell(best_row.get("alpha_0_dBcm_per_sqrtGHz")) if best_row else "—"

    # Per-exp table
    rows_html = []
    header = ("<tr>"
              "<th>exp</th><th>when</th><th class='txt'>topology</th>"
              "<th>FOM</th>"
              "<th>α₀</th><th>Re(Z₀)</th><th>n_eff</th>"
              "<th>R<br>(Ω/mm)</th><th>L<br>(nH/mm)</th>"
              "<th>G<br>(S/mm)</th><th>C<br>(pF/mm)</th>"
              "<th>T_S</th><th>T_R</th><th>T_H</th><th>T_T</th><th>T_C</th>"
              "<th>G</th><th>WS</th><th>WG</th><th>TM</th><th>TSIO21</th>"
              "<th>t (s)</th><th class='txt'>status</th>"
              "<th>preview</th><th>S-params</th>"
              "<th class='txt'>description</th></tr>")
    rows_html.append(header)
    for r in reversed(rows):
        cls = ""
        if best_row and r["experiment"] == best_row["experiment"]:
            cls = ' class="best"'
        rows_html.append(
            f"<tr{cls}>"
            f"<td>{html.escape(r['experiment'])}</td>"
            f"<td>{html.escape((r.get('timestamp') or '')[:19])}</td>"
            f"<td class='txt'>{html.escape(r.get('topology') or '')}</td>"
            f"<td>{_fmt_cell(r.get('FOM'))}</td>"
            f"<td>{_fmt_cell(r.get('alpha_0_dBcm_per_sqrtGHz'))}</td>"
            f"<td>{_fmt_cell(r.get('Z0_real_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('n_eff_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('R_Ohm_per_mm_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('L_nH_per_mm_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('G_S_per_mm_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('C_pF_per_mm_at_Fref'))}</td>"
            f"<td>{_fmt_cell(r.get('T_S'))}</td>"
            f"<td>{_fmt_cell(r.get('T_R'))}</td>"
            f"<td>{_fmt_cell(r.get('T_H'))}</td>"
            f"<td>{_fmt_cell(r.get('T_T'))}</td>"
            f"<td>{_fmt_cell(r.get('T_C'))}</td>"
            f"<td>{_fmt_cell(r.get('G'))}</td>"
            f"<td>{_fmt_cell(r.get('WS'))}</td>"
            f"<td>{_fmt_cell(r.get('WG'))}</td>"
            f"<td>{_fmt_cell(r.get('TM'))}</td>"
            f"<td>{_fmt_cell(r.get('TSIO21'))}</td>"
            f"<td>{_fmt_cell(r.get('wall_time_s'))}</td>"
            f"<td class='txt'>{html.escape(r.get('status') or '')}</td>"
            f"<td>{_thumb(int(r['experiment']), 'preview')}</td>"
            f"<td>{_thumb(int(r['experiment']), 'segmented_summary')}</td>"
            f"<td class='txt'>{html.escape(r.get('description') or '')}</td>"
            "</tr>")

    notice = ("" if n_exp else
              '<p class="notice">No experiments yet — '
              'run <code>python simulate.py</code>.</p>')

    html_doc = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>RF AutoDesign — Segmented CPW</title>
<style>{_CSS}</style>
</head><body>
<h1>RF AutoDesign — Segmented CPW (T-rail)</h1>
<div class="subtitle">{n_exp} experiment(s) logged.
 Targets: α₀ minimize, Re(Z₀) → 50 Ω, n_eff → 2.20.
 Regenerated from <code>output/results.tsv</code>.</div>

<div class="stats">
  {_card("Experiments", n_exp)}
  {_card("Best FOM", best_fom)}
  {_card("Best exp", best_exp)}
  {_card("α₀ (dB/cm/√GHz)", best_a)}
  {_card("Re(Z₀) (Ω)", best_z)}
  {_card("n_eff", best_n)}
</div>

{notice}

<div class="section">
  <h2>Topology evolution across iterations</h2>
  <p style="color:#666;margin-top:-6px;">
    Each frame is one experiment, showing the metal geometry the AI has tried.
    Top panel: top-down view at the metal plane (G–S–G labels).
    Bottom panel: transverse cross-section through the active gap (z-axis exaggerated).
  </p>
  <img src="plots/topology_evolution.gif" alt="topology evolution"
       style="max-width:100%;border:1px solid #e3e3e3;border-radius:6px;background:#fff;">
  <p style="color:#666;font-size:13px;margin-top:8px;">
    Static at-a-glance grid: <a href="plots/topology_evolution_grid.png">topology_evolution_grid.png</a>
    &nbsp;•&nbsp;
    Per-frame PNGs: <a href="plots/topology_frames/">plots/topology_frames/</a>
  </p>
</div>

<div class="section">
  <h2>Key tradeoffs (the agent should push toward the target lines)</h2>
  <p style="color:#888;font-size:12px;margin-top:-6px;">
    Excluded from these scatters (still in the table below): {", ".join(f"exp {e}" for e in sorted(TRADEOFF_EXCLUDE))}
    — broken simulations whose extreme values would compress the meaningful clusters.
  </p>
  <div class="plot-grid">
    <img src="plots/alpha_vs_neff.png">
    <img src="plots/Z0_vs_neff.png">
    <img src="plots/alpha_vs_Z0.png">
  </div>
</div>

<div class="section">
  <h2>Time-series</h2>
  <div class="plot-grid">
    <img src="plots/fom_over_time.png">
    <img src="plots/alpha0_over_time.png">
    <img src="plots/Z0_over_time.png">
    <img src="plots/neff_over_time.png">
  </div>
</div>

<div class="section">
  <h2>Experiments (newest first)</h2>
  <table>
    {"".join(rows_html)}
  </table>
</div>

</body></html>
"""
    DASHBOARD_HTML.write_text(html_doc)
    return DASHBOARD_HTML


if __name__ == "__main__":
    path = render_dashboard()
    print(f"Wrote {path}")
