"""PDK adapter for SiPhoPDK (a synthetic 220 nm SOI and SiN platform for the O-band).

There is one adapter for each PDK. spec.md gives the name of the adapter (`pdk: siphopdk`). The
other tools use only the functions in this file. A new PDK needs a new file with the same names.
"""

import photonforge as pf
import siphopdk as sp
from siphopdk import _calibration as cal

NAME = "siphopdk"
WAVELENGTH = cal.WAVELENGTH        # um, design wavelength of the calibrated models
library = sp                       # the PDK cells: sp.directional_coupler, sp.straight, ...

# Analytic strip models with the PDK's calibrated numbers. A route piece without a model runs a
# mode solver; these models make post-layout circuit simulation fast and free. Length comes from
# each piece's geometry (length=None measures it).
WG_MODEL = pf.AnalyticWaveguideModel(
    n_eff=cal.N_EFF_STRIP, n_group=cal.N_GROUP_STRIP,
    propagation_loss=cal.LOSS_STRIP, reference_frequency=cal.REF_FREQUENCY)
BEND_MODEL = pf.AnalyticWaveguideModel(
    n_eff=cal.N_EFF_STRIP, n_group=cal.N_GROUP_STRIP,
    propagation_loss=cal.LOSS_STRIP, extra_loss=cal.LOSS_BEND_90,
    reference_frequency=cal.REF_FREQUENCY)
ROUTE_MODELS = dict(straight_kwargs={"model": WG_MODEL}, bend_kwargs={"model": BEND_MODEL})


def technology() -> pf.Technology:
    tech = sp.siphopdk()
    pf.config.default_technology = tech
    return tech


def fast_models(component: pf.Component, _seen=None) -> pf.Component:
    """Give every route piece that would need a mode solver the analytic strip model (in place)."""
    _seen = set() if _seen is None else _seen
    for ref in component.references:
        c = ref.component
        if id(c) in _seen:
            continue
        _seen.add(id(c))
        if type(c.active_model).__name__ in ("WaveguideModel", "Tidy3DModel") and not c.references:
            c.add_model(BEND_MODEL if "bend" in c.name else WG_MODEL, "analytic")
            c.activate_model("analytic")
        fast_models(c, _seen)
    return component


def drc(component: pf.Component) -> dict:
    """KLayout DRC with the PDK deck. Returns {'clean', 'violations', 'by_rule', 'report'}."""
    r = sp.drc_check(component, show_progress=False)
    text = r.summary() if hasattr(r, "summary") else str(r)
    by_rule = {}
    for line in text.splitlines():
        name, _, count = line.partition(":")
        if count.strip().isdigit() and int(count) > 0 and "Total" not in name:
            by_rule[name.strip()] = int(count)
    return {"clean": bool(r.is_clean), "violations": sum(by_rule.values()), "by_rule": by_rule, "report": text}


def lvs(component: pf.Component) -> dict:
    """KLayout LVS of the layout against the netlist intent. Returns {'match', 'report'}."""
    r = sp.lvs_check(component, show_progress=False)
    return {"match": r.verdict == "match", "report": str(r)}
