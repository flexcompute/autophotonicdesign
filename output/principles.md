# Literature Principles for the 1310 nm SiN Edge Coupler

## Target and Constraints

- Platform here is a single 400 nm thick SiN layer in SiO2, with a 1.0 um final waveguide and a 50 um fixed taper length.
- Input is a free-space Gaussian at the facet, MFD = 3.2 um, TE-like Ey polarization, centered on the 400 nm SiN core.
- Fabrication floor is 150 nm, so the smallest robust solid SiN tip is 150-200 nm.
- Because no additional layers or materials may be introduced beyond existing SiN/SiO2/Si/air, the most useful topology levers are in-plane: inverse taper profile, multi-tip/trident tips, segmented/SWG effective-index sections, and mode-expander rails.

## Baseline Inverse Taper

- Core idea: a narrow SiN tip weakens lateral confinement so the guided mode expands into SiO2 and better overlaps the incident Gaussian; then a gradual taper compresses the mode into the 1 um waveguide.
- The total efficiency is the product of facet mode overlap and taper conversion efficiency. The facet shape should match the Gaussian as closely as possible, while the taper should change effective index slowly enough to avoid radiation and higher-order excitation.
- Literature guidance:
  - A theoretical SiN edge coupler study emphasizes electric-field overlap at the end face, followed by adiabatic mode conversion. It used a 200 nm inverse-taper tip as a fabrication-aware critical dimension and, for 400 nm SiN transfer, a much longer multi-stage taper than this 50 um problem allows. Source: https://www.mdpi.com/2304-6732/10/3/231
  - A tutorial/review on SiN inverted tapers reports very low loss when the fiber and taper mode are well matched, including -0.15 dB per connection with UHNA-7 fiber and -1.50 dB with standard SMF at 1550 nm for a 220 x 1200 nm platform. Source: https://arxiv.org/abs/2405.11980
  - For thin SiN, coupling improves when tip width is small enough to expand the mode; 150 nm thick SiN needed sub-500 nm tips for roughly 5 um beam diameters. Our 400 nm layer and 3.2 um MFD require careful balance: small enough tip for mode expansion, but not so small that the 50 um transition radiates. Source: https://pdfs.semanticscholar.org/c5bd/258248e818c61b09b4d7dd8877698a84a585.pdf

## Taper Profile

- Linear width ramps are simple but are rarely optimal over short lengths because effective index changes fastest near the narrow tip.
- A nonlinear taper that expands slowly at the facet and faster later can reduce abrupt effective-index change where the mode is largest and least confined.
- For this 50 um fixed length, prioritize profiles with a gentle first 10-20 um:
  - power-law width: w(x) = w_tip + (w_out - w_tip) * (x/L)^p, p > 1
  - Bezier/smoothstep curve with low initial slope
  - piecewise taper: short near-constant narrow tip section plus accelerated output transition
- Risk: too-slow early widening leaves an abrupt final transition, so tune p and any hold length with sweeps.

## Multi-Tip and Trident Couplers

- Multi-tip/trident edge couplers broaden the lateral field at the facet and improve alignment tolerance by splitting the input aperture into several weakly guiding tips that merge into the single waveguide.
- A recent SWG-assisted SiN trident paper reports that the trident produces a broader lateral mode than a single tip, improving modal-area match and robustness to tip-width variation. It also notes that a 200 nm tip gave similar overlap to a single-tip design while SWG tri-tip was more robust across tip widths. Source: https://www.nature.com/articles/s41598-025-26434-x
- In this design space, a practical single-layer variant is three SiN tapers at the facet:
  - center tip aligned to y = 0
  - two side tips placed symmetrically, with >=150 nm gaps
  - side tips merge adiabatically into the central 1 um waveguide over 50 um
- Key parameters: tip width 0.15-0.22 um, facet gap 0.2-0.8 um, side-tip merge length/location, side final width, and whether the center taper starts narrow or carries most of the power.
- Risk: side rails too close can trigger DRC spacing failures or behave like one wide slab; too far can radiate or miss the 3.2 um Gaussian.

## Subwavelength-Grating Effective Index

- SWG tapers can lower effective index and soften the width-to-index slope, helping short tapers approximate a longer adiabatic transition.
- The SWG trident paper used 400 nm pitch and 0.625 fill factor at 1550 nm, observing that SWG tapers can achieve compact transitions because the effective index changes more slowly with width than a solid taper.
- For 1310 nm and a 150 nm feature rule, conservative periods near 0.35-0.45 um and SiN segment/gap >=150 nm are possible, but the harness DRC checks in-plane gaps and the preview must confirm every segment is connected or intentionally separated.
- Risk: a broken segmented taper may fail connectivity, add reflections, or be expensive to simulate because of many small features.

## Compact SiN Wire Tapers

- Compact SiN taper literature shows that short optimized profiles can outperform simple linear transitions. One SiN wire taper paper reports 95% transmission in a 19.5 um optimized taper from 10 um to 1 um, compared with a 50 um linear taper, indicating profile shape matters strongly for compact SiN mode conversion. Source: https://arxiv.org/abs/1711.09831
- Although that paper addresses waveguide-to-waveguide tapering rather than free-space edge coupling, it supports using nonlinear profiles and local mode-evolution tuning inside the 50 um length.

## Simulation Strategy

- Establish a baseline metric for the plain linear inverse taper.
- First topology moves should be low-risk:
  1. tune single-tip width and nonlinear taper exponent;
  2. try a trident/multi-tip mode expander;
  3. tune side-tip gap and merge;
  4. try segmented/SWG-like facet sections if solid multi-tip saturates.
- For each topology, use exploration sweeps for numerical parameters instead of burning experiment numbers.
- Always run DRC before preview and inspect for taper-output connectivity, side-tip merge gaps, source clearance, and monitor placement.

