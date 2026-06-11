"""
Reduced-order, hierarchical representation of the chip for the AI to reason about.

The agent should NOT read raw GDS or thousands of polygons. It reads this compact summary: a
hierarchy (chip -> placed test structures -> key attributes), a per-layer histogram (counts +
area, not geometry), per-structure connectivity from get_netlist (so disconnects/dangling ports
are visible), and the validation verdict. This is the "what am I building" view that fits in a
prompt and still captures placement, connectivity, scale, and cleanliness.
"""
import photonforge as pf

from . import validation as V


def _bbox(obj):
    (x0, y0), (x1, y1) = obj.bounds()
    return {"w": round(float(x1 - x0), 1), "h": round(float(y1 - y0), 1),
            "x": round(float(x0), 1), "y": round(float(y0), 1)}


def _layer_name(tech, gds):
    for name, spec in tech.layers.items():
        if spec.layer == gds:
            return name
    return str(gds)


def layer_histogram(chip):
    """Per-layer polygon count + total area (um^2). Compact stand-in for the geometry."""
    tech = pf.config.default_technology
    structs = chip.get_structures(depth=-1)
    hist = {}
    items = structs.items() if isinstance(structs, dict) else []
    for gds, polys in items:
        if not polys:
            continue
        name = _layer_name(tech, gds) if not isinstance(gds, str) else gds
        area = sum(abs(p.area()) for p in polys)
        hist[name] = {"polys": len(polys), "area_um2": round(area, 1)}
    return hist


def _dangling_ports(comp):
    """Optical ports of internal instances not consumed by a connection (unrouted)."""
    nl = comp.get_netlist()
    instances = nl.get("instances", [])
    used = set()
    for (a, b) in nl.get("connections", []) + nl.get("virtual connections", []):
        used.add((a[0], a[1]))
        used.add((b[0], b[1]))
    dangling = 0
    exposed = {(ip[0], ip[1]) for ip in nl.get("ports", {})}
    for i, ref in enumerate(instances):
        for p in ref.component.ports:
            key = (i, p)
            if key not in used and key not in exposed:
                dangling += 1
    return dangling, len(nl.get("connections", []))


def route_lengths(structure):
    """Physical length (um) of each optical route in a structure, via native pf.route_length."""
    out = {}
    for r in structure.references:
        nm = r.component.name
        if nm.startswith("route") and not nm.startswith("route_manhattan"):
            try:
                out[nm] = round(pf.route_length(r.component), 1)
            except Exception:  # noqa: BLE001
                pass
    return out


def structure_summary(ref, dut_type=None):
    comp = ref.component
    try:
        dangling, n_conn = _dangling_ports(comp)
    except Exception:  # noqa: BLE001 - never let the summary crash the loop
        dangling, n_conn = -1, -1
    bondpads = sum(1 for r in comp.references
                   if r.component.name.startswith("BondPad"))
    rl = route_lengths(comp)
    route_um = round(sum(rl.values()), 1)
    return {
        "name": comp.name,
        "type": dut_type or comp.name.split("_")[0],
        "bbox": _bbox(ref),
        "fiber_ports": len(comp.ports),
        "bondpads": bondpads,
        "connections": n_conn,
        "dangling_ports": dangling,
        "route_um": route_um,            # total physical waveguide route length (pf.route_length)
        "n_routes": len(rl),
        "wg_overlap_um2": round(V.overlap_area(comp, V.WG), 3),
        "routed": (dangling == 0),
    }


def localize_drc(chip, lyrdb_path):
    """Map each KLayout DRC marker to the structure that contains it: {rule: {structure: count}}.

    Turns 'Si_space=4 somewhere on the chip' into 'Si_space x4 in dcoupler_coupling_gap0.30'.
    """
    from . import violations
    markers = violations.parse_drc_markers(lyrdb_path)
    boxes = [(r.component.name, r.bounds()) for r in chip.references]
    out = {}
    for rule, marks in markers.items():
        for (mx0, my0, mx1, my1) in marks:
            cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2
            owner = "<top-level>"
            for nm, ((ax0, ay0), (ax1, ay1)) in boxes:
                if ax0 <= cx <= ax1 and ay0 <= cy <= ay1:
                    owner = nm
                    break
            out.setdefault(rule, {}).setdefault(owner, 0)
            out[rule][owner] += 1
    return out


def chip_summary(chip, *, metrics=None, meta=None, collisions=None, drc=None, area_tier=None):
    """Full reduced-order representation as a JSON-able dict."""
    type_by_name = {}
    if meta:
        for m in meta:
            type_by_name[m["tag"]] = m.get("factory")
    structures = [structure_summary(r, type_by_name.get(r.component.name)) for r in chip.references]
    summary = {
        "die": {
            "w_um": metrics["die_w_um"] if metrics else None,
            "h_um": metrics["die_h_um"] if metrics else None,
            "area_mm2": round(metrics["die_area_mm2"], 2) if metrics else None,
            "fill_pct": round(metrics["fill_fraction"] * 100, 1) if metrics else None,
            "free_right_mm2": metrics.get("free_right_mm2") if metrics else None,
            "free_top_mm2": metrics.get("free_top_mm2") if metrics else None,
        },
        "counts": {
            "structures_placed": len(structures),
            "structures_total": metrics["n_total"] if metrics else len(structures),
            "spilled": metrics["n_spilled"] if metrics else 0,
            "fiber_ports": sum(s["fiber_ports"] for s in structures),
            "bondpads": sum(s["bondpads"] for s in structures),
            "unrouted_structures": sum(1 for s in structures if not s["routed"]),
        },
        "layers": layer_histogram(chip),
        "structures": structures,
    }
    if area_tier:
        summary["area_tier_mm2"] = area_tier
    if collisions is not None:
        summary["collisions"] = {
            "clean": collisions.clean,
            "inter_structure_um2": collisions.inter_structure_um2,
            "wg_crossing_um2": collisions.wg_crossing_um2,
            "wg_crossing_by_structure": collisions.wg_crossing_by_structure,
            "m2_over_m1_um2": collisions.m2_over_m1_um2,
        }
    if drc is not None:
        summary["drc"] = {
            "available": drc.available, "passes_hard": drc.passes,
            "violations": drc.counts, "warnings": drc.warnings,
        }
    return summary


def render_text(summary):
    """Compact human/AI-readable rendering of the reduced-order summary."""
    d, c = summary["die"], summary["counts"]
    free = ""
    if d.get("free_right_mm2") is not None:
        free = f"  free: right {d['free_right_mm2']}mm2 / top {d['free_top_mm2']}mm2 (room to pack more)"
    lines = [
        f"CHIP  die {d['w_um']}x{d['h_um']} um ({d['area_mm2']} mm2)  fill {d['fill_pct']}%{free}",
        f"      placed {c['structures_placed']}/{c['structures_total']} "
        f"(spilled {c['spilled']}, unrouted {c['unrouted_structures']})  "
        f"fiber_ports {c['fiber_ports']}  bondpads {c['bondpads']}",
    ]
    if "area_tier_mm2" in summary:
        lines.append(f"      MPW area tier {summary['area_tier_mm2']} mm2")
    lines.append("LAYERS  " + "  ".join(
        f"{n}:{v['polys']}p/{v['area_um2']:.0f}um2" for n, v in summary["layers"].items()))
    if "collisions" in summary:
        cc = summary["collisions"]
        lines.append(f"COLLISIONS {'clean' if cc['clean'] else 'DIRTY'}  "
                     f"inter={cc['inter_structure_um2']} wg_cross={cc['wg_crossing_um2']} "
                     f"m2/m1={cc['m2_over_m1_um2']}")
    if "drc" in summary:
        dd = summary["drc"]
        if dd["available"]:
            lines.append(f"DRC {'PASS' if dd['passes_hard'] else 'FAIL'}  "
                         f"violations={dd['violations'] or 'none'}  warnings={dd['warnings'] or 'none'}")
        else:
            lines.append("DRC skipped (KLayout not found)")
    lines.append("STRUCTURES (hierarchy):")
    for s in summary["structures"]:
        b = s["bbox"]
        flags = []
        if not s["routed"]:
            flags.append(f"DANGLING:{s['dangling_ports']}")
        if s["wg_overlap_um2"] >= 0.05:
            flags.append(f"WGCROSS:{s['wg_overlap_um2']}")
        lines.append(f"  - {s['name']:26s} {b['w']:6.0f}x{b['h']:5.0f}um  "
                     f"io={s['fiber_ports']} pads={s['bondpads']} conn={s['connections']} "
                     f"route={s.get('route_um', 0):.0f}um "
                     + (" ".join(flags)))
    return "\n".join(lines)
