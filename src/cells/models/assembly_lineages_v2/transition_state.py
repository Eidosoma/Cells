"""cells.transition_state_factor@1: catalysis as a factor on the common state (OL1; §2.4 b, §0.2a).

A catalyst that stabilises a step's transition state by ΔΔG‡ (k_BT) multiplies both directions'
rates by the same factor, so the equilibrium is unchanged (transition-state theory; IUPAC's
definition of a catalyst). For single-contact stabilisation in an ideal mixture, a step r's factor
on the pair's common state m = min(n, n + ν) is

    g_r(m) = Σ_j x_j(m) e^ΔΔG‡_rj = 1 + Σ_j β_rj x_j(m),   β_rj = e^ΔΔG‡_rj − 1 > −1,

with x_j(m) = m_j/N_cat(m) the catalysts' fractions in the catalysing phase. Inhibition is a
negative ΔΔG‡ (β in (−1, 0)); g stays positive.

- **Evaluated on m only.** The factor never sees a direction, so a moving molecule never catalyses
  its own reverse step: GARD's pair-consistent form is this law's special case (β from GARD's
  matrix, the membrane as the catalysing phase). The form evaluated at each direction's own state
  (GARD's single-event form) cannot be declared here.
- **The catalysing phase** (§0.2a): the membrane only in OL1. A dilute catalysing phase is refused
  until a declared meaning exists, since its fraction would have to include the solvent.
- **Boundary** (`empty_catalyst_phase: uncatalysed`): g = 1 where the catalysing phase is empty at
  m.

Data, per world (`rate_factor`): `{"law": "cells.transition_state_factor@1", "catalysing_phase":
"membrane", "entries": [{"catalyst": "B", "step": "join_A", "ddG_kT": 0.5}, ...]}`, a sparse list,
each (catalyst, step) at most once, generated in validation/ with a recorded seed and law when it is
large (§2.4).

Incremental state: z_r = Σ_j β_rj n_j over the membrane (one entry per step), computed exactly by a
serial fold at the founder and updated by one column of β per entry moved. At the common state of a
direction, z_r(m) = z_r(n) − Σ_e β_r,e (n_e − m_e) and N_cat(m) = N − r*.
"""

import math

import numpy as np

from cells.definitions.specs import ConfigError, require_fields
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import MODEL_ID, TRANSITION_STATE
from cells.models.assembly_lineages_v2.interfaces import CATALYSING, RateFactorLaw
from cells.models.assembly_lineages_v2.mass_action import entry_sum
from cells.modules import Citation, CitedWork

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_kernel.py::"
    "test_catalysis_is_kinetic_only_and_a_factor_at_each_direction_is_caught"
)
DDG_DOMAIN = (-30.0, 80.0)  # k_BT: g stays clear of rounding below; the event domain above.


def parse_data(raw, world):
    require_fields(raw, {"law", "catalysing_phase", "entries"}, "world: rate_factor")
    if raw["catalysing_phase"] not in CATALYSING:
        raise ConfigError(
            f"world: rate_factor: the catalysing phase is the membrane in OL1 (§0.2a), not "
            f"{raw['catalysing_phase']!r}: a dilute phase's fraction would have to include the "
            "solvent, and no meaning for it is declared"
        )
    entries = raw["entries"]
    if type(entries) is not list or not entries:
        raise ConfigError("world: rate_factor: entries is a non-empty list")
    catalysts = {p.species for p in world.places if p.phase == raw["catalysing_phase"]}
    steps = {s.id for s in world.steps}
    seen, out = set(), []
    for entry in entries:
        require_fields(entry, {"catalyst", "step", "ddG_kT"}, "world: rate_factor: an entry")
        catalyst, step = entry["catalyst"], entry["step"]
        if catalyst not in catalysts:
            raise ConfigError(
                f"world: rate_factor: catalyst {catalyst!r} is not a species of the "
                f"{raw['catalysing_phase']}"
            )
        if step not in steps:
            raise ConfigError(f"world: rate_factor: step {step!r} is not a declared step")
        if (catalyst, step) in seen:
            raise ConfigError(f"world: rate_factor: ({catalyst}, {step}) is listed twice")
        seen.add((catalyst, step))
        value = entry["ddG_kT"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ConfigError(f"world: rate_factor: ({catalyst}, {step})'s ddG_kT is finite")
        if not DDG_DOMAIN[0] <= float(value) <= DDG_DOMAIN[1]:
            raise ConfigError(
                f"world: rate_factor: ({catalyst}, {step})'s ddG_kT is in [{DDG_DOMAIN[0]}, "
                f"{DDG_DOMAIN[1]}]: the event domain's bound above (|dF/kT| <= 80, §2.1), and "
                "below "
                "it an inhibition so strong that g would be lost in rounding (a factor g <= 0 is "
                "refused, §2.4)"
            )
        out.append((catalyst, step, float(value)))
    return {"catalysing_phase": raw["catalysing_phase"], "entries": tuple(out)}


def data_to_dict(data):
    return {
        "catalysing_phase": data["catalysing_phase"],
        "entries": [{"catalyst": c, "step": s, "ddG_kT": v} for c, s, v in data["entries"]],
    }


def layout(data, world, steps, places):
    """(beta [R, P],): β_rj = e^ΔΔG‡ − 1 at the catalyst's membrane place, zero elsewhere."""
    beta = np.zeros((steps, places), dtype=np.float64)
    step_index = {s.id: i for i, s in enumerate(world.steps)}
    place_index = {
        p.species: i for i, p in enumerate(world.places) if p.phase == data["catalysing_phase"]
    }
    for catalyst, step, value in data["entries"]:
        beta[step_index[step], place_index[catalyst]] = math.expm1(value)
    return (beta,)


def state(counts, factor_layout, xp):
    """z = β n, exactly: for each step, a serial fold over the places in place order."""
    (beta,) = factor_layout
    return folds.total((beta * counts.astype(np.float64)[None, :]).T, xp)


def update(z, factor_layout, places, change, xp):
    """z after one step: places [K] and change [K] at the fired step's entries."""
    (beta,) = factor_layout
    return z + folds.total((beta[:, places] * change.astype(np.float64)[None, :]).T, xp)


def log_factor(z, factor_layout, view, xp):
    """ln g_r(m) for each step's direction (view), at the pair's common state."""
    (beta,) = factor_layout
    at = xp.take_along_axis(beta, view.places, axis=1)  # β_r at each entry's place: [R, K]
    consumed = xp.where(view.membrane, view.consumed, 0)
    z_m = z - entry_sum(at * consumed.astype(np.float64), xp)
    n_m = (view.membrane_total - entry_sum(consumed, xp)).astype(np.float64)
    g = xp.where(n_m > 0, 1.0 + z_m / xp.where(n_m > 0, n_m, 1.0), 1.0)
    # g > 0 wherever the direction can fire (β > −1); where it cannot, m is not a state and g is
    # not used: −inf there keeps the direction's −inf (never a nan).
    return xp.where(g > 0, xp.log(xp.where(g > 0, g, 1.0)), -xp.inf)


FORMULAS = {
    "g_r(m)": "1 + sum_j beta_rj x_j(m), x_j = m_j / N_cat(m), beta_rj = exp(ddG_rj) - 1 > -1; "
    "the same factor for both directions of the pair",
    "common_state": "m = min(n, n + nu) elementwise: z_r(m) = z_r(n) - sum_e beta_r,e (n_e - m_e), "
    "N_cat(m) = N - r*",
    "empty_catalyst_phase": "g = 1 where the catalysing phase is empty at m (uncatalysed)",
    "catalysing_phase": "the membrane only (OL1, sec. 0.2a)",
    "state": "z = beta n, exactly at the founder; one column of beta per entry moved",
}

LAW = law_registry.BUILTIN.register(
    RateFactorLaw(
        "cells.transition_state_factor@1",
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Eyring (1935), J Chem Phys 3:107 (transition-state theory); "
            "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §2.4 (b), §0.2a",
            "a catalyst lowers the transition state's free energy by ddG, raising both "
            "directions' rates by the same factor",
            "no numbers taken",
            (
                "single-contact stabilisation in an ideal mixture, evaluated on the pair's common "
                "state m: g = 1 + sum beta x(m), beta = exp(ddG) - 1",
            ),
            (
                CitedWork(
                    ("H. Eyring",),
                    1935,
                    "The activated complex in chemical reactions",
                    doi="10.1063/1.1749604",
                ),
            ),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        evaluated_on="common_state",
        catalysing_phases=CATALYSING,
        data=("catalysing_phase", "entries"),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        layout=layout,
        state=state,
        update=update,
        log_factor=log_factor,
        formulas=FORMULAS,
    )
)
assert LAW.law_id == TRANSITION_STATE
