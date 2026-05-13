"""
tools/runners.py — Reusable routing runners extracted from the reproduction kit.

Exposes:
    cfg_defaults()                — config dict with sensible defaults.
    reload_modules()              — purge cached PhotonForge circuit state.
    run_manhattan(cfg, mode)      — pf.parametric.route_manhattan baseline.
    run_grid(cfg)                 — shared grid maze router (BFS / A* / Bundle / Rip-Up / Hybrid).

Each runner returns a dict with keys:
    routed, n_total, heater, rr, pp, wirelength_um, error (optional).

THE AGENT DOES NOT MODIFY THIS FILE.
"""
from __future__ import annotations

import io
import os
import sys
import contextlib


def cfg_defaults(**kw):
    """Routing-strategy config. The agent tunes the contents of design.py
    via this same dict shape (CONFIG = cfg_defaults(...) with overrides)."""
    base = dict(
        ALGORITHM="Hybrid",
        GRID_PITCH=15.0,
        TRACE_WIDTH=15.0,
        INFLATE_UM=0.0,
        MARGIN=1,
        M1_MARGIN=1,
        BLOCK_M1=True,
        BP_SPACING=120.0,
        BP_X_SHIFT=-1500.0,
        BP_Y_OFFSET=700.0,
        SPLIT="by_terminal",
        ASSIGNMENT="nearest",
        T0_APPROACH=("W", "N", "S"),
        T1_APPROACH=("E", "N", "S"),
        PAD_LAYOUT="single_row",
    )
    base.update(kw)
    return base


def reload_modules():
    """Purge cached state so each experiment starts from a fresh circuit."""
    for m in list(sys.modules):
        if m in {
            "projector_circuit_setup", "pf_routing_arena",
            "pf_maze_router", "routing_algorithms", "criteria",
        }:
            del sys.modules[m]


# -----------------------------------------------------------------------------
# Bondpad placement (verbatim from run_autoresearch.py:_place_bondpads)
# -----------------------------------------------------------------------------
def _place_bondpads(cfg, amzi_list, bp, n_src):
    """Return (top_refs, bot_refs, top_targets, bot_targets).
    Verbatim from the original run_autoresearch.py — self-contained, no
    side-effecting imports of route_amzi_bondpads."""
    import photonforge as pf
    half = n_src // 2
    if cfg["SPLIT"] == "by_terminal":
        top_pool_src = [(i, "T0") for i in range(n_src)]
        bot_pool_src = [(i, "T1") for i in range(n_src)]
    else:  # by_amzi
        top_pool_src = [(i, t) for i in range(half) for t in ("T0", "T1")]
        bot_pool_src = [(i, t) for i in range(half, n_src) for t in ("T0", "T1")]

    top_pool = [{"xy": tuple(amzi_list[i].get_terminals()[tn][0].center()),
                 "amzi_i": i, "tname": tn, "label": f"AMZI{i}.{tn}"}
                for (i, tn) in top_pool_src]
    bot_pool = [{"xy": tuple(amzi_list[i].get_terminals()[tn][0].center()),
                 "amzi_i": i, "tname": tn, "label": f"AMZI{i}.{tn}"}
                for (i, tn) in bot_pool_src]

    bp_y_top = amzi_list[0].y_max + cfg["BP_Y_OFFSET"]
    bp_y_bot = amzi_list[-1].y_min - cfg["BP_Y_OFFSET"]
    bp_x0_top = top_pool[0]["xy"][0] + cfg["BP_X_SHIFT"]
    bp_x0_bot = bot_pool[0]["xy"][0] + cfg["BP_X_SHIFT"]

    top_xs = [bp_x0_top + i * cfg["BP_SPACING"] for i in range(len(top_pool))]
    bot_xs = [bp_x0_bot + i * cfg["BP_SPACING"] for i in range(len(bot_pool))]

    if cfg["ASSIGNMENT"] == "x_sort":
        top_pool.sort(key=lambda t: t["xy"][0])
        bot_pool.sort(key=lambda t: t["xy"][0])
        top_targets = top_pool
        bot_targets = bot_pool
    else:  # "nearest" — pick nearest remaining pool entry for each bondpad x
        def _assign(pool, xs):
            rem = list(pool)
            out = []
            for px in xs:
                rem.sort(key=lambda t: (abs(t["xy"][0] - px), t["xy"][1]))
                out.append(rem.pop(0))
            return out
        top_targets = _assign(top_pool, top_xs)
        bot_targets = _assign(bot_pool, bot_xs)

    top_refs = [pf.Reference(bp, origin=(x, bp_y_top)) for x in top_xs]
    bot_refs = [pf.Reference(bp, origin=(x, bp_y_bot)) for x in bot_xs]
    return top_refs, bot_refs, top_targets, bot_targets


# -----------------------------------------------------------------------------
# Manhattan runner (verbatim with patched imports)
# -----------------------------------------------------------------------------
def run_manhattan(cfg, mode):
    """Route each pair via pf.parametric.route_manhattan.
    mode='indep': each net ignores all others.
    mode='seq':   sequential order (no obstacle awareness anyway).
    """
    import photonforge as pf
    from projector_circuit_setup import projector_circuit, amzi_list, bp, n_src
    from pf_routing_arena import add_collision_layer, show_route_violations

    top_refs, bot_refs, top_targets, bot_targets = _place_bondpads(cfg, amzi_list, bp, n_src)
    for r in top_refs + bot_refs:
        projector_circuit.add(r)

    n_routed = 0
    pairs = []
    for i, t in enumerate(top_targets):
        pairs.append(("U_" + t["label"], top_refs[i], "T0",
                      amzi_list[t["amzi_i"]], t["tname"]))
    for i, t in enumerate(bot_targets):
        pairs.append(("D_" + t["label"], bot_refs[i], "T0",
                      amzi_list[t["amzi_i"]], t["tname"]))

    from photonforge import parametric
    dir1, dir2 = ("y", "x") if mode == "indep" else ("x", "y")
    for name, bp_ref, bp_tname, amzi_ref, amzi_tname in pairs:
        try:
            t_bp = bp_ref.get_terminals()[bp_tname][0]
            t_az = amzi_ref.get_terminals()[amzi_tname][0]
            path = parametric.route_manhattan(
                terminal1=t_bp, terminal2=t_az,
                width=cfg["TRACE_WIDTH"],
                layer=(12, 0),
                direction1=dir1,
                direction2=dir2,
                technology=pf.config.default_technology,
                name=f"route_{name}",
            )
            projector_circuit.add(pf.Reference(path))
            n_routed += 1
        except Exception:
            pass

    add_collision_layer(pf.config.default_technology)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        vis, _n = show_route_violations(projector_circuit, (12, 0), (11, 0))
    log = buf.getvalue()

    import re
    m_heater = re.search(r"heater_cross\s*=\s*(\d+)", log)
    m_rr = re.search(r"route_x_route\s*=\s*(\d+)", log)
    m_pp = re.search(r"pad_x_pad\s*=\s*(\d+)", log)
    n_total = len(pairs)

    return dict(
        routed=n_routed, n_total=n_total,
        heater=int(m_heater.group(1)) if m_heater else -1,
        rr=int(m_rr.group(1)) if m_rr else -1,
        pp=int(m_pp.group(1)) if m_pp else -1,
        wirelength_um=None,
        log=log,
    )


# -----------------------------------------------------------------------------
# Grid maze runner
# -----------------------------------------------------------------------------
def run_grid(cfg):
    """Shared-grid maze router. cfg['ALGORITHM'] picks BFS / A* / Bundle / Rip-Up / Hybrid."""
    import photonforge as pf
    from projector_circuit_setup import projector_circuit, amzi_list, bp, n_src
    from pf_routing_arena import (
        PFRoutingArena, add_collision_layer, show_route_violations,
    )

    top_refs, bot_refs, top_targets, bot_targets = _place_bondpads(cfg, amzi_list, bp, n_src)
    for r in top_refs + bot_refs:
        projector_circuit.add(r)

    bbox = projector_circuit.bounds()
    x0, y0 = bbox[0]
    x1, y1 = bbox[1]
    pitch = cfg["GRID_PITCH"]
    arena = PFRoutingArena(x0=x0, y0=y0, x1=x1, y1=y1, pitch=pitch)

    arena.add_obstacles_from_layer(projector_circuit, (12, 0),
                                    inflate_um=cfg["INFLATE_UM"], margin=cfg["MARGIN"])
    if cfg.get("BLOCK_M1", True):
        arena.add_obstacles_from_layer(projector_circuit, (11, 0),
                                        inflate_um=cfg["INFLATE_UM"],
                                        margin=cfg["M1_MARGIN"])

    pairs = []
    for i, t in enumerate(top_targets):
        pairs.append(("U_" + t["label"], top_refs[i], "T0",
                      amzi_list[t["amzi_i"]], t["tname"]))
    for i, t in enumerate(bot_targets):
        pairs.append(("D_" + t["label"], bot_refs[i], "T0",
                      amzi_list[t["amzi_i"]], t["tname"]))

    for name, bp_ref, bp_tname, amzi_ref, amzi_tname in pairs:
        t_bp = bp_ref.get_terminals()[bp_tname][0]
        t_az = amzi_ref.get_terminals()[amzi_tname][0]
        arena.add_net(name, source=t_bp.origin, target=t_az.origin)

    arena.route_all(algorithm=cfg["ALGORITHM"])

    n_routed = 0
    for net in arena.nets:
        path = arena.realize_path(net, layer=(12, 0), width=cfg["TRACE_WIDTH"])
        if path is not None:
            projector_circuit.add(pf.Reference(path))
            n_routed += 1

    add_collision_layer(pf.config.default_technology)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        vis, _n = show_route_violations(projector_circuit, (12, 0), (11, 0))
    log = buf.getvalue()

    import re
    m_heater = re.search(r"heater_cross\s*=\s*(\d+)", log)
    m_rr = re.search(r"route_x_route\s*=\s*(\d+)", log)
    m_pp = re.search(r"pad_x_pad\s*=\s*(\d+)", log)
    n_total = len(pairs)

    return dict(
        routed=n_routed, n_total=n_total,
        heater=int(m_heater.group(1)) if m_heater else -1,
        rr=int(m_rr.group(1)) if m_rr else -1,
        pp=int(m_pp.group(1)) if m_pp else -1,
        wirelength_um=None,
        log=log,
    )
