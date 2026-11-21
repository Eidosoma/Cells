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

import copy
import functools

import numpy as np

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    GATE_FACTOR,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    MODEL_ID,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    PRESCRIBED_SHELL,
    REGULAR_MIXING,
    SHELL_PERMEATION,
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


def _within(counts, tables):
    """Whether a state fits the world's log-factorial table: every finite count, and the
    membrane's total less the offset, at most its last index (ledger.state_free_energy's rule)."""
    last = tables.log_factorial.shape[0] - 1
    largest = int(np.max(np.where(tables.finite, counts, 0), initial=0))
    membrane = int(np.sum(np.where(tables.membrane, counts, 0)))
    return largest <= last and membrane - tables.offset <= last


def deviations(spec, rng, states=STATES, max_count=MAX_COUNT):
    """ln a⁺(n) − ln a⁻(n') + ΔF − w for every step that can fire at `states` random states.

    The states are drawn within the world's own capacity (D263): at most min(max_count, molecule
    capacity) molecules per place, and a state or a result the world's table cannot hold is no
    pair. Before, a low-capacity world drew states above its capacity and checked none of them. A
    world of capacity 12 or more draws exactly as it did, and checks the same pairs unless a state's
    membrane total passed its capacity (read from the clamped table before, skipped now)."""
    world = spec.model.world
    structure, layout, tables = model.structure(spec), model.layout(spec), model.tables(spec)
    terms = world.terms
    term_layouts = layout.terms
    R = structure.steps
    membrane = np.asarray([p.phase == "membrane" and not p.held for p in world.places])
    max_count = min(max_count, structure.molecules)
    found = []
    for _ in range(states):
        n = random_state(world, structure.places, rng, max_count)
        if not _within(n, tables):
            continue
        forward = host_log_rates(n, layout, structure)
        f_n = ledger.free_energy(n, tables, terms, term_layouts)
        for r in range(len(world.steps)):
            if not np.isfinite(forward[r]):
                continue
            after = n + _nu(layout, r)
            if np.any(after < 0) or not _within(after, tables):
                continue
            emptied = after[: len(world.places)][membrane].sum() == 0
            if emptied and structure.last_molecule == "extinct":
                continue  # No reverse: an extinction is not a pair.
            bilayer = structure.geometry not in (None, PRESCRIBED_SHELL)
            if bilayer and kernel.lysis_at(after, layout, np):
                continue  # No reverse: a lysis ends the life (§0.2b rule 3), not a pair.
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


def verdict():
    """_verdict()'s result, a fresh copy for each caller: the cached object is never
    handed out, so one run's edit to its check cannot reach another run's (D263)."""
    return copy.deepcopy(_verdict())


@functools.cache
def _verdict():
    """The check's verdict on its generic probe worlds (PROBES), as a dict; refuses (ConfigError)
    if any pair fails the identity. Cached: it is a property of the family's code."""
    from cells.definitions.specs import parse_spec

    rng = np.random.default_rng(PROBE_SEED)
    worst, pairs = 0.0, 0
    for measure, last, regular, catalysis in PROBES:
        spec = parse_spec(probe_world(rng, measure, last, regular=regular, catalysis=catalysis))
        found = np.abs(deviations(spec, rng))
        require_pairs(found, spec, "the check's probe world")
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


def require_pairs(found, spec, what):
    """D263: an identity checked on no pair is no evidence. A world with any step must have at
    least one pair checked, or the check refuses (ConfigError), never reporting a zero error."""
    if found.size == 0 and spec.model.world.steps:
        raise ConfigError(
            f"{MODEL_ID}: on {what} the identity was checked on no pair of its "
            f"{len(spec.model.world.steps)} steps, which is no evidence: refused (D263)"
        )


def world_report(spec, *, states=STATES):
    """The identity on the world's own data (random states); refused (ConfigError) if it fails."""
    rng = np.random.default_rng(PROBE_SEED)
    found = np.abs(deviations(spec, rng, states=states))
    require_pairs(found, spec, "this world's data")
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


# ------------------------------------------------------------------ OL2: worlds with a geometry


def geometry_probe_world(rng, measure, encounter, *, regular, catalysis):
    """A generic world with a bilayer geometry (OL2): joins by phase exchange (one from a held
    species), an entry by permeation, a membrane isomerisation that changes the footprint and a
    dimerisation that keeps it, a pool reaction, random potentials, rates and volumes."""
    species = []
    for name, moiety in (("A", {"m": 1}), ("B", {"m": 1}), ("C", {"m": 2}), ("H", {"h": 1}),
                         ("S", {"s": 1})):  # fmt: skip
        potentials = {"solution": float(rng.normal(0, 2))}
        if name in ("A", "B", "C", "H"):
            potentials["bilayer"] = float(rng.normal(-1, 2))
        species.append({"id": name, "moieties": moiety, "standard_mu_RT": potentials,
                        "catalogue": None, "evidence": None})  # fmt: skip
    k = lambda: float(np.exp(rng.normal(0, 1)))  # noqa: E731
    key = "insertion_velocity_m_per_s" if encounter == "insertion_area" else "diffusivity_m2_per_s"
    scale = 1e-8 if encounter == "insertion_area" else 1e-17
    steps = [
        {"id": "join_a", "locus": "membrane", "reactants": {"A@pool": 1},
         "products": {"A@membrane": 1}, "law": PHASE_EXCHANGE,
         key: {"value": scale * k(), "provenance": "unsourced; probe"}},
        {"id": "join_h", "locus": "membrane", "reactants": {"H@pool": 1},
         "products": {"H@membrane": 1}, "law": PHASE_EXCHANGE,
         key: {"value": scale * k(), "provenance": "unsourced; probe"}},
        {"id": "entry_s", "locus": "membrane", "reactants": {"S@pool": 1},
         "products": {"S@lumen": 1}, "law": MEMBRANE_PERMEATION,
         "permeability_m_per_s": {"value": 1e-8 * k(), "provenance": "unsourced; probe"}},
        {"id": "iso", "phase": "membrane", "reactants": {"A": 1}, "products": {"B": 1},
         "law": MASS_ACTION, "forward_rate_per_s": k()},
        {"id": "dimer", "phase": "membrane", "reactants": {"A": 1, "B": 1},
         "products": {"C": 1}, "law": MASS_ACTION, "forward_rate_per_s": k()},
        {"id": "pool_dimer", "phase": "pool", "reactants": {"A": 2}, "products": {"C": 1},
         "law": MASS_ACTION, "forward_rate_per_s": k()},
    ]  # fmt: skip
    terms = [{"law": IDEAL_MIXING}]
    if regular:
        terms.append({"law": REGULAR_MIXING, "chi_kT": [
            {"pair": ["A", "B"], "chi": float(rng.normal(0, 1))},
            {"pair": ["B", "C"], "chi": float(rng.normal(0, 1))}]})  # fmt: skip
    q = 5e-21
    quanta = {"A": 60, "B": 140, "C": 200, "H": 90}  # C = A + B: the dimerisation keeps W.
    world = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {
            "free_energy_form": "discrete", "condensed_measure": measure,
            "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
            "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept",
            "exchange_encounter": encounter,
        },
        "species": species,
        "phases": {
            "pool": {"volume_L": float(np.exp(rng.normal(-52, 1))), "species": [
                {"id": "A", "kind": "finite"}, {"id": "C", "kind": "finite"},
                {"id": "S", "kind": "finite"},
                {"id": "H", "kind": "held", "held_mM": float(np.exp(rng.normal(0, 1)))}]},
            "membrane": {"species": ["A", "B", "C", "H"]},
            "lumen": {"volume_L": float(np.exp(rng.normal(-54, 1))), "species": ["S"]},
        },
        "steps": steps,
        "free_energy": terms,
        "founder": {"A@pool": 3, "C@pool": 1, "S@pool": 2, "A@membrane": 2, "B@membrane": 1,
                    "C@membrane": 1, "H@membrane": 1, "S@lumen": 1},
        "geometry": {
            "law": BILAYER_GEOMETRY, "area_quantum_m2": q,
            "area_per_leaflet": {s: {"quanta": n, "provenance": "unsourced; probe"}
                                 for s, n in quanta.items()},
            "vesicle_floor": {"quanta": 60, "provenance": "unsourced; probe"},
            "closure_cost_kT": {"value": float(abs(rng.normal(0, 10))),
                                "provenance": "unsourced; probe"},
        },
    }  # fmt: skip
    if catalysis:
        world["rate_factor"] = {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                                "entries": [{"catalyst": "C", "step": "iso",
                                             "ddG_kT": float(rng.normal(0, 1.5))},
                                            {"catalyst": "B", "step": "join_a",
                                             "ddG_kT": float(rng.normal(0, 1.5))}]}  # fmt: skip
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world},
        "experiment": {"time_horizon_s": 1.0, "event_limit": 1, "row_every_events": 1,
                       "observation_times_s": [], "trace": False, "uniforms": False},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 0, "environment": 0, "lineage": 0, "branch": 0},
                      "molecule_capacity": 64},
    }  # fmt: skip


GEOMETRY_PROBES = tuple(
    (measure, encounter, regular, catalysis)
    for measure in ("multinomial", "multinomial_less_one")
    for encounter in ("insertion_area", "diffusion_radius")
    for regular in (False, True)
    for catalysis in (False, True)
)


def geometry_verdict():
    """_geometry_verdict()'s result, a fresh copy for each caller: the cached object is never
    handed out, so one run's edit to its check cannot reach another run's (D263)."""
    return copy.deepcopy(_geometry_verdict())


@functools.cache
def _geometry_verdict():
    """The check's verdict on OL2's generic geometry worlds (GEOMETRY_PROBES), as for verdict():
    refuses (ConfigError) if any pair fails the identity. OL1's verdict() is left as it was, so
    OL1's records do not move."""
    from cells.definitions.specs import parse_spec

    rng = np.random.default_rng(PROBE_SEED + 2)
    worst, pairs = 0.0, 0
    for measure, encounter, regular, catalysis in GEOMETRY_PROBES:
        world = geometry_probe_world(rng, measure, encounter, regular=regular, catalysis=catalysis)
        spec = parse_spec(world)
        found = np.abs(deviations(spec, rng))
        require_pairs(found, spec, "a probe world")
        pairs += found.size
        worst = max(worst, float(np.max(found)) if found.size else 0.0)
    if not worst <= ATOL:
        raise ConfigError(
            f"{MODEL_ID}: the kernel's rates fail ln a+ - ln a- = -dF + w on the geometry probe: "
            f"the largest deviation is {worst:.3g} > {ATOL:g}. Refused"
        )
    return {
        "identity": "ln a+(n) - ln a-(n + nu) + F(n + nu) - F(n) - w = 0",
        "holds": True,
        "probe": {
            "worlds": [
                {
                    "condensed_measure": m,
                    "exchange_encounter": e,
                    "regular_mixing": g,
                    "rate_factor": c,
                }
                for m, e, g, c in GEOMETRY_PROBES
            ],  # fmt: skip
            "states_per_world": STATES,
            "seed": PROBE_SEED + 2,
            "pairs": pairs,
            "tolerance_ln": ATOL,
            "max_abs_deviation_ln": worst,
        },
    }


# ------------------------------------------------------------------ FR-21: the prescribed shell


def shell_probe_world(rng, measure, *, regular, catalysis):
    """A generic world with a prescribed shell (FR-21): a tracer S entering the declared lumen by
    the shell's permeation, a gate flipping between its forms G and H in the wall, a ligand X
    binding a declared site R to its complex XR, and a wall subunit B; random potentials, rates,
    volumes and area. With catalysis the gate factor speeds or slows the entry by its forms."""
    species = []
    for name, moiety, kinds in (("S", {"s": 1}, ("solution",)), ("X", {"x": 1}, ("solution",)),
                                ("G", {"g": 1}, ("bilayer",)), ("H", {"g": 1}, ("bilayer",)),
                                ("R", {"r": 1}, ("bilayer",)),
                                ("XR", {"x": 1, "r": 1}, ("bilayer",)),
                                ("B", {"b": 1}, ("bilayer",))):  # fmt: skip
        potentials = {kind: float(rng.normal(0, 2)) for kind in kinds}
        species.append({"id": name, "moieties": moiety, "standard_mu_RT": potentials,
                        "catalogue": None, "evidence": None})  # fmt: skip
    k = lambda: float(np.exp(rng.normal(0, 1)))  # noqa: E731
    steps = [
        {"id": "entry_s", "locus": "membrane", "reactants": {"S@pool": 1},
         "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
         "permeability_m_per_s": {"value": 1e-8 * k(), "provenance": "unsourced; probe"}},
        {"id": "flip", "phase": "membrane", "reactants": {"G": 1}, "products": {"H": 1},
         "law": MASS_ACTION, "forward_rate_per_s": k()},
        {"id": "bind", "locus": "membrane", "reactants": {"X@pool": 1, "R@membrane": 1},
         "products": {"XR@membrane": 1}, "law": MASS_ACTION, "forward_rate_per_s": k()},
    ]  # fmt: skip
    terms = [{"law": IDEAL_MIXING}]
    if regular:
        terms.append({"law": REGULAR_MIXING, "chi_kT": [
            {"pair": ["G", "B"], "chi": float(rng.normal(0, 1))},
            {"pair": ["R", "XR"], "chi": float(rng.normal(0, 1))}]})  # fmt: skip
    world = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {
            "free_energy_form": "discrete", "condensed_measure": measure,
            "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
            "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept",
        },
        "species": species,
        "phases": {
            "pool": {"volume_L": float(np.exp(rng.normal(-52, 1))), "species": [
                {"id": "S", "kind": "finite"}, {"id": "X", "kind": "finite"}]},
            "membrane": {"species": ["G", "H", "R", "XR", "B"]},
            "lumen": {"volume_L": float(np.exp(rng.normal(-54, 1))), "species": ["S"]},
        },
        "steps": steps,
        "free_energy": terms,
        "founder": {"S@pool": 3, "X@pool": 2, "S@lumen": 1, "G@membrane": 1, "H@membrane": 1,
                    "R@membrane": 2, "XR@membrane": 1, "B@membrane": 3},
        "sites": [{"site": "R", "complex": "XR"}],
        "geometry": {"law": PRESCRIBED_SHELL,
                     "area_m2": {"value": float(np.exp(rng.normal(-35, 1))),
                                 "provenance": "unsourced; probe"}},
    }  # fmt: skip
    if catalysis:
        world["rate_factor"] = {"law": GATE_FACTOR, "forms": ["G", "H"],
                                "entries": [{"form": "G", "step": "entry_s",
                                             "ddG_kT": float(rng.normal(0, 1.5))},
                                            {"form": "H", "step": "entry_s",
                                             "ddG_kT": float(rng.normal(0, 1.5))}]}  # fmt: skip
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world},
        "experiment": {"time_horizon_s": 1.0, "event_limit": 1, "row_every_events": 1,
                       "observation_times_s": [], "trace": False, "uniforms": False},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 0, "environment": 0, "lineage": 0, "branch": 0},
                      "molecule_capacity": 64},
    }  # fmt: skip


SHELL_PROBES = tuple(
    (measure, regular, catalysis)
    for measure in ("multinomial", "multinomial_less_one")
    for regular in (False, True)
    for catalysis in (False, True)
)


def shell_verdict():
    """_shell_verdict()'s result, a fresh copy for each caller: the cached object is never
    handed out, so one run's edit to its check cannot reach another run's (D263)."""
    return copy.deepcopy(_shell_verdict())


@functools.cache
def _shell_verdict():
    """The check's verdict on FR-21's generic shell worlds (SHELL_PROBES), as for
    geometry_verdict(): refuses (ConfigError) if any pair fails the identity. The other verdicts
    are left as they were, so no other run's record moves."""
    from cells.definitions.specs import parse_spec

    rng = np.random.default_rng(PROBE_SEED + 4)
    worst, pairs = 0.0, 0
    for measure, regular, catalysis in SHELL_PROBES:
        world = shell_probe_world(rng, measure, regular=regular, catalysis=catalysis)
        spec = parse_spec(world)
        found = np.abs(deviations(spec, rng))
        require_pairs(found, spec, "a probe world")
        pairs += found.size
        worst = max(worst, float(np.max(found)) if found.size else 0.0)
    if not worst <= ATOL:
        raise ConfigError(
            f"{MODEL_ID}: the kernel's rates fail ln a+ - ln a- = -dF + w on the shell probe: "
            f"the largest deviation is {worst:.3g} > {ATOL:g}. Refused"
        )
    return {
        "identity": "ln a+(n) - ln a-(n + nu) + F(n + nu) - F(n) - w = 0",
        "holds": True,
        "probe": {
            "worlds": [
                {"condensed_measure": m, "regular_mixing": g, "rate_factor": c}
                for m, g, c in SHELL_PROBES
            ],
            "states_per_world": STATES,
            "seed": PROBE_SEED + 4,
            "pairs": pairs,
            "tolerance_ln": ATOL,
            "max_abs_deviation_ln": worst,
        },
    }


# ------------------------------------------------------------------ OL2 milestone 2: osmotic lumen


def osmotic_probe_world(rng, measure, encounter, *, regular, catalysis):
    """A geometry probe world with an osmotic lumen: S enters the lumen from the pool and turns into
    T there (one lumen reactant: §0.2c rule 7), every membrane and lumen species has a pool place,
    and the quantum and c_ext are chosen so that the probe's states cross the kink V_osm = V_sph."""
    out = geometry_probe_world(rng, measure, encounter, regular=regular, catalysis=catalysis)
    world = out["model"]["world"]
    world["conventions"]["lumen_volume"] = "osmotic"
    world["species"].append({"id": "T", "moieties": {"s": 1},
                             "standard_mu_RT": {"solution": float(rng.normal(0, 2))},
                             "catalogue": None, "evidence": None})  # fmt: skip
    world["phases"]["pool"]["species"] += [{"id": "B", "kind": "finite"},
                                           {"id": "T", "kind": "finite"}]  # fmt: skip
    world["phases"]["lumen"] = {"species": ["S", "T"]}
    world["steps"].append({"id": "lumen_iso", "phase": "lumen", "reactants": {"S": 1},
                           "products": {"T": 1}, "law": MASS_ACTION,
                           "forward_rate_per_s": float(np.exp(rng.normal(0, 1)))})  # fmt: skip
    pool = world["phases"]["pool"]
    finite = sum(world["founder"].get(f"{s['id']}@pool", 0) for s in pool["species"]
                 if s["kind"] == "finite") + 2  # B and T join the pool below.  # fmt: skip
    held = sum(s["held_mM"] for s in pool["species"] if s["kind"] == "held")
    solutes = finite / (6.02214076e23 * pool["volume_L"]) * 1e3 + held
    world["free_energy"].append({"law": OSMOTIC_LUMEN, "outside_osmolarity_mM": {
        "value": max(2000.0, 2.0 * solutes), "provenance": "unsourced; probe"}})  # fmt: skip
    geometry = world["geometry"]
    q = 1e-19
    geometry["area_quantum_m2"] = q
    geometry["sigma_max_N_per_m"] = {"value": 1e12, "provenance": "unsourced; probe: no lysis"}
    world["founder"].update({"B@pool": 1, "T@pool": 1, "T@lumen": 1})
    return out


def osmotic_verdict():
    """_osmotic_verdict()'s result, a fresh copy for each caller: the cached object is never
    handed out, so one run's edit to its check cannot reach another run's (D263)."""
    return copy.deepcopy(_osmotic_verdict())


@functools.cache
def _osmotic_verdict():
    """The check's verdict on OL2 milestone 2's generic osmotic worlds, as geometry_verdict's."""
    from cells.definitions.specs import parse_spec

    rng = np.random.default_rng(PROBE_SEED + 3)
    worst, pairs = 0.0, 0
    for measure, encounter, regular, catalysis in GEOMETRY_PROBES:
        world = osmotic_probe_world(rng, measure, encounter, regular=regular, catalysis=catalysis)
        spec = parse_spec(world)
        found = np.abs(deviations(spec, rng))
        require_pairs(found, spec, "a probe world")
        pairs += found.size
        worst = max(worst, float(np.max(found)) if found.size else 0.0)
    if not worst <= ATOL:
        raise ConfigError(
            f"{MODEL_ID}: the kernel's rates fail ln a+ - ln a- = -dF + w on the osmotic probe: "
            f"the largest deviation is {worst:.3g} > {ATOL:g}. Refused"
        )
    return {
        "identity": "ln a+(n) - ln a-(n + nu) + F(n + nu) - F(n) - w = 0",
        "holds": True,
        "probe": {
            "worlds": [
                {
                    "condensed_measure": m,
                    "exchange_encounter": e,
                    "regular_mixing": g,
                    "rate_factor": c,
                    "lumen_volume": "osmotic",
                }
                for m, e, g, c in GEOMETRY_PROBES
            ],  # fmt: skip
            "states_per_world": STATES,
            "seed": PROBE_SEED + 3,
            "pairs": pairs,
            "tolerance_ln": ATOL,
            "max_abs_deviation_ln": worst,
        },
    }
