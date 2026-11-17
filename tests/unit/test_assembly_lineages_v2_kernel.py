"""The claims of cells.assembly_lineages@2's kernel (OL1, §7.1), each with planted errors (D187).

- Every pair keeps local detailed balance: ln a⁺ − ln a⁻ = −ΔF + w on the check's probe and on a
  world's own data (planted: a factor at each direction's own state, a power propensity, a
  one-sided composition term; each fails by far more than rounding).
- The reverse is the products' mass action, against textbook formulas written here (planted: the
  power propensity).
- Catalysis is kinetic only: a closed world's stationary law, solved from the kernel's own rates,
  is exp(−F)/Z with and without catalysts (planted: the factor at each direction's own state moves
  it); a world with every rate constant doubled draws the same channels at exactly half the times.
- The last molecule under `extinct` leaves at the cancelled form, k⁻·1; `kept` gives 0 and
  `reversible` a pair (planted: the literal form, which gives 0).
- The kernel replays on a host oracle from its saved uniforms (planted: reverse channels drawn at
  0.9 of their weight).
"""

import dataclasses
import itertools
import math

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models.assembly_lineages_v2 import (
    balance,
    kernel,
    ledger,
    mass_action,
    model,
    reference,
    runner,
    transition_state,
)
from cells.registry import laws as law_registry
from tests.assembly_lineage_v2_fixtures import HELD_MM, definition, paired, step, world

TOL = balance.ATOL


def spec_of(the_world, **kw):
    return parse_spec(definition(the_world, **kw))


def worst(spec, states=60):
    found = np.abs(balance.deviations(spec, np.random.default_rng(3), states=states))
    return float(np.max(found)) if found.size else 0.0


# ------------------------------------------------------------------ planted laws


def _at_state(z, factor_layout, view, xp):
    """Planted: the factor at the firing state n, not the pair's common state m."""
    (beta,) = factor_layout
    n = view.membrane_total.astype(np.float64) + xp.zeros_like(z)
    g = xp.where(n > 0, 1.0 + z / xp.where(n > 0, n, 1.0), 1.0)
    return xp.log(xp.maximum(g, 1e-300))


def _power(view, locus_membrane, log_extent_dilute, offset, xp):
    """Planted: n^a in place of the falling factorial n!/(n − a)!."""
    real = mass_action.log_direction(view, locus_membrane, log_extent_dilute, offset, xp)
    k = view.coeff.astype(np.float64)
    n = view.counts.astype(np.float64)
    finite = view.membrane | view.dilute
    ff = mass_action.gather(view.log_factorial, view.counts, xp) - mass_action.gather(
        view.log_factorial, view.counts - view.coeff, xp
    )
    power = xp.where(view.coeff > 0, k * xp.log(xp.maximum(n, 1.0)), 0.0)
    shift = mass_action.entry_sum(xp.where(finite & (view.coeff > 0), power - ff, 0.0), xp)
    return real + shift


def _one_sided(view, locus_membrane, log_extent_dilute, offset, xp):
    """Planted: a composition term at the firing state (D's fraction), with no reciprocal term."""
    real = mass_action.log_direction(view, locus_membrane, log_extent_dilute, offset, xp)
    d = xp.where(view.membrane & (view.places == 5), view.counts, 0)  # D@membrane in the fixture
    n = view.membrane_total.astype(np.float64)
    return real + mass_action.entry_sum(d, xp).astype(np.float64) / xp.maximum(n, 1.0)


def _literal(view, locus_membrane, log_extent_dilute, offset, xp):
    """Planted: the membrane factor's literal product E(m) · 1/ff(N − c, r), never cancelled."""
    lf = view.log_factorial
    k = view.coeff
    r = mass_action.entry_sum(xp.where(view.membrane, k, 0), xp)
    r_star = mass_action.entry_sum(xp.where(view.membrane, view.consumed, 0), xp)
    M = view.membrane_total - offset + xp.zeros_like(r)
    usable = (M - r) >= 0
    literal = mass_action.safe_log((M - r_star + 1).astype(np.float64), xp) - xp.where(
        usable, mass_action.gather(lf, M, xp) - mass_action.gather(lf, M - r, xp), np.inf
    )
    real = mass_action.log_direction(view, locus_membrane, log_extent_dilute, offset, xp)
    factor = mass_action.membrane_factor(view, offset, xp)
    return xp.where(locus_membrane, real - factor + literal, real)


def scoped(*laws):
    law_registry.active()
    return law_registry.scope(law_registry.BUILTIN.extended(*laws))


def renamed_mass_action(name, kernel_function):
    return dataclasses.replace(mass_action.LAW, law_id=name, log_direction=kernel_function)


def with_law(the_world, law_id):
    out = dict(the_world)
    out["steps"] = [dict(s, law=law_id) for s in the_world["steps"]]
    return out


# ------------------------------------------------------------------ the kernel identity


def test_the_kernel_identity_holds_on_its_probe_and_on_worlds():
    verdict = balance.verdict()
    assert verdict["holds"] and verdict["probe"]["max_abs_deviation_ln"] <= TOL
    assert verdict["probe"]["pairs"] > 10000
    for kw in ({}, {"measure": "multinomial_less_one", "last": "extinct"},
               {"last": "reversible"}):  # fmt: skip
        spec = spec_of(world(**kw))
        assert worst(spec) <= TOL
        assert balance.world_report(spec, states=20)["max_abs_deviation_ln"] <= TOL


def test_planted_kinetics_fail_the_identity_by_far_more_than_rounding():
    at_state = dataclasses.replace(
        transition_state.LAW, law_id="tests.at_state_factor@1", log_factor=_at_state
    )
    power = renamed_mass_action("tests.power_propensity@1", _power)
    one_sided = renamed_mass_action("tests.one_sided@1", _one_sided)
    with scoped(at_state, power, one_sided):
        planted = world()
        planted["rate_factor"]["law"] = "tests.at_state_factor@1"
        assert worst(spec_of(planted)) > 1e-3
        assert worst(spec_of(with_law(paired(world(catalysis=False)), "tests.power_propensity@1"))) > 1e-3
        assert worst(spec_of(with_law(world(catalysis=False), "tests.one_sided@1"))) > 1e-3


# ------------------------------------------------------------------ textbook mass action


def rates_at(spec, counts_by_place):
    structure, layout = model.structure(spec), model.layout(spec)
    counts = np.zeros(structure.places, dtype=np.int64)
    for name, value in counts_by_place.items():
        counts[spec.model.world.place_index(name)] = value
    totals = kernel.totals_of(counts, layout, np)
    factor_state, term_states = kernel.states(counts, totals, layout, structure, np)
    rates = kernel.rates(counts, totals, factor_state, term_states, layout, structure, np)
    return rates[: structure.steps], rates[structure.steps :]


def test_the_reverse_from_F_is_the_products_mass_action():
    """Steps of the plain world (no factor, no excess term), against formulas written here."""
    spec = spec_of(world(regular=False, catalysis=False))
    w = spec.model.world
    mu = {p.name: w.species_by_id(p.species).mu(p.phase) for p in w.places}
    X_pool = math.exp(model.log_extent(w, "pool"))
    state = {"L@pool": 7, "S@pool": 5, "L@membrane": 4, "P@membrane": 3, "D@membrane": 2,
             "L@lumen": 2, "S@lumen": 1}  # fmt: skip
    plus, minus = rates_at(spec, state)
    ids = [s.id for s in w.steps]
    N = 4 + 3 + 2
    # join_L: L(pool) -> L(membrane), locus membrane: k E(m) a_pool, m = n, E = N + 1 (c = 0).
    r = ids.index("join_L")
    assert plus[r] == pytest.approx(10.0 * (N + 1) * 7 / X_pool, rel=1e-13)
    # its reverse, the leave, at n: k- E(m) n_L/N with m = n - e_L(membrane): E = N.
    k_minus = 10.0 * math.exp(mu["L@membrane"] - mu["L@pool"])
    assert minus[r] == pytest.approx(k_minus * N * 4 / N, rel=1e-13)
    # dimerise: L + P -> D inside the membrane: k n_L n_P / N; reverse k- n_D.
    r = ids.index("dimerise")
    assert plus[r] == pytest.approx(1.0 * 4 * 3 / N, rel=1e-13)
    k_minus = math.exp(mu["D@membrane"] - mu["L@membrane"] - mu["P@membrane"])
    assert minus[r] == pytest.approx(k_minus * 2, rel=1e-13)
    # make_L: F (held, a = c/c0) -> L in the pool, locus pool: k X a_F; reverse k- X n_L/X.
    r = ids.index("make_L")
    a_F = HELD_MM / 1000.0
    assert plus[r] == pytest.approx(0.1 * X_pool * a_F, rel=1e-13)
    k_minus = 0.1 * math.exp(mu["L@pool"] - 2.0)  # μ°(F, solution) = 2.0 in the fixture
    assert minus[r] == pytest.approx(k_minus * 7, rel=1e-13)
    # Planted: a power propensity, n^a for n!/(n − a)!, seen on a step of order two in one species.
    power = renamed_mass_action("tests.power_propensity@1", _power)
    two = paired(world(regular=False, catalysis=False))
    honest = spec_of(two)
    r = [s.id for s in honest.model.world.steps].index("pair_L")
    plus, _ = rates_at(honest, state | {"Q@pool": 0})
    assert plus[r] == pytest.approx(0.7 * 7 * 6 / X_pool, rel=1e-13)  # ff: n (n − 1)
    with scoped(power):
        planted, _ = rates_at(spec_of(with_law(two, "tests.power_propensity@1")), state | {"Q@pool": 0})
    assert planted[r] == pytest.approx(0.7 * 7 * 7 / X_pool, rel=1e-13)  # n²: caught
    assert planted[r] != pytest.approx(plus[r], rel=1e-3)


# ------------------------------------------------------------------ catalysis is kinetic only


def closed_world(*, catalysis, law=None):
    """A membrane-only closed world: A <-> B, A + B <-> C, catalysed by C (or not)."""
    sp = [
        {"id": "A", "moieties": {"x": 1}, "standard_mu_RT": {"bilayer": 0.0}, "catalogue": None,
         "evidence": None},
        {"id": "B", "moieties": {"x": 1}, "standard_mu_RT": {"bilayer": -0.5}, "catalogue": None,
         "evidence": None},
        {"id": "C", "moieties": {"x": 2}, "standard_mu_RT": {"bilayer": -1.2}, "catalogue": None,
         "evidence": None},
    ]  # fmt: skip
    out = {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"},
        "species": sp,
        "phases": {"membrane": {"species": ["A", "B", "C"]}},
        "steps": [step("iso", {"A": 1}, {"B": 1}, 1.3, phase="membrane"),
                  step("bind", {"A": 1, "B": 1}, {"C": 1}, 0.8, phase="membrane")],
        "free_energy": [{"law": "cells.ideal_mixing@1"},
                        {"law": "cells.regular_mixing@1", "chi_kT": [{"pair": ["A", "C"], "chi": 0.7}]}],
        "founder": {"A@membrane": 4, "B@membrane": 2, "C@membrane": 1},
    }  # fmt: skip
    if catalysis:
        out["rate_factor"] = {
            "law": law or "cells.transition_state_factor@1",
            "catalysing_phase": "membrane",
            "entries": [{"catalyst": "C", "step": "iso", "ddG_kT": 1.5},
                        {"catalyst": "A", "step": "bind", "ddG_kT": -0.6},
                        {"catalyst": "B", "step": "iso", "ddG_kT": 0.9}],
        }  # fmt: skip
    return out


def stationary_tv(spec):
    """TV between the stationary law of the kernel's own rates on the closed world's states and
    exp(−F)/Z (an exact linear solve; every state with x-moiety 8)."""
    w = spec.model.world
    structure, layout, tables = model.structure(spec), model.layout(spec), model.tables(spec)
    states = [s for s in itertools.product(range(9), repeat=3) if s[0] + s[1] + 2 * s[2] == 8]
    states = [s for s in states if sum(s) > 0]
    index = {s: i for i, s in enumerate(states)}
    count_change, _ = runner.changes(layout, structure)
    order = [w.place_index(n) for n in ("A@membrane", "B@membrane", "C@membrane")]
    Q = np.zeros((len(states), len(states)))
    for s, i in index.items():
        counts = np.zeros(structure.places, dtype=np.int64)
        counts[order] = s
        totals = kernel.totals_of(counts, layout, np)
        fs, ts = kernel.states(counts, totals, layout, structure, np)
        rates = kernel.rates(counts, totals, fs, ts, layout, structure, np)
        for j, rate in enumerate(rates):
            if rate > 0:
                target = tuple(np.asarray(s) + count_change[j][order])
                Q[i, index[target]] += rate
    Q -= np.diag(Q.sum(1))
    A = np.vstack((Q.T, np.ones(len(states))))
    pi = np.linalg.lstsq(A, np.r_[np.zeros(len(states)), 1.0], rcond=None)[0]
    F = []
    for s in states:
        counts = np.zeros(structure.places, dtype=np.int64)
        counts[order] = s
        F.append(ledger.free_energy(counts, tables, w.terms, layout.terms))
    F = np.asarray(F)
    boltzmann = np.exp(-(F - F.min()))
    return 0.5 * np.abs(pi - boltzmann / boltzmann.sum()).sum()


def test_catalysis_is_kinetic_only_and_a_factor_at_each_direction_is_caught():
    assert stationary_tv(spec_of(closed_world(catalysis=False))) < 1e-10
    assert stationary_tv(spec_of(closed_world(catalysis=True))) < 1e-10
    at_state = dataclasses.replace(
        transition_state.LAW, law_id="tests.at_state_factor@1", log_factor=_at_state
    )
    with scoped(at_state):
        planted = spec_of(closed_world(catalysis=True, law="tests.at_state_factor@1"))
        assert stationary_tv(planted) > 1e-3


def test_doubling_every_rate_constant_halves_every_time_exactly():
    base = world()
    doubled = world()
    for s in doubled["steps"]:
        s["forward_rate_per_s"] *= 2.0
    a = runner.run(spec_of(base, horizon=50.0, event_limit=300, row_every=100))
    b = runner.run(spec_of(doubled, horizon=25.0, event_limit=300, row_every=100))
    assert np.array_equal(a.trace["event_channel"], b.trace["event_channel"])
    assert np.array_equal(a.trace["event_time"] / 2, b.trace["event_time"])
    # Planted: one rate constant doubled alone draws another sequence.
    one = world()
    one["steps"][0]["forward_rate_per_s"] *= 2.0
    c = runner.run(spec_of(one, horizon=25.0, event_limit=300, row_every=100))
    assert not np.array_equal(a.trace["event_channel"], c.trace["event_channel"])


# ------------------------------------------------------------------ the last molecule


def lone(measure, last, law=None):
    """A G1-like world: one type L joining from a held pool, and a lone L in the membrane."""
    out = world(measure=measure, last=last, regular=False, catalysis=False, lumen=False)
    out["phases"]["pool"]["species"] = [{"id": "L", "kind": "held", "held_mM": 0.5}]
    out["steps"] = [step("join_L", {"L@pool": 1}, {"L@membrane": 1}, 3.0, locus="membrane")]
    out["founder"] = {"L@membrane": 1, "P@membrane": 0, "D@membrane": 0}
    if law is not None:
        out = with_law(out, law)
    return spec_of(out)


def test_the_last_molecule_leaves_at_the_cancelled_form_under_extinct():
    spec = lone("multinomial_less_one", "extinct")
    w = spec.model.world
    k_minus = 3.0 * math.exp(w.species_by_id("L").mu("membrane") - w.species_by_id("L").mu("pool"))
    plus, minus = rates_at(spec, {"L@membrane": 1})
    assert minus[0] == pytest.approx(k_minus, rel=1e-14) and minus[0] > 0  # k⁻·1, G1's leave
    assert rates_at(spec, {"L@membrane": 0})[0][0] == 0.0  # nothing joins an empty membrane
    assert rates_at(lone("multinomial", "kept"), {"L@membrane": 1})[1][0] == 0.0
    reversible = rates_at(lone("multinomial", "reversible"), {"L@membrane": 1})[1][0]
    assert reversible == pytest.approx(k_minus, rel=1e-14)  # E(m) = 1 under c = 0
    literal = renamed_mass_action("tests.literal_last_molecule@1", _literal)
    with scoped(literal):
        planted = lone("multinomial_less_one", "extinct", "tests.literal_last_molecule@1")
        assert rates_at(planted, {"L@membrane": 1})[1][0] == 0.0  # the literal zero: an error
    # A run under extinct ends at the extinction (a nearly empty reservoir), its ledger closed.
    leaving = world(measure="multinomial_less_one", last="extinct", regular=False,
                    catalysis=False, lumen=False)  # fmt: skip
    leaving["phases"]["pool"]["species"] = [{"id": "L", "kind": "held", "held_mM": 1e-9}]
    leaving["steps"] = [step("join_L", {"L@pool": 1}, {"L@membrane": 1}, 3.0, locus="membrane")]
    leaving["founder"] = {"L@membrane": 3, "P@membrane": 0, "D@membrane": 0}
    run = runner.run(spec_of(leaving, horizon=1e6, event_limit=10_000))
    assert run.status == "extinct" and run.closure["holds"]
    assert run.rows["place_count"][-1].sum() == 0


# ------------------------------------------------------------------ replay


def test_the_kernel_replays_on_a_host_oracle_from_its_uniforms():
    spec = spec_of(world(), horizon=30.0, event_limit=400, row_every=100, uniforms=True)
    run = runner.run(spec)
    channels, times = reference.replay(spec, run.diagnostics["event_uniforms"])
    assert np.array_equal(channels, run.trace["event_channel"])
    assert np.allclose(times, run.trace["event_time"], rtol=1e-12, atol=0)
    planted, _ = reference.replay(spec, run.diagnostics["event_uniforms"], reverse_weight=0.9)
    assert not np.array_equal(planted, run.trace["event_channel"])


# ------------------------------------------------------------------ the singular state


def singular_world(measure, last):
    """A membrane of A, B, C and E with A + B + E -> C + E (E on both sides): under @1's measure
    its rate is singular where the membrane holds exactly its reactants, A = B = E = 1, C = 0."""
    sp = [
        {"id": n, "moieties": m, "standard_mu_RT": {"bilayer": mu}, "catalogue": None,
         "evidence": None}
        for n, m, mu in (("A", {"a": 1}, 0.0), ("B", {"b": 1}, 0.0), ("C", {"a": 1, "b": 1}, -0.7),
                         ("E", {"e": 1}, -0.4))
    ]  # fmt: skip
    return {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": measure,
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": last},
        "species": sp,
        "phases": {"membrane": {"species": ["A", "B", "C", "E"]}},
        "steps": [step("r4", {"A": 1, "B": 1, "E": 1}, {"C": 1, "E": 1}, 2.0, phase="membrane")],
        "free_energy": [{"law": "cells.ideal_mixing@1"}],
        "founder": {"A@membrane": 1, "B@membrane": 1, "C@membrane": 0, "E@membrane": 1},
    }  # fmt: skip


def test_a_singular_state_of_g1_s_measure_is_reported_inf_and_a_run_that_reaches_it_stalls():
    """The declared convention (FORMAT.md; the lead rules on it in §0.2b): +inf in a probe's table,
    and a run whose state is singular stops stalled (refused, nothing repaired)."""
    from validation.assembly_lineages_v2 import probes

    names = ["A@membrane", "B@membrane", "C@membrane", "E@membrane"]
    singular = np.asarray([[1, 1, 0, 1]], dtype=np.int64)
    regular = np.asarray([[2, 1, 0, 1]], dtype=np.int64)
    for last in ("kept", "extinct"):
        spec = spec_of(singular_world("multinomial_less_one", last))
        plus, minus, free = probes.rate_table(spec, names, singular)
        assert plus[0, 0] == np.inf and np.isfinite(free[0])  # The probe reports +inf.
        assert np.isfinite(probes.rate_table(spec, names, regular)[0][0, 0])
        run = runner.run(spec_of(singular_world("multinomial_less_one", last), horizon=10.0))
        assert run.status == "stalled" and run.rows["row_event"][-1] == 0  # Nothing committed.
    # Control: the multinomial measure has no singular state there; the run goes on.
    spec = spec_of(singular_world("multinomial", "kept"))
    assert np.isfinite(probes.rate_table(spec, names, singular)[0][0, 0])
    assert runner.run(spec_of(singular_world("multinomial", "kept"), horizon=10.0)).status != "stalled"
