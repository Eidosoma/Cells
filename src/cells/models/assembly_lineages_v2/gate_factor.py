"""cells.gate_factor@1: a gate's catalysis, a factor over the gate's own forms (FR-21; D244).

The design is docs/ASSEMBLY_SHELL_DESIGN.md §4.3 (option G2), and the rulings are D244 and D246.

**Why.** The transition-state factor's fractions are over every wall molecule,
x_j = m_j/N(m) (transition_state.py). In a wall that also holds binding sites, two walls that differ
only in their site count would then gate an entry at different rates, which breaks the shell's
independence from its inventory. Here the fractions are over the gate's own declared forms only:

    g_r(m) = Σ_{j ∈ gate} m_j e^ΔΔG‡_rj / Σ_{j ∈ gate} m_j        (1 where the gate is absent at m)

on the pair's common state m, with weight 1 for a form without an entry for step r. A step that
no entry names gets g = 1 exactly. The factor is the count-weighted mean of positive terms, so it
keeps its digits for any ΔΔG‡ in the domain (no cancellation; compare transition_state.py's
ill-conditioned case).

- **Evaluated on m only,** so both directions of a pair carry the same factor and the equilibrium
  is unchanged (transition-state theory), as the transition-state factor's is.
- **It is also the right open fraction for a pore on a bilayer:** no feature here is a shell's.
- **Its large-count limit** (cells.rate_equations@1; FR-47, D323) is log_factor itself on the
  continuous view, where nothing is consumed, so m = n and the factor is g(n), as the
  transition-state factor's limit is.

Data, per world (`rate_factor`): `{"law": "cells.gate_factor@1", "forms": ["G", "H"],
"entries": [{"form": "G", "step": "entry", "ddG_kT": 2.0}, ...]}`. The forms are distinct
membrane species. Each entry names a form and a declared step that touches the membrane (the
fuel note's L1: a step wholly in the pool or in the lumen is refused), each pair at most once,
with ddG_kT in the transition-state factor's domain.
"""

import math

import numpy as np

from cells.definitions.specs import ConfigError, require_fields
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import GATE_FACTOR, MODEL_ID
from cells.models.assembly_lineages_v2 import transition_state as ts
from cells.models.assembly_lineages_v2.interfaces import CATALYSING, RateFactorLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

TEST = (
    "tests/unit/test_assembly_lineages_v2_geometry.py::"
    "test_a_shell_s_rates_follow_its_declared_conductance_alone"
)


def parse_data(raw, world):
    require_fields(raw, {"law", "forms", "entries"}, "world: rate_factor")
    membrane = {p.species for p in world.places if p.phase == "membrane"}
    forms = raw["forms"]
    if type(forms) is not list or not forms or len(set(forms)) != len(forms):
        raise ConfigError("world: rate_factor: a gate's forms are a non-empty list, each once")
    for form in forms:
        if form not in membrane:
            raise ConfigError(
                f"world: rate_factor: the gate's form {form!r} is not a membrane species"
            )
    entries = raw["entries"]
    if type(entries) is not list or not entries:
        raise ConfigError("world: rate_factor: entries is a non-empty list")
    steps = {s.id for s in world.steps}
    seen, out = set(), []
    for entry in entries:
        require_fields(entry, {"form", "step", "ddG_kT"}, "world: rate_factor: an entry")
        form, step, value = entry["form"], entry["step"], entry["ddG_kT"]
        if form not in forms:
            raise ConfigError(f"world: rate_factor: {form!r} is not one of the gate's forms")
        if step not in steps:
            raise ConfigError(f"world: rate_factor: step {step!r} is not a declared step")
        if (form, step) in seen:
            raise ConfigError(f"world: rate_factor: ({form}, {step}) is listed twice")
        seen.add((form, step))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"world: rate_factor: ({form}, {step})'s ddG_kT is finite")
        if not (math.isfinite(value) and ts.DDG_DOMAIN[0] <= value <= ts.DDG_DOMAIN[1]):
            raise ConfigError(
                f"world: rate_factor: ({form}, {step})'s ddG_kT is finite, in "
                f"[{ts.DDG_DOMAIN[0]}, {ts.DDG_DOMAIN[1]}], the transition-state factor's domain"
            )
        out.append((form, step, float(value)))
    ts.refuse_steps_off_the_membrane(out, world)  # after every earlier check (L1)
    return {"forms": tuple(forms), "entries": tuple(out)}


def data_to_dict(data):
    return {
        "forms": list(data["forms"]),
        "entries": [{"form": f, "step": s, "ddG_kT": v} for f, s, v in data["entries"]],
    }


def layout(data, world, steps, places):
    """(weight [R, P], gate [P]): e^ΔΔG‡ at a form's place for a step its entry names, 1 at the
    gate's other places, 0 off the gate; and 1 at each of the gate's places."""
    gate = np.zeros(places, dtype=np.float64)
    at = {p.species: i for i, p in enumerate(world.places) if p.phase == "membrane"}
    for form in data["forms"]:
        gate[at[form]] = 1.0
    weight = np.tile(gate, (steps, 1))
    index = {s.id: i for i, s in enumerate(world.steps)}
    for form, step, value in data["entries"]:
        weight[index[step], at[form]] = math.exp(value)
    return (weight, gate)


def state(counts, factor_layout, xp):
    """n, the counts in float64 (exact): the factor is evaluated afresh on m."""
    return counts.astype(np.float64)


def update(factor_state, factor_layout, places, change, xp):
    moved = change.astype(np.float64)
    if xp is np:
        n = factor_state.copy()
        np.add.at(n, places, moved)
        return n
    return factor_state.at[places].add(moved)


def log_factor(factor_state, factor_layout, view, xp):
    """ln g_r(m) for each step's direction (view), at the pair's common state m."""
    weight, gate = factor_layout
    n = factor_state
    consumed = xp.where(view.membrane, view.consumed, 0)
    spots = xp.arange(n.shape[0])
    taken = xp.sum(consumed.astype(np.float64)[..., None] * (view.places[..., None] == spots), 1)
    m = n[None, :] - taken  # [R, P]: the common state, per step
    numerator = folds.total((weight * m).T, xp)
    forms = folds.total((gate[None, :] * m).T, xp)
    g = xp.where(forms > 0, numerator / xp.where(forms > 0, forms, 1.0), 1.0)
    return xp.where(g > 0, xp.log(xp.where(g > 0, g, 1.0)), -xp.inf)


FORMULAS = {
    "g_r(m)": "sum_{j in gate} m_j exp(ddG_rj) / sum_{j in gate} m_j, weight 1 for a form without "
    "an entry for r; 1 where the gate is absent at m; the same factor for both directions",
    "common_state": "m = min(n, n + nu) elementwise, evaluated afresh from n",
    "denominator": "the gate's own forms only: the wall's other molecules, binding sites "
    "included, do not dilute it",
    "state": "n, the counts (exact in float64)",
}

LAW = law_registry.BUILTIN.register(
    RateFactorLaw(
        GATE_FACTOR,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "docs/ASSEMBLY_SHELL_DESIGN.md §4.3, option G2 (FR-21; D244, D246); transition-state "
            "theory as cells.transition_state_factor@1 cites it",
            "a gate's forms speed or slow a step by ddG; its open fraction is over its own forms",
            "no numbers taken",
            ("the fractions are over the gate's declared forms only, not every wall molecule",),
        ),
        test=TEST,
        energy_role="passive",
        energy_source=None,
        evaluated_on="common_state",
        catalysing_phases=CATALYSING,
        data=("forms", "entries"),
        parse_data=parse_data,
        data_to_dict=data_to_dict,
        layout=layout,
        state=state,
        update=update,
        log_factor=log_factor,
        formulas=FORMULAS,
        limit=log_factor,  # FR-47: on a continuous view (consumed 0), the factor is g(n)
        limit_formulas={
            "g_r(n)": "sum_{j in gate} n_j exp(ddG_rj) / sum_{j in gate} n_j at real counts: the "
            "common state m = n, since nothing is consumed on the continuous view",
        },
    )
)
assert LAW.law_id == GATE_FACTOR
