"""charge_sim.py — Build the Tidy3D HeatChargeSimulation from IMPLANTS.

Pattern matches the SISCAP TWModulator_Simple_latest notebook and the
Yong campaign's build_junction.py:

  - Every silicon structure (core, slab, contact pads) shares one
    MultiPhysicsMedium whose charge model is `intrinsic_si.charge.updated_copy(
        N_a=[GaussianDoping(...), ...], N_d=[GaussianDoping(...), ...])`.
  - Each `IMPLANTS` entry becomes a GaussianDoping(width=0.001, ref_con=1e6)
    — the Tidy3D idiom for a step-function box.
  - Boundary conditions: P contact at 0 V, N contact swept over V_SWEEP.
  - Mesh refinement at every implant y-edge inside (and just outside) the rib.
"""
from __future__ import annotations

from typing import Sequence

from .doping_builders import DopingRegion, geometry_bounds, merge_overlapping_regions


def build_charge_simulation(
    implants: Sequence[DopingRegion],
    geometry: dict,
    v_sweep: Sequence[float],
    wavelength_um: float = 1.31,
    mesh_res_nm: float = 7.0,
    mesh_bulk_factor: int = 20,
):
    """Return (charge_sim, handles).

    Imports Tidy3D locally so the rest of the scaffolding stays import-free.
    """
    import tidy3d as td

    h_core = geometry["h_core"]
    h_slab = geometry["h_slab"]
    w_core = geometry["w_core"]
    w_clearance = geometry["w_clearance"]
    w_contact = geometry["w_contact"]

    b = geometry_bounds(**geometry)
    w_tot = b["w_tot"]

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------
    intrinsic_si = td.material_library["cSi"].variants["Si_MultiPhysics"].medium

    # Resolve last-wins semantics into non-overlapping rectangles so that
    # Tidy3D's additive Nd/Na model yields the intended doping profile.
    # Without this, an opposite-polarity "island" inside an outer region
    # becomes compensated (~intrinsic) instead of carving through it.
    implants = merge_overlapping_regions(implants)

    donors, acceptors = [], []
    for r in implants:
        gd = td.GaussianDoping.from_bounds(
            rmin=[-1e3, r.ymin, r.zmin],
            rmax=[+1e3, r.ymax, r.zmax],
            concentration=float(r.concentration),
            ref_con=1e6,
            width=0.001,
            source="zmax",
        )
        (donors if r.kind == "donor" else acceptors).append(gd)

    Si_2D = td.MultiPhysicsMedium(
        charge=intrinsic_si.charge.updated_copy(N_d=donors, N_a=acceptors),
        name="Si_doping",
    )
    SiO2 = td.MultiPhysicsMedium(
        optical=td.Medium(permittivity=1.447 ** 2),
        charge=td.ChargeInsulatorMedium(permittivity=3.9),
        name="SiO2",
    )
    al = td.MultiPhysicsMedium(
        charge=td.ChargeConductorMedium(conductivity=38),
        name="Aluminium",
    )
    air = td.MultiPhysicsMedium(heat=td.FluidSpec(), name="air")

    # ------------------------------------------------------------------
    # Structures: core + slab + full-height silicon contact pads + Al contacts
    # ------------------------------------------------------------------
    core = td.Structure(
        geometry=td.Box(center=(0, 0, h_core / 2),
                        size=(td.inf, w_core, h_core)),
        medium=Si_2D, name="core",
    )
    slab = td.Structure(
        geometry=td.Box(center=(0, 0, h_slab / 2),
                        size=(td.inf, w_tot, h_slab)),
        medium=Si_2D, name="slab",
    )
    # Silicon "pads" directly under each metal contact (full rib height so the
    # ohmic contact has vertical extent to collect current).
    y_pad_p = (b["y_pp_L"] + b["y_slab_L"]) / 2
    y_pad_n = (b["y_slab_R"] + b["y_pp_R"]) / 2
    pad_p = td.Structure(
        geometry=td.Box(center=(0, y_pad_p, h_core / 2),
                        size=(td.inf, w_contact, h_core)),
        medium=Si_2D, name="pad_p",
    )
    pad_n = td.Structure(
        geometry=td.Box(center=(0, y_pad_n, h_core / 2),
                        size=(td.inf, w_contact, h_core)),
        medium=Si_2D, name="pad_n",
    )
    # Metal contacts on top of the pads
    h_metal = 0.25
    contact_p = td.Structure(
        geometry=td.Box(center=(0, y_pad_p, h_core + h_metal / 2),
                        size=(td.inf, w_contact, h_metal)),
        medium=al, name="contact_p",
    )
    contact_n = td.Structure(
        geometry=td.Box(center=(0, y_pad_n, h_core + h_metal / 2),
                        size=(td.inf, w_contact, h_metal)),
        medium=al, name="contact_n",
    )
    # Oxide cladding covers the whole simulation domain.
    oxide_half_thick = 2.5
    oxide = td.Structure(
        geometry=td.Box(center=(0, 0, 0),
                        size=(td.inf, td.inf, 2 * oxide_half_thick)),
        medium=SiO2, name="oxide",
    )
    structures = [oxide, core, slab, pad_p, pad_n, contact_p, contact_n]

    # ------------------------------------------------------------------
    # Monitors
    # ------------------------------------------------------------------
    carrier_monitor = td.SteadyFreeCarrierMonitor(
        center=(0, 0, 0), size=(td.inf, td.inf, td.inf),
        name="carriers", unstructured=True,
    )
    capacitance_monitor = td.SteadyCapacitanceMonitor(
        center=(0, 0, h_core / 2 + 0.05),
        size=(0, td.inf, td.inf),
        name="capacitance_mnt",
    )

    # ------------------------------------------------------------------
    # Mesh refinement at every implant y-edge inside/near the rib
    # ------------------------------------------------------------------
    res = mesh_res_nm * 1e-3        # nm -> um
    refs = [
        td.GridRefinementRegion(
            center=(0, 0, h_core / 2),
            size=(0, w_core, h_core),
            dl_internal=res * 0.5,
            transition_thickness=res * 60,
        ),
    ]
    y_edges = set()
    for r in implants:
        y_edges.add(round(r.ymin, 6))
        y_edges.add(round(r.ymax, 6))
    for yv in sorted(y_edges):
        if -w_core / 2 - 0.2 < yv < w_core / 2 + 0.2:
            refs.append(td.GridRefinementRegion(
                center=(0, yv, h_core / 2),
                size=(0, 0.03, h_core),
                dl_internal=res * 0.4,
                transition_thickness=res * 20,
            ))

    mesh = td.DistanceUnstructuredGrid(
        dl_interface=res * 1.2,
        dl_bulk=res * mesh_bulk_factor,
        distance_interface=res,
        distance_bulk=res * 40,
        relative_min_dl=0,
        sampling=500,
        non_refined_structures=[oxide.name],
        mesh_refinements=refs,
    )

    # ------------------------------------------------------------------
    # Boundary conditions — P grounded, N swept over v_sweep (reverse bias)
    # ------------------------------------------------------------------
    bc_p = td.HeatChargeBoundarySpec(
        condition=td.VoltageBC(source=td.DCVoltageSource(voltage=0.0)),
        placement=td.StructureBoundary(structure=contact_p.name),
    )
    bc_n = td.HeatChargeBoundarySpec(
        condition=td.VoltageBC(
            source=td.DCVoltageSource(voltage=list(map(float, v_sweep)))),
        placement=td.StructureBoundary(structure=contact_n.name),
    )

    conv = td.ChargeToleranceSpec(
        rel_tol=1e-4, abs_tol=1e5, max_iters=800, ramp_up_iters=20,
    )
    analysis = td.IsothermalSteadyChargeDCAnalysis(
        temperature=300, convergence_dv=10, tolerance_settings=conv,
    )

    charge_sim = td.HeatChargeSimulation(
        sources=[],
        monitors=[carrier_monitor, capacitance_monitor],
        analysis_spec=analysis,
        center=(0, 0, 0),
        size=(0, max(10.0, 2 * w_tot), 5.0),
        structures=structures,
        medium=air,
        boundary_spec=[bc_p, bc_n],
        grid_spec=mesh,
        symmetry=(0, 0, 0),
    )

    handles = dict(
        core=core, slab=slab, pad_p=pad_p, pad_n=pad_n,
        contact_p=contact_p, contact_n=contact_n,
        oxide=oxide, Si_2D=Si_2D, SiO2=SiO2,
        carrier_monitor=carrier_monitor,
        capacitance_monitor=capacitance_monitor,
        w_tot=w_tot,
        freq0=td.C_0 / wavelength_um,
    )
    return charge_sim, handles
