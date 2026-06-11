"""
plan.py  ──  Phase 0: the DoE planner. Look at the device library, decide the experiment.

This runs BEFORE the packing loop. It inspects every `DeviceSource` in `tools/library.py`
(PCells AND user GDS files), and for each decides:
  - WHICH parameter(s) to sweep (a device may get more than one experiment),
  - over WHAT range and how many points (domain-informed, in `SWEEP_KB`),
  - and how many REPLICATES to seed (uniformity sampling, esp. for the replicate-only GDS device).
It measures the REAL packed footprint of one site per experiment, estimates how the base DoE
fits the fixed 8x3 mm die, and reports the replicate multiplier the loop will need to fill it.

Output (the contract with the loop):
  - `blackboard/doe_plan.json`  — the machine-readable plan `optimize.py` reads.
  - `blackboard/doe_plan.md`    — the human rationale (what each sweep measures and why).
  - stdout                      — device catalog + proposed DoE + fit estimate.

It is rule-based + introspective so it is reproducible and explains itself; a human (or an agent)
can edit `SWEEP_KB` / the die and re-run. Usage:  python plan.py
"""
import sys
import json
import pathlib
import warnings

warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

from tools import library, test_structures, floorplan
from tools import criteria

# Fixed die for this campaign (~8 mm x 3 mm = 24 mm^2, within the 25 mm^2 MPW area tier).
DIE_W, DIE_H = 8000.0, 3000.0
GAP = 20.0
TARGET_FILL = 0.62          # realistic packing fraction for these aspect-1 sites, no rotation

# Domain-informed sweeps. Each tuple (source, param) -> values; rationale explains the choice.
# A source may appear more than once (multiple experiments). `fixed` pins the non-swept params.
SWEEP_KB = [
    # source        param              values                          fixed            rationale
    ("straight", "length", [25, 50, 100, 200, 400, 800], {"width": 0.5},
     "geometric cutback ladder over >1 decade -> trustworthy loss slope + coupling intercept"),
    ("straight", "width", [0.4, 0.5, 0.7, 1.0, 1.5, 2.0], {"length": 100},
     "propagation loss / multimode behavior vs core width, tapered from the 500 nm GC feed"),
    ("spiral", "length", [1000, 2000, 4000], {},
     "mm-scale arm of the SAME loss cutback, folded compact so it fits the die"),
    ("dcoupler", "coupling_gap", [0.18, 0.24, 0.30, 0.36], {},
     "bracket the 50:50 gap on both sides so the split-ratio curve can be interpolated"),
    ("dcoupler", "coupling_length", [5, 10, 15, 20], {"coupling_gap": 0.30},
     "split ratio vs interaction length at a fixed mid gap (the orthogonal DC axis)"),
    ("crossing", "added_width", [0.6, 1.0, 1.4, 1.8], {"arm_length": 6.0},
     "crossing insertion loss vs multimode intersection width (the wide-section / taper trade)"),
    ("heater", "length", [50, 100, 200, 300], {},
     "thermo-optic efficiency: resolvable P_pi differences across length (active -> 2 bond pads)"),
    ("heater", "heater_width", [3.0, 4.0, 5.0, 6.0], {"length": 150},
     "efficiency vs resistance trade at fixed length (active -> 2 bond pads)"),
    ("modulator", "length", [300, 600, 1000], {"imbalance": 30.0},
     "EO modulation efficiency vs travelling-wave electrode length (unbalanced MZI, signal/ground pads)"),
    ("ybranch_gds", None, [None], {},
     "BYO-GDS device: no internal parameter, replicate for split-uniformity sampling"),
]
REPLICATE_HINT = {"ybranch_gds": 4}   # seed extra copies of replicate-only / nominal devices


def device_catalog(lib):
    """Introspect every DeviceSource: kind, ports, what it measures, footprint of one site."""
    cat = {}
    for name, dev in lib.items():
        params = {name: v["default"] for name, v in dev.sweepable.items()}
        site = test_structures.site_for(dev, params=({dev.primary_param: dev.sweepable[dev.primary_param]["default"]}
                                                     if dev.primary_param else {}))
        (x0, y0), (x1, y1) = site.bounds()
        cat[name] = {
            "kind": dev.kind, "active": dev.active, "measures": dev.measures,
            "n_optical_ports": dev.n_optical_ports, "n_terminals": dev.n_terminals,
            "sweepable": list(dev.sweepable), "primary_param": dev.primary_param,
            "source_path": dev.source_path,
            "site_footprint_um": (round(float(x1 - x0), 1), round(float(y1 - y0), 1)),
        }
    return cat


def propose(lib):
    """Build the experiments list + a per-experiment footprint estimate + die-fit summary."""
    experiments, areas = [], []
    for source, param, values, fixed, rationale in SWEEP_KB:
        if source not in lib:
            continue
        dev = lib[source]
        params0 = dict(fixed)
        if param is not None:
            params0[param] = values[0]
        (x0, y0), (x1, y1) = test_structures.site_for(dev, params=params0).bounds()
        cell = (float(x1 - x0) + GAP) * (float(y1 - y0) + GAP)
        rep = REPLICATE_HINT.get(source, 1)
        n_pts = len([v for v in values])
        experiments.append({
            "source": source, "kind": dev.kind, "param": param, "values": values,
            "fixed": fixed, "replicate_hint": rep, "measures": dev.measures,
            "rationale": rationale, "n_points": n_pts,
            "site_um2": round(cell, 0), "subtotal_um2": round(cell * n_pts * rep, 0),
        })
        areas.append(cell * n_pts * rep)
    n_base = sum(e["n_points"] * e["replicate_hint"] for e in experiments)
    base_area = sum(areas)
    usable = (DIE_W - 2 * floorplan.DICE_MARGIN) * (DIE_H - 2 * floorplan.DICE_MARGIN)
    # replicate multiplier the loop needs to fill the die to TARGET_FILL
    fill_mult = max(1, int(usable * TARGET_FILL / base_area)) if base_area else 1
    tier = criteria.mpw_area_tier(DIE_W * DIE_H / 1e6)
    summary = {
        "die_w_um": DIE_W, "die_h_um": DIE_H, "die_area_mm2": round(DIE_W * DIE_H / 1e6, 2),
        "usable_mm2": round(usable / 1e6, 2), "mpw_tier_mm2": tier,
        "n_unique_base": n_base, "base_area_mm2": round(base_area / 1e6, 3),
        "target_fill": TARGET_FILL, "fill_multiplier_est": fill_mult,
        "est_structures_at_fill": n_base * fill_mult,
    }
    return experiments, summary


def render(cat, experiments, summary):
    L = ["DEVICE LIBRARY (what the planner sees):"]
    for name, info in cat.items():
        src = f"  <- {pathlib.Path(info['source_path']).name}" if info.get("source_path") else ""
        L.append(f"  {name:12s} [{info['kind']}/{'active' if info['active'] else 'passive'}] "
                 f"site {info['site_footprint_um'][0]:.0f}x{info['site_footprint_um'][1]:.0f}um  "
                 f"ports={info['n_optical_ports']} term={info['n_terminals']}  "
                 f"sweepable={info['sweepable']}{src}")
        L.append(f"               measures: {info['measures']}")
    L += ["", "PROPOSED DoE (base variety; the loop replicates this to fill the die):"]
    for e in experiments:
        sweep = f"{e['param']} x{e['n_points']} = {e['values']}" if e["param"] else f"replicate x{e['replicate_hint']}"
        fx = f"  fixed={e['fixed']}" if e["fixed"] else ""
        L.append(f"  {e['source']:12s} {sweep}{fx}")
        L.append(f"               why: {e['rationale']}")
    s = summary
    L += ["",
          f"DIE: {s['die_w_um']/1000:.1f} x {s['die_h_um']/1000:.1f} mm = {s['die_area_mm2']} mm^2 "
          f"(usable {s['usable_mm2']} mm^2, MPW area tier {s['mpw_tier_mm2']} mm^2)",
          f"BASE DoE: {s['n_unique_base']} unique structures ~ {s['base_area_mm2']} mm^2",
          f"FILL: loop replicates ~x{s['fill_multiplier_est']} -> ~{s['est_structures_at_fill']} structures "
          f"at {s['target_fill']:.0%} fill (the loop searches the true capacity)"]
    return "\n".join(L)


def main():
    lib = library.default_library()
    cat = device_catalog(lib)
    experiments, summary = propose(lib)
    text = render(cat, experiments, summary)
    print(text)

    plan = {"die": {"DIE_W": DIE_W, "DIE_H": DIE_H}, "pack": {"GAP": GAP},
            "experiments": experiments, "summary": summary, "catalog": cat}
    bb = ROOT / "blackboard"
    bb.mkdir(exist_ok=True)
    (bb / "doe_plan.json").write_text(json.dumps(plan, indent=2))

    md = ["# DoE plan (Phase 0 — generated by plan.py)\n",
          f"Fixed die **{DIE_W/1000:.0f} x {DIE_H/1000:.0f} mm = {summary['die_area_mm2']} mm^2** "
          f"(MPW area tier {summary['mpw_tier_mm2']} mm^2).\n",
          f"Base DoE = **{summary['n_unique_base']} unique structures** across "
          f"{len({e['source'] for e in experiments})} devices "
          f"({sum(1 for e in experiments if e['kind']=='pcell')} from PCells, "
          f"{sum(1 for e in experiments if e['kind']=='gds')} from GDS). The packing loop "
          f"replicates this base set (~x{summary['fill_multiplier_est']}) to fill the die.\n",
          "## Experiments\n"]
    for e in experiments:
        sweep = f"sweep `{e['param']}` over {e['values']}" if e["param"] else f"replicate x{e['replicate_hint']}"
        md.append(f"- **{e['source']}** ({e['kind']}): {sweep}. _{e['rationale']}_  \n"
                  f"  measures: {e['measures']}")
    (bb / "doe_plan.md").write_text("\n".join(md) + "\n")
    print(f"\nwrote blackboard/doe_plan.json + blackboard/doe_plan.md")
    print("next: python optimize.py   (fills the fixed 8x3 mm die from this plan)")


if __name__ == "__main__":
    main()
