# Lessons

Read this file before you start. When you find a new problem and its solution, add an item at the
end. Each item gives the rule and the reason, in one to three lines.

Versions: PhotonForge 2.0.0, SiPhoPDK 1.0.0.

## Tools

1. Route all optical nets with one call to `tools/routing.py: route_nets`. Reason: LVS sees one
   `route_auto` result as one wire and connects all its nets. `route_nets` adds one wire for each net.
2. Make delay arms and meanders from PDK cells (`library.straight`, `library.bend`). Put them in a
   component with `pf.CircuitModel()` and give it the end ports. Reason: LVS cannot identify a chain
   of `pf.parametric.straight` and `bend` in your own component.
3. Give a model to each reference. Add `pf.CircuitModel()` to the chip. Call `pdk.fast_models(chip)`
   at the end of `build()`. Reason: without a model, the circuit simulation stops ("No active
   model"). `fast_models` gives the route pieces an analytic model, so the simulation needs no mode solver.
4. The checks in `tools/` run on this computer and stop cloud runs. The first simulation of a new
   chip takes approximately 10 s (port mode solves). The next simulations take approximately 0.6 s for 401 wavelengths.
5. An `SMatrix` is not a dict. `sm[("IN1@0", "OUT1@0")]` is the element from IN1 to OUT1. `sm.elements` gives the keys.
6. To change the model of one instance, use
   `chip.s_matrix(f, model_kwargs={"updates": {key: {"model_updates": {...}}}})`. The key is
   `(name_regex, index, name_regex, index, ...)`. The index is the order of the instances with the
   same name in `get_netlist()["instances"]`. `tools/measure.py: instances(chip)` gives a list of the keys.
7. Do not use `route` waypoints for a route that turns back (a U-turn or a meander). Reason: the
   router adds a loop. Make the U-turn from bends and straights. Measure the length with `pf.route_length`.

## SiPhoPDK models (values from `siphopdk._calibration`)

8. Directional coupler (`library.directional_coupler`): analytic model. The power coupling is
   kappa = sin^2(pi/2 x coupling_length / 30 um). The loss is 0.1 dB. The coupling does not change
   with wavelength. The model does not include coupling in the S-bends. The gap variation of a die
   changes the 30 um value (see the variation in `spec.md`).
9. Strip waveguide: n_eff = 2.5932 and n_g = 4.2949 at 1310 nm. Loss: 0.2 dB/mm, plus 0.01 dB for each 90 degree bend.
10. Heater (`library.thermal_phase_shifter`): the n_eff of the heated waveguide increases by
    1.86e-4 for each K. The phase change for each K is 2 pi x 1.86e-4 x L / lambda. For L = 100 um,
    a 2 pi change needs approximately 70 K. A heater only adds phase. A phase change "below zero" needs almost 2 pi.
11. Grating coupler: data model with 1.3 dB loss at the peak (1310 nm), 20 nm 1-dB bandwidth, and
    -25 dB back-reflection. At 1315 nm, the loss is approximately 0.2 dB higher for each coupler.
12. Add a `FLOORPLAN` rectangle that encloses all shapes of the chip. Reason: SiPhoPDK DRC rule FP.1
    gives a violation for each shape outside the floorplan.
13. Do not give `straight_kwargs` or `bend_kwargs` to `route_auto` (it does not accept them).
    `pdk.fast_models(chip)` at the end of `build()` gives the models to the route pieces.
