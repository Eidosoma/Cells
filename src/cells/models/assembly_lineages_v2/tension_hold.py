"""cells.operator.tension_hold@1: a membrane tension held over a declared interval, an applied protocol
(FR-31, Phase A; docs/VESICLE_PORES_LAWS.md §3, tagged pores-laws-sheet-registered-2026-11-22;
the lead's rulings of 22 November 2026).

**The declaration** is the experiment's, as a pipette's suction is the experiment's and not the
vesicle's: `tension_holds = [{index, sigma_N_per_m, start_s, end_s}]`. Every living vesicle's
membrane is held at σ (N/m) from start_s to end_s (s), whatever its counts. Its physical basis is
the micropipette (Kwok and Evans 1981, Eq. 2; Evans and Smith 2011, §2.3 and Appendix A).
- **One hold in Phase A** (the sheet's "one tension per world"): a second hold is refused, and so
  an overlapping one. The index, the hold axis of its work column and its payer stay, so stepped
  holds and ramps can come later without reshaping the record.
- **The cross-checks** run once the world and the experiment are both parsed (spec.parse):
  - the world declares the pore law (pore_nucleation.py), the hold's only reader in Phase A, and
    a world that declares the pore law declares a hold, unless its lumen is osmotic: its tension
    then comes from F, with σ_max ≤ σ_β/4, and the clock is on the device (OL6 S4,
    pore_device.py);
  - a world with a hold refuses `lumen_volume: osmotic`, so the hazard reads σ_hold and nothing
    else (the sheet's §3);
  - σ ≤ σ_β/4, with σ_β = πΓ²/(k_B·T) from the world's line tension and temperature (the sheet's
    §2: σ_β ≫ σ; declared, uncited).

**A work source** (U2, D199): the hold is not passive. At each pore's opening to its critical
radius r_c = Γ/σ it does w = σ·πr_c² = πΓ²/σ, booked in its own column, `tension_hold_work_kT`
[row, hold], and paid by `source:tension_hold/<index>`, as a shear's work is paid by its schedule.
It books no work for a pore's growth past r_c, which an exact-event world does not represent
(D287: rupture only there). It draws nothing.

**The interval** is [start_s, end_s): a vesicle's internal time H grows at its rate k_v(σ) while
the hold is in force, and it ruptures where H reaches its threshold, at t* ≤ end_s and t* within
the horizon (the clock: pore_nucleation.py's formulas, the sheet's §5).
"""

from dataclasses import dataclass

from cells.definitions.specs import ConfigError, bounded_integer, finite_number
from cells.models.assembly_lineages_v2 import MODEL_ID, PORE_NUCLEATION, TENSION_HOLD
from cells.models.assembly_lineages_v2.interfaces import AssemblyOperator
from cells.modules import Citation, CitedWork

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import operators as operator_registry

KEYS = {"index", "sigma_N_per_m", "start_s", "end_s"}
SIGMA_BETA_FRACTION = 0.25  # σ ≤ σ_β/4 (the sheet's §2; declared, uncited)


@dataclass(frozen=True)
class Hold:
    """One declared hold: its index (its payer's and its column's name), σ and its interval."""

    index: int
    sigma: float  # N/m
    start: float  # s
    end: float  # s


def parse(raw):
    """The experiment's `tension_holds`: (Hold,), one in Phase A."""
    if type(raw) is not list or not raw:
        raise ConfigError(
            "experiment: tension_holds is a non-empty list of {index, sigma_N_per_m, start_s, "
            "end_s}"
        )
    if len(raw) > 1:
        raise ConfigError(
            "experiment: tension_holds: Phase A holds one tension per world, so a second hold, "
            "or an overlapping one, is refused (the lead's ruling of 22 November 2026)"
        )
    entry = raw[0]
    if not isinstance(entry, dict) or set(entry) != KEYS:
        found = sorted(entry) if isinstance(entry, dict) else type(entry).__name__
        raise ConfigError(f"experiment: a tension hold's keys are {sorted(KEYS)}, not {found}")
    index = bounded_integer(entry["index"], "experiment: a tension hold's index", minimum=0)
    sigma = finite_number(entry["sigma_N_per_m"], "experiment: a hold's sigma_N_per_m",
                          positive=True)  # fmt: skip
    start = finite_number(entry["start_s"], "experiment: a hold's start_s")
    end = finite_number(entry["end_s"], "experiment: a hold's end_s")
    if not end > start:
        raise ConfigError(
            f"experiment: a hold's end_s ({end:g} s) must come after its start_s ({start:g} s)"
        )
    return (Hold(index, sigma, start, end),)


def to_dict(holds):
    return [{"index": h.index, "sigma_N_per_m": h.sigma, "start_s": h.start, "end_s": h.end}
            for h in holds]  # fmt: skip


def cross_checks(world, holds):
    """The refusals that read both the world and the experiment (module docstring)."""
    from cells.models.assembly_lineages_v2 import pore_nucleation

    pores = world.hazard is not None and world.hazard[0] == PORE_NUCLEATION
    if pores and not holds and world.conventions.lumen_volume == "osmotic":
        sigma_from_f(world)  # OL6 S4: σ from F, the clock on the device (pore_device.py)
        return
    if pores and not holds:
        raise ConfigError(
            f"world: hazard: {PORE_NUCLEATION} reads a held tension, and in Phase A the only "
            "tension is a hold: the experiment declares one in tension_holds"
        )
    if not holds:
        return
    if not pores:
        raise ConfigError(
            f"experiment: tension_holds: a hold's only reader in Phase A is the pore law, so the "
            f"world declares {PORE_NUCLEATION} as its hazard"
        )
    if world.conventions.lumen_volume == "osmotic":
        raise ConfigError(
            "experiment: tension_holds: a world with a hold refuses lumen_volume osmotic, so the "
            "pore law reads the held tension and nothing else (the sheet's §3)"
        )
    _, gamma, _, _ = pore_nucleation.parameters(world)
    beta = pore_nucleation.sigma_beta(gamma, world.units.temperature_K)
    for h in holds:
        if h.sigma > SIGMA_BETA_FRACTION * beta:
            raise ConfigError(
                f"experiment: hold {h.index}'s sigma, {h.sigma:g} N/m, is beyond sigma_beta/4 = "
                f"{SIGMA_BETA_FRACTION * beta:.6g} N/m (sigma_beta = pi Gamma^2/(k_B T) at the "
                "world's line tension and temperature): the law needs sigma_beta >> sigma (the "
                "sheet's §2)"
            )


def sigma_from_f(world):
    """OL6 S4: a pore world with no hold takes its tension from F, the osmotic lumen's, which
    reaches σ_max before the vesicle lyses: σ_max ≤ σ_β/4 keeps the law in its domain on every
    trajectory that has not lysed (the sheet's §2; the OL6 design note's §3.5)."""
    from cells.models.assembly_lineages_v2 import pore_nucleation

    _, gamma, _, _ = pore_nucleation.parameters(world)
    beta = pore_nucleation.sigma_beta(gamma, world.units.temperature_K)
    sigma_max = world.geometry[1]["sigma_max_N_per_m"][0]
    if not sigma_max <= SIGMA_BETA_FRACTION * beta:
        raise ConfigError(
            f"world: hazard: with sigma from F the tension reaches sigma_max = {sigma_max:g} N/m, "
            f"beyond sigma_beta/4 = {SIGMA_BETA_FRACTION * beta:.6g} N/m (sigma_beta = pi Gamma^2/"
            "(k_B T) at the world's line tension and temperature): the law needs sigma_beta >> "
            "sigma (the sheet's §2)"
        )


def payer(hold):
    return f"source:tension_hold/{hold.index}"


CONTRACT = {
    "declaration": "experiment.tension_holds = [{index, sigma_N_per_m, start_s, end_s}]; one hold "
    "in Phase A (a second, or an overlapping one, is refused)",
    "holds": "every living vesicle's membrane at sigma over [start_s, end_s), whatever its counts",
    "requires": "the world's pore law (its only reader in Phase A) and no osmotic lumen; sigma <= "
    "sigma_beta/4",
    "draw": "none",
    "booking": "at each pore's opening w = sigma pi r_c^2 = pi Gamma^2/sigma, in "
    "tension_hold_work_kT's column for the hold, paid by source:tension_hold/<index>; no work for "
    "a pore's growth past r_c (rupture only in an exact-event world)",
}

OPERATOR = operator_registry.BUILTIN.register(
    AssemblyOperator(
        TENSION_HOLD,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/VESICLE_PORES_LAWS.md §3, tagged pores-laws-sheet-registered-2026-11-22 (D287; "
            "the lead's rulings of 22 November 2026); Kwok and Evans (1981), Biophys J 35:637, "
            "Eq. 2; Evans and Smith (2011), §2.3 and Appendix A",
            "a tension clamp: a micropipette's suction holds the membrane's tension, sigma = dP "
            "R_p / [2 (1 - R_p/R_v)], held fixed until rupture",
            "no numbers taken: the tension and its interval are the experiment's",
            (
                "the tension is declared, not computed from a pipette's geometry",
                "a pipette holds sigma only approximately once a pore opens (Moroz and Nelson "
                "1997); the hold here is exact",
            ),
            (
                CitedWork(
                    ("R. Kwok", "E. Evans"),
                    1981,
                    "Thermoelasticity of large lecithin bilayer vesicles",
                    doi="10.1016/S0006-3495(81)84817-5",
                ),
            ),
        ),
        test="tests/unit/test_assembly_lineages_v2_pores.py::"
        "test_a_pore_world_parses_round_trips_and_names_its_pieces",
        reads="the vesicles' areas (the pore law's) and the declared tension",
        writes="the membrane's tension, held at sigma over [start_s, end_s)",
        energy_role="work: sigma pi r_c^2 at each pore's opening, from the hold (its payer)",
        rules={"holds": ["one per world in Phase A"], "interval": ["[start_s, end_s)"]},
        stream="none: a hold draws nothing",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()
assert OPERATOR.operator_id == TENSION_HOLD
