---
name: 3D FDTD grid resolution
description: In the autophotonicdesign repo, min_steps_per_wvl=20 is the floor for 3D FDTD runs; 25-30 is needed for final verification.
type: feedback
---

For 3D FDTD simulations in the grating-coupler repo, `min_steps_per_wvl` below 20 gives inaccurate results — 12 and 16 were confirmed too coarse.

**Why:** The user verified empirically that 3D-specific near-field phenomena (fan/tooth junction, focusing interference) need finer gridding than 2D did. This is a CORRECTION to my earlier default recommendation of 16 (which I copied over from 2D thinking).

**How to apply:**
- Iteration runs: `min_steps_per_wvl = 20` (minimum).
- Final verification / polish: `min_steps_per_wvl = 25-30`.
- Do not drop below 20 to save credits — use smaller buffers or narrower angular_half_span instead.
- 2D simulations in this repo can still use 20 (original default) without issue.
