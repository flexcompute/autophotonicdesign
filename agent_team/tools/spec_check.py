"""Do a check of the numbers in spec.md. Print the targets for the approval of the human.

    python tools/spec_check.py                  # checks spec.md
    python tools/spec_check.py specs/lattice_demux_2ch.md

The exit code is 0 if the spec is complete and consistent, and 1 if not. This check does not show
that the targets are possible. The architect shows that at gate A.
"""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import yaml  # noqa: E402,F401
from tools.metrics import METRICS  # noqa: E402

REQUIRED = {
    "name": None, "pdk": None,
    "layout": ["max_size", "optical_ports"],
    "simulation": ["band", "points", "paths"],
    "metrics": None,
    "variation": ["dies", "pass_fraction", "training_dies", "n_eff", "coupler_length_scale"],
    "measurement": ["budget_per_die", "noise_db", "floor_db"],
}


def problems(spec: dict) -> list[str]:
    out = []
    for key, sub in REQUIRED.items():
        if key not in spec:
            out.append(f"missing '{key}'")
        elif sub:
            out += [f"missing '{key}.{s}'" for s in sub if s not in spec[key]]
    if out:
        return out
    if not os.path.exists(os.path.join(ROOT, "tools", "pdks", f"{spec['pdk']}.py")):
        out.append(f"no PDK adapter tools/pdks/{spec['pdk']}.py")
    ports = set(spec["layout"]["optical_ports"])
    paths = [tuple(p) for p in spec["simulation"]["paths"]]
    out += [f"path {p} uses a port that is not in layout.optical_ports" for p in paths if not set(p) <= ports]
    lo, hi = spec["simulation"]["band"]
    wl = np.linspace(lo, hi, int(spec["simulation"]["points"]))
    for m in spec["metrics"]:
        name = m.get("name", "?")
        if m.get("type") not in METRICS:
            out.append(f"{name}: type '{m.get('type')}' is not in tools/metrics.py ({', '.join(METRICS)})")
            continue
        if tuple(m.get("path", ())) not in paths:
            out.append(f"{name}: path {m.get('path')} is not in simulation.paths")
        try:
            args = dict(m.get("args", {}))
            if "other_path" in args:
                if tuple(args["other_path"]) not in paths:
                    out.append(f"{name}: other_path {args['other_path']} is not in simulation.paths")
                args.pop("other_path")
                args["other"] = np.full(wl.size, 0.5)
            keys = set(METRICS[m["type"]](wl, np.full(wl.size, 0.5), **args))
        except Exception as e:
            out.append(f"{name}: args do not work with '{m['type']}': {e}")
            continue
        for which in ("nominal", "die"):
            for k, rule in (m.get(which) or {}).items():
                if k not in keys:
                    out.append(f"{name}.{which}: '{k}' is not an output of '{m['type']}' ({', '.join(sorted(keys))})")
                if not set(rule) <= {"min", "max", "abs_max"}:
                    out.append(f"{name}.{which}.{k}: use only min, max, abs_max")
        c = m.get("args", {}).get("center")
        if c is not None and not lo <= c <= hi:
            out.append(f"{name}: center {c} is outside the band {lo}..{hi}")
    if spec.get("tuning") and "max_dT" not in spec["tuning"]:
        out.append("missing 'tuning.max_dT'")
    if not 0 < spec["variation"]["pass_fraction"] <= 1:
        out.append("variation.pass_fraction must be in (0, 1]")
    return out


def table(spec: dict) -> str:
    rows = ["| Metric | Path | Target | Nominal die | Each virtual die |", "|---|---|---|---|---|"]
    fmt = lambda r: ", ".join(f"{'>=' if k == 'min' else '<=' if k == 'max' else '|x| <='} {v}" for k, v in r.items())
    for m in spec["metrics"]:
        keys = list(dict.fromkeys([*(m.get("nominal") or {}), *(m.get("die") or {})]))
        for k in keys:
            rows.append(f"| {m['name']} | {'->'.join(m['path'])} | {k} | {fmt((m.get('nominal') or {}).get(k, {})) or '-'} "
                        f"| {fmt((m.get('die') or {}).get(k, {})) or '-'} |")
    v, h = spec["variation"], spec.get("tuning")
    rows += [""]
    if h:
        rows += [f"Tuning ({h.get('type', 'thermal')}): at most {h['max_dT']} K for each element; "
                 f"sum on the nominal die at most {h.get('nominal_total_dT_max', '-')} K."]
    rows += [
             f"Dies: {v['dies']} blind dies, {v['pass_fraction']:.0%} must pass; {spec['measurement']['budget_per_die']} "
             f"measurements per die. Variation: n_eff {v['n_eff']}, coupler length scale {v['coupler_length_scale']}.",
             f"Layout: max {spec['layout']['max_size']} um, ports {spec['layout']['optical_ports']}, PDK {spec['pdk']}."]
    return "\n".join(rows)


def main():
    from tools.measure import load_spec
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "spec.md")
    try:
        spec = load_spec(path)
    except Exception as e:
        sys.exit(f"FAIL: cannot read the Numbers block of {path}: {e}")
    bad = problems(spec)
    if bad:
        print("FAIL:\n  " + "\n  ".join(bad))
        sys.exit(1)
    print(f"OK: {spec['name']}\n")
    print(table(spec))


if __name__ == "__main__":
    main()
