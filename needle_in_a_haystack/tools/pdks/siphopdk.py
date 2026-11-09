"""SiPhoPDK: synthetic 220 nm SOI + SiN demo PDK, O-band. It has a DRC deck, DevRec and PinRec layers."""
import photonforge as pf

NAME = "siphopdk"
WAVELENGTH = 1.31
ROUTE_SPEC = "SI_STRIP_O"
CORE = ("SI",)
ALT_CORE = ("SLAB",)
CONNECT = ("SI", "SLAB")
DEVICE_LAYER = "DEVREC"
PIN_LAYER = "PINREC"
PIN_LAYER_E = "PINREC_E"
ELECTRICAL = {"conductors": ["NPP", "PPP", "M1", "M2"],
              "vias": [("VIA1", ("NPP", "PPP"), ("M1",)), ("VIA3", ("M1",), ("M2",))]}
COLORS = {"SI": "#2b6cb0", "SLAB": "#9f7aea", "GRAT": "#38a169", "SIN": "#319795", "HTR": "#dd6b20", "M1": "#d69e2e",
          "M2": "#b7791f", "VIA1": "#c53030", "VIA2": "#c53030", "VIA3": "#9b2c2c", "PAD": "#718096", "DEVREC": "#a0aec0",
          "PINREC": "#e53e3e", "PINREC_E": "#805ad5", "FLOORPLAN": "#cbd5e0", "GE": "#4a5568"}
BASIC_RULES = {"SI": {"width": 0.15, "space": 0.15}, "SLAB": {"width": 0.3, "space": 0.3}}


def technology():
    import siphopdk as sp
    tech = sp.siphopdk()
    pf.config.default_technology = tech
    return tech


def drc_deck():
    import siphopdk as sp
    return sp.DRC_RULES


def is_device(name):
    return False
