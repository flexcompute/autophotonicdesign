# Lessons (read first, add at the end of each phase)

Each lesson: what happened, why, what to do. One to three lines. Newest at the bottom.
The first ones come from building and testing this harness (PhotonForge 2.0.0, SiPhoPDK 1.0.0).

## Toolchain

1. **LVS merges nets of a multi-net route_auto.** PF 2.0 LVS treats one route component as one wire.
   Route all optical nets in ONE `route_auto` call (it avoids collisions), then add the result with
   `tools/routing.py: add_routes` (or call `route_nets`). LVS then sees one wire per net.
2. **Raw `pf.parametric.straight` / `bend` chains inside your own component fail LVS** (no device
   outline). Build meanders and delay arms from PDK cells (`library.straight`, `library.bend`), give the
   container `pf.CircuitModel()`, and expose its end ports.
3. **Every reference needs a model** or the circuit simulation stops with "No active model". The chip
   needs `pf.CircuitModel()`. Call `pdk.fast_models(chip)` at the end of `build()`: route pieces get
   the PDK's analytic strip model, so the post-layout simulation needs no mode solver and no cloud.
4. **Checks are offline.** `tools/verify.py` and `tools/measure.py` block cloud runs and use the local
   mode solver. The first simulation of a new chip takes about 10 s (port mode solves); after that
   about 0.6 s for 401 wavelengths.
5. **SMatrix is not a dict.** Element `sm[("IN1@0", "OUT1@0")]` = from IN1 to OUT1. `sm.elements` lists keys.
6. **Per-instance model changes** go through `chip.s_matrix(f, model_kwargs={"updates": {key: {"model_updates": {...}}}})`
   with key = `(name_regex, index, name_regex, index, ...)`, index = order among same-named instances in
   `get_netlist()["instances"]`. `tools/measure.py: instances(chip)` lists them.
7. **A reversing detour with `route` waypoints makes self-loops.** Build U-turns and meanders as a
   deterministic chain of bends and straights; measure length with `pf.route_length`.

## SiPhoPDK models (synthetic platform; numbers from `siphopdk._calibration`)

8. **Directional coupler** (`library.directional_coupler`): analytic model, power coupling
   kappa = sin^2(pi/2 * coupling_length / 30 um), 0.1 dB loss, flat in wavelength. The S-bends add no
   coupling in the model. Gap variation scales the 30 um (spec.yaml variation).
9. **Strip waveguide**: n_eff 2.5932, n_g 4.2949 at 1310 nm, 0.2 dB/mm (0.01 dB per 90 deg bend).
10. **Heater** (`library.thermal_phase_shifter`): the waveguide's n_eff rises by dn/dT = 1.86e-4 per K
    over the heater length. Phase per K = 2 pi dn/dT L / lambda (100 um: 2 pi at about 70 K).
    Heaters only add phase; a phase you need "below zero" costs nearly 2 pi.
11. **Grating coupler**: measured-style model, 1.3 dB peak loss at 1310 nm, 20 nm 1-dB bandwidth,
    -25 dB back-reflection. Channel B (1315 nm) pays about 0.2 dB more per coupler than channel A.

## Design intent

12. **"DRC clean, LVS clean, simulation runs" does not mean the chip works.** A first try copied delay
    lengths from another chip and three default couplers: it passed DRC and LVS, and the response was
    two unrelated MZIs, not a filter. Score the response shape against the spec every time, and
    look at the plot.
13. **Draw the phases.** Heaters correct variation; they are not the bias. Put the stage phases in the
    drawn lengths (a fraction of a wavelength of extra length), so the nominal die needs only a few K.
