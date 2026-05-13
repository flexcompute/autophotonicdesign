"""
Projector circuit + bondpads, geometry-only.

This is stage 1 of the quantum-chip autorouting experiment. We load the
components from the Quantum_Chip_Components notebook (inlined here with
hardcoded n_eff/n_group so no mode solvers run), assemble the full
projector_circuit, and place bond pads — but DO NOT draw any routes.

Stage 2 will hand the bondpad↔terminal pairs to PFRoutingArena.
"""
import warnings
warnings.filterwarnings("ignore")

import os
import time
import numpy as np
import photonforge as pf
import photonforge.typing as pft
import siepic_forge as siepic
from photonforge.live_viewer import LiveViewer
from scipy.interpolate import make_interp_spline

os.chdir(os.path.dirname(os.path.abspath(__file__)))

VIEWER_PORT = 8765

# Keep SVG visualization clean — suppress all label rendering
pf.config.svg_labels = False
pf.config.svg_port_names = False
pf.config.svg_reference_names = False
pf.config.svg_reference_port_names = False
pf.config.svg_reference_labels = False

# ── Technology ────────────────────────────────────────────────────────
tech = siepic.ebeam(si_thickness=0.26, bottom_oxide_thickness=1.0, top_oxide_thickness=1.0)
pf.config.default_technology = tech
bend_radius = 10.0
pf.config.default_kwargs = {"port_spec": "TE_1550_450", "radius": bend_radius}

STRIP_TE_1550_450 = pf.PortSpec(
    description="Strip TE 1550 nm, w=450 nm", width=2,
    limits=(-0.99, 1.25), num_modes=1, added_solver_modes=0,
    polarization="", target_neff=3.5, path_profiles=[(0.45, 0, (1, 0))],
)
tech.add_port("TE_1550_450", STRIP_TE_1550_450)

wavelengths = np.linspace(1.53, 1.57, 101)
freq0 = pf.C_0 / wavelengths[len(wavelengths) // 2]
freqs = pf.C_0 / wavelengths
propagation_loss = 3.0e-4
n_eff = 2.4680        # hardcoded — skips mode solve
n_group = 4.3213      # hardcoded — skips mode solve
T_BAR = 336.06
T_CROSS = 292.97
signal_frequency = pf.C_0 / 1.53973
idler_frequency = pf.C_0 / 1.54932

# ── Components (inlined from notebook, no simulations) ────────────────
@pf.parametric_component(name_prefix="Straight WG")
def create_wg(*, port_spec="TE_1550_450", length: pft.Dimension = 100.0,
              propagation_loss: float = 3.0e-4, reference_frequency: float = freq0):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    model = pf.AnalyticWaveguideModel(n_eff=n_eff, reference_frequency=reference_frequency,
        length=length, propagation_loss=propagation_loss, n_group=n_group)
    return pf.parametric.straight(port_spec=port_spec, length=length, model=model)

@pf.parametric_component(name_prefix="Bend")
def create_bend(*, port_spec="TE_1550_450", radius: pft.Dimension = bend_radius,
                angle: float = 90.0, propagation_loss: float = 3.0e-4,
                reference_frequency: float = freq0):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    length = np.pi * radius * np.abs(angle) / 180
    model = pf.AnalyticWaveguideModel(n_eff=n_eff, reference_frequency=reference_frequency,
        length=length, propagation_loss=propagation_loss, n_group=n_group)
    return pf.parametric.bend(port_spec=port_spec, radius=radius, angle=angle, model=model)

@pf.parametric_component(name_prefix="Thermal Phase Shifter")
def thermo_optic_phase_shifter(*, port_spec="TE_1550_450", heater_length: pft.Dimension = 100.0,
    heater_width: pft.Dimension = 5.0, pad_width: pft.Dimension = 25.0,
    heater_overlap: pft.Dimension = 5.0, propagation_loss: float = 3.0e-4,
    reference_frequency: float = freq0, dn_dT: float = 1.8e-4, temperature: float = 300.0):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    model = pf.AnalyticWaveguideModel(n_eff=n_eff, reference_frequency=reference_frequency,
        length=heater_length, propagation_loss=propagation_loss, n_group=n_group,
        dn_dT=dn_dT, temperature=temperature)
    ps = pf.parametric.straight(port_spec=port_spec, length=heater_length,
                                 name="Thermal Phase Shifter", model=model)
    pad_left = pf.Path((-pad_width * 1.5, 0), width=pad_width).segment((-0.5 * pad_width, 0))
    pad_right = pad_left.copy()
    pad_right.x_min = heater_length + 0.5 * pad_width
    ps.add_terminal([pf.Terminal("M2_router", pad_left.copy()),
                      pf.Terminal("M2_router", pad_right.copy())])
    heater = (pf.Path((-0.5 * pad_width - heater_overlap, 0), pad_width)
        .segment((-0.5 * pad_width, 0), pad_width).segment((0, 0), heater_width)
        .segment((heater_length, 0), heater_width).segment((heater_length + 0.5 * pad_width, 0), pad_width)
        .segment((heater_length + 0.5 * pad_width + heater_overlap, 0), pad_width))
    ps.add("M2_router", pad_left, pad_right)
    ps.add("M1_heater", heater)
    return ps

default_widths = (0.5, 0.6, 0.95, 1.32, 1.44, 1.46, 1.466, 1.52, 1.58, 1.62, 1.76, 2.15, 0.5)

@pf.parametric_component(name_prefix="Angled Crossing")
def angled_adiabatic_crossing(*, port_spec="TE_1550_450", arm_length: pft.Dimension = 4.7,
    widths=default_widths, radius: pft.Dimension = bend_radius):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    wg_width, _ = port_spec.path_profile_for("Si")
    num_points = int(arm_length / pf.config.tolerance)
    projected_arm_length = arm_length * 2**-0.5
    arc_y = radius * 2**-0.5
    arc_x = radius - arc_y
    xp = pf.snap_to_grid(projected_arm_length + arc_x)
    yp = pf.snap_to_grid(projected_arm_length + arc_y)
    coords = np.linspace(0, projected_arm_length, len(widths))
    spline = make_interp_spline(coords, widths[::-1], k=3)
    coords = np.linspace(projected_arm_length, 0, num_points)
    widths = spline(coords)
    arm1 = pf.Path((xp, yp), wg_width)
    arm1.arc(0, -45, radius, width=(widths[0], "smooth"),
             endpoint=(projected_arm_length, projected_arm_length))
    for x, w in zip(coords[1:], widths[1:]):
        arm1.segment((x, x), w)
    arm2, arm3, arm4 = arm1.copy().mirror(), arm1.copy().rotate(180), arm1.copy().mirror().rotate(180)
    c = pf.Component("Angled Crossing")
    c.add("Si", *pf.boolean([arm1, arm2], [arm3, arm4], "+"))
    c.add_port(c.detect_ports([port_spec]))
    return c

@pf.parametric_component(name_prefix="MMI2x2")
def mmi_2x2(*, port_spec="TE_1550_450", l1: pft.Dimension = 1.0, l2: pft.Dimension = 2.4,
    l3: pft.Dimension = 1.6, w1: pft.Dimension = 1.48, w2: pft.Dimension = 1.48,
    w4: pft.Dimension = 0.50, w5: pft.Dimension = 0.70, w6: pft.Dimension = 0.20,
    sbend_length: pft.Dimension = 2.0, sbend_offset: pft.Dimension = 0.2):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    mmi = pf.Component()
    wg_width, _ = port_spec.path_profile_for("Si")
    w3 = 2 * w5 + w6
    input_up = (pf.Path((-sbend_length, (w5+w6)/2 + sbend_offset), wg_width)
        .s_bend(endpoint=(0, (w5+w6)/2), width=w4)
        .segment((l1, 0), w5, relative=True))
    input_dn = input_up.copy().mirror()
    output_up = input_up.copy().mirror(axis_endpoint=(l1+l2+l3, 1), axis_origin=(l1+l2+l3, 0))
    output_dn = output_up.copy().mirror()
    body = (pf.Path((l1, 0), w3)
        .segment((l2, 0), w1, relative=True).segment((l3, 0), w2, relative=True)
        .segment((l3, 0), w2, relative=True).segment((l2, 0), w3, relative=True))
    mmi.add("Si", input_up, input_dn, output_up, output_dn, body)
    mmi.add_port(mmi.detect_ports([port_spec]))
    return mmi

@pf.parametric_component(name_prefix="Tunable MZI")
def create_mzi(*, port_spec="TE_1550_450", heater_length: pft.Dimension = 100.0,
    propagation_loss: float = 3.0e-4, reference_frequency: float = freq0,
    dn_dT: float = 1.8e-4, heater_temp: float = 293.0, heater_width: pft.Dimension = 5.0,
    pad_width: pft.Dimension = 25.0, heater_overlap: pft.Dimension = 5.0):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    wg = create_wg(port_spec=port_spec, length=heater_length,
                   propagation_loss=propagation_loss, reference_frequency=reference_frequency)
    tps = thermo_optic_phase_shifter(port_spec=port_spec, heater_length=heater_length,
        heater_width=heater_width, pad_width=pad_width, heater_overlap=heater_overlap,
        propagation_loss=propagation_loss, reference_frequency=reference_frequency,
        dn_dT=dn_dT, temperature=heater_temp)
    sbm = pf.AnalyticWaveguideModel(n_eff=n_eff, reference_frequency=freq0,
                                      propagation_loss=propagation_loss, n_group=n_group)
    sb_up = pf.parametric.s_bend(port_spec=port_spec, length=bend_radius, offset=bend_radius, model=sbm)
    sb_dn = pf.parametric.s_bend(port_spec=port_spec, length=bend_radius, offset=-bend_radius, model=sbm)
    mmi = mmi_2x2(port_spec=port_spec)
    return pf.component_from_netlist({
        "name": "Tunable MZI",
        "instances": {"mmi_in": mmi, "mmi_out": mmi, "tps": tps, "wg": wg,
                      "sb0": sb_dn, "sb1": sb_up, "sb2": sb_up, "sb3": sb_dn},
        "connections": [(("sb0","P0"),("mmi_in","P2")),(("wg","P0"),("sb0","P1")),
                        (("sb1","P0"),("mmi_in","P3")),(("tps","P0"),("sb1","P1")),
                        (("sb2","P0"),("wg","P1")),(("sb3","P0"),("tps","P1")),
                        (("mmi_out","P1"),("sb3","P1"))],
        "ports": [("mmi_in","P0"),("mmi_in","P1"),("mmi_out","P2"),("mmi_out","P3")],
        "terminals": [("tps","T0"),("tps","T1")],
    })

@pf.parametric_component(name_prefix="Asymmetric MZI")
def create_amzi(*, port_spec="TE_1550_450", heater_length: pft.Dimension = 100.0,
    propagation_loss: float = 3.0e-4, reference_frequency: float = freq0,
    signal_frequency: float = signal_frequency, idler_frequency: float = idler_frequency,
    dn_dT: float = 1.8e-4, heater_temp: float = 305.0, heater_width: pft.Dimension = 5.0,
    pad_width: pft.Dimension = 25.0, heater_overlap: pft.Dimension = 5.0):
    if isinstance(port_spec, str):
        port_spec = pf.config.default_technology.ports[port_spec]
    fsr = 2 * np.abs(signal_frequency - idler_frequency)
    delta_L = pf.C_0 / (n_group * fsr)
    br = pf.snap_to_grid(delta_L / (2 * (np.pi - 2)))
    wg = create_wg(port_spec=port_spec, length=heater_length + 4*br,
                   propagation_loss=propagation_loss, reference_frequency=reference_frequency)
    tps = thermo_optic_phase_shifter(port_spec=port_spec, heater_length=heater_length,
        heater_width=heater_width, pad_width=pad_width, heater_overlap=heater_overlap,
        propagation_loss=propagation_loss, reference_frequency=reference_frequency,
        dn_dT=dn_dT, temperature=heater_temp)
    bend = create_bend(port_spec=port_spec, reference_frequency=reference_frequency,
                        radius=br, propagation_loss=propagation_loss)
    mmi = mmi_2x2(port_spec=port_spec)
    return pf.component_from_netlist({
        "name": "Asymmetric MZI",
        "instances": {"mmi_in": mmi, "mmi_out": mmi, "tps": tps, "wg": wg,
                       "b0": bend, "b1": bend, "b2": bend, "b3": bend},
        "connections": [(("wg","P0"),("mmi_in","P2")),(("b0","P0"),("mmi_in","P3")),
                        (("b1","P1"),("b0","P1")),(("tps","P0"),("b1","P0")),
                        (("b2","P1"),("tps","P1")),(("b3","P0"),("b2","P0")),
                        (("mmi_out","P1"),("b3","P1"))],
        "ports": [("mmi_in","P0"),("mmi_in","P1"),("mmi_out","P2"),("mmi_out","P3")],
        "terminals": [("tps","T0"),("tps","T1")],
    })

print("Building components ...", flush=True)
t0 = time.perf_counter()
angled_crossing = angled_adiabatic_crossing()
mzi = create_mzi()
amzi = create_amzi()
tps = thermo_optic_phase_shifter()
bp = siepic.component("ebeam_BondPad")
print(f"  Done in {time.perf_counter()-t0:.1f}s\n", flush=True)

# ── S-bend routing (optical) ──────────────────────────────────────────
def s_bend_route(circuit, port1, port2):
    model = pf.AnalyticWaveguideModel(n_eff=n_eff, reference_frequency=freq0,
                                        propagation_loss=propagation_loss, n_group=n_group)
    d = port2.center - port1.center
    circuit.add_reference(
        pf.parametric.s_bend(length=d[0], offset=d[1], model=model)
    ).connect("P0", port1)

# ── Projector circuit assembly ────────────────────────────────────────
print("Building projector_circuit ...", flush=True)
t0 = time.perf_counter()
n_src, period_y, period_x, trace_width = 16, 100.0, 80.0, 20.0
projector_circuit = pf.Component("Projector Circuit")
amzi_list, crossing_list, wg_list, tps_list, mzi_list = [], [], [], [], []
mzi.update(heater_temp=T_CROSS)

for i in range(n_src):
    amzi_list.append(projector_circuit.add_reference(amzi))
    amzi_list[i].y_min -= period_y * i
    p0_i = amzi_list[i].get_ports()["P0"][0]
    p2_i = amzi_list[i].get_ports()["P2"][0]
    p3_i = amzi_list[i].get_ports()["P3"][0]
    c_i = (p2_i.center[1] + p3_i.center[1]) / 2
    projector_circuit.add_port(p0_i)
    for j in range(i + 1):
        crossing_list.append(projector_circuit.add_reference(angled_crossing).rotate(90))
        crossing_list[-1].y_mid = c_i + j * period_y / 2
        crossing_list[-1].x_mid = 200 + j * period_x
        p0_j, p1_j = crossing_list[-1].get_ports()["P0"][0], crossing_list[-1].get_ports()["P1"][0]
        p2_j, p3_j = crossing_list[-1].get_ports()["P2"][0], crossing_list[-1].get_ports()["P3"][0]
        if j == 0:
            s_bend_route(projector_circuit, p3_i, p3_j)
            s_bend_route(projector_circuit, p2_i, p1_j)
        else:
            s_bend_route(projector_circuit, crossing_list[-2].get_ports()["P2"][0], p1_j)
            s_bend_route(projector_circuit, crossing_list[-(i+2)].get_ports()["P0"][0], p3_j)
        if j == i:
            wg_list.append(projector_circuit.add_reference(create_wg(length=(n_src-j)*period_x)))
            wg_list[-1].x_min = crossing_list[-1].x_max + 4*bend_radius
            wg_list[-1].y_mid = crossing_list[-1].y_max + 2*bend_radius
            s_bend_route(projector_circuit, p2_j, wg_list[-1].get_ports()["P0"][0])
            tps_list.append(projector_circuit.add_reference(tps))
            tps_list[-1].connect("P0", wg_list[-1].get_ports()["P1"][0])
        if i == n_src - 1:
            wg_list.append(projector_circuit.add_reference(create_wg(length=(n_src-j)*period_x)))
            wg_list[-1].x_min = crossing_list[-1].x_max + 4*bend_radius
            wg_list[-1].y_mid = crossing_list[-1].y_min - 2*bend_radius
            s_bend_route(projector_circuit, p0_j, wg_list[-1].get_ports()["P0"][0])
            tps_list.append(projector_circuit.add_reference(tps))
            tps_list[-1].connect("P0", wg_list[-1].get_ports()["P1"][0])

print(f"  {len(amzi_list)} AMZIs, {len(crossing_list)} crossings, {len(tps_list)} TPS")

# ── MZI tree ─────────────────────────────────────────────────────────
print("Building MZI tree ...", flush=True)
sorted_indices = sorted(range(len(tps_list)), key=lambda i: tps_list[i].origin[1], reverse=True)
previous_layer = [tps_list[idx] for idx in sorted_indices]
layer_number = 0
while len(previous_layer) > 2:
    current_layer = []
    for i in range(0, len(previous_layer), 2):
        top_ref, bottom_ref = previous_layer[i], previous_layer[i+1]
        new_mzi = projector_circuit.add_reference(mzi)
        new_mzi.y_mid = (top_ref.y_mid + bottom_ref.y_mid) / 2
        new_mzi.x_min = top_ref.x_max + period_x
        mzi_list.append(new_mzi); current_layer.append(new_mzi)
        if len(previous_layer) == 4:
            projector_circuit.add_port(new_mzi.get_ports()["P2"][0])
            projector_circuit.add_port(new_mzi.get_ports()["P3"][0])
        pk = "P1" if layer_number == 0 else "P2"
        pb = "P1" if layer_number == 0 else "P3"
        s_bend_route(projector_circuit, top_ref.get_ports()[pk][0], new_mzi.get_ports()["P1"][0])
        s_bend_route(projector_circuit, bottom_ref.get_ports()[pb][0], new_mzi.get_ports()["P0"][0])
    previous_layer = current_layer; layer_number += 1
print(f"  {len(mzi_list)} MZIs in {layer_number} layers")
print(f"  Build time: {time.perf_counter()-t0:.1f}s\n", flush=True)

# ── Demo: show the bare circuit + all 156 bondpads, no routes ────────
if __name__ == "__main__":
    y_top = amzi_list[0].y_max
    y_bot = amzi_list[-1].y_min
    y_mid = (y_top + y_bot) / 2

    print("Collecting heater terminals ...", flush=True)
    all_terms = []
    for i in range(n_src):
        for tname in ["T0", "T1"]:
            ht = amzi_list[i].get_terminals()[tname][0].center()
            all_terms.append({"label": f"AMZI[{i}].{tname}",
                              "xy": (float(ht[0]), float(ht[1])),
                              "y_ref": amzi_list[i].y_mid})
    for k, ref in enumerate(tps_list):
        terms = ref.get_terminals()
        for tname in list(terms.keys()):
            ht = terms[tname][0].center()
            all_terms.append({"label": f"TPS[{k}].{tname}",
                              "xy": (float(ht[0]), float(ht[1])),
                              "y_ref": ref.y_mid})
    for k, ref in enumerate(mzi_list):
        terms = ref.get_terminals()
        for tname in list(terms.keys()):
            ht = terms[tname][0].center()
            all_terms.append({"label": f"MZI[{k}].{tname}",
                              "xy": (float(ht[0]), float(ht[1])),
                              "y_ref": ref.y_mid})

    top_terms = sorted([t for t in all_terms if t["y_ref"] > y_mid], key=lambda t: t["xy"][0])
    bot_terms = sorted([t for t in all_terms if t["y_ref"] <= y_mid], key=lambda t: t["xy"][0])
    print(f"  {len(top_terms)} top, {len(bot_terms)} bottom, {len(all_terms)} total\n")

    bp_pad_spacing = 120.0
    bp_y_top = y_top + 1000
    bp_y_bot = y_bot - 1000
    x_start_top = top_terms[0]["xy"][0] - 500
    x_start_bot = bot_terms[0]["xy"][0] - 500

    print("Placing bond pads ...", flush=True)
    for i in range(len(top_terms)):
        projector_circuit.add(pf.Reference(bp, origin=(x_start_top + i * bp_pad_spacing, bp_y_top)))
    for i in range(len(bot_terms)):
        projector_circuit.add(pf.Reference(bp, origin=(x_start_bot + i * bp_pad_spacing, bp_y_bot)))
    print(f"  Top: {len(top_terms)} pads at y={bp_y_top:.0f}")
    print(f"  Bot: {len(bot_terms)} pads at y={bp_y_bot:.0f}\n")

    bbox = projector_circuit.bounds()
    print(f"Circuit bbox: ({bbox[0][0]:.0f}, {bbox[0][1]:.0f}) → "
          f"({bbox[1][0]:.0f}, {bbox[1][1]:.0f})")
    print(f"  width  = {bbox[1][0] - bbox[0][0]:.0f} um")
    print(f"  height = {bbox[1][1] - bbox[0][1]:.0f} um\n")

    viewer = LiveViewer(port=VIEWER_PORT)
    viewer(projector_circuit)
    print(f"LiveViewer: http://localhost:{VIEWER_PORT}")
    print("Ctrl+C to exit.")

    import signal
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
