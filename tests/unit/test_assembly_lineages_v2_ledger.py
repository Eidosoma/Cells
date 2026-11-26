"""The ledgers of cells.model.assembly_lineages@2 (OL1, §3.3), each claim with planted errors (D187).

- The ledger closes at every saved row: F(n_t) − F(n_0) = W − Q, to rounding, under both probed
  token pairs, with held exchange, a lumen, regular mixing and catalysis (planted: the heat's sign
  flipped, the reservoir work dropped; each leaves a residual far beyond rounding).
- The ideal term is exact (ln n!) and its incremental change is its value's difference (planted:
  Stirling's form, which differs at small counts).
- The regular term's incremental state equals its exact recomputation after a run of events, and
  its change is its value's difference (planted: an asymmetric chi, which breaks the update).
- Every declared moiety is conserved at every row, held exchange counted from the reservoir's
  supply (planted: the supply ignored).
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import (
    ideal_mixing,
    kernel,
    ledger,
    model,
    regular_mixing,
    runner,
)
from tests.assembly_lineage_v2_fixtures import definition, world

PAIRS = (("multinomial", "kept"), ("multinomial_less_one", "extinct"))


def run_of(measure, last, **kw):
    spec = parse_spec(definition(world(measure=measure, last=last), horizon=40.0, row_every=25,
                                 event_limit=3000, **kw))  # fmt: skip
    return spec, runner.run(spec)


@pytest.mark.parametrize("pair", PAIRS)
def test_the_ledger_closes_at_every_row_and_planted_bookings_do_not(pair):
    spec, run = run_of(*pair)
    rows = run.rows
    assert run.closure["holds"] and run.status in ("complete", "event_limit")
    assert len(rows["row_time"]) > 5 and np.max(np.abs(rows["reservoir_work_kT"])) > 1.0
    f, q, w = rows["free_energy_kT"], rows["event_heat_kT"], rows["reservoir_work_kT"]
    tolerance = ledger.closure_tolerance(np.abs(q).max() + np.abs(w).max(), 0.0, f, f[0])
    assert np.all(np.abs(ledger.residual(q, w, f, f[0])) <= tolerance)
    assert np.max(np.abs(ledger.residual(-q, w, f, f[0]))) > 1.0  # Planted: the heat's sign.
    assert np.max(np.abs(ledger.residual(q, 0 * w, f, f[0]))) > 1.0  # Planted: W dropped.


def host(spec):
    return model.structure(spec), model.layout(spec), model.tables(spec)


def test_the_ideal_term_is_exact_and_its_change_matches_its_value():
    spec = parse_spec(definition(world(regular=False, catalysis=False)))
    structure, layout, tables = host(spec)
    rng = np.random.default_rng(11)
    R = len(spec.model.world.steps)
    for _ in range(40):
        counts = np.zeros(structure.places, dtype=np.int64)
        for i, place in enumerate(spec.model.world.places):
            counts[i] = 0 if place.held else rng.integers(1, 9)
        totals = kernel.totals_of(counts, layout, np)
        for forward in (True, False):
            v = kernel.view(counts, totals, layout, structure.offset, forward, np)
            change = v.other - v.coeff  # The direction's move at its entries.
            delta = ideal_mixing.delta((), (), v, change, np)
            count_change, _ = runner.changes(layout, structure)
            for r in range(R):
                after = counts + count_change[r if forward else structure.steps + r]
                if np.any(after < 0):
                    continue
                exact = ideal_mixing.value(after, tables, ()) - ideal_mixing.value(
                    counts, tables, ()
                )
                assert delta[r] == pytest.approx(exact, abs=1e-11)
    # ln n! exactly: one membrane species' term at n molecules, against math.lgamma.
    n = np.zeros(structure.places, dtype=np.int64)
    i = spec.model.world.place_index("D@membrane")
    n[i] = 3
    mu = tables.mu0[i]
    assert ideal_mixing.value(n, tables, ()) == pytest.approx(
        3 * mu + math.lgamma(4) - math.lgamma(4), abs=1e-13
    )  # −ln N! + ln n_D! with N = n_D: they cancel.
    stirling = 3 * math.log(3) - 3  # Planted: Stirling's ln 3!, off by 0.8 k_BT at three.
    assert abs(stirling - math.lgamma(4)) > 0.5


def test_the_regular_term_is_exact_and_its_change_matches_its_value():
    spec = parse_spec(definition(world(catalysis=False), horizon=30.0, event_limit=200))
    structure, layout, tables = host(spec)
    (term_layout,) = layout.terms
    run = runner.run(spec)
    final = run.final
    y, s = final["term_states"][0]
    exact_y, exact_s = regular_mixing.state(final["counts"], final["totals"], term_layout, np)
    assert np.allclose(y, exact_y, rtol=0, atol=1e-10) and s == pytest.approx(exact_s, abs=1e-9)
    value = regular_mixing.value(final["counts"], tables, term_layout)
    N = final["totals"][kernel.MEMBRANE]
    assert value == pytest.approx(exact_s / (2 * N), abs=1e-12)
    # The change of each step equals the value's difference.
    counts = final["counts"].copy()
    totals = kernel.totals_of(counts, layout, np)
    state = regular_mixing.state(counts, totals, term_layout, np)
    v = kernel.view(counts, totals, layout, structure.offset, True, np)
    delta = regular_mixing.delta(state, term_layout, v, v.other - v.coeff, np)
    count_change, _ = runner.changes(layout, structure)
    for r in range(len(spec.model.world.steps)):
        after = counts + count_change[r]
        if np.all(after >= 0):
            exact = regular_mixing.value(after, tables, term_layout) - value
            assert delta[r] == pytest.approx(exact, abs=1e-11)
    # Planted: an asymmetric chi (A-B one way only) breaks the incremental update.
    (chi,) = term_layout
    skew = chi.copy()
    i, j = np.argwhere(chi != 0)[0]
    skew[i, j] += 0.5
    y0, s0 = regular_mixing.state(counts, totals, (skew,), np)
    places = np.asarray([j, i], dtype=np.int32)
    moved = np.asarray([1, 1], dtype=np.int64)
    y1, s1 = regular_mixing.update((y0, s0), (skew,), places, moved, np)
    after = counts.copy()
    after[[j, i]] += 1
    _, exact_s1 = regular_mixing.state(after, totals, (skew,), np)
    assert abs(s1 - exact_s1) > 0.1


def moieties(spec):
    """{moiety: [count per place]} of the world's places."""
    w = spec.model.world
    out = {}
    for i, place in enumerate(w.places):
        for moiety, count in w.species_by_id(place.species).moiety_counts().items():
            out.setdefault(moiety, np.zeros(len(w.places), dtype=np.int64))[i] += count
    return out


@pytest.mark.parametrize("pair", PAIRS)
def test_every_moiety_is_conserved_with_the_held_exchange_counted(pair):
    spec, run = run_of(*pair)
    rows = run.rows
    supplied = rows["reservoir_supplied"]
    assert supplied.any()  # The held precursor did exchange.
    for moiety, weights in moieties(spec).items():
        total = rows["place_count"] @ weights - supplied @ weights
        assert np.all(total == total[0]), moiety
    # Planted: the reservoir's supply ignored.
    weights = moieties(spec)["l"]
    assert not np.all(rows["place_count"] @ weights == (rows["place_count"] @ weights)[0])
