"""PDK adapters. One file per PDK, with the same names in each file.

The review tools and the planter use only these names, so a new PDK needs only a new file:

    NAME             str, the adapter name (the file name)
    WAVELENGTH       float, um, the design wavelength
    ROUTE_SPEC       str, the port spec of the routes (gives the waveguide cross-section)
    CORE             tuple of layer names that carry the light in the routes
    ALT_CORE         tuple of other optical layers (partial etch, slab), or ()
    CONNECT          tuple of layers that join an optical net (a rib slab that runs under many routes
                     must not be one of them)
    DEVICE_LAYER     layer name that marks a device cell (like DevRec), or None
    PIN_LAYER        layer name of the optical pin markers (like PinRec), or None
    PIN_LAYER_E      layer name of the electrical pin markers, or None
    ELECTRICAL       {"conductors": [layer, ...], "vias": [(via layer, (lower layers), (upper layers)), ...]};
                     a heater is a resistor body, not a conductor, so its two ends stay two nets
    COLORS           {layer name: color} for pictures
    BASIC_RULES      {layer name: {"width": um, "space": um}}, the fallback check when there is no DRC deck
    technology()     -> photonforge.Technology
    drc_deck()       -> path of a KLayout DRC deck, or None
    is_device(name)  -> True if a cell with this name is a device (used only when DEVICE_LAYER is None)
"""
import importlib


def load(name):
    return importlib.import_module(f"pdks.{name}")
