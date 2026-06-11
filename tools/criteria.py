"""
Figure of merit + hard gates for one packed test chip.

FOM shape mirrors the autophotonicdesign routing branch: hard gates must ALL pass, then the
primary objective ranks. Objective = DoE coverage (structures placed + routed + clean), the
inverse of the area-cost problem.

Hard gates:
  fits_in_die      - every requested structure landed in a single die-sized bin (none spilled)
  min_dim_ok       - die narrow dimension >= 2 mm (user constraint)
  area_ok          - die area <= the MPW area-tier budget (default 25 mm^2)
  collisions_clean - no inter-structure overlap, no waveguide crossing, no M2-over-M1 heatsink
                     crossing  (tools/validation.check_collisions)
  drc_pass         - no HARD KLayout SiEPIC DRC violations  (tools/validation.klayout_drc;
                     skipped-gate if KLayout is unavailable)
  orientation_ok   - every placed site shares ONE pose (same rotation, no reflection) so the
                     wafer prober's fiber array + probe card land the same way at every site
                     (tools/validation.orientation_consistent)

Primary objective (maximize): n_placed. Tie-breaker: fill_fraction.
"""
from dataclasses import dataclass, field


@dataclass
class ChipScore:
    n_placed: int
    n_total: int
    n_spilled: int
    die_w_um: float
    die_h_um: float
    die_area_mm2: float
    fill_fraction: float
    # gates
    fits_in_die: bool
    min_dim_ok: bool
    area_ok: bool
    collisions_clean: bool
    drc_pass: bool
    orientation_ok: bool = True
    # detail
    wg_crossing_um2: float = 0.0
    inter_structure_um2: float = 0.0
    m2_over_m1_um2: float = 0.0
    orientation_poses: int = 1
    drc_available: bool = False
    drc_violations: dict = field(default_factory=dict)
    drc_warnings: dict = field(default_factory=dict)

    @property
    def passes(self):
        return (self.fits_in_die and self.min_dim_ok and self.area_ok
                and self.collisions_clean and self.drc_pass and self.orientation_ok)

    @property
    def fom(self):
        """Higher is better; any gate failure zeros it so gates are never traded away."""
        if not self.passes:
            return 0.0
        return self.n_placed + 0.5 * self.fill_fraction

    def summary(self):
        flag = "PASS" if self.passes else "FAIL"
        g = []
        if not self.fits_in_die: g.append(f"spilled={self.n_spilled}")
        if not self.min_dim_ok: g.append("min_dim<2mm")
        if not self.area_ok: g.append(f"area={self.die_area_mm2:.1f}>budget")
        if not self.collisions_clean:
            g.append(f"collide(inter={self.inter_structure_um2},wg={self.wg_crossing_um2},"
                     f"m2/m1={self.m2_over_m1_um2})")
        if not self.drc_pass: g.append(f"DRC={self.drc_violations}")
        if not self.orientation_ok: g.append(f"orient={self.orientation_poses}poses")
        warn = f" warn={self.drc_warnings}" if self.drc_warnings else ""
        return (f"[{flag}] FOM={self.fom:.2f} placed={self.n_placed}/{self.n_total} "
                f"die={self.die_w_um/1000:.2f}x{self.die_h_um/1000:.2f}mm "
                f"({self.die_area_mm2:.1f}mm2) fill={self.fill_fraction*100:.1f}% "
                + (" ".join(g) if g else "all gates clean") + warn)


def score_chip(chip, metrics, collisions, drc, orientation=None, *,
               area_budget_mm2=25.0, min_dim_um=2000.0):
    return ChipScore(
        n_placed=metrics["n_placed"],
        n_total=metrics["n_total"],
        n_spilled=metrics["n_spilled"],
        die_w_um=metrics["die_w_um"],
        die_h_um=metrics["die_h_um"],
        die_area_mm2=metrics["die_area_mm2"],
        fill_fraction=metrics["fill_fraction"],
        fits_in_die=(metrics["n_spilled"] == 0),
        min_dim_ok=(min(metrics["die_w_um"], metrics["die_h_um"]) >= min_dim_um - 1e-6),
        area_ok=(metrics["die_area_mm2"] <= area_budget_mm2 + 1e-6),
        collisions_clean=collisions.clean,
        drc_pass=drc.passes,
        orientation_ok=(orientation.consistent if orientation is not None else True),
        wg_crossing_um2=collisions.wg_crossing_um2,
        inter_structure_um2=collisions.inter_structure_um2,
        m2_over_m1_um2=collisions.m2_over_m1_um2,
        orientation_poses=(orientation.n_distinct if orientation is not None else 1),
        drc_available=drc.available,
        drc_violations=dict(drc.counts),
        drc_warnings=dict(drc.warnings),
    )


# ---- standard MPW die-area tiers (mm^2); the die area is the fixed budget ----
MPW_AREA_TIERS_MM2 = (25, 50, 100)


def mpw_area_tier(area_mm2):
    """Smallest standard MPW die-area tier (mm^2) that contains `area_mm2`."""
    for tier in MPW_AREA_TIERS_MM2:
        if area_mm2 <= tier + 1e-6:
            return tier
    return None
