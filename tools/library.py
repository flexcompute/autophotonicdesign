"""
library.py  ──  the generalized device-ingestion layer.

This is what makes the harness reusable: the DoE loop never talks to a hard-coded factory list.
It talks to a **library of `DeviceSource`s**, and a DeviceSource can be either

  * a **PCell** — a `@pf.parametric_component` factory (sweepable by argument), or
  * a **GDS cell** — a user-supplied `.gds`/`.oas` file, loaded with `pf.load_layout` and given
    ports by auto-detection (`Component.detect_ports(..., on_boundary="xy")`).

Both expose the SAME interface, so a user can bring their own PCells OR their own GDS components
and run the identical place / route / validate / pack loop:

    lib = default_library()                       # the built-in demo set (5 PCells + 1 GDS)
    lib["mydev"] = gds_source("mydev", "my.gds",  # ... or drop in your own
                              measures="...", spec="TE_1550_500")
    dev = lib["straight"]
    dut = dev.instantiate(length=200.0)           # PCell: pass swept params
    dut = lib["ybranch_gds"].instantiate()        # GDS: fixed geometry, params ignored

A DeviceSource reports what it *measures*, which parameters are *sweepable* (with defaults +
units), and how many optical ports / electrical terminals it has — everything the planner
(`plan.py`) needs to design a Design-of-Experiments without knowing the device internals.
"""
import inspect
import pathlib
from dataclasses import dataclass, field
from typing import Callable, Optional

import photonforge as pf

from . import components as C

GDS_DIR = pathlib.Path(__file__).resolve().parents[1] / "components_gds"


# ───────────────────────────── the uniform interface ─────────────────────────────
@dataclass
class DeviceSource:
    """One device the DoE can sweep / replicate, whether it came from a PCell or a GDS file."""
    name: str
    kind: str                         # "pcell" | "gds"
    measures: str                     # what a DoE on this device measures (human-readable)
    _instantiate: Callable            # (**params) -> pf.Component
    sweepable: dict = field(default_factory=dict)   # {param: {"default":.., "type":"float|int", "unit":..}}
    primary_param: Optional[str] = None             # the parameter a DoE would normally sweep
    active: bool = False              # True -> has electrical terminals -> needs bond pads
    n_optical_ports: int = 0
    n_terminals: int = 0
    source_path: Optional[str] = None  # for GDS sources, the file it came from

    def instantiate(self, **params):
        """Build one instance. PCell: params are factory kwargs. GDS: params are ignored."""
        if self.kind == "gds":
            return self._instantiate()
        return self._instantiate(**params)

    def describe(self):
        sw = ", ".join(f"{k}={v['default']}{v.get('unit','')}" for k, v in self.sweepable.items())
        return (f"{self.name:14s} [{self.kind}/{'active' if self.active else 'passive'}] "
                f"ports={self.n_optical_ports} term={self.n_terminals}  "
                f"sweepable: {sw or '(none — replicate only)'}\n"
                f"{'':16s}measures: {self.measures}")


# ───────────────────────────── PCell ingestion ─────────────────────────────
# Parameters that are construction details, not meaningful DoE sweep axes (keep the planner focused).
_PCELL_SKIP = {"contact_depth", "contact", "lead", "radius", "separation"}
_UNITS = {"length": "um", "coupling_gap": "um", "coupling_length": "um", "arm_length": "um",
          "heater_width": "um"}


def pcell_source(name, factory, *, measures, primary_param=None, active=False):
    """Wrap a `@pf.parametric_component` factory as a DeviceSource (introspects its sweepable args)."""
    sig = inspect.signature(factory)
    sweepable = {}
    for pname, p in sig.parameters.items():
        if p.default is inspect.Parameter.empty or not isinstance(p.default, (int, float)):
            continue
        if pname in _PCELL_SKIP:
            continue
        sweepable[pname] = {"default": p.default,
                            "type": "int" if isinstance(p.default, int) else "float",
                            "unit": _UNITS.get(pname, "")}
    if primary_param is None and sweepable:
        primary_param = next(iter(sweepable))
    probe = factory()
    return DeviceSource(
        name=name, kind="pcell", measures=measures, _instantiate=factory,
        sweepable=sweepable, primary_param=primary_param, active=active,
        n_optical_ports=len(probe.ports), n_terminals=len(probe.terminals),
    )


# ───────────────────────────── GDS ingestion ─────────────────────────────
def _pick_top(loaded, cell):
    if cell is not None:
        return loaded[cell]
    if len(loaded) == 1:
        return next(iter(loaded.values()))
    try:                                  # multiple cells: ask PhotonForge which are top-level
        tops = pf.find_top_level(*loaded.values())
        if tops:
            return tops[0]
    except Exception:  # noqa: BLE001
        pass
    return next(iter(loaded.values()))


def load_gds_component(gds_path, *, spec=C.PORT_SPEC, cell=None, on_boundary="xy",
                       boundary_margin=0.5, technology=None):
    """Load ONE component from a GDS/OASIS file and give it ports by auto-detection.

    `detect_ports(..., on_boundary="xy")` returns ports only where a waveguide of `spec` crosses
    the device boundary, so internal taper steps are NOT mistaken for ports (a plain bounds scan
    over-detects). The returned ports are added P0, P1, ... left-to-right-ish in detection order.
    """
    loaded = pf.load_layout(str(gds_path), technology=technology)
    comp = _pick_top(loaded, cell)
    if not comp.ports:
        detected = comp.detect_ports([spec], on_boundary=on_boundary,
                                     boundary_margin=boundary_margin)
        for i, port in enumerate(detected):
            comp.add_port(port, f"P{i}")
    return comp


def gds_source(name, gds_path, *, measures, spec=C.PORT_SPEC, cell=None, on_boundary="xy",
               boundary_margin=0.5, technology=None, active=False):
    """Wrap a GDS/OASIS file as a DeviceSource. The component is loaded + ported ONCE and cached;
    `instantiate()` returns the cached cell (fixed geometry -> shared across replicates)."""
    comp = load_gds_component(gds_path, spec=spec, cell=cell, on_boundary=on_boundary,
                              boundary_margin=boundary_margin, technology=technology)
    return DeviceSource(
        name=name, kind="gds", measures=measures, _instantiate=lambda: comp,
        sweepable={}, primary_param=None, active=active,
        n_optical_ports=len(comp.ports), n_terminals=len(comp.terminals),
        source_path=str(gds_path),
    )


def ensure_demo_gds():
    """Materialize the demo BYO-GDS file (components_gds/ybranch.gds) if absent.

    For the demo we export SiEPIC's 1x2 Y-branch to a GDS and then treat that file as an opaque,
    user-supplied component — so the GDS-ingestion path is exercised end to end on a real file the
    user can open and inspect. A real user simply drops their own .gds in components_gds/ instead.
    """
    GDS_DIR.mkdir(exist_ok=True)
    path = GDS_DIR / "ybranch.gds"
    if not path.exists():
        import siepic_forge as sf
        sf.component("ebeam_y_1550").write_gds(str(path))
    return path


# ───────────────────────────── the default demo library ─────────────────────────────
def default_library():
    """The built-in demo device set: 5 PCells (incl. 2 new vs the v0 scaffold) + 1 GDS-ingested.

    Doubles the original 3-device set and exercises both ingestion paths. A user replaces or
    extends this dict with their own PCell factories / GDS files.
    """
    C.technology()
    lib = {
        "straight": pcell_source("straight", C.straight_dut,
                                 measures="waveguide propagation loss (cutback slope)",
                                 primary_param="length"),
        "spiral": pcell_source("spiral", C.spiral_dut,
                               measures="propagation loss at mm-scale lengths (compact spiral cutback)",
                               primary_param="length"),
        "dcoupler": pcell_source("dcoupler", C.directional_coupler_dut,
                                 measures="directional-coupler power splitting ratio",
                                 primary_param="coupling_gap"),
        "crossing": pcell_source("crossing", C.crossing_dut,
                                 measures="waveguide-crossing insertion loss vs intersection width",
                                 primary_param="added_width"),
        "heater": pcell_source("heater", C.heater_dut,
                               measures="thermo-optic phase-shifter efficiency (optical + electrical)",
                               primary_param="length", active=True),
        # active (RF), but it carries its own signal/ground probe pads -> active=False so the
        # test-site does NOT add a second bond-pad cage (which would route over the CPS rails).
        "modulator": pcell_source("modulator", C.cps_modulator_dut,
                                  measures="segmented-CPS travelling-wave EO modulator (unbalanced MZI)",
                                  primary_param="length", active=False),
    }
    lib["ybranch_gds"] = gds_source(
        "ybranch_gds", ensure_demo_gds(),
        measures="1x2 Y-branch splitter insertion loss (device supplied as a GDS file)")
    return lib


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", message=".*renamed in the layout.*")
    for dev in default_library().values():
        print(dev.describe())
