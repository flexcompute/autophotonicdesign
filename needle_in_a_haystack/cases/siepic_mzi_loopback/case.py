"""Test circuit on SiEPIC EBeam (220 nm SOI, C-band): two unbalanced MZIs and a loopback through a crossing.

    GC0 -> MZI A (dL = 100 um) -> GC1
    GC2 -> MZI B (dL =  60 um) -> GC3
    GC4 -> crossing (through) -> GC5, the other two crossing arms end in terminators

The six grating couplers sit on one column at a 127 um pitch for a fibre array.
build(**knobs) makes the clean circuit with the default knobs; the planter changes knobs to plant design mistakes.
"""
import numpy as np
import photonforge as pf

PDK = "siepic_ebeam"
TOP = "mzi_loopback"
PITCH = 127.0
RADIUS = 5.0

KNOBS = dict(
    dl_a=100.0,           # um, long arm minus short arm, MZI A
    dl_b=60.0,            # um, MZI B
    gc_dy={},             # {grating index: um} move gratings along the column; their routes follow
    bend_r={},            # {route name: um} bend radius of some routes
    crossing_rot=0.0,     # degrees, turn of the crossing cell
)

# Design-level plants the planter can choose: knob values with what they do. Severity is set by the planter from
# physics where it can (bend loss, fibre offset); 'function' plants change what the circuit does.
PLANTS = [
    dict(knob="dl_a", value=80.0, title="MZI A long arm 20 um short: dL = 80 um, not 100 um", severity="high",
         why="the free spectral range moves from 5.6 nm to 7.0 nm: the filter does not meet its function"),
    dict(knob="dl_b", value=60.4, title="MZI B dL = 60.4 um, not 60 um", severity="none",
         why="0.4 um is within the +-0.5 um tolerance of the intent sheet"),
    dict(knob="gc_dy", value={3: 2.0}, title="grating coupler 3 is 2 um off its 127 um pitch", severity="physics:fibre"),
    dict(knob="gc_dy", value={5: 0.1}, title="grating coupler 5 is 0.1 um off its 127 um pitch", severity="physics:fibre"),
    dict(knob="bend_r", value={"route_b_out": 2.0}, title="one MZI B output route bends at 2 um radius, not 5 um",
         severity="physics:bend"),
    dict(knob="crossing_rot", value=90.0, title="the crossing is turned by 90 degrees", severity="none",
         why="the crossing is 4-fold symmetric: same geometry, only the pin names change"),
]

INTENT = """\
# Design intent: two unbalanced MZIs and a loopback (SiEPIC EBeam, C-band)

The designer's statement of what the layout must be. Top cell: `mzi_loopback`. Units: um.

## Process and operating point

- SiEPIC EBeam PDK: 220 nm silicon (layer Si 1/0), TE, 1550 nm.
- Fibre array: 127 um pitch, single-mode fibre (mode-field diameter about 10.4 um).

## What the circuit does

| Path | From | Through | To |
|---|---|---|---|
| MZI A | GC0 (y = 0) | Y-branch, two arms, Y-branch | GC1 (y = 127) |
| MZI B | GC2 (y = 254) | Y-branch, two arms, Y-branch | GC3 (y = 381) |
| Loopback | GC4 (y = 508) | the crossing, straight through | GC5 (y = 635) |

The two other arms of the crossing end in terminators.

## Rules the layout must follow

- Every route is the TE_1550_500 strip: 500 nm wide on Si. No tapers and no width changes in the routes.
- Every bend radius is 5 um or more.
- Every route meets its device port on axis, end to end.
- The six grating couplers sit on one column (one x) at a 127 um pitch, all facing +x.
- MZI A: long arm minus short arm = 100.0 um (+-0.5 um). MZI B: 60.0 um (+-0.5 um).
- Loss budget: any single unplanned loss above 0.05 dB on a path is a defect. Above 1 dB it is critical.

## What has been checked

The design passed the PDK DRC and an LVS against `intent_nets.json` before this review was requested. Something may
have changed since.
"""


def _route(p1, p2, radius, name, waypoints=()):
    r = pf.parametric.route(port1=p1, port2=p2, radius=radius, waypoints=list(waypoints))
    r.name = name
    return r


def _arm_length(route):
    """Centre-line length of a 500 nm route (area / width)."""
    a = 0.0
    for shapes in route.get_structures(depth=-1).values():
        for s in shapes:
            a += s.area()
    return a / 0.5


def _mzi(chip, ybr, y0, dl, tag):
    """Y-branch MZI between grating y0 and grating y0 + PITCH."""
    y1 = chip.add_reference(ybr).translate((40.0, y0))
    y2 = chip.add_reference(ybr).rotate(180).translate((200.0, y0))
    short = _route(y1["P2"], y2["P1"], RADIUS, f"route_{tag}_short")
    # the long arm dips down by h: tune h so that the extra length is dl
    lo, hi = 2 * RADIUS + 1.0, 400.0
    for _ in range(40):
        h = 0.5 * (lo + hi)
        x0, x1 = y1["P1"].center[0] + 15.0, y2["P2"].center[0] - 15.0
        yl = y1["P1"].center[1] - h
        long_ = _route(y1["P1"], y2["P2"], RADIUS, f"route_{tag}_long", [(x0, yl), (x1, yl)])
        d = _arm_length(long_) - _arm_length(short)
        lo, hi = (h, hi) if d < dl else (lo, h)
    chip.add_reference(short)
    chip.add_reference(long_)
    return y1, y2, _arm_length(long_) - _arm_length(short)


def build(**knobs):
    k = dict(KNOBS, **knobs)
    import siepic_forge as se
    tech = se.ebeam()
    pf.config.default_technology = tech
    chip = pf.Component(TOP, technology=tech)
    gc, ybr, xing, term = (se.component(n) for n in ("ebeam_gc_te1550", "ebeam_y_1550", "ebeam_crossing4",
                                                       "ebeam_terminator_te1550"))   # one cell each, many placements
    gcs = []
    for i in range(6):
        dy = k["gc_dy"].get(i, 0.0)
        gcs.append(chip.add_reference(gc).translate((0.0, i * PITCH + dy)))
    radius = dict(k["bend_r"])
    out = {}
    for tag, gi, dl in (("a", 0, k["dl_a"]), ("b", 2, k["dl_b"])):
        y0 = gi * PITCH
        y1, y2, got = _mzi(chip, ybr, y0, dl, tag)
        out[f"dl_{tag}"] = got
        chip.add_reference(_route(gcs[gi]["P0"], y1["P0"], radius.get(f"route_{tag}_in", RADIUS), f"route_{tag}_in"))
        up = gcs[gi + 1]["P0"]
        chip.add_reference(_route(y2["P0"], up, radius.get(f"route_{tag}_out", RADIUS), f"route_{tag}_out",
                                  [(260.0, y0), (260.0, up.center[1])]))
    # loopback through the crossing
    yc = 4 * PITCH
    x = chip.add_reference(xing).rotate(k["crossing_rot"]).translate((120.0, yc))
    near = {}
    for pn in x.component.ports:                    # match the turned crossing's ports by where they are
        c = x[pn].center
        side = "W" if c[0] < 119.0 else "E" if c[0] > 121.0 else ("S" if c[1] < yc else "N")
        near[side] = x[pn]
    chip.add_reference(_route(gcs[4]["P0"], near["W"], RADIUS, "route_c_in"))
    chip.add_reference(_route(near["E"], gcs[5]["P0"], RADIUS, "route_c_out", [(200.0, yc), (200.0, 5 * PITCH)]))
    for side, dy, ang in (("N", 15.0, 270.0), ("S", -15.0, 90.0)):   # a 15 um straight, then a terminator
        t = chip.add_reference(term).rotate(ang).translate((120.0, yc + dy))
        chip.add_reference(_route(near[side], t["P0"], RADIUS, f"route_c_term_{side}"))
    (x0, y0b), (x1, y1b) = chip.bounds()
    chip.add((99, 0), pf.Rectangle((x0 - 10.0, y0b - 10.0), (x1 + 10.0, y1b + 10.0)))   # SiEPIC floor plan
    build.info = out
    return chip


if __name__ == "__main__":
    c = build()
    print(c.bounds(), build.info)
