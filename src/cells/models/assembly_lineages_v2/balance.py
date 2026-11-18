"""The kernel's check (§2.1, §7.1): every pair keeps ln a⁺ − ln a⁻ = −ΔF + w, to rounding.

For every step r and state n from which its forward can fire, with n' = n + ν_r:

    ln a⁺_r(n) − ln a⁻_r(n') + [F(n') − F(n)] − w_r = 0

where the rates are the kernel's own (kernel.log_rates, the same code on the host in NumPy), F is
the ledger's exact value (ledger.free_energy, from the terms' own values), and w_r the step's
reservoir work. The reverse is computed by the kernel as the products' mass action with
k⁻ = k_f exp(Σ ν μ°), never as θ⁺ exp(ΔF), so the identity is a check of that derivation, not true
by construction. A pair that touches the boundary under `last_molecule: extinct` has no reverse and
is not a pair; under `kept` such a pair (its step changes the membrane's count) has both rates zero
and is skipped.

**Where it is taken** (as @1's balance.py):
- the verdict on the check's own generic probe worlds (probe_world: every order up to three on
  each side, steps inside each phase and across them, held species, both measures, regular mixing
  and the rate factor), since special data can satisfy an identity by accident; refused if it
  fails, whatever a world says;
- the world's own report (world_report), on random states of its own data, refused if it fails.
The check's draws come from its own NumPy generator (PROBE_SEED), never from a simulation stream.
"""

import functools

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MASS_ACTION,
    MODEL_ID,
    REGULAR_MIXING,
    TRANSITION_STATE,
    kernel,
    ledger,
    model,
)
from cells.models.assembly_lineages_v2 import world as world_rules

PROBE_SEED = 20261118
STATES = 120
MAX_COUNT = 12
ATOL = 1e-9  # ln units: rounding of a few logarithms and log-factorials.


def host_log_rates(counts, layout, structure):
    """The kernel's ln a of every channel at a state, on the host (NumPy)."""
    counts = np.asarray(counts, dtype=np.int64)
    totals = kernel.totals_of(counts, layout, np)
    factor_state, term_states = kernel.states(counts, totals, layout, structure, np)
    return kernel.log_rates(counts, totals, factor_state, term_states, layout, structure, np)


def _nu(layout, r):
    nu = np.zeros(layout.place_held.shape[0], dtype=np.int64)
    for k in range(kernel.ENTRIES):
        if layout.entry_alpha[r, k] + layout.entry_beta[r, k] > 0 and not layout.entry_held[r, k]:
            nu[layout.entry_place[r, k]] += layout.entry_beta[r, k] - layout.entry_alpha[r, k]
    return nu


def random_state(world, capacity, rng, max_count=MAX_COUNT):
    counts = np.zeros(capacity, dtype=np.int64)
    for i, place in enumerate(world.places):
        if not place.held:
            counts[i] = rng.integers(0, max_count + 1)
    membrane = [i for i, p in enumerate(world.places) if p.phase == "membrane"]
    if world.conventions.last_molecule in ("kept", "extinct") and counts[membrane].sum() == 0:
        counts[membrane[rng.integers(len(membrane))]] = 1
    return counts


def deviations(spec, rng, states=STATES, max_count=MAX_COUNT):
    """ln a⁺(n) − ln a⁻(n') + ΔF − w for every step that can fire at `states` random states."""
    world = spec.model.world
    structure, layout, tables = model.structure(spec), model.layout(spec), model.tables(spec)
    terms = world.terms
    term_layouts = layout.terms
    R = structure.steps
    membrane = np.asarray([p.phase == "membrane" and not p.held for p in world.places])
    found = []
    for _ in range(states):
        n = random_state(world, structure.places, rng, max_count)
        forward = host_log_rates(n, layout, structure)
        f_n = ledger.free_energy(n, tables, terms, term_layouts)
        for r in range(len(world.steps)):
            if not np.isfinite(forward[r]):
                continue
            after = n + _nu(layout, r)
            if np.any(after < 0) or np.max(after) > structure.molecules:
                continue
            emptied = after[: len(world.places)][membrane].sum() == 0
            if emptied and structure.last_molecule == "extinct":
                continue  # No reverse: an extinction is not a pair.
            backward = host_log_rates(after, layout, structure)[R + r]
            if backward == np.inf:
                continue  # A singular state of @1's measure (mass_action.py): declared, not a pair.
            if backward == -np.inf:
                found.append(np.inf)  # A pair with a zero reverse: a fault.
                continue
            df = ledger.free_energy(after, tables, terms, term_layouts) - f_n
            found.append(forward[r] - backward + df - layout.step_work[r])
    return np.asarray(found, dtype=np.float64)


def probe_world(rng, measure, last_molecule, *, regular, catalysis):
    """A generic world for the check: random potentials, rates and volumes; steps of every order
    up to three on each side, inside each phase and across them, with held species."""
    species = []
    for name in ("A", "B", "C", "D", "S", "F"):
        potentials = {"solution": float(rng.normal(0, 2))}
        if name in ("A", "B", "C", "D"):
            potentials["bilayer"] = float(rng.normal(-1, 2))
        species.append(
            {"id": name, "moieties": None, "standard_mu_RT": potentials, "catalogue": None,
             "evidence": None}
        )  # fmt: skip
    # Moieties make the probe's steps balanced: A, B, C and D share one moiety ("m"), and the
    # dimers and trimers carry their counts of it.
    species[0]["moieties"] = {"m": 1}
    species[1]["moieties"] = {"m": 1}
    species[2]["moieties"] = {"m": 2}
    species[3]["moieties"] = {"m": 3}
    species[4]["moieties"] = {"s": 1}
    species[5]["moieties"] = {"m": 1}
    k = lambda: float(np.exp(rng.normal(0, 1)))  # noqa: E731
    steps = [
        {"id": "join_a", "locus": "membrane", "reactants": {"A@pool": 1},
         "products": {"A@membrane": 1}},
        {"id": "join_held", "locus": "membrane", "reactants": {"F@pool": 1},
         "products": {"B@membrane": 1}},
        {"id": "iso", "phase": "membrane", "reactants": {"A": 1}, "products": {"B": 1}},
        {"id": "dimer", "phase": "membrane", "reactants": {"A": 1, "B": 1}, "products": {"C": 1}},
        {"id": "trimer", "phase": "membrane", "reactants": {"A": 3}, "products": {"D": 1}},
        {"id": "swap", "phase": "membrane", "reactants": {"C": 1, "A": 1},
         "products": {"D": 1}},
        {"id": "split", "phase": "membrane", "reactants": {"D": 1}, "products": {"A": 1, "C": 1}},
        {"id": "pool_dimer", "phase": "pool", "reactants": {"A": 2}, "products": {"C": 1}},
        {"id": "lumen_trimer", "phase": "lumen", "reactants": {"A": 1, "C": 1},
         "products": {"D": 1}},
        {"id": "permeate", "locus": "membrane", "reactants": {"S@pool": 1},
         "products": {"S@lumen": 1}},
        {"id": "inner", "locus": "membrane", "reactants": {"A@lumen": 2},
         "products": {"C@membrane": 1}},
        {"id": "interface", "locus": "membrane", "reactants": {"A@pool": 1, "B@membrane": 1},
         "products": {"C@membrane": 1}},
    ]  # fmt: skip
    if measure == "multinomial":  # A membrane place on both sides (singular at N = r under @1's).
        steps.append(
            {"id": "catalysed", "phase": "membrane", "reactants": {"C": 1, "A": 1},
             "products": {"C": 1, "B": 1}}
        )  # fmt: skip
    for step in steps:
        step["law"] = MASS_ACTION
        step["forward_rate_per_s"] = k()
    terms = [{"law": IDEAL_MIXING}]
    if regular:
        terms.append(
            {"law": REGULAR_MIXING, "chi_kT": [
                {"pair": ["A", "B"], "chi": float(rng.normal(0, 1))},
                {"pair": ["A", "C"], "chi": float(rng.normal(0, 1))},
                {"pair": ["B", "D"], "chi": float(rng.normal(0, 1))}]}
        )  # fmt: skip
    world = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {
            "free_energy_form": "discrete",
            "condensed_measure": measure,
            "membrane_kinetics": "count_on_m",
            "lumen_volume": "declared",
            "empty_catalyst_phase": "uncatalysed",
            "last_molecule": last_molecule,
        },
        "species": species,
        "phases": {
            "pool": {"volume_L": float(np.exp(rng.normal(-52, 1))), "species": [
                {"id": "A", "kind": "finite"}, {"id": "C", "kind": "finite"},
                {"id": "S", "kind": "finite"},
                {"id": "F", "kind": "held", "held_mM": float(np.exp(rng.normal(0, 1)))}]},
            "membrane": {"species": ["A", "B", "C", "D"]},
            "lumen": {"volume_L": float(np.exp(rng.normal(-54, 1))),
                      "species": ["A", "C", "D", "S"]},
        },
        "steps": steps,
        "free_energy": terms,
        "founder": {},
    }  # fmt: skip
    finite = [
        f"{s['id']}@pool" for s in world["phases"]["pool"]["species"] if s["kind"] == "finite"
    ]
    finite += [f"{s}@membrane" for s in world["phases"]["membrane"]["species"]]
    finite += [f"{s}@lumen" for s in world["phases"]["lumen"]["species"]]
    world["founder"] = {name: 1 for name in finite}
    if catalysis:
        world["rate_factor"] = {
            "law": TRANSITION_STATE,
            "catalysing_phase": "membrane",
            "entries": [
                {"catalyst": c, "step": s, "ddG_kT": float(rng.normal(0, 1.5))}
                for c, s in (("C", "iso"), ("D", "dimer"), ("B", "join_a"), ("A", "interface"),
                             ("C", "permeate"), ("D", "trimer"))
            ],
        }  # fmt: skip
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world},
        "experiment": {"time_horizon_s": 1.0, "event_limit": 1, "row_every_events": 1,
                       "observation_times_s": [], "trace": False, "uniforms": False},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 0, "environment": 0, "lineage": 0, "branch": 0},
                      "molecule_capacity": 64},
    }  # fmt: skip


PROBES = tuple(
    (measure, last, regular, catalysis)
    for measure, lasts in (
        ("multinomial", ("kept", "reversible")),
        ("multinomial_less_one", ("kept", "extinct")),
    )
    for last in lasts
    for regular in (False, True)
    for catalysis in (False, True)
)


@functools.cache
def verdict():
    """The check's verdict on its generic probe worlds (PROBES), as a dict; refuses (ConfigError)
    if any pair fails the identity. Cached: it is a property of the family's code."""
    from cells.core.specs import parse_spec

    rng = np.random.default_rng(PROBE_SEED)
    worst, pairs = 0.0, 0
    for measure, last, regular, catalysis in PROBES:
        spec = parse_spec(probe_world(rng, measure, last, regular=regular, catalysis=catalysis))
        found = np.abs(deviations(spec, rng))
        pairs += found.size
        worst = max(worst, float(np.max(found)) if found.size else 0.0)
    if not worst <= ATOL:
        raise ConfigError(
            f"{MODEL_ID}: the kernel's rates fail ln a+ - ln a- = -dF + w on the check's probe: "
            f"the largest deviation is {worst:.3g} > {ATOL:g}. Refused: every law of this family "
            "is passive, so a deviation is a fault"
        )
    return {
        "identity": "ln a+(n) - ln a-(n + nu) + F(n + nu) - F(n) - w = 0",
        "holds": True,
        "probe": {
            "worlds": [
                {
                    "condensed_measure": m,
                    "last_molecule": last,
                    "regular_mixing": g,
                    "rate_factor": c,
                }
                for m, last, g, c in PROBES
            ],
            "states_per_world": STATES,
            "seed": PROBE_SEED,
            "pairs": pairs,
            "tolerance_ln": ATOL,
            "max_abs_deviation_ln": worst,
        },
    }


def world_report(spec, *, states=STATES):
    """The identity on the world's own data (random states); refused (ConfigError) if it fails."""
    rng = np.random.default_rng(PROBE_SEED)
    found = np.abs(deviations(spec, rng, states=states))
    worst = float(np.max(found)) if found.size else 0.0
    if not worst <= ATOL:
        raise ConfigError(
            f"{MODEL_ID}: on this world's data the kernel's rates fail the identity by {worst:.3g} "
            f"> {ATOL:g}: refused"
        )
    return {
        "states": states,
        "seed": PROBE_SEED,
        "pairs": int(found.size),
        "max_abs_deviation_ln": worst,
        "tolerance_ln": ATOL,
    }


assert world_rules.MEMBRANE == "membrane"
