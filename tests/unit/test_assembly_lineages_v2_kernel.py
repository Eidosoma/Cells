"""The claims of cells.model.assembly_lineages@2's kernel (OL1, §7.1), each with planted errors (D187).

- Every pair keeps local detailed balance: ln a⁺ − ln a⁻ = −ΔF + w on the check's probe and on a
  world's own data (planted: a factor at each direction's own state, a power propensity, a
  one-sided composition term; each fails by far more than rounding).
- The reverse is the products' mass action, against textbook formulas written here (planted: the
  power propensity); at counts in the thousands the activities keep double precision, each falling
  factorial a sum of direct logarithms (OL5's precision fix; planted: the log-factorial table's
  differences, 5e-12 off at OL2-1's registered state).
- Catalysis is kinetic only: a closed world's stationary law, solved from the kernel's own rates,
  is exp(−F)/Z with and without catalysts (planted: the factor at each direction's own state moves
  it); a world with every rate constant doubled draws the same channels at exactly half the times.
- The last molecule under `extinct` leaves at the cancelled form, k⁻·1; `kept` gives 0 and
  `reversible` a pair (planted: the literal form, which gives 0).
- `kept` zeroes only a pair whose step changes the membrane's count and has an empty end state: at
  an empty membrane a pool step and a permeation fire at their own rates (§0.2a as reworded on 18
  November 2026; planted: the earlier wording, which froze them).
- The kernel replays on a host oracle from its saved uniforms (planted: reverse channels drawn at
  0.9 of their weight).
"""

import dataclasses
import itertools
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
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


def _at_state(factor_state, factor_layout, view, xp):
    """Planted: the factor at the firing state n, not the pair's common state m."""
    z = factor_state[0]
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


def fresh_verdict():
    """balance.verdict() in a fresh process with RuntimeWarning as an error. log_direction once
    summed an infeasible direction's −inf activity and +inf extent before the feasibility mask,
    which NumPy reports as an invalid value (four such entries in the verdict's probe). A fresh
    process, because a warning already issued in this one is not issued again."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    env = {**os.environ, "PYTHONPATH": str(src), "OPENBLAS_NUM_THREADS": "1",
           "JAX_PLATFORMS": "cpu", "JAX_ENABLE_X64": "1"}  # fmt: skip
    code = ("import json; from cells.models.assembly_lineages_v2.balance import verdict; "
            "v = verdict(); print(json.dumps({'holds': bool(v['holds']), 'probe': "
            "{'pairs': int(v['probe']['pairs']), "
            "'max_abs_deviation_ln': float(v['probe']['max_abs_deviation_ln'])}}))")  # fmt: skip
    done = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-c", code], env=env,
                          capture_output=True, text=True, timeout=900)  # fmt: skip
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_kernel_identity_holds_on_its_probe_and_on_worlds():
    verdict = fresh_verdict()  # The probe's verdict, with RuntimeWarning an error.
    assert verdict["holds"] and verdict["probe"]["max_abs_deviation_ln"] <= TOL
    assert verdict["probe"]["pairs"] > 10000
    for kw in ({}, {"measure": "multinomial_less_one", "last": "extinct"},
               {"last": "reversible"}):  # fmt: skip
        spec = spec_of(world(**kw))
        assert worst(spec) <= TOL
        assert balance.world_report(spec, states=20)["max_abs_deviation_ln"] <= TOL


def test_the_world_report_is_kept_per_world_capacities_and_states_and_never_when_refused(
    monkeypatch,
):
    """balance.world_report is kept per process (FR-35's cost ruling; the lead's condition of 21
    November): a second run of one world reuses it, and a change to any input it reads misses the
    cache and recomputes: the world's content (its id, a full digest of world_to_dict), each of the
    molecule, place and step capacities, and the probe states. A refused world is never kept: asked
    again, it is recomputed and refused again. Host arithmetic at 20 states."""
    calls = []
    real = balance._world_report
    monkeypatch.setattr(balance, "_WORLD_REPORTS", {})

    def counted(spec, states):
        calls.append(states)
        return real(spec, states)

    monkeypatch.setattr(balance, "_world_report", counted)

    def report(the_world, states=20, **execution):
        d = definition(the_world)
        d["execution"].update(execution)
        return balance.world_report(parse_spec(d), states=states)

    first = report(world())
    assert report(world()) == first and len(calls) == 1  # the same world: kept
    faster = world()
    faster["steps"][0]["forward_rate_per_s"] *= 2.0
    misses = (lambda: report(faster), lambda: report(world(), molecule_capacity=128),
              lambda: report(world(), place_capacity=32), lambda: report(world(), step_capacity=16),
              lambda: report(world(), states=21))  # fmt: skip
    for n, miss in enumerate(misses, start=2):
        miss()
        assert len(calls) == n  # each input it reads is in the key
    power = renamed_mass_action("tests.reaction.power_propensity@1", _power)
    with scoped(power):
        refused = with_law(paired(world(catalysis=False)), "tests.reaction.power_propensity@1")
        for attempt in (1, 2):
            with pytest.raises(ConfigError, match="fail the identity"):
                report(refused)
            assert len(calls) == len(misses) + 1 + attempt  # recomputed: never kept
    assert len(balance._WORLD_REPORTS) == len(misses) + 1


def test_planted_kinetics_fail_the_identity_by_far_more_than_rounding():
    at_state = dataclasses.replace(
        transition_state.LAW, law_id="tests.rate_factor.at_state_factor@1", log_factor=_at_state
    )
    power = renamed_mass_action("tests.reaction.power_propensity@1", _power)
    one_sided = renamed_mass_action("tests.reaction.one_sided@1", _one_sided)
    with scoped(at_state, power, one_sided):
        planted = world()
        planted["rate_factor"]["law"] = "tests.rate_factor.at_state_factor@1"
        assert worst(spec_of(planted)) > 1e-3
        assert (
            worst(
                spec_of(
                    with_law(paired(world(catalysis=False)), "tests.reaction.power_propensity@1")
                )
            )
            > 1e-3
        )
        assert worst(spec_of(with_law(world(catalysis=False), "tests.reaction.one_sided@1"))) > 1e-3


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
    power = renamed_mass_action("tests.reaction.power_propensity@1", _power)
    two = paired(world(regular=False, catalysis=False))
    honest = spec_of(two)
    r = [s.id for s in honest.model.world.steps].index("pair_L")
    plus, _ = rates_at(honest, state | {"Q@pool": 0})
    assert plus[r] == pytest.approx(0.7 * 7 * 6 / X_pool, rel=1e-13)  # ff: n (n − 1)
    with scoped(power):
        planted, _ = rates_at(
            spec_of(with_law(two, "tests.reaction.power_propensity@1")), state | {"Q@pool": 0}
        )
    assert planted[r] == pytest.approx(0.7 * 7 * 7 / X_pool, rel=1e-13)  # n²: caught
    assert planted[r] != pytest.approx(plus[r], rel=1e-3)
    # OL5's precision fix: at OL2-1's registered counts (r1's worst, n = 1672 of N = 1847 in the
    # membrane) the dimerisation and the leave keep double precision; the table's differences,
    # lgamma(n + 1) − lgamma(n − 1), missed by 5e-12.
    big = {"L@pool": 7, "S@pool": 5, "L@membrane": 1672, "P@membrane": 175, "D@membrane": 0,
           "L@lumen": 2, "S@lumen": 1}  # fmt: skip
    wide = spec_of(world(regular=False, catalysis=False), molecules=4096)
    plus, minus = rates_at(wide, big)
    N = 1672 + 175
    r = ids.index("dimerise")
    assert plus[r] == pytest.approx(1.0 * 1672 * 175 / N, rel=2e-15)
    r = ids.index("join_L")
    assert minus[r] == pytest.approx(10.0 * math.exp(mu["L@membrane"] - mu["L@pool"]) * 1672,
                                     rel=2e-15)  # fmt: skip
    n1, M = 1672, 1847
    tabled = math.exp(
        (math.lgamma(n1 + 1) - math.lgamma(n1 - 1)) - (math.lgamma(M + 1) - math.lgamma(M))
    )
    assert abs(tabled / (n1 * (n1 - 1) / M) - 1) > 1e-12  # planted: the table's differences


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
        "free_energy": [{"law": "cells.free_energy.ideal_mixing@1"},
                        {"law": "cells.free_energy.regular_mixing@1",
                         "chi_kT": [{"pair": ["A", "C"], "chi": 0.7}]}],
        "founder": {"A@membrane": 4, "B@membrane": 2, "C@membrane": 1},
    }  # fmt: skip
    if catalysis:
        out["rate_factor"] = {
            "law": law or "cells.rate_factor.transition_state_factor@1",
            "catalysing_phase": "membrane",
            "entries": [{"catalyst": "C", "step": "iso", "ddG_kT": 1.5},
                        {"catalyst": "A", "step": "bind", "ddG_kT": -0.6},
                        {"catalyst": "B", "step": "iso", "ddG_kT": 0.9}],
        }  # fmt: skip
    return out


def contact_world():
    """The Lean proofs project's world (19 November 2026): A <-> B at 1e9 /s, equal potentials, with
    contacts of +20 k_BT for A and B and -20 for C, from one A and one C."""
    sp = [{"id": x, "moieties": {"x": 1}, "standard_mu_RT": {"bilayer": 0.0}, "catalogue": None,
           "evidence": None} for x in ("A", "B", "C")]  # fmt: skip
    out = closed_world(catalysis=True)
    out["species"], out["phases"] = sp, {"membrane": {"species": ["A", "B", "C"]}}
    out["steps"] = [step("iso", {"A": 1}, {"B": 1}, 1e9, phase="membrane")]
    out["free_energy"] = [{"law": "cells.free_energy.ideal_mixing@1"}]
    out["founder"] = {"A@membrane": 1, "B@membrane": 0, "C@membrane": 1}
    contacts = (("A", 20.0), ("B", 20.0), ("C", -20.0))
    out["rate_factor"]["entries"] = [
        {"catalyst": x, "step": "iso", "ddG_kT": v} for x, v in contacts
    ]
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
        transition_state.LAW, law_id="tests.rate_factor.at_state_factor@1", log_factor=_at_state
    )
    with scoped(at_state):
        planted = spec_of(closed_world(catalysis=True, law="tests.rate_factor.at_state_factor@1"))
        assert stationary_tv(planted) > 1e-3
    # Extreme contacts (the Lean proofs project's finding, 19 November 2026): the pair's only common
    # catalyst is C, so both directions carry e^-20, 2.06 /s at 1e9 /s. The cached form gave 0 to
    # both, and the run stopped inert; the count-weighted mean keeps them.
    contact = spec_of(contact_world())
    structure, layout = model.structure(contact), model.layout(contact)
    a, b = (contact.model.world.place_index(f"{x}@membrane") for x in ("A", "B"))
    for there, step_ in ((a, 0), (b, structure.steps)):  # forward from (A, C), reverse from (B, C)
        counts = np.zeros(structure.places, dtype=np.int64)
        counts[[there, contact.model.world.place_index("C@membrane")]] = 1
        totals = kernel.totals_of(counts, layout, np)
        fs, ts = kernel.states(counts, totals, layout, structure, np)
        rate = kernel.rates(counts, totals, fs, ts, layout, structure, np)[step_]
        assert rate == pytest.approx(1e9 * math.exp(-20.0), rel=1e-12)


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
    literal = renamed_mass_action("tests.reaction.literal_last_molecule@1", _literal)
    with scoped(literal):
        planted = lone("multinomial_less_one", "extinct", "tests.reaction.literal_last_molecule@1")
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


def _earlier_kept(total, moves):
    """Planted: §0.2a's earlier wording, rate 0 for any pair one of whose end states has an empty
    membrane, whether or not its step changes the membrane's count."""
    return (total == 0) | (total + moves == 0)


def test_kept_zeroes_only_the_pairs_that_change_the_membrane_s_count(monkeypatch):
    """At a probe state with an empty membrane, under `kept`: a pool step fires at the pool's mass
    action and a permeation at its own rate (E(m) = N + 1 = 1 under c = 0); a join to the empty
    membrane, and the last molecule's leave, have rate 0."""
    spec = spec_of(world(regular=False, catalysis=False))  # multinomial, kept
    w = spec.model.world
    mu = {p.name: w.species_by_id(p.species).mu(p.phase) for p in w.places}
    X_pool = math.exp(model.log_extent(w, "pool"))
    X_lumen = math.exp(model.log_extent(w, "lumen"))
    ids = [s.id for s in w.steps]
    empty = {"L@pool": 7, "S@pool": 5, "L@membrane": 0, "P@membrane": 0, "D@membrane": 0,
             "L@lumen": 2, "S@lumen": 1}  # fmt: skip
    plus, minus = rates_at(spec, empty)
    make, permeate = ids.index("make_L"), ids.index("permeate_S")
    assert plus[make] == pytest.approx(0.1 * X_pool * HELD_MM / 1000.0, rel=1e-13)
    assert minus[make] == pytest.approx(0.1 * math.exp(mu["L@pool"] - 2.0) * 7, rel=1e-13)
    assert plus[permeate] == pytest.approx(1.0 * 1 * 5 / X_pool, rel=1e-13)
    k_minus = math.exp(mu["S@lumen"] - mu["S@pool"])
    assert minus[permeate] == pytest.approx(k_minus * 1 * 1 / X_lumen, rel=1e-13)
    full_plus, full_minus = rates_at(spec_of(world()), empty)  # χ terms and catalysts: 0 and 1 here
    for r in (make, permeate):
        assert (full_plus[r], full_minus[r]) == (plus[r], minus[r])
    for joining in ("join_L", "inner_L"):  # Each changes the membrane's count from empty.
        assert plus[ids.index(joining)] == 0.0
    lone_state = empty | {"L@membrane": 1}
    assert rates_at(spec, lone_state)[1][ids.index("join_L")] == 0.0  # the last molecule stays
    released = rates_at(spec_of(world(regular=False, catalysis=False, last="reversible")), empty)
    assert released[0][ids.index("join_L")] > 0.0  # what kept removes: a join to the empty one
    monkeypatch.setattr(kernel, "kept_zero", _earlier_kept)
    planted_plus, planted_minus = rates_at(spec, empty)
    assert planted_plus[make] == planted_minus[make] == 0.0  # the pool step frozen: caught
    assert planted_plus[permeate] == planted_minus[permeate] == 0.0


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
    its rate is singular where the membrane holds exactly its reactants, A = B = E = 1, C = 0, so
    the world declares world_role: probe there (§0.2b rule 8)."""
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
        "free_energy": [{"law": "cells.free_energy.ideal_mixing@1"}],
        "founder": {"A@membrane": 1, "B@membrane": 1, "C@membrane": 0, "E@membrane": 1},
    } | ({"world_role": "probe"} if measure == "multinomial_less_one" else {})  # fmt: skip


def test_a_singular_state_of_g1_s_measure_is_reported_inf_and_a_run_that_reaches_it_stalls():
    """The declared convention (FORMAT.md; §0.2b rule 8): +inf in a probe world's table, and a run
    whose state is singular stops stalled (refused, nothing repaired); without world_role: probe
    the world is refused at parse (the spec tests)."""
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
    assert (
        runner.run(spec_of(singular_world("multinomial", "kept"), horizon=10.0)).status != "stalled"
    )
