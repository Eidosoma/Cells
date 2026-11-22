"""cells.rate_equations@1, OL6's first slice (S1; docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md).

The deterministic representation of OL1's laws in a single lineage: its parse and refusals, the
limit's check with two planted failures (P-D2, a power off by one; P-D7, a shifted μ° in F_cont
only), parity with the exact kernel, a linear network against its matrix exponential, and a closed
membrane world that relaxes to F_cont's minimum with its books closed. A new file for a new
representation (D224); about 60 s, compiling included.
"""

import copy
import dataclasses

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from scipy.linalg import expm

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    REGULAR_MIXING,
    TRANSITION_STATE,
    balance,
    rate_equations,
    runner,
)
from tests.assembly_lineage_v2_fixtures import CONVENTIONS, definition, species, step

jax.config.update("jax_enable_x64", True)

ENVELOPE = {"min_count": 100.0, "provenance": "a test envelope"}
INTEGRATOR = {"id": "rosenbrock_rodas4_dense@1", "rtol": 1e-9, "atol_count": 1e-6,
              "step_limit": 100000}  # fmt: skip


def as_representation(raw, envelope=ENVELOPE, integrator=INTEGRATOR):
    out = copy.deepcopy(raw)
    x = out["execution"]
    for key in ("molecule_capacity", "chunk_events"):
        x.pop(key, None)
    x["representation"] = {"id": "cells.rate_equations@1", "envelope": dict(envelope),
                           "integrator": dict(integrator)}  # fmt: skip
    out["experiment"]["trace"] = False
    return out


def linear_world():
    """A ⇌ B ⇌ C in a finite pool, first order, and one inert membrane molecule (no rate reads
    it): the rate equations are linear, so their solution is a matrix exponential."""
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1000.0},
        "conventions": dict(CONVENTIONS, condensed_measure="multinomial", last_molecule="kept"),
        "species": [species("A", {"x": 1}, solution=0.0), species("B", {"x": 1}, solution=-0.5),
                    species("C", {"x": 1}, solution=-1.0), species("M", None, bilayer=0.0)],
        "phases": {"pool": {"volume_L": 1e-18, "species": [
            {"id": s, "kind": "finite"} for s in ("A", "B", "C")]},
                   "membrane": {"species": ["M"]}},
        "steps": [step("ab", {"A": 1}, {"B": 1}, 2.0, phase="pool"),
                  step("bc", {"B": 1}, {"C": 1}, 1.0, phase="pool")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"A@pool": 10000, "B@pool": 2000, "C@pool": 1000, "M@membrane": 1},
    }  # fmt: skip


def membrane_world():
    """A closed world: T and U exchange between a finite pool and a membrane, and dimerise in the
    membrane (order 2 there), catalysed (the transition-state factor) with regular mixing."""
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1000.0},
        "conventions": dict(CONVENTIONS, condensed_measure="multinomial_less_one",
                            last_molecule="kept"),
        "species": [species("T", {"t": 1}, solution=0.0, bilayer=-2.0),
                    species("U", {"u": 1}, solution=0.0, bilayer=-1.5),
                    species("D", {"t": 1, "u": 1}, bilayer=-4.0)],
        "phases": {"pool": {"volume_L": 1e-20, "species": [
            {"id": "T", "kind": "finite"}, {"id": "U", "kind": "finite"}]},
                   "membrane": {"species": ["T", "U", "D"]}},
        "steps": [step("join_T", {"T@pool": 1}, {"T@membrane": 1}, 3.0, locus="membrane"),
                  step("join_U", {"U@pool": 1}, {"U@membrane": 1}, 2.0, locus="membrane"),
                  step("dimer", {"T": 1, "U": 1}, {"D": 1}, 5.0, phase="membrane")],
        "free_energy": [{"law": IDEAL_MIXING},
                        {"law": REGULAR_MIXING, "chi_kT": [{"pair": ["T", "U"], "chi": 1.0}]}],
        "rate_factor": {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                        "entries": [{"catalyst": "D", "step": "join_T", "ddG_kT": 1.2},
                                    {"catalyst": "T", "step": "dimer", "ddG_kT": 0.7}]},
        "founder": {"T@pool": 3000, "U@pool": 2500, "T@membrane": 2000, "U@membrane": 1500,
                    "D@membrane": 500},
    }  # fmt: skip


def test_a_representation_parses_beside_its_exact_twin_and_round_trips():
    exact = parse_spec(definition(linear_world(), trace=False, molecules=20000))
    spec = parse_spec(as_representation(definition(linear_world(), observations=(0.5,))))
    assert rate_equations.is_representation(spec) and not rate_equations.is_representation(exact)
    assert spec.model.world == exact.model.world  # one world, two representations
    assert spec.fingerprint != exact.fingerprint
    again = parse_spec(spec.to_dict() if hasattr(spec, "to_dict") else _to_dict(spec))
    assert again.fingerprint == spec.fingerprint


def _to_dict(spec):
    from cells.models.assembly_lineages_v2.spec import to_dict

    return to_dict(spec)


def _edit(path, value):
    def edit(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return raw

    return edit


@pytest.mark.parametrize(
    "edit, words",
    [
        (_edit(("execution", "molecule_capacity"), 64), "does not apply"),
        (_edit(("execution", "representation", "integrator", "id"), "rk4"), "integrator's id"),
        (_edit(("execution", "representation", "integrator", "rtol"), 1e-2), "rtol"),
        (_edit(("execution", "representation", "envelope", "min_count"), 0.5), "min_count"),
        (_edit(("experiment", "trace"), True), "event-level readout"),
        (_edit(("model", "world", "founder", "C@pool"), 50), "below the envelope"),
        (_edit(("execution", "mode"), "population"), "single_lineage"),
    ],
)
def test_refusals(edit, words):
    raw = edit(as_representation(definition(linear_world())))
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_the_limit_check_passes_on_the_generic_probes_and_catches_two_plants():
    verdict = rate_equations.verdict()
    assert verdict["worlds"] == len(rate_equations.generic_probes()) == 4
    assert verdict["identity"] <= rate_equations.IDENTITY_ATOL
    assert verdict["potential"] <= 1e-6 and verdict["dissipation_margin"] >= 0.0
    spec = parse_spec(as_representation(definition(membrane_world())))
    problem = rate_equations.Problem(spec)
    rng = np.random.default_rng(3)
    rate_equations.limit_check(problem, rng, states=2)

    # P-D7: one species' μ° shifted by 0.5 k_BT in F_cont only.
    ideal = problem.terms[0]
    shifted = dataclasses.replace(
        ideal, limit=lambda n, t, l, xp: ideal.limit(n, t, l, xp) + 0.5 * n[0]
    )
    problem.terms = (shifted, *problem.terms[1:])
    with pytest.raises(ConfigError, match="not the products' law"):
        rate_equations.limit_check(problem, rng, states=2)

    # P-D2: a power off by one in mass action's limit (n^(a+1) for every coefficient a).
    problem = rate_equations.Problem(spec)
    law = problem.reactions[0]

    def off_by_one(view, *args):
        bumped = view._replace(coeff=jnp.where(view.coeff > 0, view.coeff + 1, 0))
        return law.limit(bumped, *args)

    problem.reactions = tuple(dataclasses.replace(r, limit=off_by_one) for r in problem.reactions)
    with pytest.raises(ConfigError, match="not the products' law"):
        rate_equations.limit_check(problem, rng, states=2)


def test_each_limit_tends_to_its_exact_form_as_one_over_the_counts():
    rng = np.random.default_rng(5)
    for measure, last, regular, catalysis in balance.PROBES[:4:3]:
        raw = balance.probe_world(rng, measure, last, regular=regular, catalysis=catalysis)
        out = rate_equations.parity(raw, rng)
        assert out["identical"] or out["order"] >= 0.9, out


def test_a_linear_network_follows_its_matrix_exponential():
    times = (0.25, 0.5, 1.0, 2.0)
    spec = parse_spec(as_representation(definition(linear_world(), horizon=2.0,
                                                   observations=times)))  # fmt: skip
    run = runner.run(spec)
    assert run.status == "complete"
    k1, k1r = 2.0, 2.0 * np.exp(-0.5)  # k⁻ = k_f exp(Σ ν μ°)
    k2, k2r = 1.0, 1.0 * np.exp(-0.5)
    rates = np.array([[-k1, k1r, 0.0], [k1, -k1r - k2, k2r], [0.0, k2, -k2r]])
    start = np.array([10000.0, 2000.0, 1000.0])
    observed = run.rows["row_kind"] == "observed"
    for t, counts in zip(run.rows["row_time_s"][observed], run.rows["counts"][observed],
                         strict=True):  # fmt: skip
        expected = expm(rates * t) @ start
        assert np.max(np.abs(counts[:3] - expected) / expected) < 1e-7
    run.check_books()


def test_a_closed_membrane_relaxes_to_f_cont_s_minimum_with_its_books_closed():
    raw = as_representation(definition(membrane_world(), horizon=40.0, observations=(1.0, 10.0)))
    spec = parse_spec(raw)
    run = runner.run(spec)
    assert run.status == "complete"
    run.check_books()
    assert run.dissipation["holds"]
    problem = rate_equations.Problem(spec)
    final = np.zeros(problem.P)
    final[: len(spec.model.world.places)] = run.rows["counts"][-1]
    _, d_f = problem.flux(jnp.asarray(final))
    assert np.max(np.abs(np.asarray(d_f))) < 1e-6  # every step at its equilibrium
    heat = run.rows["heat_kT"]
    assert np.all(np.diff(heat) >= -1e-9)  # dQ/dt >= 0 between rows
    again = runner.run(spec)  # deterministic: the same bits
    for name, values in run.rows.items():
        assert np.array_equal(values, again.rows[name]), name
