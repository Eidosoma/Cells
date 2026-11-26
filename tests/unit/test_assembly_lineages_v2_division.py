"""OL3 milestone 1: single-lineage division at shear events in cells.model.assembly_lineages@2
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §2.1–§2.5; the design note's §0.2c rules 9–13, §0.2d items
6, 7, 9 and 10, §0.2e).

Each claim with a planted error it must catch (D187):
- D0: admission refuses before any draw: the stress test, then 36πkV² ≤ A³ on both sides of
  V_sph(A)/√k (planted: a refused attempt that computes an energy fails);
- D1: C3x is rule 9 exactly, against a direct reading of the rule, and at equal weights its law is
  the multivariate hypergeometric on the balanced size vector in a random order, by exact
  enumeration (planted: the largest minimising cut, and ties ranked by reverse position);
- D2: the lumen split is rule 10's multinomial, p_j ∝ V_sph(A_j), cumulated in π's order
  (planted: p_j ∝ A_j);
- D3: a lineage divides at its declared times in item 10.2's order. The fission counter counts
  draws, the daughters take the next keys, the followed daughter is recorded, and the trace
  replays on the host from the streams under the clock rule (planted: the draw discarded at a
  schedule time not counted);
- D4: the shear work is Σ_j F_v(d_j) − F_v(parent) in closed form, and the books close with it and
  the sink (planted: F_v without its closure cost; the sink left out);
- D5: a followed daughter born beyond σ_max ends the lineage lysed at its birth, booked as a lysis,
  and cells.relations@2 carries the lysed life (planted: relations@1 refuses it);
- D6: the refusals this milestone owns, §0.2d item 9's among them.

World-compiling cost: one program (three runs of one structure), 37.64 s for the whole file on the
timed lane; D1, D2 and D6 are host arithmetic. Reason: the clock rule and the booking need the
device's run.
"""

import itertools
import math
from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    SHEAR_FISSION,
    division,
    kernel,
    ledger,
    model,
    records,
    runner,
    streams,
)
from cells.records import relations as rel
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_lumen import C_EXT_MM, K_L, NA, Q, osmotic_world

TIMES = [2.0, 4.0, 6.0, 8.0, 10.0]
CLOSE = 25.0  # the osmotic world's declared closure cost (k_BT)


def c3x_by_the_rule(counts, quanta, k, u, *, smallest=True, reverse_ties=False):
    """Rule 9 read directly, with loops (the test's own reading)."""
    molecules = [s for s, n in enumerate(counts) for _ in range(n)]
    n = len(molecules)
    positions = sorted(range(n), key=lambda i: (u[i], -i if reverse_ties else i))
    ranked = [molecules[i] for i in positions]
    prefix = [0]
    for s in ranked:
        prefix.append(prefix[-1] + quanta[s])
    total, cuts = prefix[-1], [0]
    for t in range(1, k):
        gaps = [(abs(k * prefix[c] - t * total), c) for c in range(cuts[-1], n + 1)]
        best = min(g for g, _ in gaps)
        chosen = [c for g, c in gaps if g == best]
        cuts.append(chosen[0] if smallest else chosen[-1])
    cuts.append(n)
    blocks = [[sum(1 for s in ranked[cuts[t]:cuts[t + 1]] if s == g) for g in range(len(counts))]
              for t in range(k)]  # fmt: skip
    pi = sorted(range(k), key=lambda t: (u[n + t], t))
    return np.asarray(blocks), np.asarray(pi)


def test_c3x_and_the_lumen_split_are_rule_9_and_10_s_laws():
    rng = np.random.default_rng(7)
    # D1: unequal weights, with ties (uniforms on a grid of eighths), against the rule's reading.
    counts, quanta, k = [4, 3, 2], [3, 2, 5], 3
    differ = False
    for _ in range(200):
        u = (rng.integers(0, 8, size=sum(counts) + k) + 0.5) / 8
        blocks, pi, _ = division.c3x(counts, quanta, k, u)
        want, want_pi = c3x_by_the_rule(counts, quanta, k, u)
        assert np.array_equal(blocks, want) and np.array_equal(pi, want_pi)
        planted, _ = c3x_by_the_rule(counts, quanta, k, u, reverse_ties=True)
        differ |= not np.array_equal(planted, want)
    assert differ  # Planted: ties ranked by reverse position is caught.
    # D1: equal weights, N = 5, k = 2, by exact enumeration of the 5! rankings and both orders.
    # The cut is the smallest minimiser of |2 S_c − 5|, c = 2: blocks of 2 and 3, then a random
    # order, so daughter 0 holds m ∈ {2, 3} with probability 1/2 and a hypergeometric composition.
    counts, quanta = [3, 2], [1, 1]
    seen = {}
    for ranking in itertools.permutations(range(5)):
        for order in ([0.25, 0.75], [0.75, 0.25]):
            u = np.asarray([(r + 0.5) / 5 for r in ranking] + order)
            blocks, pi, _ = division.c3x(counts, quanta, 2, u)
            assert blocks[0].sum() == 2  # the smallest minimising cut
            planted, _ = c3x_by_the_rule(counts, quanta, 2, u, smallest=False)
            assert planted[0].sum() == 3  # Planted: the largest minimising cut is caught.
            daughter = tuple(blocks[np.argsort(pi)][0])  # block t goes to daughter pi[t]
            seen[daughter] = seen.get(daughter, 0) + 1
    law = {}
    for m in (2, 3):
        for a in range(0, m + 1):
            if a <= 3 and m - a <= 2:
                law[(a, m - a)] = Fraction(1, 2) * Fraction(
                    math.comb(3, a) * math.comb(2, m - a), math.comb(5, m)
                )
    assert {d: Fraction(n, 240) for d, n in seen.items()} == law
    # D2: the lumen split's law, on a grid of M uniforms for M molecules of one species.
    M, pi, areas = 100_000, np.asarray([1, 0, 2]), np.asarray([1.0, 2.0, 3.0])
    grid = (np.arange(M) + 0.5) / M
    got = division.lumen_split([M], pi, areas, grid)[:, 0]
    p = areas**1.5 / np.sum(areas**1.5)
    assert np.all(np.abs(got - M * p) <= 1)
    first = division.lumen_split([1], pi, areas, [p[pi[0]] * (1 - 1e-9)])[:, 0]
    assert first.tolist() == [0, 1, 0]  # u below p_pi(0) goes to daughter pi(0) = 1
    assert np.any(np.abs(got - M * areas / areas.sum()) > 1)  # Planted: p ∝ A is caught.
    # split(): daughters' membranes are C3x's blocks by π, their lumens rule 10's by their areas.
    u = rng.random(9 + 2 + 4)
    by_m, by_l = division.split([5, 4], [2, 3], [4], 2, 1e-19, u)
    blocks, pi, w = division.c3x([5, 4], [2, 3], 2, u[:11])
    assert np.array_equal(by_m[pi], blocks) and by_l.sum() == 4


def world_a(**kw):
    w = osmotic_world(L_pool=20, L_mem=12, S_pool=4, S_lumen=0, I_lumen=2, floor=4 * K_L, **kw)
    w["division"] = {"law": SHEAR_FISSION, "continuation": "uniform"}
    return w


def spec_of(w, *, seed=1, times=TIMES, horizon=10.0, stress=None):
    d = definition(w, molecules=64, horizon=horizon, event_limit=20000, row_every=50,
                   uniforms=True, seed=seed)  # fmt: skip
    d["experiment"]["schedules"] = [{"index": 0, "kind": "shear", "k": 2, "times_s": times}]
    if stress is not None:
        d["experiment"]["schedules"][0]["stress_Pa"] = stress
    return parse_spec(d)


def oracle(spec, table, *, counted=True):
    """(channels, times) replayed on the host from the declaration: each occupant's draws are
    regenerated from its stream (its key, domain 1) at its counter; at a schedule time the draw
    that crosses it is discarded and (if counted) counted; at a split the followed daughter takes
    the slot, its counter at 0, after its daughters are checked against rules 9 and 10's split of
    the parent's own block (domain 2, its key, its counter)."""
    world = spec.model.world
    structure, layout = model.structure(spec), model.layout(spec)
    P = len(world.places)
    counts = model.founder(spec).copy()
    change, _ = runner.changes(layout, structure)
    R, horizon = structure.steps, spec.experiment.time_horizon_s
    stops = sorted({t for s in spec.experiment.schedules for t in s.times if t <= horizon})
    membrane, inside = division.vesicle_places(world)
    quanta = division.geometry.place_quanta(world, P)
    key, counter, time, row = 0, 0, 0.0, 0
    stream = streams.stream_key_data(layout.base_key, 0, "events")
    channels, times = [], []
    while True:
        stop = stops[0] if stops else horizon
        totals = kernel.totals_of(counts, layout, np)
        f_state, t_states = kernel.states(counts, totals, layout, structure, np)
        prefix = np.cumsum(kernel.rates(counts, totals, f_state, t_states, layout, structure, np))
        total = prefix[-1]
        u1, u2 = np.asarray(streams.uniforms(stream, counter, 2))
        wait = -np.log(u1) / total if total > 0 else np.inf
        if time + wait > stop:
            if not stops:
                return np.asarray(channels), np.asarray(times)
            stops.pop(0)
            time, counter = stop, counter + (1 if counted else 0)
            while row < len(table["fission_time"]) and table["fission_time"][row] == stop:
                r, row = row, row + 1
                if table["fission_outcome"][r] != 0:
                    continue
                n, n_l = counts[membrane].sum(), counts[inside].sum()
                # The plain draw: division.block's power-of-two prefix is the same, bit for bit.
                part = streams.stream_key_data(layout.base_key, key, "partition")
                u = np.asarray(streams.uniforms(part, table["fission_counter"][r], n + 2 + n_l))
                by_m, by_l = division.split(counts[membrane], quanta[membrane], counts[inside], 2,
                                            Q, u)  # fmt: skip
                daughters = table["fission_daughter_counts"][r]
                assert np.array_equal(daughters[:, membrane], by_m)
                assert np.array_equal(daughters[:, inside], by_l)
                c = streams.stream_key_data(layout.base_key, key, "continuation")
                j = int(np.floor(float(streams.uniforms(c, 0, 1)[0]) * 2))
                assert j == table["fission_followed"][r]
                counts[:P] = daughters[j]
                key, counter = int(table["fission_daughters"][r, j]), 0
                stream = streams.stream_key_data(layout.base_key, key, "events")
            continue
        j = int(np.argmax(prefix > min(u2 * total, np.nextafter(total, 0.0))))
        time, counter = time + wait, counter + 1
        counts = counts + change[j]
        channels.append(j + 1 if j < R else -(j - R + 1))
        times.append(time)


def vesicle_f(world, counts):
    """F_v in closed form for the osmotic world: n_L μ°_bilayer (one membrane species, so no
    mixing), Σ ln n! over the lumen (μ° = 0, X = 1), F_osm at V(n), and the closure cost."""
    names = [p.name for p in world.places]
    n = dict(zip(names, counts, strict=True))
    lumen_n = n["S@lumen"] + n["I@lumen"]
    area = Q * K_L * n["L@membrane"] / 2.0
    v = min(lumen_n / (NA * C_EXT_MM / 1e3), area**1.5 / (6 * math.sqrt(math.pi)) * 1e3)
    osm = (-lumen_n * math.log(NA * 1.0 * v) if lumen_n else 0.0) + NA * C_EXT_MM / 1e3 * v
    return (-2.0 * n["L@membrane"] + math.lgamma(n["S@lumen"] + 1) + math.lgamma(n["I@lumen"] + 1)
            + osm + CLOSE)  # fmt: skip


def test_admission_refuses_before_any_draw():
    """Item 10.2's first step on the host: the stress test, then v <= k^(-1/2), as 36 pi k V^2 <=
    A^3, from the test's own closed form; a refused assembly draws nothing (counter -1)."""
    a = Q * K_L * 12 / 2.0  # m², twelve L
    edge_L = a**1.5 / (6 * math.sqrt(math.pi)) / math.sqrt(2) * 1e3  # V_sph(A)/sqrt(2), in L
    assert division.admitted_volume(edge_L * (1 - 1e-9), K_L * 12, Q, 2)
    assert not division.admitted_volume(edge_L * (1 + 1e-9), K_L * 12, Q, 2)
    w = world_a()
    w["division"]["critical_stress_Pa"] = {"value": 2.0, "provenance": "unsourced; test"}
    world = spec_of(w, stress=3.0).model.world
    names = [p.name for p in world.places]
    tense = np.zeros(len(names), dtype=np.int64)
    tense[names.index("L@membrane")] = 12
    tense[names.index("I@lumen")] = math.ceil(edge_L * NA * C_EXT_MM / 1e3)  # just past the edge

    def never(_):
        raise AssertionError("a refused attempt computes no energy")

    for stress, outcome in ((1.0, "refused_stress"), (3.0, "refused_volume")):
        got = division.attempt(world, tense, 0, 0, (1.0, 0, 2, stress), (0, 1), never, 1)
        assert (got.outcome, got.counter, got.keys) == (outcome, -1, ())


def test_a_lineage_divides_at_its_schedule_books_its_work_and_replays(tmp_path):
    s = spec_of(world_a())
    run = runner.run(s).check()
    table = run.division["fissions"]
    world = s.model.world
    # D3: one attempt per declared time, in order; three splits, then two refused at the floor.
    assert table["fission_time"].tolist() == TIMES
    outcomes = [division.OUTCOMES[o] for o in table["fission_outcome"]]
    assert outcomes == ["split"] * 3 + ["refused_floor"] * 2
    # The fission counter counts draws: the parent refused at 8 s draws again at 10 s.
    parents = table["fission_parent"].tolist()
    for r, parent in enumerate(parents):
        drew = sum(1 for q in range(r) if parents[q] == parent and table["fission_counter"][q] >= 0)
        assert table["fission_counter"][r] == drew
    # The daughters take the lineage counter's next keys; each split records the followed one.
    splits = np.flatnonzero(table["fission_outcome"] == 0)
    assert table["fission_daughters"][splits].tolist() == [[1, 2], [3, 4], [5, 6]]
    assert all(table["fission_followed"][r] in (0, 1) for r in splits)
    channels, times = oracle(s, table)
    assert np.array_equal(channels, run.trace["event_channel"])
    np.testing.assert_allclose(times, run.trace["event_time"], rtol=1e-12, atol=0)
    planted, _ = oracle(s, table, counted=False)
    assert not np.array_equal(planted, run.trace["event_channel"])  # Planted: caught.
    # D4: the shear work in closed form, (k − 1) C_close included; the books close with the sink.
    for r in splits:
        daughters = table["fission_daughter_counts"][r]
        parent = vesicle_f(world, table["fission_parent_counts"][r])
        want = sum(vesicle_f(world, d) for d in daughters) - parent
        assert table["fission_shear_work_kT"][r] == pytest.approx(want, rel=1e-12, abs=1e-12)
        no_close = sum(vesicle_f(world, d) - CLOSE for d in daughters) - (parent - CLOSE)
        assert abs(no_close - want) == pytest.approx(CLOSE)  # Planted: caught by (k − 1) C_close.
    assert run.closure["holds"]
    rows = run.rows
    open_books = ledger.residual(rows["event_heat_kT"], rows["reservoir_work_kT"]
                                 + rows["shear_work_kT"], rows["free_energy_kT"],
                                 rows["free_energy_kT"][0])  # fmt: skip
    assert abs(open_books[-1]) == pytest.approx(rows["discarded_free_energy_kT"][-1], rel=1e-9)
    assert rows["discarded_free_energy_kT"][-1] != 0  # Planted: the sink left out is caught.
    # The bundle and its relationship tables (cells.relations@2), read back.
    records.write_run(tmp_path / "a", run)
    _, run_record, arrays = records.read(tmp_path / "a")
    assert run_record["division"]["outcomes"] == {
        "split": 3,
        "refused_stress": 0,
        "refused_volume": 0,
        "refused_floor": 2,
    }
    assert "discarded" in run_record["ssa"]["draw"] and set(table) <= set(arrays)
    assert {r["base"] for r in run_record["records"].values()} <= set(run_record["time"]["bases"])
    descriptor, tables = rel.read(tmp_path / "a")
    assert descriptor["format"] == rel.FORMAT_V2 and "lysed" in descriptor["vocabulary"][
        "end_reasons"]  # fmt: skip
    reasons = [life["end_reason"] for life in run.division["lives"]]
    assert reasons.count("divided") == 3 and reasons.count("not_followed") == 3
    assert reasons.count("censored") == 1


def test_a_daughter_born_beyond_sigma_max_ends_the_lineage_lysed(tmp_path):
    w = osmotic_world(L_pool=20, L_mem=12, S_pool=0, S_lumen=0, I_lumen=8, floor=4 * K_L,
                      sigma_max=1e-9)  # fmt: skip
    w["division"] = {"law": SHEAR_FISSION, "continuation": "first"}
    run = runner.run(spec_of(w, seed=21)).check()
    table = run.division["fissions"]
    assert run.status == "lysed" and run.closure["holds"]
    assert run.rows["row_time"][-1] == 4.0 and table["fission_lysed_at_birth"][1, 0]
    names = [p.name for p in run.spec.model.world.places]
    end = dict(zip(names, run.rows["place_count"][-1], strict=True))
    assert end["L@membrane"] == end["I@lumen"] == 0  # released into the pool
    assert run.osmotic["lysis"]["time_s"] == 4.0
    (life,) = [x for x in run.division["lives"] if x["end_reason"] == "lysed"]
    assert (life["key"], life["end_reason"], life["end_event"]) == (3, "lysed", "event:lysis/3")
    records.write_run(tmp_path / "b", run)
    descriptor, _ = rel.read(tmp_path / "b")
    assert descriptor["format"] == rel.FORMAT_V2
    tables = records.relation_tables(tmp_path / "b", run)
    with pytest.raises(rel.RelationsRefused, match="end_reason 'lysed'"):
        rel.tables(world=run.qualifier, version=rel.FORMAT, **tables)  # Planted: @1 refuses it.


def _declared_lumen(w):
    w["conventions"]["lumen_volume"] = "declared"
    w["phases"]["lumen"]["volume_L"] = 1e-22
    w["free_energy"] = w["free_energy"][:1]
    w["geometry"].pop("sigma_max_N_per_m")


def _schedule(**entry):
    return [{"index": 0, "kind": "shear", "k": 2, "times_s": [1.0], **entry}]


REFUSALS = {
    "division_without_an_osmotic_lumen": (_declared_lumen, None, "needs a geometry and an osmotic"),
    "a_shear_schedule_without_k": (None, [{"index": 0, "kind": "shear", "times_s": [1.0]}],
                                   "schedule keys are"),
    "a_schedule_without_division": (lambda w: w.pop("division"), _schedule(), "needs the world's"),
    "times_and_a_poisson_rate_both": (None, [{"index": 0, "kind": "shear", "k": 2,
                                              "times_s": [1.0], "poisson_rate_per_s": 1.0}],
                                      "schedule keys are"),
    "an_unknown_continuation": (lambda w: w["division"].update(continuation="second"), None,
                                "continuation is one of"),
    "times_not_increasing": (None, _schedule(times_s=[2.0, 1.0]), "strictly increasing"),
    "a_stress_without_a_critical_stress": (None, _schedule(stress_Pa=1.0), "schedule keys are"),
    "two_schedules_share_a_time": (None, [*_schedule(), {"index": 1, "kind": "shear", "k": 2,
                                                         "times_s": [1.0, 2.0]}], "share the time"),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_single_lineage_division(case):
    mutate, schedules, message = REFUSALS[case]
    w = world_a()
    if mutate is not None:
        mutate(w)
    d = definition(w, molecules=64, horizon=10.0)
    d["experiment"]["schedules"] = schedules or _schedule()
    with pytest.raises(ConfigError, match=message):
        parse_spec(d)


def test_division_refuses_a_threefry_that_is_not_partitionable():
    import jax

    s = spec_of(world_a())
    jax.config.update("jax_threefry_partitionable", False)
    try:
        with pytest.raises(ConfigError, match="§0.2d item 9"):
            runner.run(s)
    finally:
        jax.config.update("jax_threefry_partitionable", True)
