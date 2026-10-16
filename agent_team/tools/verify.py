"""The gates. Builds design/chip.py, checks it, and scores it against spec.md.

    python tools/verify.py                       # all gates, blind dies from spec.md
    python tools/verify.py --gates build,drc,lvs # layout gates only (fast)
    python tools/verify.py --dies 2              # fewer blind dies while iterating
    python tools/verify.py --seeds 123 456       # re-run given dies (to reproduce a failure)

Gates, in order (a failed gate stops the later ones):
  build    design/chip.py build() returns a component with the spec's ports, heater terminals, size
  drc      PDK DRC deck: 0 violations
  lvs      PDK LVS: layout matches the netlist intent
  nominal  calibrate() (if the spec has tuning) on the nominal die, then post-layout circuit simulation meets the 'nominal' targets
  dies     calibrate() (if the spec has tuning) on blind virtual dies; the share of dies that meet the 'die' targets >= pass_fraction

Writes output/verify.json and output/verify.png. Exit code 0 only if every gate run passed.
"""

import argparse
import importlib
import importlib.util
import json
import os
import secrets
import sys
import time
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import noclouds  # noqa: F401,E402
from tools.measure import Station, load_design, load_spec  # noqa: E402
from tools.metrics import METRICS, check, db  # noqa: E402

GATES = ["build", "drc", "lvs", "nominal", "dies"]
OUT = os.path.join(ROOT, "output")


def load_tuning(path=None):
    path = os.path.abspath(path or os.path.join(ROOT, "design", "tuning.py"))
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("design_tuning", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "calibrate", None)


def score(spec, wl, resp, which):
    """Run every spec metric on a response; `which` = 'nominal' or 'die' picks the targets."""
    rows, values = [], {}
    for m in spec["metrics"]:
        t = resp["->".join(m["path"])]
        args = dict(m.get("args", {}))
        if "other_path" in args:                     # a metric that compares two paths (for example imbalance)
            args["other"] = resp["->".join(args.pop("other_path"))]
        v = METRICS[m["type"]](wl, t, **args)
        values[m["name"]] = v
        for r in check(v, m.get(which, {})):
            rows.append({"metric": f"{m['name']}.{r['metric']}", **{k: r[k] for k in ("value", "target", "ok")}})
    return values, rows


def run_die(chip, spec, die, calibrate, budget):
    """Calibrate on one die, then score the noiseless response at the chosen settings."""
    st = Station(chip, spec, die=die, noise=die != "nominal", budget=budget)
    t0 = time.time()
    try:
        settings = {k: float(v) for k, v in (calibrate(st.handle()) if calibrate else {}).items()}
        error = None
    except Exception as e:  # a crash in calibrate fails the die, not the run
        settings, error = {}, f"{type(e).__name__}: {e}"
    resp = st.response(settings)
    values, rows = score(spec, st.wavelengths, resp, "nominal" if die == "nominal" else "die")
    return {
        "die": die, "settings": settings, "calls": st.calls, "seconds": round(time.time() - t0, 1),
        "error": error, "values": values, "rows": rows, "ok": error is None and all(r["ok"] for r in rows),
        "heaters": {n: {"path": h.path, "position": h.position} for n, h in st.heaters.items()},
    }, st.wavelengths, resp


def plot(spec, wl, nominal_resp, die_resps, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    paths = ["->".join(p) for p in spec["simulation"]["paths"]]
    fig, axes = plt.subplots(1, len(paths), figsize=(6.5 * len(paths), 4.2), sharey=True, squeeze=False)
    for ax, p in zip(axes[0], paths):
        for d, r in die_resps:
            ax.plot(wl * 1e3, db(r[p]), lw=0.8, alpha=0.5, color="#c43959" if not d["ok"] else "#2e7fd4")
        if nominal_resp is not None:
            ax.plot(wl * 1e3, db(nominal_resp[p]), lw=2, color="#111417", label="nominal die, calibrated")
        for m in spec["metrics"]:
            if "->".join(m["path"]) != p or m["type"] != "channel":
                continue
            a = m["args"]
            ax.axvspan((a["center"] - a["pass_halfwidth"]) * 1e3, (a["center"] + a["pass_halfwidth"]) * 1e3, color="#1aaf6b", alpha=0.15)
            for o in a.get("stop_offsets", []):
                c = a["center"] + o
                ax.axvspan((c - a["stop_halfwidth"]) * 1e3, (c + a["stop_halfwidth"]) * 1e3, color="#c43959", alpha=0.12)
        ax.set(title=p, xlabel="Wavelength (nm)", ylim=(-45, 0))
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel("Transmission (dB); green = pass band, red = stop band")
    axes[0][0].legend(loc="lower left", fontsize=8)
    fig.suptitle("verify: black = nominal, blue = passing blind die, red = failing blind die", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gates", default=",".join(GATES))
    ap.add_argument("--dies", type=int, default=None, help="number of blind dies (default from spec.md)")
    ap.add_argument("--seeds", type=int, nargs="*", default=None, help="explicit die seeds instead of random ones")
    ap.add_argument("--design", default=None)
    ap.add_argument("--tuning", default=None)
    ap.add_argument("--spec", default=None, help="spec file (default spec.md)")
    a = ap.parse_args()
    want = [g for g in GATES if g in a.gates.split(",")]
    spec = load_spec(a.spec)
    pdk = importlib.import_module(f"tools.pdks.{spec['pdk']}")
    os.makedirs(OUT, exist_ok=True)
    report = {"spec": spec["name"], "gates": {}, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    t_all = time.time()

    def gate(name, ok, **info):
        report["gates"][name] = {"ok": bool(ok), **info}
        print(f"[{'PASS' if ok else 'FAIL'}] {name:8s} " + "; ".join(f"{k}={v}" for k, v in info.items() if k not in ("report", "rows", "dies")), flush=True)
        return ok

    chip = None
    nominal_resp, die_resps, wl = None, [], None
    for g in want:
        t0 = time.time()
        try:
            if g == "build":
                chip = load_design(a.design).build()
                lo, hi = chip.bounds()
                size = [round(float(v), 2) for v in hi - lo]
                lay = spec["layout"]
                missing = [p for p in lay["optical_ports"] if p not in chip.ports]
                st = Station(chip, spec)
                n_h = len(st.heaters)
                terms = sorted(chip.terminals)
                want_terms = sorted(f"H{k}{s}" for k in range(1, n_h + 1) for s in "PN") if lay.get("heater_terminals") else []
                bad_terms = sorted(set(want_terms) - set(terms))
                too_big = any(s > m + 1e-6 for s, m in zip(size, lay["max_size"]))
                no_tuners = bool(spec.get("tuning")) and n_h == 0      # the spec asks for tuning, the chip has none
                ok = not missing and not bad_terms and not too_big and not no_tuners
                if not gate(g, ok, size_um=size, max_size_um=lay["max_size"], missing_ports=missing, heaters=n_h,
                            missing_terminals=bad_terms, seconds=round(time.time() - t0, 1)):
                    break
            elif g == "drc":
                r = pdk.drc(chip)
                if not gate(g, r["clean"], violations=r["violations"], by_rule=r["by_rule"], seconds=round(time.time() - t0, 1), report=r["report"]):
                    break
            elif g == "lvs":
                r = pdk.lvs(chip)
                if not gate(g, r["match"], seconds=round(time.time() - t0, 1), report=r["report"]):
                    print(r["report"][:2000])
                    break
            elif g == "nominal":
                calibrate = load_tuning(a.tuning) if spec.get("tuning") else None
                budget = spec["measurement"]["budget_per_die"]
                d, wl, nominal_resp = run_die(chip, spec, "nominal", calibrate, budget)
                lim = (spec.get("tuning") or {}).get("nominal_total_dT_max")
                if lim is not None:
                    total = sum(d["settings"].values())
                    d["rows"].append({"metric": "tuning.total_dT", "value": total, "target": {"max": lim}, "ok": total <= lim})
                ok = d["error"] is None and all(r["ok"] for r in d["rows"])
                for r in d["rows"]:
                    v = r["value"]
                    print(f"     {'ok ' if r['ok'] else 'BAD'} {r['metric']:32s} {v if v is None else round(v, 3)!s:>9}  target {r['target']}")
                if d["error"]:
                    print("     calibrate() error:", d["error"])
                if not gate(g, ok, settings={k: round(v, 2) for k, v in d["settings"].items()}, calls=d["calls"],
                            seconds=round(time.time() - t0, 1), rows=d["rows"]):
                    break
            elif g == "dies":
                calibrate = load_tuning(a.tuning) if spec.get("tuning") else None
                budget = spec["measurement"]["budget_per_die"]
                n = a.dies if a.dies is not None else int(spec["variation"]["dies"])
                floor = int(spec["variation"]["training_dies"])
                seeds = a.seeds if a.seeds else [floor + secrets.randbelow(10 ** 9) for _ in range(n)]
                rows = []
                for s in seeds:
                    d, wl, r = run_die(chip, spec, s, calibrate, budget)
                    die_resps.append((d, r))
                    bad = [x["metric"] for x in d["rows"] if not x["ok"]]
                    print(f"     die {s}: {'pass' if d['ok'] else 'FAIL'}  calls={d['calls']}  {d['seconds']} s  "
                          f"settings={ {k: round(v, 1) for k, v in d['settings'].items()} }" + (f"  failed: {bad}" if bad else "")
                          + (f"  error: {d['error']}" if d["error"] else ""), flush=True)
                    rows.append({k: d[k] for k in ("die", "ok", "settings", "calls", "seconds", "error", "rows")})
                frac = float(np.mean([r["ok"] for r in rows])) if rows else 0.0
                need = float(spec["variation"]["pass_fraction"])
                if not gate(g, frac >= need, pass_fraction=round(frac, 3), required=need, n=len(rows),
                            seeds=seeds, seconds=round(time.time() - t0, 1), dies=rows):
                    break
        except Exception as e:
            gate(g, False, error=f"{type(e).__name__}: {e}")
            traceback.print_exc()
            break

    if nominal_resp is not None or die_resps:
        plot(spec, wl, nominal_resp, die_resps, os.path.join(OUT, "verify.png"))
    report["seconds"] = round(time.time() - t_all, 1)
    report["all_pass"] = all(report["gates"].get(g, {}).get("ok", False) for g in want)
    with open(os.path.join(OUT, "verify.json"), "w") as f:
        json.dump(report, f, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    print(f"{'ALL PASS' if report['all_pass'] else 'NOT PASSED'}  ({', '.join(want)})  {report['seconds']} s  -> output/verify.json, output/verify.png")
    sys.exit(0 if report["all_pass"] else 1)


if __name__ == "__main__":
    main()
