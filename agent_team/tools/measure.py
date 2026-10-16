"""Virtual test station: measure the chip on a virtual die, with heater settings, like a prober.

A die is the drawn chip plus fabrication variation from spec.md: an n_eff error on every
waveguide piece (whole-die offset + linear gradient across the die + local noise) and a scale
error on every coupler's full-transfer length (gap variation). The station runs the
post-layout circuit simulation with these errors and returns noisy power spectra in dB.

The team's calibration routine (design/tuning.py) gets only a handle: heater names,
wavelengths, the heater limit and measure(). It cannot see the die's errors.

    python tools/measure.py --list                       # heaters and their positions
    python tools/measure.py --die 3 --set heater_1=10 heater_2=0 --plot output/die3.png
    python tools/measure.py --die nominal --plot output/nominal.png
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import noclouds  # noqa: F401,E402  (no cloud runs from a check)
import photonforge as pf  # noqa: E402
import yaml  # noqa: E402

from tools.metrics import db  # noqa: E402


class MeasurementBudgetExceeded(RuntimeError):
    pass


def load_spec(path=None) -> dict:
    """Read the numbers of the spec: the first ```yaml block in spec.md."""
    with open(path or os.path.join(ROOT, "spec.md")) as f:
        text = f.read()
    m = re.search(r"^```yaml\s*\n(.*?)^```", text, re.S | re.M)
    if not m:
        raise ValueError("spec.md has no ```yaml block with the numbers")
    return yaml.safe_load(m.group(1))


@dataclass
class Instance:
    key: tuple          # updates key for CircuitModel: (name_regex, index, name_regex, index, ...)
    path: str           # readable: "delay_arm_1[0]/straight_l30p0[1]"
    model: str          # model class name
    kwargs: dict        # model parameters
    position: tuple     # (x, y) um, centre of the instance on the die


def _apply(chain, point):
    """Map a point from the innermost reference's component frame to the chip frame."""
    x, y = point
    for ref in reversed(chain):
        if ref.x_reflection:
            y = -y
        s = ref.scaling or 1.0
        x, y = x * s, y * s
        a = np.radians(ref.rotation)
        x, y = x * np.cos(a) - y * np.sin(a), x * np.sin(a) + y * np.cos(a)
        x, y = x + ref.origin[0], y + ref.origin[1]
    return float(x), float(y)


def instances(chip: pf.Component) -> list[Instance]:
    """Leaf model instances, keyed the way CircuitModel counts them (per-name order in get_netlist)."""
    out = []

    def walk(comp, key, path, chain):
        count = {}
        for ref in comp.get_netlist()["instances"]:
            c = ref.component
            i = count.get(c.name, -1) + 1
            count[c.name] = i
            k = key + ("^" + re.escape(c.name) + "$", i)
            p = f"{path}/{c.name}[{i}]" if path else f"{c.name}[{i}]"
            m = c.active_model
            if m is None:
                continue
            if isinstance(m, pf.CircuitModel):
                walk(c, k, p, chain + [ref])
                continue
            lo, hi = c.bounds()
            pos = _apply(chain + [ref], ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2))
            kw = dict(getattr(m, "parametric_kwargs", None) or {})
            out.append(Instance(k, p, type(m).__name__, kw, pos))

    walk(chip, (), "", [])
    return out


def _is_heater(inst: Instance) -> bool:
    return inst.model == "AnalyticWaveguideModel" and float(inst.kwargs.get("dn_dT") or 0.0) != 0.0


class Station:
    """Virtual prober for one die. `die` = "nominal" or an integer seed."""

    def __init__(self, chip, spec=None, die="nominal", noise=True, budget=None):
        self.chip = chip
        self.spec = spec or load_spec()
        self.die = die
        sim = self.spec["simulation"]
        self.wavelengths = np.linspace(*sim["band"], int(sim["points"]))
        self.paths = [tuple(p) for p in sim["paths"]]
        self.tuning = self.spec.get("tuning") or {}       # optional: only for chips with tuning elements
        self.max_dT = float(self.tuning.get("max_dT", 0.0))
        m = self.spec.get("measurement", {})
        self.noise_db = float(m.get("noise_db", 0.0)) if noise else 0.0
        self.floor = 10 ** (float(m.get("floor_db", -60.0)) / 10)
        self.budget = budget
        self.calls = 0
        self._inst = instances(chip)
        lo, hi = chip.bounds()
        self._centre = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        heaters = sorted((i for i in self._inst if _is_heater(i)), key=lambda i: (i.position[1], i.position[0]))
        self.heaters = {f"heater_{n + 1}": h for n, h in enumerate(heaters)}
        self._base = self._variation()
        self._noise_rng = np.random.default_rng(None if die == "nominal" else (int(die), 7))

    # ---- die -------------------------------------------------------------------------
    def _variation(self) -> dict:
        """updates dict with this die's errors (empty for the nominal die)."""
        if self.die == "nominal":
            return {}
        v = self.spec["variation"]
        rng = np.random.default_rng(int(self.die))
        dn0 = rng.normal(0, v["n_eff"]["global"])
        grad = rng.normal(0, v["n_eff"]["gradient_per_um"], 2)
        cs0 = rng.normal(0, v["coupler_length_scale"]["global"])
        up = {}
        for inst in self._inst:
            dx, dy = inst.position[0] - self._centre[0], inst.position[1] - self._centre[1]
            dn = dn0 + grad[0] * dx + grad[1] * dy + rng.normal(0, v["n_eff"]["local"])
            cs = cs0 + rng.normal(0, v["coupler_length_scale"]["local"])
            n_eff = inst.kwargs.get("n_eff")
            mu = {}
            if isinstance(n_eff, (int, float)):
                mu["n_eff"] = float(n_eff) + dn
            if inst.model == "AnalyticDirectionalCouplerModel" and isinstance(inst.kwargs.get("coupling_length"), (int, float)):
                mu["coupling_length"] = float(inst.kwargs["coupling_length"]) * (1 + cs)
            if mu:
                up[inst.key] = {"model_updates": mu}
        return up

    # ---- measurement ---------------------------------------------------------------------
    def _updates(self, settings: dict) -> dict:
        up = {k: {"model_updates": dict(v["model_updates"])} for k, v in self._base.items()}
        if settings and not self.tuning:
            raise ValueError("spec.md has no tuning section, so the station accepts no settings")
        for name, dT in (settings or {}).items():
            if name not in self.heaters:
                raise KeyError(f"unknown heater '{name}'; heaters: {list(self.heaters)}")
            dT = float(dT)
            if not 0.0 <= dT <= self.max_dT:
                raise ValueError(f"{name}: dT {dT} K is outside [0, {self.max_dT}] K")
            h = self.heaters[name]
            t0 = float(h.kwargs.get("temperature") or 293.0)
            up.setdefault(h.key, {"model_updates": {}})["model_updates"]["temperature"] = t0 + dT
        return up

    def response(self, settings=None, wavelengths=None) -> dict:
        """Noiseless linear power transmission per path (for the checks; not counted, not for calibrate)."""
        wl = self.wavelengths if wavelengths is None else np.asarray(wavelengths, float)
        sm = self.chip.s_matrix(pf.C_0 / wl, show_progress=False, model_kwargs={"updates": self._updates(settings)})
        return {f"{a}->{b}": np.abs(sm[(f"{a}@0", f"{b}@0")]) ** 2 for a, b in self.paths}

    def measure(self, settings=None, wavelengths=None) -> dict:
        """Measured spectra in dB (noise and floor added), keyed 'IN->OUT'. Counts against the budget."""
        if self.budget is not None and self.calls >= self.budget:
            raise MeasurementBudgetExceeded(f"measurement budget of {self.budget} calls used")
        self.calls += 1
        out = {}
        for k, t in self.response(settings, wavelengths).items():
            d = db(t + self.floor)
            if self.noise_db:
                d = d + self._noise_rng.normal(0, self.noise_db, d.shape)
            out[k] = d
        return out

    def handle(self) -> "StationHandle":
        return StationHandle(self)


class StationHandle:
    """What calibrate() gets: heater names, wavelengths, heater limit, budget, measure()."""

    def __init__(self, station: Station):
        self._s = station
        self.heaters = list(station.heaters)
        self.heater_positions = {n: h.position for n, h in station.heaters.items()}
        self.wavelengths = station.wavelengths.copy()
        self.paths = [f"{a}->{b}" for a, b in station.paths]
        self.max_dT = station.max_dT
        self.budget = station.budget

    @property
    def calls(self) -> int:
        return self._s.calls

    def measure(self, settings=None, wavelengths=None) -> dict:
        return self._s.measure(settings, wavelengths)


def load_design(path=None):
    """Import design/chip.py (or `path`) and return its module."""
    import importlib.util
    path = os.path.abspath(path or os.path.join(ROOT, "design", "chip.py"))
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("design_chip", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--design", default=None)
    ap.add_argument("--die", default="nominal", help='"nominal" or a training seed (0..training_dies-1)')
    ap.add_argument("--set", nargs="*", default=[], help="heater_1=12.5 heater_2=0 ...")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--plot", default=None)
    ap.add_argument("--spec", default=None, help="spec file (default spec.md)")
    a = ap.parse_args()
    spec = load_spec(a.spec)
    die = a.die if a.die == "nominal" else int(a.die)
    if die != "nominal" and not 0 <= die < int(spec["variation"]["training_dies"]):
        sys.exit(f"training dies are 0..{spec['variation']['training_dies'] - 1}")
    chip = load_design(a.design).build()
    st = Station(chip, spec, die=die)
    if a.list:
        for n, h in st.heaters.items():
            print(f"{n}: {h.path} at ({h.position[0]:.1f}, {h.position[1]:.1f}) um")
        return
    settings = {k: float(v) for k, v in (s.split("=") for s in a.set)}
    m = st.measure(settings)
    for k, d in m.items():
        print(f"{k}: max {d.max():.2f} dB at {st.wavelengths[np.argmax(d)] * 1e3:.2f} nm, min {d.min():.2f} dB")
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4))
        for k, d in m.items():
            ax.plot(st.wavelengths * 1e3, d, label=k)
        ax.set(xlabel="Wavelength (nm)", ylabel="Measured (dB)", title=f"die {die}, {settings or 'heaters off'}")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(a.plot, dpi=110)
        print("saved", a.plot)


if __name__ == "__main__":
    main()
