"""Review tools for a pre-tape-out check of a photonic layout (GDS), for any PDK that has an adapter in pdks/.

    source tools/env.sh
    $PY -c "import review as rv, json; print(json.dumps(rv.summary(), indent=1))"

In a sandbox, the tools read chip/chip.json (the GDS, the top cell, the PDK adapter). Elsewhere, call
rv.configure(gds, top, pdk). Coordinates are um, in the frame of the top cell. Slow calls keep their results in a cache
folder; delete it to rebuild.

Groups of calls:
    layout   summary, instances, find, cell_shapes, flat, query, cross_section, centerline_length, fingerprint, render
    checks   drc, basic_drc, extraction, lvs, pin_xy, optical_net_geometry
    physics  modes, junction_loss, bend_loss, mode_fields, overlap (local Tidy3D mode solver, no cloud)
    board    post, board
"""
import functools
import hashlib
import json
import os
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import photonforge as pf                 # noqa: E402
import shapely                           # noqa: E402
from shapely.strtree import STRtree      # noqa: E402

import pdks                              # noqa: E402

_CFG = {}
_MEMO = {}


# ------------------------------------------------------------------------------------------------------- configuration
def configure(gds, top=None, pdk=None, intent_nets=None, cache=None, board=None):
    """Point the tools at a layout. `pdk` is the adapter name in pdks/ (for example 'siepic_ebeam')."""
    gds = Path(gds).resolve()
    _CFG.clear()
    _MEMO.clear()
    _CFG.update(gds=gds, top=top, pdk=pdk, intent_nets=Path(intent_nets).resolve() if intent_nets else None,
                cache=Path(cache or gds.parent / ".review_cache"), board=Path(board) if board else None)
    _CFG["cache"].mkdir(parents=True, exist_ok=True)


def _auto():
    f = TOOLS.parent / "chip" / "chip.json"
    if not f.exists():
        raise RuntimeError("no chip/chip.json next to tools/: call review.configure(gds, top, pdk) first")
    c = json.loads(f.read_text())
    d = f.parent
    configure(d / c["gds"], c.get("top"), c["pdk"], d / c["intent_nets"] if c.get("intent_nets") else None,
              TOOLS.parent / "cache", TOOLS.parent / "board")


def cfg():
    if not _CFG:
        _auto()
    return _CFG


def memo(fn):
    """Cache a result until the next configure()."""
    @functools.wraps(fn)
    def wrap(*a, **k):
        key = (fn.__name__, a, tuple(sorted(k.items())))
        if key not in _MEMO:
            _MEMO[key] = fn(*a, **k)
        return _MEMO[key]
    return wrap


def pdk():
    """The PDK adapter module (see pdks/__init__.py for what it holds)."""
    return pdks.load(cfg()["pdk"])


# -------------------------------------------------------------------------------------------------------------- layout
@memo
def tech():
    return pdk().technology()


@memo
def chip():
    """The top cell as a PhotonForge Component (hierarchy kept)."""
    lib = pf.load_layout(str(cfg()["gds"]), technology=tech())
    top = cfg()["top"]
    if top is None:
        tops = pf.find_top_level(*lib.values())
        top = tops[0].name
        cfg()["top"] = top
    return lib[top]


@memo
def layer_names():
    """{(layer, datatype): layer name} from the PDK technology."""
    return {tuple(v.layer): k for k, v in tech().layers.items()}


def _lname(layer):
    return layer_names().get(tuple(layer), str(tuple(layer)))


def _layer(name):
    return tuple(tech().layers[name].layer)


def _shp(s):
    if not hasattr(s, "vertices"):
        s = s.to_polygon()
    p = shapely.Polygon(np.asarray(s.vertices), [np.asarray(h) for h in getattr(s, "holes", []) or []])
    return p if p.is_valid else p.buffer(0)


def _cache_file(name):
    g = cfg()["gds"]
    tag = hashlib.sha1(f"{g}|{g.stat().st_mtime}|{g.stat().st_size}|{cfg()['top']}".encode()).hexdigest()[:10]
    return cfg()["cache"] / f"{name}_{tag}.pkl"


@memo
def flat():
    """{layer name: [shapely Polygon, ...]} for every shape on the chip, in the top frame."""
    chip()
    f = _cache_file("flat")
    if f.exists():
        return pickle.loads(f.read_bytes())
    out = defaultdict(list)
    for layer, shapes in chip().get_structures(depth=-1).items():
        out[_lname(layer)].extend(_shp(s) for s in shapes)
    out = dict(out)
    f.write_bytes(pickle.dumps(out))
    return out


@memo
def tree(layer):
    return STRtree(flat().get(layer, []))


def _family(name):
    base = name.split("#")[0]
    parts = base.split("_")
    while len(parts) > 1 and (parts[-1].isdigit() or len(parts[-1]) >= 6 and all(c in "0123456789abcdef" for c in parts[-1])):
        parts.pop()
    return "_".join(parts)


def summary():
    """Chip size, shape count per layer, number of top-level references, cell families."""
    (x0, y0), (x1, y1) = chip().bounds()
    fam = Counter(_family(r.component.name) for r in chip().references)
    return dict(pdk=pdk().NAME, wavelength_um=pdk().WAVELENGTH, route_spec=pdk().ROUTE_SPEC, top=cfg()["top"],
                bbox=[float(x0), float(y0), float(x1), float(y1)],
                shapes={k: len(v) for k, v in sorted(flat().items())},
                top_level_references=len(chip().references), families=dict(fam.most_common()),
                drc_deck=bool(pdk().drc_deck()), pin_layers=bool(pdk().PIN_LAYER))


def _affine(ref):
    a = np.radians(float(ref.rotation or 0.0))
    m = float(getattr(ref, "magnification", 1.0) or 1.0)
    R = m * np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    if getattr(ref, "x_reflection", False):
        R = R @ np.array([[1.0, 0.0], [0.0, -1.0]])
    return R, np.array([float(v) for v in ref.origin])


@memo
def instances():
    """Every placed cell at every level: dict(path, cell, depth, origin, angle, mirrored, bbox, device).
    `path` is 'cell#index' joined by '.', the names that the extraction and LVS use."""
    out = []

    def walk(comp, A, b, path, depth):
        for i, ref in enumerate(comp.references):
            Ar, br = _affine(ref)
            An, bn = A @ Ar, A @ br + b
            p = path + (f"{ref.component.name}#{i}",)
            (x0, y0), (x1, y1) = ref.component.bounds()
            c = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) @ An.T + bn
            dev = _is_device(ref.component)
            out.append(dict(path=".".join(p), cell=ref.component.name, depth=depth, origin=[float(bn[0]), float(bn[1])],
                            angle=round(float(np.degrees(np.arctan2(An[1, 0], An[0, 0]))), 6),
                            mirrored=bool(np.linalg.det(An) < 0), device=dev,
                            bbox=[float(c[:, 0].min()), float(c[:, 1].min()), float(c[:, 0].max()), float(c[:, 1].max())]))
            if ref.component.references and not dev:
                walk(ref.component, An, bn, p, depth + 1)

    walk(chip(), np.eye(2), np.zeros(2), (), 0)
    return out


def find(cell_prefix=None, bbox=None, devices_only=False):
    """Instances whose cell name starts with `cell_prefix` and/or whose bbox overlaps `bbox` [x0, y0, x1, y1]."""
    res = []
    for d in instances():
        if cell_prefix and not d["cell"].startswith(cell_prefix):
            continue
        if devices_only and not d["device"]:
            continue
        if bbox:
            b = d["bbox"]
            if b[2] < bbox[0] or b[0] > bbox[2] or b[3] < bbox[1] or b[1] > bbox[3]:
                continue
        res.append(d)
    return res


def _cell(name):
    def walk(c):
        for r in c.references:
            if r.component.name == name:
                return r.component
            hit = walk(r.component)
            if hit is not None:
                return hit
        return None
    c = walk(chip())
    if c is None:
        raise KeyError(name)
    return c


def cell_shapes(cell_name):
    """{layer name: [shapely Polygon]} of one cell in its own frame (its whole subtree)."""
    out = defaultdict(list)
    for layer, shapes in _cell(cell_name).get_structures(depth=-1).items():
        out[_lname(layer)].extend(_shp(s) for s in shapes)
    return dict(out)


def query(bbox, layers=None):
    """Shapes overlapping bbox [x0, y0, x1, y1]: list of dict(layer, bounds, area, n_vertices, polygon)."""
    box = shapely.box(*bbox)
    out = []
    for layer in (layers or flat().keys()):
        polys = flat().get(layer, [])
        for i in tree(layer).query(box, predicate="intersects"):
            p = polys[int(i)]
            out.append(dict(layer=layer, bounds=[round(v, 4) for v in p.bounds], area=round(p.area, 5),
                            n_vertices=len(p.exterior.coords) - 1, polygon=p))
    return out


def cross_section(x, y, direction_deg, layers=None, span=4.0):
    """Material on a cut through (x, y), across a waveguide that runs at direction_deg (0 = along +x).
    Returns {layer: [(s0, s1, width), ...]}, s along the cut from -span/2 to +span/2 (um)."""
    layers = layers or (pdk().CORE + pdk().ALT_CORE)
    a = np.radians(direction_deg + 90.0)
    d = np.array([np.cos(a), np.sin(a)])
    p0, p1 = np.array([x, y]) - d * span / 2, np.array([x, y]) + d * span / 2
    line = shapely.LineString([p0, p1])
    out = {}
    for layer in layers:
        polys = flat().get(layer, [])
        hits = [polys[int(i)] for i in tree(layer).query(line, predicate="intersects")]
        segs = []
        if hits:
            inter = shapely.union_all(hits).intersection(line)
            for g in getattr(inter, "geoms", [inter]):
                if g.is_empty or g.length == 0:
                    continue
                cs = np.array(g.coords)
                s = sorted(float(np.dot(c - p0, d)) - span / 2 for c in cs[[0, -1]])
                segs.append((round(s[0], 4), round(s[1], 4), round(s[1] - s[0], 4)))
        out[layer] = sorted(segs)
    return out


def route_width(layer=None):
    """Core width of the route waveguide (um), from the PDK route spec."""
    spec = tech().ports[pdk().ROUTE_SPEC]
    layer = layer or pdk().CORE[0]
    for w, _, lay in spec.path_profiles:
        if tuple(lay) == _layer(layer):
            return float(w)
    return float(spec.path_profiles[0][0])


def centerline_length(polygon, width=None):
    """Approximate centre-line length of a waveguide polygon of known width (area / width)."""
    return polygon.area / (width or route_width())


def fingerprint(shapes_by_layer, decimals=3):
    """A hash of geometry that ignores translation: equal shapes in different places give equal hashes."""
    allp = [p for ps in shapes_by_layer.values() for p in ps]
    if not allp:
        return "empty"
    x0 = min(p.bounds[0] for p in allp)
    y0 = min(p.bounds[1] for p in allp)
    h = hashlib.sha1()
    for layer in sorted(shapes_by_layer):
        u = shapely.affinity.translate(shapely.union_all(shapes_by_layer[layer]), -x0, -y0)
        h.update(layer.encode())
        h.update(shapely.normalize(shapely.set_precision(u, 10 ** -decimals)).wkb)
    return h.hexdigest()[:12]


_PALETTE = ["#2b6cb0", "#9f7aea", "#38a169", "#dd6b20", "#d69e2e", "#c53030", "#718096", "#319795", "#b7791f", "#4a5568"]


def render(bbox, out, layers=None, px=1400, marks=(), title=None, outline=False):
    """Draw the region bbox [x0, y0, x1, y1] to a PNG. `marks`: [(x, y, text), ...]. Returns the file path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MP
    colors = dict(pdk().COLORS)
    layers = layers or [k for k in colors if k in flat()] + [k for k in flat() if k not in colors]
    for i, k in enumerate(layers):
        colors.setdefault(k, _PALETTE[i % len(_PALETTE)])
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    fig = plt.figure(figsize=(px / 100, max(2.0, px / 100 * h / max(w, 1e-9))), dpi=100)
    ax = fig.add_axes([0.06, 0.06, 0.92, 0.88])
    box = shapely.box(*bbox)
    for layer in layers:
        polys = flat().get(layer, [])
        for i in tree(layer).query(box, predicate="intersects"):
            p = polys[int(i)].intersection(box)
            for g in getattr(p, "geoms", [p]):
                if g.is_empty or g.geom_type != "Polygon":
                    continue
                ax.add_patch(MP(np.array(g.exterior.coords), closed=True, fc="none" if outline else colors[layer],
                                ec=colors[layer], lw=0.6 if outline else 0.2, alpha=0.75))
    for (mx, my, txt) in marks:
        ax.plot([mx], [my], "x", color="red", ms=10, mew=2)
        ax.annotate(txt, (mx, my), color="red", fontsize=9, xytext=(5, 5), textcoords="offset points")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(title or f"{[round(v, 3) for v in bbox]}  layers {', '.join(layers)}", fontsize=9)
    ax.grid(alpha=0.2)
    fig.savefig(out)
    plt.close(fig)
    return str(out)


# --------------------------------------------------------------------------------------------------------------- checks
def _marker_bbox(m):
    pts = []
    for attr in ("hull", "points", "edge", "edge_pair", "box", "p1", "p2", "polygon"):
        v = getattr(m, attr, None)
        if v is None:
            continue
        a = np.asarray(v, dtype=float).reshape(-1)
        pts += list(a)
    if len(pts) < 2:
        return None
    p = np.array(pts[: len(pts) // 2 * 2]).reshape(-1, 2)
    return [float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())]


@memo
def drc():
    """The PDK's DRC deck (KLayout) when the adapter has one, else basic_drc(). dict(source, counts, markers)."""
    deck = pdk().drc_deck()
    if not deck:
        r = basic_drc()
        r["note"] = "the PDK has no DRC deck here; this is the basic width and space check from the adapter"
        return r
    res = pf.drc_check(str(cfg()["gds"]), deck, engine="klayout", show_progress=False,
                       results_file=str(cfg()["cache"] / "drc.lyrdb"))
    markers = []
    for cell, viols in res.violations_by_cell.items():
        for v in viols:
            for m in v.markers:
                try:
                    m = res.in_top_cell(m)
                except Exception:
                    pass
                b = _marker_bbox(m)
                if b:
                    markers.append(dict(rule=v.category, bbox=b))
    counts = {k: n for k, n in res.violation_counts.items() if n}
    return dict(source=f"PDK deck {Path(deck).name}", clean=bool(res.is_clean), counts=counts, markers=markers)


def basic_drc(rules=None):
    """Minimum width and space on the layers in the adapter's BASIC_RULES (or `rules`). dict(source, counts, markers)."""
    rules = rules or pdk().BASIC_RULES
    eps = 1e-4
    markers = []
    for layer, r in rules.items():
        u = shapely.union_all(flat().get(layer, [])) if flat().get(layer) else None
        polys = [g for g in getattr(u, "geoms", [u]) if g is not None and not g.is_empty and g.area > 0]
        w, s = r.get("width", 0.0), r.get("space", 0.0)
        for p in polys:
            if w:
                thin = p.difference(p.buffer(-w / 2 + eps, join_style=2).buffer(w / 2 - eps, join_style=2))
                for g in getattr(thin, "geoms", [thin]):
                    if not g.is_empty and g.area > (w * eps * 10):
                        markers.append(dict(rule=f"{layer}.width<{w}", bbox=list(g.bounds)))
            if s:
                notch = p.buffer(s / 2 - eps, join_style=2).buffer(-(s / 2 - eps), join_style=2).difference(p)
                for g in getattr(notch, "geoms", [notch]):
                    if not g.is_empty and g.area > (s * eps * 10):
                        markers.append(dict(rule=f"{layer}.space<{s}", bbox=list(g.bounds)))
        if s and len(polys) > 1:
            grown = [p.buffer(s / 2 - eps, join_style=2) for p in polys]
            t = STRtree(grown)
            for i, g in enumerate(grown):
                for j in t.query(g, predicate="intersects"):
                    if int(j) > i:
                        markers.append(dict(rule=f"{layer}.space<{s}", bbox=list(g.intersection(grown[int(j)]).bounds)))
    counts = Counter(m["rule"] for m in markers)
    return dict(source="basic width/space check", clean=not markers, counts=dict(counts), markers=markers)


def _key(point):
    return (round(float(point[0]), 3), round(float(point[1]), 3))


def _is_device(comp):
    P = pdk()
    if P.DEVICE_LAYER:          # the marker layer on the cell's own level (a wrapper of devices has none)
        return _layer(P.DEVICE_LAYER) in {tuple(k) for k in comp.structures}
    return P.is_device(comp.name)


@memo
def devices():
    """[(path, A, b, component)] for every placed device, with the full transform to the top frame."""
    out = []

    def walk(comp, A, b, path):
        for i, ref in enumerate(comp.references):
            Ar, br = _affine(ref)
            An, bn = A @ Ar, A @ br + b
            p = path + (f"{ref.component.name}#{i}",)
            if _is_device(ref.component):
                out.append((p, An, bn, ref.component))
            elif ref.component.references:
                walk(ref.component, An, bn, p)

    walk(chip(), np.eye(2), np.zeros(2), ())
    return out


_DETECTED = {}


def _cell_pins(comp, kind):
    """[(name, (x, y) in the cell frame, size)] for one device cell."""
    P = pdk()
    layer = P.PIN_LAYER if kind == "optical" else P.PIN_LAYER_E
    if layer:
        labels = defaultdict(list)
        for group in comp.labels.values() if isinstance(comp.labels, dict) else [comp.labels]:
            for lab in group:
                labels[_key(lab.origin)].append(lab.text)
        markers = defaultdict(list)
        own = {tuple(k): v for k, v in comp.structures.items()}
        for m in own.get(_layer(layer)) or comp.get_structures().get(_layer(layer), []):
            (bx0, by0), (bx1, by1) = m.bounds()
            markers[_key(((bx0 + bx1) / 2, (by0 + by1) / 2))].append(max(bx1 - bx0, by1 - by0))
        found = []
        for point, sizes in markers.items():
            names = sorted(labels.get(point, []))
            for k, size in enumerate(sizes):
                found.append((names[k] if k < len(names) else (names[0] if names else f"pin{len(found)}"), point, size))
        return found
    if kind != "optical":
        return []
    if comp.name not in _DETECTED:
        spec = tech().ports[P.ROUTE_SPEC]
        ports = comp.detect_ports([P.ROUTE_SPEC], on_boundary="xy", boundary_margin=0.05)
        ports = sorted(ports, key=lambda q: (round(float(q.input_direction) % 360), round(float(q.center[1]), 3),
                                             round(float(q.center[0]), 3)))
        _DETECTED[comp.name] = [(f"P{k}", _key(q.center), route_width()) for k, q in enumerate(ports)]
        del spec
    return _DETECTED[comp.name]


@memo
def pins(kind="optical"):
    """[(device.pin, (x, y), size)] in the top frame."""
    found = []
    for path, A, b, comp in devices():
        prefix = ".".join(path)
        for name, point, size in _cell_pins(comp, kind):
            c = A @ np.array(point, dtype=float) + b
            found.append((f"{prefix}.{name}", (float(c[0]), float(c[1])), float(size)))
    return found


class _Union:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _named(nets):
    return {f"N{i}": sorted(m) for i, m in enumerate(sorted((sorted(v) for v in nets.values())))}


@memo
def _device_boxes():
    P = pdk()
    if P.DEVICE_LAYER:
        return flat().get(P.DEVICE_LAYER, [])
    boxes = []
    for path, A, b, comp in devices():
        (x0, y0), (x1, y1) = comp.bounds()
        c = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) @ A.T + b
        boxes.append(shapely.Polygon(c))
    return boxes


@memo
def _route_pieces():
    """Optical layer shapes with the device areas removed: [(polygon, layer)], and their spatial index."""
    dv = _device_boxes()
    dtree = STRtree(dv)
    pieces = []
    for layer in getattr(pdk(), "CONNECT", pdk().CORE + pdk().ALT_CORE):
        for poly in flat().get(layer, []):
            hit = dtree.query(poly, predicate="intersects")
            rest = poly.difference(shapely.union_all([dv[int(i)] for i in hit])) if len(hit) else poly
            pieces += [(g, layer) for g in getattr(rest, "geoms", [rest]) if g.area > 1e-6]
    return pieces, STRtree([g for g, _ in pieces])


def _extract_optical():
    pieces, ptree = _route_pieces()
    u = _Union()
    for i, (g, _) in enumerate(pieces):
        u.find(("W", i))
        for j in ptree.query(g.buffer(1e-3), predicate="intersects"):
            if int(j) != i:
                u.union(("W", i), ("W", int(j)))
    found = pins("optical")
    at = defaultdict(list)
    for k, (name, point, size) in enumerate(found):
        u.find(("P", k))
        at[_key(point)].append(k)
        h = max(size, route_width()) / 2
        hits = ptree.query(shapely.box(point[0] - h, point[1] - h, point[0] + h, point[1] + h), predicate="intersects")
        if len(hits):
            u.union(("P", k), ("W", int(hits[0])))
    for group in at.values():
        for other in group[1:]:
            u.union(("P", group[0]), ("P", other))
    nets, dangling = defaultdict(list), []
    for k, (name, point, size) in enumerate(found):
        root = u.find(("P", k))
        if root == ("P", k) and len(at[_key(point)]) == 1:
            dangling.append(name)
        else:
            nets[root].append(name)
    return _named(nets), sorted(dangling)


def _extract_electrical():
    E = getattr(pdk(), "ELECTRICAL", None) or {}
    found = pins("electrical")
    if not E.get("conductors") or not found:
        return {}, []
    pieces = []
    for layer in E["conductors"]:
        polys = flat().get(layer, [])
        if polys:
            u = shapely.union_all(polys)
            pieces += [(g, layer) for g in getattr(u, "geoms", [u])]
    if not pieces:
        return {}, [n for n, _, _ in found]
    ptree = STRtree([g for g, _ in pieces])
    un = _Union()
    for i in range(len(pieces)):
        un.find(i)
    for via, lower, upper in E.get("vias", []):
        for v in flat().get(via, []):
            hits = [int(j) for j in ptree.query(v, predicate="intersects")]
            lo = [j for j in hits if pieces[j][1] in lower]
            hi = [j for j in hits if pieces[j][1] in upper]
            for a in lo:
                for b in hi:
                    un.union(a, b)
    nets, dangling = defaultdict(list), []
    for name, point, size in found:
        hits = [int(j) for j in ptree.query(shapely.Point(point), predicate="intersects")]
        (nets[un.find(hits[0])] if hits else dangling).append(name)
    return _named(nets), sorted(dangling)


def extraction():
    """Optical and electrical nets extracted from the layout, as device.pin names, and the position of every pin."""
    f = _cache_file("extraction")
    if "extraction" in _MEMO:
        return _MEMO["extraction"]
    if f.exists():
        _MEMO["extraction"] = pickle.loads(f.read_bytes())
        return _MEMO["extraction"]
    o, od = _extract_optical()
    e, ed = _extract_electrical()
    pos = {n: p for n, p, s in pins("optical") + pins("electrical")}
    out = dict(optical=o, optical_dangling=od, electrical=e, electrical_dangling=ed, pin_xy=pos,
               devices=[".".join(p) for p, _, _, _ in devices()])
    f.write_bytes(pickle.dumps(out))
    _MEMO["extraction"] = out
    return out


def compare(intent, layout):
    """Compare two {net: [pins]} dictionaries by their partitions (net names are not compared, one-pin nets ignored)."""
    a = {frozenset(v) for v in intent.values() if len(v) > 1}
    b = {frozenset(v) for v in layout.values() if len(v) > 1}
    return dict(matched=len(a & b), design_only=sorted(sorted(s) for s in a - b), layout_only=sorted(sorted(s) for s in b - a))


def lvs():
    """Compare the extracted nets with the intended netlist (chip/intent_nets.json)."""
    path = cfg()["intent_nets"]
    if not path or not Path(path).exists():
        raise RuntimeError("no intended netlist configured")
    intent = json.loads(Path(path).read_text())
    x = extraction()
    out = {}
    for kind in ("optical", "electrical"):
        if kind not in intent:
            continue
        r = compare(intent[kind], x[kind])
        r["dangling"] = x[f"{kind}_dangling"]
        out[kind] = r
    out["clean"] = all(not v["design_only"] and not v["layout_only"] and not v["dangling"] for v in out.values())
    return out


def pin_xy(pin):
    return extraction()["pin_xy"].get(pin)


def optical_net_geometry():
    """For every extracted optical net: its pins, the routing shapes that join them (device areas removed), the
    approximate centre-line length (area / route width), the layers used and the bbox. {net: dict}."""
    pieces, ptree = _route_pieces()
    u = _Union()
    for i, (g, _) in enumerate(pieces):
        u.find(i)
        for j in ptree.query(g.buffer(1e-3), predicate="intersects"):
            if int(j) != i:
                u.union(i, int(j))
    groups = defaultdict(list)
    for i in range(len(pieces)):
        groups[u.find(i)].append(i)
    x = extraction()
    w = route_width()
    out = {}
    for net, members in x["optical"].items():
        pts = [x["pin_xy"][m] for m in members]
        h = w / 2
        hits = ptree.query(shapely.box(pts[0][0] - h, pts[0][1] - h, pts[0][0] + h, pts[0][1] + h), predicate="intersects")
        if not len(hits):
            out[net] = dict(pins=members, xy=pts, length_um=0.0, layers={}, n_pieces=0)
            continue
        g = groups[u.find(int(hits[0]))]
        area = defaultdict(float)
        for i in g:
            area[pieces[i][1]] += pieces[i][0].area
        un = shapely.union_all([pieces[i][0] for i in g])
        out[net] = dict(pins=members, xy=pts, length_um=round(area.get(pdk().CORE[0], 0.0) / w, 3),
                        layers={k: round(v, 4) for k, v in area.items()}, n_pieces=len(g),
                        bbox=[round(v, 3) for v in un.bounds])
    return out


# -------------------------------------------------------------------------------------------------------------- physics
def _spec(name=None, core_width=None, layer=None):
    """The PDK route spec (or `name`), with the core width or the core layer changed if asked."""
    s = tech().ports[name or pdk().ROUTE_SPEC].copy()
    core = {_layer(n) for n in pdk().CORE}
    prof = []
    w0 = None
    for w, off, lay in s.path_profiles:
        if tuple(lay) in core:
            if core_width is not None:
                w0, w = w, core_width
            if layer is not None:
                lay = _layer(layer)
        prof.append((w, off, lay))
    s.path_profiles = prof
    if w0 is not None and core_width > w0:
        s.width = s.width + (core_width - w0)
    return s


class _Solved:
    """A solved mode set: .data (Tidy3D ModeSolverData) and .plane."""

    def __init__(self, data, plane):
        self.data, self.plane = data, plane


def _solve(spec, num_modes=2, bend_radius=None, wavelength=None):
    """Mode solve on this computer (PhotonForge port mode solver). A bend uses a 10 nm grid, a mode plane that stays
    inside the radius and absorbing layers at the plane edges, as radiation loss needs."""
    pf.config.use_local_mode_solver = True
    spec.num_modes = num_modes
    f0 = pf.C_0 / (wavelength or pdk().WAVELENGTH)
    ms = pf.port_modes(spec, [f0], group_index=not bend_radius, technology=tech(), show_progress=False, verbose=False)
    if not bend_radius:
        return _Solved(ms.data, ms.plane)
    import tidy3d as td
    from tidy3d.plugins.mode import ModeSolver
    sim, plane = ms.simulation, ms.plane
    normal = int(np.argmin(plane.size))
    tang = [i for i in range(3) if i != normal]
    lat = tang[0] if tang[0] != 2 else tang[1]                       # the in-chip axis across the waveguide
    ly = min(float(plane.size[lat]) + 2.0, 1.8 * float(bend_radius))
    psize, ssize = list(plane.size), list(sim.size)
    psize[lat] = ly
    ssize[lat] = max(ssize[lat], ly + 0.2)
    sim2 = sim.updated_copy(size=ssize, grid_spec=td.GridSpec.uniform(dl=0.01),
                            boundary_spec=td.BoundarySpec.all_sides(td.PML()))
    ref = float(np.max(ms.data.n_eff.values))
    spec2 = td.ModeSpec(num_modes=num_modes, target_neff=ref, precision="double", bend_radius=float(bend_radius),
                        bend_axis=tang.index(2) if 2 in tang else 1, num_pml=(12, 12))
    pl = plane.updated_copy(size=psize)
    return _Solved(ModeSolver(simulation=sim2, plane=pl, mode_spec=spec2, freqs=[f0]).solve(), pl)


def _te_mode(solved):
    """Index of the fundamental TE-like guided mode (largest n_eff among modes with TE fraction > 0.5), or None."""
    d = solved.data
    te = d.pol_fraction.te.isel(f=0).values
    ne = d.n_eff.isel(f=0).values
    idx = [int(i) for i in range(len(ne)) if te[i] > 0.5 and ne[i] > 1.0]
    return max(idx, key=lambda i: ne[i]) if idx else None


def modes(width=None, bend_radius=None, num_modes=2, spec=None, wavelength=None):
    """Local mode solve of the route waveguide (the PDK cross-section), with another core width or a bend if asked.
    Returns [dict(mode, n_eff, k_eff, n_g, loss_dB_per_cm, te_fraction)]. A bend gives radiation loss only; values
    within about +-1 dB/cm of zero are solver noise."""
    n = max(num_modes, 4) if bend_radius else num_modes
    ms = _solve(_spec(spec, width), n, bend_radius, wavelength)
    d = ms.data
    wl = wavelength or pdk().WAVELENGTH
    order = list(range(n))
    if bend_radius:              # a tight bend can return absorber or radiation modes first: rank by power in the core
        core = _core_fraction(ms, (width or route_width()) / 2 + 0.3)
        te = d.pol_fraction.te.isel(f=0).values
        order = sorted(order, key=lambda m: (-float(te[m] > 0.5), -core[m]))
    res = []
    for m in order[:num_modes]:
        k = float(d.k_eff.isel(f=0, mode_index=m).values)
        ng = d.n_group.isel(f=0, mode_index=m).values if d.n_group is not None else np.nan
        res.append(dict(mode=m, n_eff=float(d.n_eff.isel(f=0, mode_index=m).values), k_eff=k, n_g=float(ng),
                        loss_dB_per_cm=float(4 * np.pi * k / (wl * 1e-4) * 10 * np.log10(np.e)),
                        te_fraction=float(d.pol_fraction.te.isel(f=0, mode_index=m).values)))
    return res


def _core_fraction(ms, half):
    """For each mode: the fraction of |E|^2 within +-half um of the waveguide axis, across the chip plane."""
    d = ms.data
    normal = int(np.argmin(ms.plane.size))
    tang = [i for i in range(3) if i != normal]
    lat = "xyz"[tang[0] if tang[0] != 2 else tang[1]]
    c0 = float(ms.plane.center["xyz".index(lat)])
    out = []
    for m in range(d.n_eff.sizes["mode_index"]):
        e = sum(abs(d.field_components[c].isel(f=0, mode_index=m)) ** 2 for c in ("Ex", "Ey", "Ez")).squeeze(drop=True)
        coord = e.coords[lat].values
        inside = float(e.sel({lat: coord[np.abs(coord - c0) <= half]}).sum())
        out.append(inside / max(float(e.sum()), 1e-30))
    return out


def _fields(ms, mode):
    d = ms.data
    normal = int(np.argmin(ms.plane.size))
    ax = "xyz"
    a, b = [ax[i] for i in range(3) if i != normal]
    f = {c: d.field_components[c].isel(f=0, mode_index=mode).squeeze(drop=True) for c in
         (f"E{a}", f"E{b}", f"H{a}", f"H{b}")}
    return f, a, b


def _overlap(s1, m1, s2, m2, offset=0.0):
    """Power transmission from mode m1 of solve s1 into mode m2 of solve s2 (moved sideways by offset), E x H overlap."""
    (f1, a, b), (f2, _, _) = _fields(s1, m1), _fields(s2, m2)
    lat = a if a != "z" else b
    c1, c2 = f1[f"E{a}"].coords, f2[f"E{a}"].coords
    ga = np.arange(max(float(c1[a].min()), float(c2[a].min()) + (offset if lat == a else 0)),
                   min(float(c1[a].max()), float(c2[a].max()) + (offset if lat == a else 0)), 0.005)
    gb = np.arange(max(float(c1[b].min()), float(c2[b].min()) + (offset if lat == b else 0)),
                   min(float(c1[b].max()), float(c2[b].max()) + (offset if lat == b else 0)), 0.005)

    def on(f, shift):
        sa = ga - (shift if lat == a else 0.0)
        sb = gb - (shift if lat == b else 0.0)
        return {k: np.nan_to_num(v.interp({a: sa, b: sb}).values) for k, v in f.items()}
    g1, g2 = on(f1, 0.0), on(f2, offset)

    def cross(e, h):
        return np.sum(e[f"E{a}"] * np.conj(h[f"H{b}"]) - e[f"E{b}"] * np.conj(h[f"H{a}"]))
    t = abs(cross(g1, g2) * cross(g2, g1)) / (abs(np.real(cross(g1, g1))) * abs(np.real(cross(g2, g2))))
    return float(min(t, 1.0))


def junction_loss(width1=None, width2=None, offset=0.0, spec1=None, spec2=None, wavelength=None, layer2=None):
    """Loss (dB) where waveguide 1 meets waveguide 2 end to end, with waveguide 2 moved sideways by `offset` (um),
    from the overlap of the two fundamental TE modes (E x H over the cross-section). An estimate: no reflection.
    `layer2` draws waveguide 2 on another layer (for example a partial-etch layer instead of the core)."""
    sols = [_solve(_spec(spec1, width1), 3, None, wavelength), _solve(_spec(spec2, width2, layer2), 3, None, wavelength)]
    m1, m2 = _te_mode(sols[0]), _te_mode(sols[1])
    if m1 is None or m2 is None:
        w = width1 if m1 is None else width2
        return dict(transmission=0.0, loss_dB=float("inf"), note=f"no guided TE mode at core width {w} um")
    t = _overlap(sols[0], m1, sols[1], m2, offset)
    return dict(transmission=t, loss_dB=float(-10 * np.log10(max(t, 1e-12))))


def mode_fields(width=None, bend_radius=None, layer=None, num_modes=3, spec=None, wavelength=None):
    """The solved modes of the route cross-section (another core width, a bend or another layer if asked), for your own
    overlap calculations. Returns dict(solved, te_mode, n_eff): `solved.data` is the Tidy3D mode data and `te_mode` the
    index of the fundamental TE mode (in a bend: the TE mode with the most power in the core). Give two of them to
    overlap()."""
    n = max(num_modes, 4) if bend_radius else num_modes
    sol = _solve(_spec(spec, width, layer), n, bend_radius, wavelength)
    if bend_radius:
        core = _core_fraction(sol, (width or route_width()) / 2 + 0.3)
        te = sol.data.pol_fraction.te.isel(f=0).values
        m = max(range(n), key=lambda i: (te[i] > 0.5, core[i]))
    else:
        m = _te_mode(sol)
    return dict(solved=sol, te_mode=m, n_eff=[float(v) for v in sol.data.n_eff.isel(f=0).values])


def overlap(a, b, offset=0.0):
    """Fraction of the power in the TE mode of `a` that couples into the TE mode of `b`, with `b` moved sideways by
    `offset` um (a and b from mode_fields())."""
    return _overlap(a["solved"], a["te_mode"], b["solved"], b["te_mode"], offset)


def bend_loss(radius, angle_deg=90.0, width=None, spec=None, wavelength=None):
    """Loss (dB) of one circular bend of the route waveguide: radiation along the arc, plus the mode mismatch where the
    bend meets a straight at each end (the larger part for strongly guiding waveguides). Local mode solves, an estimate."""
    st = _solve(_spec(spec, width), 3, None, wavelength)
    bd = _solve(_spec(spec, width), 4, radius, wavelength)
    ms = _te_mode(st)
    core = _core_fraction(bd, (width or route_width()) / 2 + 0.3)
    te = bd.data.pol_fraction.te.isel(f=0).values
    mb = max(range(len(core)), key=lambda m: (te[m] > 0.5, core[m]))
    t = _overlap(st, ms, bd, mb)
    k = float(bd.data.k_eff.isel(f=0, mode_index=mb).values)
    wl = wavelength or pdk().WAVELENGTH
    rad = max(4 * np.pi * k / (wl * 1e-4) * 10 * np.log10(np.e), 0.0) * radius * np.radians(angle_deg) * 1e-4
    tr = float(-10 * np.log10(max(t, 1e-12)))
    return dict(radiation_dB=float(rad), transition_dB_each=tr, total_dB=float(rad + 2 * tr))


# ---------------------------------------------------------------------------------------------------------------- board
FIELDS = ("reviewer", "id", "title", "category", "bbox", "evidence", "severity", "confidence", "drc_or_lvs_flags_it",
          "impact", "fix")


def post(**finding):
    """Add one finding to board/<reviewer>.jsonl. Required: reviewer, id, title, bbox [x0, y0, x1, y1], evidence,
    severity (high|medium|low|none). Use confirms=<id> or disputes=<id> to review another finding."""
    missing = [k for k in ("reviewer", "id", "title", "bbox", "evidence", "severity") if k not in finding]
    if missing:
        raise ValueError(f"missing fields: {missing}")
    if finding["severity"] not in ("high", "medium", "low", "none"):
        raise ValueError("severity must be high, medium, low or none")
    import datetime
    finding.setdefault("time", datetime.datetime.now(datetime.timezone.utc).isoformat())
    d = cfg()["board"] or TOOLS.parent / "board"
    d.mkdir(exist_ok=True)
    with open(d / f"{finding['reviewer']}.jsonl", "a") as fh:
        fh.write(json.dumps(finding) + "\n")
    return finding["id"]


def board():
    """Every finding on the board, oldest first."""
    d = cfg()["board"] or TOOLS.parent / "board"
    out = []
    for f in sorted(d.glob("*.jsonl")):
        for line in open(f):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return sorted(out, key=lambda x: x.get("time", ""))


if __name__ == "__main__":
    print(json.dumps(summary(), indent=1))
    os._exit(0)
