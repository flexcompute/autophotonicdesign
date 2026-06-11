"""
Test-structure synthesis: wrap a bare DUT into a measurable, self-contained unit cell, and
turn a DoE plan into the full list of packable structures.

Vertical-coupling convention (the SiEPIC automated-measurement standard): every device gets its
OWN grating-coupler pair at the fiber-array pitch and is wired up in place, so a fiber-array
prober steps across the packed chip. Active devices additionally get a bond-pad cage with M2
routing from their terminals.

**Same direction for the wafer prober (the v1 constraint).** Every site is built with the SAME
orientation: the grating-coupler array is on the WEST side (fiber comes in from -x) and the
bond-pad cage is on the SOUTH side (-y). The floorplanner packs translation-only
(`allow_rotation=False`), so this orientation is preserved for every site on the assembled chip —
the prober's fiber array and probe card land the same way at every measurement site. The
`orientation_consistent` validation gate checks this holds.

This module is where the "route" in place-and-route happens:
  - optical:    pf.parametric.route          DUT optical ports -> GCs (radius-limited bends)
  - electrical: pf.parametric.route_manhattan DUT terminals    -> bond pads (avoiding M1)
"""
import photonforge as pf
import photonforge.parametric as par

from . import components as C


def _optical_ports(dut):
    """Names of the optical (non-electrical) ports, in order."""
    return [p for p in dut.ports]


_LABEL_PREFIX = {"straight": "WG", "spiral": "SP", "dcoupler": "DC",
                 "crossing": "X", "heater": "H", "ybranch_gds": "YB", "modulator": "MOD"}


def short_label(source, param=None, value=None):
    """Compact probe code for a site's Text-layer label, e.g. WG200, SP2000, DCg18, DCl16, X5,
    H200, Hw4, YB. Short enough to fit inside a site (descriptive names overflow small sites) and
    legible when the viewer zooms to a few sites."""
    p = _LABEL_PREFIX.get(source, source[:2].upper())
    if value is None:
        return p
    if isinstance(value, float) and not float(value).is_integer():
        v = str(int(round(value * 100))) if value < 1 else str(value)   # gap 0.18 -> 18
    else:
        v = str(int(value))
    tag = ""
    if param:
        if param.startswith("coupling_g"):
            tag = "g"
        elif param.startswith("coupling_l"):
            tag = "l"
        elif param in ("heater_width", "width"):
            tag = "w"
        elif param == "added_width":
            tag = "a"
    return f"{p}{tag}{v}"


def gc_loop(dut, name="loop", *, gc_pitch=127.0, radius=5.0, gc_clearance=25.0,
            route_pads=True, pad_size=60.0, pad_pitch=150.0, m2_width=8.0, label_size=14.0,
            label_text=None):
    """Build a self-contained grating-coupler loopback (a fiber-array measurement site).

    The two grating couplers are STACKED at the fiber-array pitch (`gc_pitch`, 127 um), both
    facing +x (so the fiber array couples from the WEST). The DUT sits to the right: its left-most
    optical port is fed by GC_in; its right-most port returns to GC_out via a route that detours
    OVER THE TOP (waypoints) so it never crosses the input route or the DUT. Extra optical ports
    are terminated.

    Active DUTs get a SOUTH-side bond-pad cage at `pad_pitch` (>=150 um) with M2 fan-out from the
    terminals. Orientation (GCs west, pads south) is identical for every site -> same prober
    direction everywhere. Returns the test-structure Component (fiber ports fiber_in / fiber_out).
    """
    c = pf.Component(name)
    d = c.add_reference(dut)

    optical = _optical_ports(dut)
    xc = {p: float(dut.ports[p].center[0]) for p in optical}
    yc = {p: float(dut.ports[p].center[1]) for p in optical}
    in_port = min(xc, key=xc.get)          # left-most optical port = input
    out_port = max(xc, key=xc.get)         # right-most optical port = output

    # place the DUT so its input port sits at (gc_clearance, 0), level with GC_in
    d.origin = (gc_clearance - xc[in_port], -yc[in_port])

    # GC pair stacked at the fiber pitch, both facing +x (WEST-facing fiber array)
    gc_in = c.add_reference(C.grating_coupler())
    gc_in.origin = (0.0, 0.0)
    gc_out = c.add_reference(C.grating_coupler())
    gc_out.origin = (0.0, gc_pitch)

    # input: GC_in -> DUT input (ports face each other -> short clean route)
    c.add_reference(par.route(port1=gc_in["P0"], port2=d[in_port], radius=radius))
    # output: DUT output -> detour right of the DUT and over the top -> GC_out (no crossing)
    (bx0, by0), (bx1, by1) = d.bounds()
    x_detour = bx1 + gc_clearance + radius
    c.add_reference(par.route(
        port1=d[out_port], port2=gc_out["P0"], radius=radius,
        waypoints=[(x_detour, d.origin[1] + yc[out_port]), (x_detour, gc_pitch)]))
    for pname in optical:
        if pname not in (in_port, out_port):
            term = c.add_reference(C.terminator())
            term.connect("P0", d[pname])

    c.add_port(gc_in["P1"], "fiber_in")
    c.add_port(gc_out["P1"], "fiber_out")

    # electrical: SOUTH-side bond-pad cage at >=150 um pitch, M2 fan-out from terminals
    terminals = list(dut.terminals)
    if route_pads and terminals:
        cx = (bx0 + bx1) / 2.0
        pad_y = by0 - pad_size / 2.0 - 60.0
        pad_x = [cx - pad_pitch / 2.0, cx + pad_pitch / 2.0]
        for i, tname in enumerate(terminals[:2]):
            pad = c.add_reference(C.bond_pad(pad_size))
            pad.origin = (pad_x[i], pad_y)
            c.add_reference(par.route_manhattan(
                terminal1=(d, tname), terminal2=(pad, "T"),
                direction1="y", direction2="y", layer="M2_router", width=m2_width))

    # small text label (the DoE tag) on the Text layer, above the GC pair, so each structure is
    # identifiable on the fabricated chip / in the GDS when probing.
    try:
        from photonforge.stencil import as_component
        lbl = c.add_reference(as_component(layer="Text", stencil="text",
                                           text_string=(label_text or name), size=label_size))
        lbl.origin = (0.0, gc_pitch + 30.0)
    except Exception:  # noqa: BLE001 - labels are nice-to-have, never break the build
        pass
    return c


def site_for(dev, *, params=None, gc_pitch=127.0, radius=5.0, name=None, label=None):
    """One measurement site for a DeviceSource `dev` at the given swept `params`. `label` is the
    compact Text-layer probe code (defaults to the device prefix, e.g. WG / DC / X / H / YB)."""
    params = params or {}
    dut = dev.instantiate(**params)
    if name is None:
        tag = "_".join(f"{k}{v}" for k, v in params.items())
        name = f"{dev.name}" + (f"_{tag}" if tag else "")
    if label is None:
        label = short_label(dev.name)
    return gc_loop(dut, name=name, gc_pitch=gc_pitch, radius=radius, route_pads=dev.active,
                   label_text=label)


def build_from_plan(plan, library, *, replicates=1, gc_pitch=127.0, radius=5.0):
    """Turn a DoE plan (from plan.py) + a device library into packable test structures.

    The plan is `{"experiments": [{"source", "param", "values", "fixed", "replicate_hint"}, ...]}`.
    Each (source, value) becomes ONE site, built ONCE and SHARED across replicates: pack_layout
    places each list entry as a separate reference, so N copies of one cell = N placements
    (hierarchical, instant). This is what makes hundreds of structures fast.

    `replicates` is a global multiplier on top of each experiment's own `replicate_hint`.
    Returns (structures, meta).
    """
    structures, meta = [], []
    for entry in plan["experiments"]:
        dev = library[entry["source"]]
        param = entry.get("param")
        values = entry.get("values", [None])
        kw_fixed = entry.get("fixed", {}) or {}
        reps = int(entry.get("replicate_hint", 1)) * int(replicates)
        for v in values:
            params = dict(kw_fixed)
            if param is not None and v is not None:
                params[param] = v
            tag = f"{dev.name}" + (f"_{param}{v}" if (param and v is not None) else "")
            label = short_label(dev.name, param, v)
            site = site_for(dev, params=params, gc_pitch=gc_pitch, radius=radius, name=tag,
                            label=label)
            for k in range(reps):
                structures.append(site)
                meta.append({"tag": tag, "source": dev.name, "param": param, "value": v,
                             "replicate": k, "measures": entry.get("measures", dev.measures)})
    return structures, meta
