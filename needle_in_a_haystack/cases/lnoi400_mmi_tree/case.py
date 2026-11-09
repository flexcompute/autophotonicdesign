"""Test circuit on Luxtelligence LNOI400 (thin-film lithium niobate, C-band): a 1 x 8 MMI splitter tree.

    EC_in -> MMI 0 -> MMI 1, 2 -> MMI 3, 4, 5, 6 -> EC_out 0 ... 7

One input edge coupler on the left facet, eight output edge couplers on the right facet at a 127 um pitch. The tree is
mirror symmetric, so the eight paths have the same length. No DRC deck and no pin layers in this PDK.
build(**knobs) makes the clean circuit with the default knobs; the planter changes knobs to plant design mistakes.
"""
import photonforge as pf

PDK = "lnoi400"
TOP = "mmi_tree"
PITCH = 127.0
RADIUS = 80.0
X_LEVEL = (500.0, 1100.0, 1700.0)          # x of the input port of the MMIs at each level
X_END = 2700.0                             # the right facet
Y_OUT = [(3.5 - i) * PITCH for i in range(8)]
Y_MMI = [[0.0], [2 * PITCH, -2 * PITCH], [3 * PITCH, PITCH, -PITCH, -3 * PITCH]]

KNOBS = dict(
    ec_dy={},      # {output index: um} move output edge couplers along the facet; their routes follow
    bend_r={},     # {route name: um} bend radius of some routes
    mmi_dx={},     # {MMI index: um} move MMIs along x; their routes follow
)

PLANTS = [
    dict(knob="bend_r", value={"route_out_1": 100.0}, title="output route 1 bends at 100 um radius: legal, but its path "
         "is then shorter than the other seven", severity="medium",
         why="the intent asks for eight equal paths (+-0.5 um); the larger radius cuts the corners"),
    dict(knob="bend_r", value={"route_out_6": 25.0}, title="output route 6 bends at 25 um radius, not 80 um",
         severity="physics:bend"),
    dict(knob="ec_dy", value={5: 3.0}, title="output edge coupler 5 is 3 um off its 127 um pitch", severity="physics:fibre"),
    dict(knob="mmi_dx", value={4: 0.3}, title="MMI 4 sits 0.3 um further right; its three routes follow", severity="none",
         why="its input route is 0.3 um longer and both output routes 0.3 um shorter: every path keeps its length"),
]

INTENT = """\
# Design intent: 1 x 8 MMI splitter tree (Luxtelligence LNOI400, C-band)

The designer's statement of what the layout must be. Top cell: `mmi_tree`. Units: um.

## Process and operating point

- Luxtelligence LNOI400: 400 nm X-cut lithium niobate film, rib waveguides (LN_RIDGE 2/0 on the LN_SLAB 3/0 slab).
- TE, 1550 nm. Route cross-section: RWG1000 (1.0 um ridge).
- Lensed fibres or a fibre array at the facets: 127 um pitch. Edge-coupler mode-field diameter about 3 um.

## What the circuit does

| Stage | Cells | x of the MMI input | y |
|---|---|---|---|
| Input | edge coupler, facet at x = 0 | | 0 |
| Split 1 | MMI 0 (1 x 2) | 500 | 0 |
| Split 2 | MMI 1, 2 | 1100 | +254, -254 |
| Split 3 | MMI 3, 4, 5, 6 | 1700 | +381, +127, -127, -381 |
| Outputs | edge couplers 0 to 7, facet at x = 2700 | | +444.5 to -444.5, 127 apart |

## Rules the layout must follow

- Every route is the RWG1000 rib: 1.0 um ridge on LN_RIDGE. No tapers and no width changes in the routes.
- Every bend radius is 80 um or more.
- Every route meets its device port on axis, end to end.
- The eight output edge couplers sit on the right facet at a 127 um pitch.
- The eight paths from the input facet to the output facets have the same length (+-0.5 um).
- Loss budget: any single unplanned loss above 0.05 dB on a path is a defect. Above 1 dB it is critical.

## What has been checked

This PDK has no DRC deck and no pin layers. The layout was checked for minimum width and space and against
`intent_nets.json` before this review was requested. Something may have changed since.
"""


def _route(p1, p2, radius, name):
    r = pf.parametric.route(port1=p1, port2=p2, radius=radius)
    r.name = name
    return r


def _length(route):
    a = 0.0
    for layer, shapes in route.get_structures(depth=-1).items():
        if tuple(layer) == (2, 0):
            a += sum(s.area() for s in shapes)
    return a / 1.0


def build(**knobs):
    k = dict(KNOBS, **knobs)
    import luxtelligence_lnoi400_forge as lx
    tech = lx.lnoi400()
    pf.config.default_technology = tech
    C = lx.component
    chip = pf.Component(TOP, technology=tech)
    ec, mmi = C.edge_coupler(), C.mmi1x2_optimized1550()       # one cell each, many placements
    radius = dict(k["bend_r"])
    ec_in = chip.add_reference(ec)                              # facet (P0) at x = 0
    mmis, idx = [], 0
    for level, ys in enumerate(Y_MMI):
        for y in ys:
            mmis.append(chip.add_reference(mmi).translate((X_LEVEL[level] + 25.0 + k["mmi_dx"].get(idx, 0.0), y)))
            idx += 1
    outs = [chip.add_reference(ec).rotate(180).translate((X_END, y + k["ec_dy"].get(i, 0.0)))   # facet at x = X_END
            for i, y in enumerate(Y_OUT)]
    lengths = {}

    def add(p1, p2, name):
        r = _route(p1, p2, radius.get(name, RADIUS), name)
        lengths[name] = _length(r)
        chip.add_reference(r)

    add(ec_in["P1"], mmis[0]["P0"], "route_in")
    # MMI ports: P1 is the upper output, P2 the lower one
    add(mmis[0]["P1"], mmis[1]["P0"], "route_l1_0")
    add(mmis[0]["P2"], mmis[2]["P0"], "route_l1_1")
    for j, parent in enumerate((1, 2)):
        add(mmis[parent]["P1"], mmis[3 + 2 * j]["P0"], f"route_l2_{2 * j}")
        add(mmis[parent]["P2"], mmis[4 + 2 * j]["P0"], f"route_l2_{2 * j + 1}")
    for j in range(4):
        add(mmis[3 + j]["P1"], outs[2 * j]["P1"], f"route_out_{2 * j}")
        add(mmis[3 + j]["P2"], outs[2 * j + 1]["P1"], f"route_out_{2 * j + 1}")
    paths = {}
    for i in range(8):
        j = i // 2
        paths[i] = (lengths["route_in"] + lengths[f"route_l1_{j // 2}"] + lengths[f"route_l2_{j}"]
                    + lengths[f"route_out_{i}"])
    build.info = dict(route_lengths=lengths, path_lengths=paths)
    return chip


if __name__ == "__main__":
    c = build()
    print(c.bounds(), build.info["path_lengths"])
