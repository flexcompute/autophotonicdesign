"""SiEPIC EBeam (siepic-forge): 220 nm SOI, C-band, community PDK. DevRec and PinRec layers.

The DRC deck is not in the PhotonForge package. It comes with the SiEPIC EBeam PDK for KLayout
(KLayout package manager, `siepic_ebeam_pdk`). Set SIEPIC_EBEAM_DRC to its path if it is not in the default place.
"""
import os
from pathlib import Path

import photonforge as pf

NAME = "siepic_ebeam"
WAVELENGTH = 1.55
ROUTE_SPEC = "TE_1550_500"
CORE = ("Si",)
ALT_CORE = ("Si Slab",)
CONNECT = ("Si", "Si Slab")
DEVICE_LAYER = "DevRec"
PIN_LAYER = "PinRec"
PIN_LAYER_E = "PinRecM"
ELECTRICAL = {"conductors": ["M2_router"], "vias": []}
COLORS = {"Si": "#2b6cb0", "Si Slab": "#9f7aea", "M1_heater": "#dd6b20", "M2_router": "#d69e2e", "M_Open": "#718096",
          "DevRec": "#a0aec0", "PinRec": "#e53e3e", "PinRecM": "#805ad5", "Text": "#4a5568",
          "Floor Plan-Not Fabricated": "#cbd5e0"}
BASIC_RULES = {"Si": {"width": 0.06, "space": 0.06}}


def technology():
    import siepic_forge as se
    tech = se.ebeam()
    pf.config.default_technology = tech
    return tech


def drc_deck():
    """The SiEPIC deck is written for the KLayout window (it reports on the open layout). This makes a batch copy:
    the same rules, with source($gdsfile) and report(..., $resultsfile). The installed deck does not change."""
    import tempfile
    import xml.etree.ElementTree as ET
    env = os.environ.get("SIEPIC_EBEAM_DRC")
    for p in ([env] if env else []) + [str(Path.home() / ".klayout/salt/siepic_ebeam_pdk/EBeam/drc/SiEPIC_EBeam_DRC.lydrc")]:
        if p and Path(p).exists():
            body = ET.parse(p).getroot().findtext("text") if p.endswith(".lydrc") else Path(p).read_text()
            head = 'report("SiEPIC-EBeam-PDK DRC")'
            if head not in body:
                return p
            body = body.replace(head, 'source($gdsfile)\nreport("SiEPIC-EBeam-PDK DRC", $resultsfile)', 1)
            out = Path(tempfile.gettempdir()) / "needle_review" / "siepic_ebeam_batch.drc"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body)
            return str(out)
    return None


def is_device(name):
    return False
