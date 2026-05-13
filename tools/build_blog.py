"""build_blog.py - Generate a standalone HTML blog post for the segmented-MZM
auto-loop. Embeds images as base64 so the .html file is self-contained.

Usage:  python -m tools.build_blog
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
PLOTS_DIR = OUTPUT_DIR / "plots"
BLOG_PATH = OUTPUT_DIR / "blog_segmented_mzm.html"


# --------------------------------------------------------------------
# Image embedding helpers
# --------------------------------------------------------------------
def png_b64(path: Path, max_w: int = 1000) -> str:
    """Resize PNG (preserving aspect) and return base64 data URI."""
    img = Image.open(path).convert("RGB")
    if img.size[0] > max_w:
        scale = max_w / img.size[0]
        img = img.resize((max_w, int(img.size[1] * scale)))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b}"


def gif_b64(path: Path) -> str:
    """Read GIF as-is (preserves animation)."""
    b = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/gif;base64,{b}"


# --------------------------------------------------------------------
# Build content
# --------------------------------------------------------------------
def build_html() -> str:
    print("Encoding images …")
    img_3d = png_b64(OUTPUT_DIR / "3D_image.png", max_w=900)
    img_gif = gif_b64(PLOTS_DIR / "topology_evolution.gif")
    img_a_vs_z = png_b64(PLOTS_DIR / "alpha_vs_Z0.png", max_w=900)
    img_a_vs_n = png_b64(PLOTS_DIR / "alpha_vs_neff.png", max_w=720)
    img_z_vs_n = png_b64(PLOTS_DIR / "Z0_vs_neff.png", max_w=720)
    img_best_geom = png_b64(OUTPUT_DIR / "experiments" / "0045" / "preview.png", max_w=900)

    css = """
:root {
  --fg: #1c1f23; --muted: #5b6268; --accent: #2a6dde;
  --rule: #e6e8eb; --bg: #ffffff; --code-bg: #f3f5f7;
}
html, body { background: var(--bg); }
body {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  max-width: 820px; margin: 40px auto; padding: 0 24px 80px;
  color: var(--fg); line-height: 1.6; font-size: 17px; font-weight: 400;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
h1 { font-size: 34px; line-height: 1.18; margin: 0 0 10px; font-weight: 700; letter-spacing: -0.01em; }
h2 { font-size: 22px; margin: 44px 0 10px; font-weight: 700; letter-spacing: -0.005em;
     border-bottom: 1px solid var(--rule); padding-bottom: 6px; }
h3 { font-size: 18px; margin: 24px 0 6px; font-weight: 600; }
.subtitle { color: var(--muted); font-size: 17px; margin: 0 0 6px; font-weight: 400; }
.byline   { color: var(--muted); font-size: 14px; margin-bottom: 26px; }
.series {
  display: inline-block; background: #eaf1fc; color: var(--accent);
  font-size: 12px; padding: 4px 10px; border-radius: 999px;
  margin-bottom: 14px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
}
figure { margin: 22px 0; text-align: center; }
figure img { max-width: 100%; border: 1px solid var(--rule); border-radius: 6px; background: white; }
figcaption { color: var(--muted); font-size: 14px; margin-top: 8px; line-height: 1.45;
             max-width: 720px; margin-left: auto; margin-right: auto; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; align-items: stretch; }
.two-col img { width: 100%; height: 100%; object-fit: contain;
               border: 1px solid var(--rule); border-radius: 6px; background: white; }
.gif-wide img { width: 100%; border: 1px solid var(--rule); border-radius: 6px; }
.pull { font-size: 19px; line-height: 1.4; font-weight: 500;
        border-left: 4px solid var(--accent); padding: 4px 18px; margin: 24px 0; color: #1c1f23; }
code { background: var(--code-bg); padding: 1px 5px; border-radius: 3px;
       font-size: 14px; font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace; }
.kpi { display: flex; gap: 14px; margin: 18px 0; flex-wrap: wrap; }
.kpi .box { flex: 1; background: #fafbfc; border: 1px solid var(--rule);
            border-radius: 8px; padding: 12px 14px; min-width: 140px; }
.kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase;
              letter-spacing: 0.06em; font-weight: 600; }
.kpi .value { font-size: 22px; font-weight: 700; margin-top: 4px; color: var(--fg); }
.kpi .delta { color: #1f9d55; font-size: 13px; font-weight: 600; margin-top: 2px; }
.kpi .delta.bad { color: #c44d4d; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid var(--rule); margin: 36px 0; }
.refs { font-size: 14px; color: #2c3036; }
.refs li { margin-bottom: 6px; }
ol, ul { padding-left: 24px; } li { margin-bottom: 4px; }
.eq { background: var(--code-bg); padding: 10px 14px; border-radius: 6px; font-size: 14.5px;
      font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; line-height: 1.55;
      overflow-x: auto; white-space: pre; margin: 16px 0; }
.loop-diagram { margin: 22px 0 8px; text-align: center; }
.loop-diagram svg { max-width: 100%; height: auto; }
.step    { fill:#fafbfc; stroke:#cdd2d8; stroke-width:1.2; }
.stepHi  { fill:#eaf1fc; stroke:#2a6dde; stroke-width:1.4; }
.label   { font: 600 13px "Inter", sans-serif; fill:#1c1f23; }
.sub     { font: 500 10px "Inter", sans-serif; fill:#5b6268; }
.arrow   { stroke:#5b6268; stroke-width:1.6; fill:none; }
.arrowFb { stroke:#2a6dde; stroke-width:1.8; fill:none; stroke-dasharray: 6 4; }
.stepNum { font: 700 11px "Inter", sans-serif; fill:#5b6268; }
"""

    loop_svg = """
<svg viewBox="0 0 870 230" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0 0 L0 6 L8 3 z" fill="#5b6268"/></marker>
    <marker id="arrowAccent" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
      <path d="M0 0 L0 6 L8 3 z" fill="#2a6dde"/></marker>
  </defs>
  <rect class="step"  x="20"  y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="30" y="78">1</text>
  <text class="label"   x="75" y="98" text-anchor="middle">Edit</text>
  <text class="sub"     x="75" y="114" text-anchor="middle">design.py knobs</text>
  <rect class="step"  x="160" y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="170" y="78">2</text>
  <text class="label"   x="215" y="98" text-anchor="middle">Preview</text>
  <text class="sub"     x="215" y="114" text-anchor="middle">top-down + xsec</text>
  <rect class="step"  x="300" y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="310" y="78">3</text>
  <text class="label"   x="355" y="98" text-anchor="middle">DRC</text>
  <text class="sub"     x="355" y="114" text-anchor="middle">100 nm + process</text>
  <rect class="stepHi" x="440" y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="450" y="78">4</text>
  <text class="label"   x="495" y="98" text-anchor="middle">Simulate</text>
  <text class="sub"     x="495" y="114" text-anchor="middle">3-D RF FDTD</text>
  <rect class="step"  x="580" y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="590" y="78">5</text>
  <text class="label"   x="635" y="98" text-anchor="middle">Evaluate</text>
  <text class="sub"     x="635" y="114" text-anchor="middle">FOM</text>
  <rect class="step"  x="720" y="60" width="110" height="70" rx="10"/>
  <text class="stepNum" x="730" y="78">6</text>
  <text class="label"   x="775" y="98" text-anchor="middle">Decide</text>
  <text class="sub"     x="775" y="114" text-anchor="middle">keep / revert</text>
  <path class="arrow"   d="M130 95 L160 95" marker-end="url(#arrow)"/>
  <path class="arrow"   d="M270 95 L300 95" marker-end="url(#arrow)"/>
  <path class="arrow"   d="M410 95 L440 95" marker-end="url(#arrow)"/>
  <path class="arrow"   d="M550 95 L580 95" marker-end="url(#arrow)"/>
  <path class="arrow"   d="M690 95 L720 95" marker-end="url(#arrow)"/>
  <path class="arrowFb" d="M775 130 Q775 195 425 195 Q75 195 75 140 L75 130" marker-end="url(#arrowAccent)"/>
  <text x="425" y="215" text-anchor="middle" class="sub" fill="#2a6dde" font-weight="600">
    update results.tsv, journal.md, dashboard.html
  </text>
</svg>
"""

    # ---- Body content ----
    body = f"""
<span class="series">Agentic Photonic Design, Part 4</span>
<h1>Agentic Photonic Design: Exploring RF transmission line designs for high-speed Mach-Zehnder modulators</h1>
<p class="subtitle">We let an autonomous design agent explore RF transmission line geometries for a high-speed Mach-Zehnder modulator. After testing several coplanar-waveguide variants, the agent is mapping out the tradeoff between microwave loss and characteristic impedance, two of the dominant constraints on electro-optic bandwidth.</p>
<p class="byline">Prashanta Kharel, Flexcompute</p>

<div class="two-col">
  <div><img src="{img_3d}" alt="3-D view of a segmented CPW design"/></div>
  <div class="gif-wide" style="margin-top: 0;"><img src="{img_gif}" alt="Topology evolution GIF, 40 iterations"/></div>
</div>
<figcaption>Left: A segmented coplanar-waveguide electrode geometry, rendered in the 3-D viewer. Right: 40 iterations of metal-layer geometry the agent tried, animated. Each frame is one cloud simulation; titles are colored by topology family.</figcaption>

<h2>Transmission line design is critical for high bandwidth operation</h2>

<p>The electrical performance of the traveling-wave electrode sets the achievable electro-optic bandwidth in Mach-Zehnder modulators across silicon, thin-film lithium niobate (TFLN), thin-film lithium tantalate (TFLT), barium titanate, and other platforms. Three properties of the RF line dominate: microwave loss <code>α₀</code> (skin-effect dominated, units dB/cm/√GHz), characteristic impedance <code>Z₀</code> (target near 50 Ω for matched drive), and RF effective index <code>n<sub>eff</sub></code> (must match the optical group index for velocity-matched co-propagation across the active length). A common high-bandwidth design is the segmented slow-wave electrode [1, 2], which loads a host CPW with periodic capacitive elements to slow the RF wave and recover velocity matching.</p>

<p>The three constraints are coupled through the four per-unit-length transmission-line parameters R, L, C, and G of the loaded CPW. Capacitive loading raises <code>n<sub>eff</sub></code> but lowers <code>Z₀</code>; thicker metal lowers R (and therefore <code>α₀</code>) but is process-bounded. Engineering teams typically traverse this design space one geometry at a time. We hand the same problem to an agent.</p>

<p class="pull">The agent maps out the loss-impedance plane for this platform in about an hour of cloud time, then locates a topology that lands the velocity-matching target.</p>

<h2>The loop</h2>

<p>The agent runs a fixed six-step iteration cycle. Each cycle is one experiment.</p>

<figure class="loop-diagram">{loop_svg}</figure>

<p>Knobs the agent edits (the only file it edits is <code>design.py</code>):</p>

<ul>
  <li><strong>T-rail geometry</strong>: T_S (along propagation), T_R (transverse), T_H (neck length into gap), T_T (neck width), T_C (gap between adjacent T's).</li>
  <li><strong>Host CPW</strong>: G (residual gap where rib waveguide lives), WS (signal trace width), WG (ground rail width).</li>
  <li><strong>Stack</strong>: TM (Au thickness), TSIO21 (cladding gap above the slab; agent can only increase it from the process minimum).</li>
  <li><strong>Topology selector</strong>: a string that switches between distinct geometry builders.</li>
</ul>

<p>The figure of merit is a single scalar:</p>

<div class="eq">FOM = -[ α₀  +  λ_Z · ((Z₀ - 50) / 50)²  +  λ_n · ((n_eff - 2.20) / 2.20)² ]</div>

<p>with <code>λ_Z = 5</code>, <code>λ_n = 50</code>, and the targets fixed for the platform: <code>Z₀ = 50</code> Ω, <code>n_eff = 2.20</code> (optical group index of the fundamental TE mode at 1310 nm). The α₀ penalty is unweighted and uncapped, so the agent always sees a benefit to lower loss. <code>α₀</code> itself is fitted from <code>α(f) ≈ α₀·√f</code> over 5 to 45 GHz.</p>

<h2>DRC, generalized</h2>

<p>The DRC step is the gate that decides whether the agent pays for a cloud simulation. Two classes of rule:</p>

<p><strong>Fab rules.</strong> Minimum 100 nm metal feature and spacing on every editable structure. Minimum 100 nm metal thickness. The residual ground-rail width after T-rail loading must also stay above 100 nm.</p>

<p><strong>Process rules.</strong> The thin-film thicknesses (600 nm rib, 300 nm slab, 30° sidewall) are platform-fixed and cannot be edited. The cladding gap above the slab can only INCREASE from baseline. The frequency band, FOM weights, and slab permittivities are all out of the agent's reach.</p>

<h2>Topology families the agent can pick from</h2>

<p>Beyond the scalar knobs, the agent picks from five distinct topology builders. Each is a parametric Python function that emits a different metal pattern.</p>

<ul>
  <li><strong>T-rail</strong>: symmetric T-shaped electrodes anchored on both signal and ground edges of every CPW gap. The published baseline.</li>
  <li><strong>asym-T</strong>: different T_R on the signal side versus the ground side. Lets the agent shift metal between the two sides.</li>
  <li><strong>wide-cap T</strong>: a wider hat on top of every T-top, in the same metal layer. Adds capacitance to the high-permittivity substrate underneath without adding ohmic path.</li>
  <li><strong>T+U</strong>: T-rails interleaved with U-shaped bridges every Nth cell. The bridges carry signal across the gap inside one super-cell, adding series inductance per super-cell.</li>
  <li><strong>half-T</strong>: only signal-anchored T's; the ground side is bare.</li>
</ul>

<p>Switching topology is a one-line change in <code>design.py</code> (<code>TOPOLOGY = "wide-cap T"</code>). The agent can do this on any iteration.</p>

<h3>Where the agent is heading next</h3>

<p>The agent's search space extends well beyond the five families already covered. As the FOM plateaus on each family, the loop pivots to a new geometry class it has not yet explored:</p>

<ul>
  <li><strong>Defected ground structures (DGS)</strong>: periodic ground-plane slots that raise inductance per cell.</li>
  <li><strong>Slotted signal trace</strong>: transverse cuts that detour the surface current, raising L without proportionally raising C.</li>
  <li><strong>Asymmetric wide-cap T</strong>: caps on the signal-side T-tops only.</li>
  <li><strong>Multi-tier T-rails</strong>: two rows per period at different sizes, shaping the per-cell loading curve.</li>
  <li><strong>Tapered T-rails</strong>: T-top length growing then shrinking along propagation to suppress band-edge reflections.</li>
</ul>

<p>The agent has already pivoted topology family three times during this run, each time prompted by the gradient signs accumulated in its own journal.</p>

<h2>The loss-impedance frontier</h2>

<figure>
  <img src="{img_a_vs_z}" alt="Microwave loss alpha vs Z0 colored by topology"/>
  <figcaption>Microwave loss <code>α₀</code> (dB/cm/√GHz) vs characteristic impedance Re(Z₀). Each point is one experiment; colors flag the topology family. The black ✕ marks the conventional T-rail baseline. Lower-right of the target line (Z₀ = 50 Ω) is best.</figcaption>
</figure>

<p>Different topology families occupy different regions of the loss-impedance plane. The plain T-rail baseline (blue) sits at α₀ ≈ 0.5 to 0.8 dB/cm/√GHz with Z₀ ≈ 38 to 41 Ω. Adding a wide cap to each T-top (purple) shifts the cluster toward lower α₀ (0.29 to 0.36) at higher Z₀ (43 to 44 Ω). The wider top increases the capacitive coupling to the high-permittivity substrate underneath, while the underlying T-stem still carries the bulk signal current, so per-unit-length R does not rise proportionally. Asymmetric variants (green, pink) sit at similar α₀ levels with broader Z₀ scatter, depending on the choice of T_R_SIG and T_R_GND.</p>

<figure>
  <div class="two-col">
    <div><img src="{img_z_vs_n}" alt="Z0 vs n_eff" /></div>
    <div><img src="{img_a_vs_n}" alt="alpha0 vs n_eff" /></div>
  </div>
  <figcaption>Left: characteristic impedance vs RF effective index. Gold star marks the (n_eff = 2.20, Z₀ = 50 Ω) sweet spot. Right: microwave loss vs n_eff. Both views colored by topology family.</figcaption>
</figure>

<p>Folding in the n<sub>eff</sub> axis tells the rest of the story. The wide-cap T cluster sits closest to the gold-star sweet spot: low α₀, Z₀ within 6 Ω of the 50 Ω target, and n_eff straddling the target line. T+U (orange) lands n_eff on target as well, but at higher α₀ because the U-bridges add ohmic path. Asymmetric topologies span a wide n_eff range (roughly 2.0 to 2.5) depending on the loading split, giving the agent a useful knob for trading n_eff against the loss-impedance pair. Pure T-rail and half-T cluster further from the sweet spot, confirming that capacitive loading alone, without a way to add C without R, runs into the same Pareto front.</p>

<h2>The best design the agent found</h2>

<p>Iteration 45: <code>TOPOLOGY = "wide-cap T"</code>, T_R = 53 μm, cap 15 μm × (T_S + 6 μm), G = 12 μm, all other parameters at platform default.</p>

<div class="kpi">
  <div class="box">
    <div class="label">FOM</div>
    <div class="value">-0.358</div>
    <div class="delta">3.4× better than baseline</div>
  </div>
  <div class="box">
    <div class="label">α₀ (dB/cm/√GHz)</div>
    <div class="value">0.291</div>
    <div class="delta">-56 % vs baseline</div>
  </div>
  <div class="box">
    <div class="label">Re(Z₀) (Ω)</div>
    <div class="value">44.3</div>
    <div class="delta">+12 % toward 50</div>
  </div>
  <div class="box">
    <div class="label">n_eff at 40 GHz</div>
    <div class="value">2.207</div>
    <div class="delta">target hit</div>
  </div>
</div>

<figure>
  <img src="{img_best_geom}" alt="Geometry preview of best design"/>
  <figcaption>Top-down geometry of the best design. Wide-cap T-rails alternate inside the loaded section between conventional CPW input/output pads. The cap extends each T-top in the propagation direction, increasing the capacitive coupling to the high-permittivity substrate without lengthening the current-carrying neck.</figcaption>
</figure>

<h2>What this means</h2>

<p>The same agentic design loop, with access to Flexcompute's RF and photonic simulation tools and the cloud compute behind them, generalizes naturally beyond this run. The framework already maps to silicon photonics, TFLN, TFLT, BTO, and polymer modulators by changing the material stack, FOM targets, and topology builders at the top of <code>design.py</code>. The simulation harness, DRC, journal, and dashboard transfer untouched. What changes between platforms is one file; what stays constant is the iteration machinery.</p>

<p>The harder design questions in real modulator electrodes are not single-layer at all. Production designs use multiple metal layers (M1 for signal, M2 for ground tying, dedicated VIA layers, bondpads at chip edges), explicit ground straps, and sometimes substrate undercut or DGS to push bandwidth past the loss-impedance front we mapped here. Each adds one or more parameters to a design space that grows combinatorially. With ~30 to 50 free parameters per geometry, manual exploration converges slowly; the loop above scales to those parameter counts naturally because the cost per iteration is the cloud simulation, not the design choice.</p>

<p>The same approach extends naturally to other parts of the modulator design problem: optical-mode engineering of the slow-wave waveguide arms, simultaneous co-design of the electrode and the rib waveguide cross-section, multi-arm push-pull layouts, and termination/launch network optimization. Each is one more parameter set on the same scaffold.</p>

<h3>What makes this different from a parameter sweep</h3>

<p>The loop is not a brute-force grid search or a black-box optimizer. The agent reads the journal of past iterations before each move, forms a hypothesis about which knob to perturb and in which direction, predicts the sign and rough magnitude of the change in each metric, and writes that prediction into the journal alongside the actual result. When the data disagrees with the prediction (and it often does; "expected n_eff up, got n_eff down" entries are some of the most useful), the agent updates its mental model of the design surface for the next move. When a topology family stops yielding improvements, the agent itself decides to switch to a different one and explains why in the journal.</p>

<p>Mid-run, the agent also reaches into the simulation infrastructure and adapts it. It noticed when the wave-port domain was too small for short-period geometries and patched the pad-length rule. It traced a builder bug that made adjacent T-tops overlap, fixed the period calculation, and re-ran the affected experiments. It tightened the conductor-loss fit window when band-edge artifacts contaminated the extraction. None of those were scripted. They came from the agent reading its own logs, recognizing that the data did not match the physics it expected, and rewriting the harness to fix the discrepancy. That is the qualitative difference: the loop is a closed feedback between reasoning, simulation, and code.</p>

<hr/>

<p class="refs"><strong>References.</strong></p>
<ol class="refs">
  <li>D. Zhuang <em>et al.</em>, "Equivalent Circuit Model of the Carrier-Depletion-Based Push-Pull Silicon Optical Modulators With T-Rail Slow Wave Electrodes," <em>IEEE Photonics Journal</em>, vol. 16, no. 4, art. 5500809, August 2024.</li>
  <li>P. Kharel, C. Reimer, K. Luke, L. He, and M. Zhang, "Breaking voltage-bandwidth limits in integrated lithium niobate modulators using micro-structured electrodes," <em>Optica</em>, vol. 8, no. 3, pp. 357-363, 2021. <a href="https://doi.org/10.1364/OPTICA.416155">https://doi.org/10.1364/OPTICA.416155</a></li>
</ol>
"""

    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Agentic Photonic Design - Segmented MZM Electrodes</title>
<style>{css}</style>
</head><body>
{body}
</body></html>
"""
    return html


def main():
    html = build_html()
    BLOG_PATH.write_text(html, encoding="utf-8")
    size_mb = BLOG_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {BLOG_PATH} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
