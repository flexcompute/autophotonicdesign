"""Red side: build a case clean, plant mistakes, write the planted GDS and the answer key.

    python tools/red/plant.py cases/siepic_mzi_loopback --seed 7 --out ../runs/siepic_s7/red

Two kinds of plant:
- design plants: the case's PLANTS list changes knobs of its build() (a wrong delay, a moved grating, a tight bend);
- geometry plants: generic edits of a random straight route piece, the same for every PDK (neck, offset, width
  change, a piece on the wrong layer, a gap).

The severity of each plant comes from physics where it can (local mode solves of the PDK cross-section):
  more than 1 dB high, 0.1 to 1 dB medium, 0.05 to 0.1 dB low; below 0.05 dB low if the plant breaks a rule of the
  intent sheet, else none.
Then the PDK's own checks (DRC or the basic check, and LVS against the clean netlist) run on the planted chip. A plant
that a check flags is an easy one; the rest are real mistakes, or harmless changes when the severity is none.

The output folder holds clean.gds, haystack.gds, answer_key.json and the files for the sandbox (intent sheet,
intended netlist). Keep it away from the reviewers.
"""
import argparse
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import photonforge as pf   # noqa: E402
import shapely             # noqa: E402
import review as rv        # noqa: E402

GEOMETRY_OPS = ["gap", "neck", "offset", "offset_tiny", "width", "wrong_layer"]
FIBRE_MFD = {"siepic_ebeam": 10.4, "siphopdk": 9.2, "lnoi400": 3.0}     # um, mode-field diameter at the couplers


def load_case(folder):
    spec = importlib.util.spec_from_file_location("case", Path(folder) / "case.py")
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(folder)))
    spec.loader.exec_module(m)
    return m


def severity(loss_db, breaks_rule):
    if loss_db is None:
        return "high"
    if loss_db > 1.0:
        return "high"
    if loss_db > 0.1:
        return "medium"
    if loss_db > 0.05:
        return "low"
    return "low" if breaks_rule else "none"


# ------------------------------------------------------------------------------------------------- geometry helpers
def _flat_core(comp, layers):
    out = []
    for layer, shapes in comp.get_structures(depth=-1).items():
        if rv._lname(layer) in layers:
            out += [rv._shp(s) for s in shapes]
    return out


def _diff_bbox(clean, planted, layers, pad=1.0):
    a = shapely.union_all(_flat_core(clean, layers))
    b = shapely.union_all(_flat_core(planted, layers))
    d = a.symmetric_difference(b)
    d = d.buffer(-1e-3).buffer(1e-3)          # drop float noise
    if d.is_empty:
        return None
    x0, y0, x1, y1 = d.bounds
    return [x0 - pad, y0 - pad, x1 + pad, y1 + pad]


def _straights(route, layer):
    """Axis-aligned rectangles on `layer` in a route cell (its own frame): [(polygon, axis, length, width)]."""
    out = []
    for lay, shapes in route.get_structures(depth=-1).items():
        if rv._lname(lay) != layer:
            continue
        for s in shapes:
            p = rv._shp(s)
            x0, y0, x1, y1 = p.bounds
            if abs(p.area - (x1 - x0) * (y1 - y0)) > 1e-4:
                continue
            ax = 0 if (x1 - x0) >= (y1 - y0) else 1
            L, W = (x1 - x0, y1 - y0) if ax == 0 else (y1 - y0, x1 - x0)
            out.append((p, ax, L, W))
    return out


def _rect(cx, cy, ax, L, W):
    return shapely.box(cx - L / 2, cy - W / 2, cx + L / 2, cy + W / 2) if ax == 0 else \
        shapely.box(cx - W / 2, cy - L / 2, cx + W / 2, cy + L / 2)


def _to_pf(poly):
    return [pf.Polygon(np.asarray(g.exterior.coords)[:-1]) for g in getattr(poly, "geoms", [poly]) if g.area > 1e-8]


def _edit_route(ref, layer, alt, piece, cut=(), add=(), add_alt=()):
    """Replace ref.component with a flat copy whose `piece` on `layer` is cut and replaced."""
    old = ref.component
    new = pf.Component(old.name, technology=old.technology)
    lay_t, alt_t = rv._layer(layer), (rv._layer(alt) if alt else None)
    target = None
    for lay, shapes in old.get_structures(depth=-1).items():
        for s in shapes:
            p = rv._shp(s)
            if target is None and tuple(lay) == lay_t and p.equals_exact(piece, 1e-6):
                target = p
                rest = p
                for c in cut:
                    rest = rest.difference(c)
                for g in _to_pf(rest):
                    new.add(lay, g)
                continue
            new.add(lay, s)
    assert target is not None, "piece not found"
    for g in add:
        for q in _to_pf(g):
            new.add(lay_t, q)
    for g in add_alt:
        for q in _to_pf(g):
            new.add(alt_t, q)
    for pn, port in old.ports.items():
        new.add_port(port, pn)
    ref.component = new


def _top_bbox(ref, poly, pad=0.5):
    A, b = rv._affine(ref)
    c = np.asarray(poly.exterior.coords) @ A.T + b
    return [float(c[:, 0].min() - pad), float(c[:, 1].min() - pad), float(c[:, 0].max() + pad), float(c[:, 1].max() + pad)]


def _pins_xy(comp):
    """Positions of all device ports of the top-level references of a built component."""
    pts = []
    for r in comp.references:
        if rv._is_device(r.component):
            pts += [tuple(float(v) for v in r[p].center[:2]) for p in r.component.ports]
    return pts


def choose(op, ref, rng, P, w, pins):
    """Pick a straight piece of route `ref` and the numbers of one edit. Interior pieces (no device port at either end)
    come first. Returns an action dict, or None if the route has no suitable piece."""
    layer = P.CORE[0]
    if op == "wrong_layer" and not P.ALT_CORE:
        return None
    cands = [(i, s) for i, s in enumerate(_straights(ref.component, layer)) if abs(s[3] - w) < 1e-3 and s[2] >= 14.0]
    A, b = rv._affine(ref)

    def at_pin(poly):
        c = np.asarray(poly.exterior.coords) @ A.T + b
        x0, y0, x1, y1 = c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()
        return any(x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1 for x, y in pins)
    inner = [c for c in cands if not at_pin(c[1][0])]
    cands = inner or cands
    if not cands:
        return None
    idx, (piece, ax, L, W) = rng.choice(cands)
    act = dict(op=op, route=ref.component.name, piece=idx, s0=rng.uniform(-(L / 2 - 6.0), L / 2 - 6.0))
    if op == "neck":
        act.update(width=round(rng.choice([0.4, 0.5]) * w, 3), length=rng.choice([2.0, 3.0]))
    elif op == "wrong_layer":
        act.update(length=rng.choice([5.0, 10.0]))
    return act


def apply_action(comp, act, P, w):
    """Apply one geometry edit to the route named act['route'] of `comp`. Returns dict(title, bbox, loss, rule)."""
    layer = P.CORE[0]
    alt = P.ALT_CORE[0] if P.ALT_CORE else None
    ref = next(r for r in comp.references if r.component.name == act["route"])
    piece, ax, L, W = _straights(ref.component, layer)[act["piece"]]
    cx, cy = piece.centroid.x, piece.centroid.y
    px, py = (cx + act["s0"], cy) if ax == 0 else (cx, cy + act["s0"])
    px, py = round(px, 3), round(py, 3)                 # on the 1 nm grid, or the GDS writer leaves 1 nm slits
    name, op = act["route"], act["op"]
    if op == "gap":
        g = 0.5
        cut = _rect(px, py, ax, g, W + 0.2)
        _edit_route(ref, layer, alt, piece, cut=[cut])
        return dict(title=f"{g} um gap in route {name}", bbox=_top_bbox(ref, cut), loss=None, rule=True, params=dict(gap=g))
    if op == "neck":
        wn, ln = act["width"], act["length"]
        cut = _rect(px, py, ax, ln, W + 0.2)
        _edit_route(ref, layer, alt, piece, cut=[cut], add=[_rect(px, py, ax, ln, wn)])
        return dict(title=f"route {name} narrows to {wn * 1000:.0f} nm for {ln:g} um", bbox=_top_bbox(ref, cut),
                    physics=("junction", dict(width2=wn)), rule=True, params=dict(width=wn, length=ln))
    if op in ("offset", "offset_tiny"):
        d = round((0.3 if op == "offset" else 0.01) * w, 4)
        dx, dy = (0.0, d) if ax == 0 else (d, 0.0)
        moved = shapely.affinity.translate(piece, dx, dy)
        _edit_route(ref, layer, alt, piece, cut=[piece.buffer(1e-4, join_style=2)], add=[moved])
        return dict(title=f"a {L:.0f} um straight of route {name} sits {d * 1000:.0f} nm off axis",
                    bbox=_top_bbox(ref, piece.union(moved)), physics=("junction", dict(offset=d)), rule=op == "offset",
                    params=dict(offset=d))
    if op == "width":
        w2 = round(0.6 * w, 3)
        _edit_route(ref, layer, alt, piece, cut=[piece.buffer(1e-4, join_style=2)], add=[_rect(cx, cy, ax, L, w2)])
        return dict(title=f"a {L:.0f} um straight of route {name} is {w2 * 1000:.0f} nm wide, no tapers",
                    bbox=_top_bbox(ref, piece), physics=("junction", dict(width2=w2)), rule=True, params=dict(width=w2, length=L))
    if op == "wrong_layer":
        ls = act["length"]
        sec = _rect(px, py, ax, ls, W)
        _edit_route(ref, layer, alt, piece, cut=[sec], add_alt=[sec])
        return dict(title=f"{ls:g} um of route {name} drawn on {alt} instead of {layer}", bbox=_top_bbox(ref, sec),
                    physics=("junction", dict(layer2=alt)), rule=True, params=dict(length=ls, layer=alt))
    raise ValueError(op)


def checks(comp, path, top, pdk, nets):
    """DRC and LVS of one built component. Returns (DRC rules that fire, LVS mismatch pins)."""
    comp.write_gds(str(path))
    rv.configure(path, top, pdk, nets, cache=path.parent / f"cache_{path.stem}")
    d, l = rv.drc(), rv.lvs()
    pins = sorted({p for k in ("optical", "electrical") if k in l for n in l[k]["design_only"] + l[k]["layout_only"]
                   for p in n} | {p for k in ("optical", "electrical") if k in l for p in l[k]["dangling"]})
    return sorted(d["counts"]), pins


# ---------------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ops", default=",".join(GEOMETRY_OPS))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    case = load_case(a.case)
    clean = case.build()
    info_clean = dict(getattr(case.build, "info", {}))
    clean.write_gds(str(out / "clean.gds"))
    rv.configure(out / "clean.gds", case.TOP, case.PDK, cache=out / "cache_clean")
    P = rv.pdk()
    w = rv.route_width()
    x = rv.extraction()
    assert not x["optical_dangling"], f"clean design has dangling pins: {x['optical_dangling']}"
    (out / "intent_nets.json").write_text(json.dumps({"optical": x["optical"], "electrical": x["electrical"]}, indent=0))
    base_drc = rv.drc()
    assert base_drc["clean"], f"clean design fails DRC: {base_drc['counts']}"
    (out / "DESIGN_INTENT.md").write_text(case.INTENT)
    plants = []

    # design plants: one at a time first, to find each one's footprint, then all together
    knobs = {}
    for d in case.PLANTS:
        if d["knob"] in knobs and not isinstance(d["value"], dict):
            continue                                   # one value per plain knob; dict knobs merge
        one = case.build(**{d["knob"]: d["value"]})
        info = dict(getattr(case.build, "info", {}))
        box = _diff_bbox(clean, one, P.CORE + P.ALT_CORE)
        if box is None:
            continue
        sev, loss = d["severity"], None
        if sev == "physics:fibre":
            dy = list(d["value"].values())[0]
            w0 = FIBRE_MFD[P.NAME] / 2
            loss = 4.343 * (dy / w0) ** 2
            sev = severity(loss, breaks_rule=abs(dy) > 0.5)
        elif sev == "physics:bend":
            r = list(d["value"].values())[0]
            loss = 2 * rv.bend_loss(r)["total_dB"]          # two 90 degree bends: radiation and bend-straight mismatch
            sev = severity(loss, breaks_rule=True)
        knobs[d["knob"]] = {**knobs.get(d["knob"], {}), **d["value"]} if isinstance(d["value"], dict) else d["value"]
        plants.append(dict(source="design", knob=d["knob"], value=d["value"], title=d["title"], bbox=box,
                           severity=sev, loss_dB=loss, why=d.get("why", ""), build_info=info))
    planted = case.build(**knobs)

    # geometry plants on routes that the design plants did not touch
    touched = set()
    for r_clean, r_plant in zip(clean.references, planted.references):
        if r_clean.component.name.startswith("route") and rv.fingerprint(
                {"c": _flat_core(r_clean.component, P.CORE)}) != rv.fingerprint({"c": _flat_core(r_plant.component, P.CORE)}):
            touched.add(r_clean.component.name)
    routes = [r for r in planted.references if not rv._is_device(r.component) and r.component.name not in touched]
    rng.shuffle(routes)
    pins = _pins_xy(planted)
    actions = []
    ops = a.ops.split(",")
    rng.shuffle(ops)                                   # routes can run out: no op type is always first
    for op in ops:
        for ref in list(routes):
            act = choose(op, ref, rng, P, w, pins)
            if act:
                routes.remove(ref)
                actions.append(act)
                break
    for act in actions:
        res = apply_action(planted, act, P, w)
        loss = res.get("loss")
        if "physics" in res:
            rv.configure(out / "clean.gds", case.TOP, case.PDK, cache=out / "cache_clean")
            j = rv.junction_loss(**res["physics"][1])
            loss = None if not math.isfinite(j["loss_dB"]) else 2 * j["loss_dB"]      # two joints, in and out
        plants.append(dict(source="geometry", action=act, title=res["title"], bbox=res["bbox"],
                           severity=severity(loss, res["rule"]), loss_dB=loss, params=res["params"]))
    planted.write_gds(str(out / "haystack.gds"))

    # which plants do the PDK checks flag? Each plant alone on the clean design, so every flag has one cause
    nets = out / "intent_nets.json"
    solo = out / "solo"
    solo.mkdir(exist_ok=True)
    for i, p in enumerate(plants, 1):
        p["id"] = f"P{i:02d}"
        if p["source"] == "design":
            c = case.build(**{p["knob"]: p["value"]})
        else:                                       # geometry plants sit on routes that no knob changes
            c = case.build()
            apply_action(c, p["action"], P, w)
        d1, l1 = checks(c, solo / f"{p['id']}.gds", case.TOP, case.PDK, nets)
        p["drc"], p["lvs"] = d1, l1
        flagged = bool(d1 or l1)
        p["kind"] = "harmless" if p["severity"] == "none" else ("easy" if flagged else "mistake")
    rv.configure(out / "haystack.gds", case.TOP, case.PDK, nets, cache=out / "cache_haystack")
    drc, lvs = rv.drc(), rv.lvs()
    key = dict(case=Path(a.case).name, pdk=case.PDK, seed=a.seed, top=case.TOP, route_width=w, plants=plants,
               build_info_clean=info_clean,
               baseline=dict(drc=drc["counts"], drc_source=drc["source"], lvs_clean=lvs["clean"]))
    (out / "answer_key.json").write_text(json.dumps(key, indent=1, default=float))
    for p in plants:
        print(f"{p['id']} {p['kind']:8s} {p['severity']:6s} loss={p['loss_dB'] if p['loss_dB'] is None else round(p['loss_dB'], 3)!s:7s} "
              f"DRC={','.join(p['drc']) or '-':18s} LVS={len(p['lvs']) or '-'!s:4s} {p['title']}")


if __name__ == "__main__":
    main()
