"""
DUT factories for the DoE test chip (the PCell side of the device library).

These are the parametric devices-under-test, taken from the PhotonForge Component Library
example (https://docs.flexcompute.com/projects/photonforge/en/latest/examples/Component_Library.html)
and re-pointed at the standard `siepic_forge.ebeam()` C-band technology. Each factory is a
plain `@pf.parametric_component`, so variations are cached by argument value.

This is the *built-in* PCell set. The generalized ingestion layer (`tools/library.py`) wraps
each of these as a `DeviceSource`, and ALSO accepts user-supplied GDS files — so a user can run
the same DoE loop on their own PCells or their own GDS components.

Every DUT exposes:
  - optical ports  P0 / P1 (and P2 / P3 for 4-port devices), and
  - (active DUTs only) electrical Terminals H0 / H1 on M2_router.

No simulation models are attached: this is a layout / packing / routing demo, so everything here
is free and local.

The whole-chip "same direction for the wafer prober" rule is satisfied here by construction:
every device is built with the SAME orientation, and the floorplanner packs translation-only
(`allow_rotation=False`), so every grating-coupler array faces west and every bond-pad cage faces
south on the assembled chip.
"""
import photonforge as pf
import siepic_forge as sf
import photonforge.parametric as par

PORT_SPEC = "TE_1550_500"          # standard SiEPIC C-band strip waveguide
RIB_SPEC = "Rib_TE_1550_500"


def technology():
    """The standard SiEPIC EBeam technology, set as the default.

    Also turns OFF port/label glyphs in the SVG render so previews and GIF frames show only the
    layout geometry (clean, LiveViewer-style) instead of red port lines / fiber-cone arcs.
    """
    tech = sf.ebeam()
    pf.config.default_technology = tech
    for flag in ("svg_ports", "svg_labels", "svg_port_names", "svg_reference_ports",
                 "svg_reference_labels", "svg_reference_names", "svg_reference_port_names",
                 "svg_virtual_connections"):
        if hasattr(pf.config, flag):
            setattr(pf.config, flag, False)
    return tech


# ---------------------------------------------------------------- IO / fixed cells
def grating_coupler():
    """Standard SiEPIC TE C-band grating coupler. WG port P0, fiber (Gaussian) port P1."""
    return sf.component("ebeam_gc_te1550")


def terminator():
    """Low-reflection waveguide terminator (for unused ports of multi-port DUTs)."""
    return sf.component("ebeam_terminator_te1550")


def bond_pad(size=75.0):
    """Square M2 bond pad with an M_Open window, terminal name 'T'."""
    bp = pf.Component(f"BondPad_{int(size)}")
    bp.add_terminal(
        pf.Terminal("M2_router", pf.Rectangle(size=(size, size))),
        terminal_name="T",
        add_structure=True,
    )
    bp.add("M_Open", pf.Rectangle(size=(size - 6, size - 6)))
    return bp


# ---------------------------------------------------------------- passive DUTs
@pf.parametric_component(name_prefix="straight")
def straight_dut(*, length=100.0, width=0.5):
    """Cutback element: a straight waveguide, optionally at a non-default core `width`.

    The grating couplers feed a 500 nm (TE_1550_500) waveguide, so to test a different core width
    the middle section tapers from 500 nm up (or down) to `width` and back, via a symmetric "bulge"
    with short linear tapers at each end. Ports P0 (-x) / P1 (+x) stay at the 500 nm spec so the
    loopback routing connects cleanly. Measures: propagation loss vs length (cutback) and vs core
    width (multimode / narrow-guide loss).
    """
    if abs(width - 0.5) < 1e-3:
        return par.straight(length=length, port_spec=PORT_SPEC)
    return par.straight(length=length, port_spec=PORT_SPEC, bulge_width=width,
                        bulge_taper_length=10.0, bulge_margin=3.0)


@pf.parametric_component(name_prefix="spiral")
def spiral_dut(*, length=1000.0, radius=5.0, separation=3.0):
    """Compact folded-spiral propagation-loss cutback element.

    A rectangular (paperclip) spiral folds a long path (`length`, µm) into a small footprint, so
    the cutback ladder can reach the mm-scale lengths a low-loss waveguide needs WITHOUT a mm-long
    straight that would not fit the die. Ports P0 / P1 exit on OPPOSITE corners (no `align_ports`),
    so the loopback routes in from one side and out the other with no detour back across the body.
    Measures: propagation loss (long-length arm of the same cutback as `straight`).
    """
    return par.rectangular_spiral(
        port_spec=PORT_SPEC, full_length=length, radius=radius, separation=separation,
    )


@pf.parametric_component(name_prefix="dcoupler")
def directional_coupler_dut(*, coupling_gap=0.30, coupling_length=10.0):
    """Standard directional coupler: s-bend access waveguides into a parallel straight coupling
    region (`pf.parametric.s_bend_straight_coupler`). Ports P0..P3 (two inputs left, through +
    coupled right). `coupling_distance` is center-to-center = core width + `coupling_gap`.
    Measures: power splitting ratio vs coupling gap and vs coupling length.
    """
    wg_width, _ = pf.config.default_technology.ports[PORT_SPEC].path_profile_for("Si")
    return par.s_bend_straight_coupler(
        port_spec=PORT_SPEC,
        coupling_distance=wg_width + coupling_gap,
        coupling_length=coupling_length,
        s_bend_length=15.0,
        s_bend_offset=5.0,
    )


@pf.parametric_component(name_prefix="crossing")
def crossing_dut(*, added_width=1.2, arm_length=6.0):
    """Realistic waveguide crossing: each arm tapers from the 500 nm waveguide out to a wider
    multimode section (`added_width` extra core width) over `arm_length`, meeting in a widened
    intersection that flattens the diffraction and lowers insertion loss. `par.crossing` builds the
    4-port (+x/+y/-x/-y) cross; we expose the THROUGH path (P0 east / P2 west) and terminate the
    orthogonal arms internally, so the device is a clean 2-port for the loopback. Measures: crossing
    insertion loss vs intersection width (the wide-section / taper trade).
    """
    cr = par.crossing(port_spec=PORT_SPEC, arm_length=arm_length, added_width=added_width)
    c = pf.Component()
    ref = c.add_reference(cr)
    # through path: east/west
    c.add_port(ref["P0"], "P0")     # east
    c.add_port(ref["P2"], "P2")     # west
    # terminate the orthogonal (north / south) arms internally
    for pn in ("P1", "P3"):
        t = c.add_reference(terminator())
        t.connect("P0", ref[pn])
    return c


# ---------------------------------------------------------------- active DUTs
@pf.parametric_component(name_prefix="heater")
def heater_dut(*, length=100.0, heater_width=4.0, contact_depth=35.0, contact=10.0, lead=4.0):
    """Thermo-optic phase shifter: straight WG + M1 heater bar + two contacts BELOW the bar.

    Optical ports P0 / P1. Electrical Terminals H0 (x=0) / H1 (x=length) sit `contact_depth`
    below the waveguide, fed by short M1 leads, so M2 routing drops straight down and never
    crosses the heater resistor (the M2-over-M1 heatsink rule). Each contact carries an
    `M_Open` via window marking the intended (allowed) M2-on-M1 connection. Measures: thermo-optic
    phase-shifter efficiency (optical phase + electrical resistance).
    """
    c = pf.Component()
    wg = c.add_reference(par.straight(length=length, port_spec=PORT_SPEC))
    c.add_port(wg["P0"], "P0")
    c.add_port(wg["P1"], "P1")
    hw = max(heater_width, 3.0)   # SiEPIC M1 min width is 3 um
    lead = max(lead, 3.0)
    cy = -contact_depth
    # Inset the leads so they sit FULLY within the bar span: a lead centered on the bar end
    # leaves a sub-3um step (M1_width violation). xs are the contact/lead centers.
    inset = contact / 2 + 1.0
    xs = (inset, length - inset)
    # Union bar + leads + contact pads into ONE clean electrode polygon (single resistor net).
    m1_parts = [pf.Rectangle(center=(length / 2, 0), size=(length, hw))]   # resistor bar
    for x in xs:
        m1_parts.append(pf.Rectangle((x - lead / 2, cy), (x + lead / 2, -hw / 2)))   # lead down
        m1_parts.append(pf.Rectangle(center=(x, cy), size=(contact, contact)))       # contact pad
    c.add("M1_heater", *pf.boolean(m1_parts, [], "+"))
    for i, x in enumerate(xs):
        c.add("M_Open", pf.Rectangle(center=(x, cy), size=(contact, contact)))        # via window
        c.add_terminal(
            pf.Terminal("M2_router", pf.Rectangle(center=(x, cy), size=(contact, contact))),
            terminal_name=f"H{i}",
            add_structure=True,
        )
    return c


def _y_branch():
    """SiEPIC 1x2 Y-branch splitter (P0 stem, P1 bottom / P2 top branches)."""
    return sf.component("ebeam_y_1550")


@pf.parametric_component(name_prefix="cps_mod")
def cps_modulator_dut(*, length=500.0, imbalance=40.0):
    """Unbalanced Mach-Zehnder interferometer driven by a segmented CPS travelling-wave modulator.

    A Y-branch splits the input into two strip arms that run side by side (push-pull) under one
    coplanar-stripline electrode: a continuous signal rail (north) and ground rail (south) on
    M2_router, loaded by a periodic ladder of T-caps reaching toward the waveguides, with M_Open
    via windows on the push-pull doping (Si p++/p/n/n++) under each cap. A second Y-branch
    recombines the arms. The LOWER arm takes a `imbalance`-deep rectangular trombone detour (an
    explicit bend+straight chain) east of the electrode, so the two arms differ in optical length
    -> an UNBALANCED MZI (finite free spectral range you can bias-test).

    RF launch: the signal and ground are fanned out with `pf.parametric.route_taper` to two probe
    pads on the SOUTH edge (the y-axis), so the transmission line runs vertically and the prober
    lands the GS probe from the same direction as every other site's pads. The signal feed is
    routed WEST of the ground rail, so the signal and ground nets never overlap (no short). The
    device carries its own pads, so the test-site adds no extra bond-pad cage.

    Swept `length` sets the active electrode length (number of T-cap periods). Geometry is scaled
    down from the Zhuang 2024 design (narrower rails) so the device tiles on a packed die. Optical
    ports P0 (in) / P1 (out); electrical terminals = the signal / ground probe pads.
    """
    # Segmented loaded-CPS geometry, sized for the SiEPIC metal rules (M2 min width 5 um, min space
    # 8 um). The slow-wave loading is a periodic comb of SOLID capacitive fingers merged into each
    # rail (no thin T-cap necks, which would notch below the width/space minimums).
    finger_w, finger_gap = 8.0, 10.0                 # finger M2 width >= 5, finger-to-finger gap >= 8
    period = finger_w + finger_gap
    n_periods = max(2, int(round(length / period)))
    l_active = n_periods * period
    arm_pitch = 7.0
    cap_gap = 12.0                                   # signal<->ground finger M2 space >= 8
    rail_gap, sig_w, gnd_w = 36.0, 20.0, 20.0
    via_size, via_inset = 4.0, 1.0
    radius, access = 5.0, 30.0

    c = pf.Component()
    y1, y2 = arm_pitch / 2.0, -arm_pitch / 2.0      # top / bottom arm centers
    x0_a, xr_a = access, access + l_active           # electrode span in x

    # --- two equal strip arms under the electrode ---
    arm = par.straight(port_spec=PORT_SPEC, length=l_active)
    a1 = c.add_reference(arm); a1.origin = (x0_a, y1)      # top
    a2 = c.add_reference(arm); a2.origin = (x0_a, y2)      # bottom

    # --- bottom-arm trombone detour: an explicit bend+straight chain (the unbalanced MZI delay) ---
    # The detour is built deterministically from `par.bend` + `par.straight` connected end to end,
    # NOT from a single multi-`waypoints` `par.route`: the heuristic waypoint router inserts a 360
    # degree self-loop at the south-then-east corner and overshoots the bend allowance, which reads
    # as a colliding loop. A primitive chain gives exact, loop-free 90 degree corners. The chain is
    # a rectangular U east of the electrode: east `troff`, turn south, down `v`, turn east, across
    # `trw`, turn north, up `v`, turn east -> a clean detour that stays at -y (never crosses the top
    # arm) and never crosses itself. The south excursion ~= `imbalance` sets the extra arm length.
    troff, trw = 12.0, 45.0          # detour east offset; trombone width (down/up legs apart)
    v = max(2 * radius, imbalance - 2 * radius)      # vertical leg so the south reach ~= imbalance
    cur = a2["P1"]
    for kind, val in (("s", troff), ("b", -90), ("s", v), ("b", 90),
                      ("s", trw), ("b", 90), ("s", v), ("b", -90)):
        seg = (par.straight(port_spec=PORT_SPEC, length=val) if kind == "s"
               else par.bend(port_spec=PORT_SPEC, radius=radius, angle=val))
        ref = c.add_reference(seg); ref.connect("P0", cur); cur = ref["P1"]
    detour_end = cur                                  # faces east at the arm level, east of the U

    # --- input Y-split (P0 = MZI input) and output Y-combine (rotated 180, just east of the detour) ---
    ysplit = c.add_reference(_y_branch()); ysplit.origin = (-2.0, 0.0)
    ycomb = c.add_reference(_y_branch())
    ycomb.rotation = 180
    ycomb.origin = (detour_end.center[0] + access, 0.0)
    # ebeam_y_1550: P1 = bottom branch (-2.75), P2 = top branch (+2.75). The TOP routes stay at +y
    # and the BOTTOM routes stay at -y, so the two arms can never cross each other.
    c.add_reference(par.route(port1=ysplit["P2"], port2=a1["P0"], radius=radius))   # top in
    c.add_reference(par.route(port1=ysplit["P1"], port2=a2["P0"], radius=radius))   # bottom in
    c.add_reference(par.route(port1=a1["P1"], port2=ycomb["P1"], radius=radius))    # top out (direct)
    c.add_reference(par.route(port1=detour_end, port2=ycomb["P2"], radius=radius))  # bottom out (after detour)
    c.add_port(ysplit["P0"], "P0")
    c.add_port(ycomb["P0"], "P1")

    # --- push-pull doping under the arms (markers; guarded by layer availability) ---
    doping = [("Si p++", 8.0), ("Si p", 1.0), ("Si n", 1.0), ("Si n++", 3.0),
              ("Si n", 1.0), ("Si p", 1.0), ("Si p++", 8.0)]
    y_cur = sum(w for _, w in doping) / 2.0
    for layer, w in doping:
        try:
            c.add(layer, pf.Rectangle((x0_a, y_cur - w), (xr_a, y_cur)))
        except Exception:  # noqa: BLE001 - doping markers are nice-to-have
            pass
        y_cur -= w

    # --- CPS rails + segmented T-caps (M2_router) + contacts to silicon (Via to silicon) ---
    c.add("M2_router",
          pf.Rectangle((x0_a, rail_gap / 2), (xr_a, rail_gap / 2 + sig_w)),
          pf.Rectangle((x0_a, -rail_gap / 2 - gnd_w), (xr_a, -rail_gap / 2)))
    via_yi, via_yo = cap_gap / 2.0 + via_inset, cap_gap / 2.0 + via_inset + via_size
    for k in range(n_periods):
        xc = x0_a + (k + 0.5) * period
        fl, fr = xc - finger_w / 2.0, xc + finger_w / 2.0
        # solid capacitive fingers: signal finger from the north rail down toward the arms, ground
        # finger from the south rail up. Solid (no thin neck) -> M2 width and space stay legal.
        c.add("M2_router",
              pf.Rectangle((fl, cap_gap / 2), (fr, rail_gap / 2)),
              pf.Rectangle((fl, -rail_gap / 2), (fr, -cap_gap / 2)))
        c.add("Via to silicon", pf.Rectangle((fl, via_yi), (fr, via_yo)),
                                pf.Rectangle((fl, -via_yo), (fr, -via_yi)))

    # --- RF launch: GS probe pads on the SOUTH (y-axis), route_taper fanout ---
    # The signal runs down as a NARROW 6 um strip (which stays >= 8 um clear of the ground rail) and
    # only widens into the pad BELOW the rail, where there is nothing to space against -> DRC clean.
    pad, gs_pitch, feed_w = 42.0, 100.0, 6.0
    y_below = -rail_gap / 2 - gnd_w - 10.0              # just south of the ground rail
    y_pad = y_below - pad / 2 - 22.0                    # pad centers, further south
    x_sig = x0_a - 14.0                                 # signal feed west of the ground rail
    x_gnd = x_sig + gs_pitch
    # signal: extend the signal rail itself west (continuous M2, no sub-rail notch near the first
    # finger), then drop a narrow vertical feed down past the ground rail
    c.add("M2_router",
          pf.Rectangle((x_sig - feed_w / 2, rail_gap / 2), (x0_a, rail_gap / 2 + sig_w)),
          pf.Rectangle((x_sig - feed_w / 2, y_below), (x_sig + feed_w / 2, rail_gap / 2)))
    sig_src = pf.Terminal("M2_router", pf.Rectangle(center=(x_sig, y_below + 3), size=(feed_w, 6)))
    # ground: short stub down from the south edge of the ground rail
    c.add("M2_router", pf.Rectangle((x_gnd - feed_w / 2, y_below), (x_gnd + feed_w / 2, -rail_gap / 2)))
    gnd_src = pf.Terminal("M2_router", pf.Rectangle(center=(x_gnd, y_below + 3), size=(feed_w, 6)))
    # probe pads (with M_Open openings >= 10 um) + route_taper fanout, all BELOW the ground rail
    sig_rect = pf.Rectangle(center=(x_sig, y_pad), size=(pad, pad))
    gnd_rect = pf.Rectangle(center=(x_gnd, y_pad), size=(pad, pad))
    c.add("M2_router", sig_rect.copy(), gnd_rect.copy())
    c.add("M_Open", pf.Rectangle(center=(x_sig, y_pad), size=(pad - 10, pad - 10)),
                    pf.Rectangle(center=(x_gnd, y_pad), size=(pad - 10, pad - 10)))
    c.add(par.route_taper(terminal1=pf.Terminal("M2_router", sig_rect.copy()), terminal2=sig_src))
    c.add(par.route_taper(terminal1=pf.Terminal("M2_router", gnd_rect.copy()), terminal2=gnd_src))
    c.add_terminal([pf.Terminal("M2_router", sig_rect.copy()),
                    pf.Terminal("M2_router", gnd_rect.copy())])
    return c


# registry the library refers to by name
DUT_FACTORIES = {
    "straight": straight_dut,
    "spiral": spiral_dut,
    "dcoupler": directional_coupler_dut,
    "crossing": crossing_dut,
    "heater": heater_dut,
    "modulator": cps_modulator_dut,
}

# which DUTs need the test-site to add a bond-pad cage (the modulator carries its own RF pads)
ACTIVE_DUTS = {"heater"}
