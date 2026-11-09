"""Luxtelligence LNOI400: thin-film lithium niobate (400 nm film, rib waveguides), C-band.

No DRC deck and no pin layers in the PDK. The review tools then use the basic width and space check below, find the
devices by their cell names and find the device pins from the waveguide geometry (Component.detect_ports).
"""
import photonforge as pf

NAME = "lnoi400"
WAVELENGTH = 1.55
ROUTE_SPEC = "RWG1000"
CORE = ("LN_RIDGE",)
ALT_CORE = ("LN_SLAB", "SLAB_NEGATIVE")
CONNECT = ("LN_RIDGE",)
DEVICE_LAYER = None
PIN_LAYER = None
PIN_LAYER_E = None
ELECTRICAL = {"conductors": ["TL"], "vias": []}
COLORS = {"LN_RIDGE": "#2b6cb0", "LN_SLAB": "#b794f4", "SLAB_NEGATIVE": "#e9d8fd", "HT": "#dd6b20", "TL": "#d69e2e",
          "CHIP_CONTOUR": "#a0aec0", "CHIP_EXCLUSION_ZONE": "#cbd5e0", "LABELS": "#4a5568"}
# from the PDK documentation of the ridge: 0.25 um minimum width (SWG250); 1 um space is the PDK's routing practice
BASIC_RULES = {"LN_RIDGE": {"width": 0.25, "space": 1.0}}
_DEVICES = None


def technology():
    import luxtelligence_lnoi400_forge as lx
    tech = lx.lnoi400()
    pf.config.default_technology = tech
    return tech


def drc_deck():
    return None


def is_device(name):
    global _DEVICES
    if _DEVICES is None:
        import luxtelligence_lnoi400_forge as lx
        _DEVICES = tuple(sorted(lx.component_names, key=len, reverse=True))
    return name.startswith(_DEVICES)
