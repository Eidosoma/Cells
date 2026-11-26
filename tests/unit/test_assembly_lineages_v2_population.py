"""OL2 milestone 3 in cells.model.assembly_lineages@2: the diagnostic record, Poisson shear times and
§0.2d item 9 (slice 1); the shared pool, population division and serial transfer follow
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.8, §2.1, §2.6; the design note's §0.2d items 5, 6, 9, 10).

Each claim with a planted error it must catch (D187):
- P1: the diagnostic record of a single-lineage division run states every draw: each committed
  draw's uniforms, recomputed from its address, are the device's own; each schedule stop discards
  one counted draw (a run that ends at a stop has no ending draw); the step events rebuild the
  rows' counts
  (planted: a draw record missing its discarded draws no longer matches the device's sequence);
- P2: Poisson shear times are −ln(u)/λ gaps on the schedule's own stream (domain 6, its index),
  each gap its own draw from counter 0, the gap past the horizon recorded; the run's stream
  identity states domains 5 and 6 (planted: gaps drawn as one block differ);
- P3: every run of the family refuses to start with threefry's partitionable flag off, and the
  bundle's environment record states the flag (§0.2d item 9);
- P4: a world of one slot has the single assembly's rate table, channel by channel, and a world of
  two founders in four slots replays on the host from the world's stream through the two-level
  map (planted: one fold over every group's channels picks other events);
- P5: a vesicle's lysis frees its slot and the world goes on: its molecules return to the pool,
  every species is conserved, the books close, and relations@2 carries the lysed life;
- P6: in a population every daughter lives: daughter 0 keeps its parent's slot and the parent's
  counter, the others take free slots in slot order and open sub-lineages in world event order;
  too few free slots stop the run `slots_full` before the draw; each schedule pays its own column
  (planted: a key rule that numbers the second daughter's sub-lineage by generation differs);
- P7: a transfer keeps the K_keep smallest of one uniform per living assembly (its own draws on the
  schedule's stream), removes the rest, refreshes the pool, books the sink and its work column, and
  the books close (planted: keeping the largest picks other slots); the fresh pool above c_ext is
  refused. The diagnostic record states each draw's slot and the pool and slots after the transfer,
  and each shear event the state after it (OL5's run rows).

World-compiling cost: the division test's program (three runs) and the population program (one
structure at K = 1, 3 and 4), 81.31 s for the whole file on the timed lane. Reason: the records,
the selection map and the stops are the runs' own.
"""

import json
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import folds
from cells.models.assembly_lineages_v2 import (
    SHARED_POOL,
    diagnostic,
    division,
    kernel,
    model,
    population,
    records,
    runner,
    streams,
)
from cells.records import relations as rel
from tests.assembly_lineage_v2_fixtures import definition, site_binding
from tests.unit.test_assembly_lineages_v2_division import TIMES, spec_of, world_a
from tests.unit.test_assembly_lineages_v2_lumen import K_L, osmotic_world


def with_diagnostic(spec):
    import dataclasses

    return dataclasses.replace(
        spec, experiment=dataclasses.replace(spec.experiment, diagnostic=True)
    )


def test_the_diagnostic_record_states_every_draw_and_rebuilds_the_rows(tmp_path):
    s = with_diagnostic(spec_of(world_a()))
    run = runner.run(s).check()
    body, arrays = run.diagnostic["body"], run.diagnostic["arrays"]
    fates = arrays["draw_fate"]
    committed = fates == diagnostic.COMMITTED
    # Every committed draw is the device's own (checked in build; here against the trace too).
    assert committed.sum() == len(run.trace["event_channel"])
    np.testing.assert_array_equal(arrays["draw_uniforms"][committed],
                                  run.diagnostics["event_uniforms"])  # fmt: skip
    # One discarded draw per schedule stop, at the occupant's next counter. The last stop is the
    # horizon (10 s), so no later draw ends the run.
    assert (fates == diagnostic.DISCARDED).sum() == len(TIMES)
    assert (fates == diagnostic.ENDED).sum() == 0
    keys, counters = arrays["draw_key"], arrays["draw_counter"]
    for key in np.unique(keys):
        assert counters[keys == key].tolist() == list(range((keys == key).sum()))
    # Planted: without the discarded draws, the counters no longer run 0, 1, 2, ... per key.
    kept = fates != diagnostic.DISCARDED
    assert any(counters[kept & (keys == key)].tolist() != list(range((kept & (keys == key)).sum()))
               for key in np.unique(keys))  # fmt: skip
    # The step events rebuild the rows: the last event's state is the end row's.
    world = s.model.world
    vesicle, pool = diagnostic._split(world, run.rows["place_count"][-1])
    assert arrays["event_vesicle_after"][-1].tolist() == vesicle.tolist()
    assert arrays["event_pool_after"][-1].tolist() == pool.tolist()
    np.testing.assert_allclose(np.cumsum(arrays["event_heat_kT"])[-1],
                               run.rows["event_heat_kT"][-1], rtol=1e-12)  # fmt: skip
    # Each attempt's block is its address's draw; the states and the environment are stated.
    attempts = [a for stop in body["shear_events"] for a in stop["attempts"]]
    assert len(attempts) == len(run.division["fissions"]["fission_time"])
    first = attempts[0]
    block = arrays["attempt_uniforms"][: first["uniforms_count"]]
    layout = runner.model.layout(s)
    np.testing.assert_array_equal(
        block, division.block(layout.base_key, first["key"], 0, len(block))
    )
    for stop in body["shear_events"]:  # the state after each shear event (OL5's run rows)
        (attempt,) = stop["attempts"]
        if attempt["outcome"] == "split":
            followed = attempt["daughters"][attempt["followed"]]
            assert stop["slots_after"] == [{"slot": 0, "key": followed["key"],
                                            "counts": followed["counts"]}]  # fmt: skip
            assert stop["pool_after"] == attempt["pool_after"]
    assert body["environment"]["jax_threefry_partitionable"] is True
    assert body["end"] == run.status and body["states"]["final"]["slots"][0]["key"] == 5
    records.write_run(tmp_path / "d", run)
    assert json.loads((tmp_path / "d" / "diagnostic.json").read_text())["fates"] == list(
        diagnostic.FATES
    )
    manifest = json.loads((tmp_path / "d" / "manifest.json").read_text())
    assert manifest["runtime"]["jax_threefry_partitionable"] is True
    assert set(manifest["files_sha256"]) >= {"diagnostic.json", "diagnostic.npz"}


def test_poisson_shear_times_are_gaps_on_the_schedule_s_own_stream():
    w = world_a()
    d = spec_of(w)
    import dataclasses

    poisson = division.Schedule(3, "shear", 2, None, 0.5, None)
    s = dataclasses.replace(d, experiment=dataclasses.replace(d.experiment, schedules=(poisson,)))
    layout = runner.model.layout(s)
    events, draws = division.timeline(s.experiment.schedules, 10.0, layout.base_key)
    key = streams.stream_key_data(layout.base_key, 3, "schedule")
    t, want = 0.0, []
    for counter, (index, c, u, use, time) in enumerate(draws):
        assert (index, c, use) == (3, counter, "gap")
        assert u == float(np.asarray(streams.uniforms(key, counter, 1))[0])
        t -= math.log(u) / 0.5
        assert time == t
        want.append(t)
    assert want[-1] > 10.0 and all(x <= 10.0 for x in want[:-1])  # the gap past the horizon
    assert [e[0] for e in events] == want[:-1]
    planted = np.asarray(streams.uniforms(key, 0, len(draws)))  # one block, not one draw each
    assert planted[1] != draws[1][2]
    from cells.models.assembly_lineages_v2.spec import stream_identity

    stated = stream_identity(s)
    assert stated["domains"]["world"] == 5 and stated["domains"]["schedule"] == 6
    assert stated["reserved_domains"] == ["label"]
    assert "schedule" not in stream_identity(spec_of(w))["domains"]  # declared times: unchanged


def test_every_run_refuses_a_threefry_that_is_not_partitionable():
    import jax

    from cells.definitions.specs import parse_spec
    from tests.assembly_lineage_v2_fixtures import definition, world

    plain = parse_spec(definition(world()))  # an OL1 world: no geometry, no division
    jax.config.update("jax_threefry_partitionable", False)
    try:
        with pytest.raises(ConfigError, match="§0.2d item 9"):
            runner.run(plain)
    finally:
        jax.config.update("jax_threefry_partitionable", True)


FOUNDER = {"L@membrane": 8, "S@lumen": 1, "I@lumen": 2}


def pop_spec(founders, slots, *, sigma_max=1e3, horizon=5.0, mu_bilayer=-2.0, schedules=None,
             pool_step=False, mode="population"):  # fmt: skip
    w = osmotic_world(L_pool=30, L_mem=0, S_pool=6, S_lumen=0, I_lumen=0, floor=4 * K_L,
                      sigma_max=sigma_max, mu_bilayer=mu_bilayer)  # fmt: skip
    if pool_step:  # a pool-locus isomerisation, the pool group's own step (as ol2_shared's iso)
        from tests.assembly_lineage_v2_fixtures import step

        for name in ("A", "B"):
            w["species"].append({"id": name, "moieties": {"a": 1}, "standard_mu_RT":
                                 {"solution": 0.0 if name == "A" else 0.5}, "catalogue": None,
                                 "evidence": None})  # fmt: skip
            w["phases"]["pool"]["species"].append({"id": name, "kind": "finite"})
            w["founder"][f"{name}@pool"] = 6 if name == "A" else 0
        w["steps"].append(step("iso", {"A": 1}, {"B": 1}, 3.0, phase="pool"))
    w["population"] = {"structure": SHARED_POOL, "slots": slots, "founders": founders}
    d = definition(w, molecules=128, horizon=horizon, event_limit=20000, row_every=20,
                   uniforms=True)  # fmt: skip
    d["execution"]["mode"] = mode
    if schedules is not None:
        d["model"]["world"]["division"] = {"law": division.SHEAR_FISSION}
        d["experiment"]["schedules"] = schedules
    return parse_spec(d)


def host_rates(spec, pool, slots, alive):
    """[K + 1, 2R] on the host: the pool group's, then each slot's (kernel.rates, NumPy)."""
    structure, layout = model.structure(spec), model.layout(spec)
    m = population.masks(spec.model.world, structure.places, structure.steps)

    def one(c):
        totals = kernel.totals_of(c, layout, np)
        f, t = kernel.states(c, totals, layout, structure, np)
        return kernel.rates(c, totals, f, t, layout, structure, np)

    out = [np.where(m.pool, one(pool), 0.0)]
    out += [np.where(m.vesicle & a, one(pool + s), 0.0) for s, a in zip(slots, alive, strict=True)]
    return np.asarray(out), m


def test_one_slot_has_the_single_rate_table():
    import jax
    import jax.numpy as jnp

    s1 = pop_spec([FOUNDER], 1, pool_step=True)
    structure, layout = model.structure(s1), model.layout(s1)
    pool = model.founder(s1)
    vesicle = (
        np.asarray(population.founder_vectors(s1.model.world)[0])
        - pool[: len(s1.model.world.places)]
    )
    slot = np.zeros_like(pool)
    slot[: len(vesicle)] = vesicle
    m = population.masks(s1.model.world, structure.places, structure.steps)
    device = jax.tree_util.tree_map(jnp.asarray, layout)
    groups = np.asarray(
        population.all_rates(pool, slot[None], np.array([True]), device, structure, m)
    )
    c = pool + slot
    totals = kernel.totals_of(c, layout, np)
    f, t = kernel.states(c, totals, layout, structure, np)
    assert np.array_equal(groups.sum(axis=0), kernel.rates(c, totals, f, t, layout, structure, np))
    # Two founders in four slots: the host replays the world's draws through the two-level map.
    s = pop_spec([FOUNDER, dict(FOUNDER, **{"L@membrane": 6})], 4, pool_step=True)
    run = runner.run(s).check()
    assert (run.trace["event_group"] == 0).any()  # the pool group fires
    layout = model.layout(s)
    stream = streams.stream_key_data(layout.base_key, streams.WORLD_CARRIER, "world")
    count_change, _ = runner.changes(layout, model.structure(s))
    R = model.structure(s).steps
    P = model.structure(s).places
    pool = model.founder(s)
    slots = np.zeros((4, P), dtype=np.int64)
    for i, v in enumerate(population.founder_vectors(s.model.world)):
        slots[i, : len(v)] = np.asarray(v) - pool[: len(v)]
    alive = np.array([True, True, False, False])
    picks, flat, time = [], [], 0.0
    for counter in range(len(run.trace["event_channel"])):
        a, m = host_rates(s, pool, slots, alive)
        u = np.asarray(streams.uniforms(stream, counter, 3))
        prefixes = np.stack([folds.prefix(g, np) for g in a])
        totals = prefixes[:, -1]
        running = folds.prefix(totals, np)
        a0 = running[-1]
        g = int(np.argmax(running > min(u[1] * a0, np.nextafter(a0, 0.0))))
        j = int(np.argmax(prefixes[g] > min(u[2] * totals[g], np.nextafter(totals[g], 0.0))))
        whole = folds.prefix(a.reshape(-1), np)  # planted: one fold over every group's channels
        flat.append(int(np.argmax(whole > min(u[1] * a0, np.nextafter(a0, 0.0)))))
        time += -np.log(u[0]) / a0
        change = count_change[j]
        pool = pool + np.where(m.place_vesicle, 0, change)
        if g > 0:
            slots[g - 1] += np.where(m.place_vesicle, change, 0)
        picks.append((g, j + 1 if j < R else -(j - R + 1)))
    got = list(
        zip(run.trace["event_group"].tolist(), run.trace["event_channel"].tolist(), strict=True)
    )
    assert picks == got
    np.testing.assert_allclose(time, run.trace["event_time"][-1], rtol=1e-12)
    want_flat = [g * 2 * R + (c - 1 if c > 0 else R - c - 1) for g, c in got]
    assert flat != want_flat  # Planted: one fold over every channel is caught.


def test_a_lysis_frees_its_slot_and_the_world_goes_on(tmp_path):
    from cells.models.assembly_lineages_v2 import lumen

    tense = dict(FOUNDER, **{"L@membrane": 6, "I@lumen": 6})
    probe = pop_spec([FOUNDER, tense], 4, mu_bilayer=3.0)  # L leaves: the membranes shrink
    sigma = lumen.host_tension(probe.model.world, population.founder_vectors(probe.model.world)[1])
    s = pop_spec([FOUNDER, tense], 4, sigma_max=sigma * 1.001, horizon=5.0, mu_bilayer=3.0)
    run = runner.run(s).check()
    lyses = run.population["lyses"]
    assert lyses and run.status == "complete" and run.closure["holds"]
    after = run.rows["row_time"] > lyses[0]["time_s"]
    assert run.rows["slot_key"][after][:, lyses[0]["slot"]].max() == -1  # its slot freed
    assert run.trace["event_time"][-1] > lyses[0]["time_s"]  # the world went on
    names = [p.name for p in s.model.world.places]
    species = [p.species for p in s.model.world.places]
    totals = run.rows["pool_count"] + run.rows["slot_count"].sum(axis=1)
    by_species = np.stack([totals[:, [i for i, x in enumerate(species) if x == sp]].sum(axis=1)
                           for sp in sorted(set(species))])  # fmt: skip
    assert (by_species == by_species[:, :1]).all() and names  # a closed world: conserved
    records.write_run(tmp_path / "p", run)
    descriptor, tables = rel.read(tmp_path / "p")
    assert descriptor["format"] == rel.FORMAT_V2
    ends = {life["key"]: life["end_reason"] for life in population.lives(run)}
    assert ends[lyses[0]["key"]] == "lysed"


def test_every_daughter_lives_and_too_few_slots_stop_the_run(tmp_path):
    shear = [{"index": 2, "kind": "shear", "k": 2, "times_s": [1.0, 2.0]}]
    s = pop_spec([dict(FOUNDER, **{"L@membrane": 12}), dict(FOUNDER, **{"L@membrane": 10})], 4,
                 schedules=shear)  # fmt: skip
    run = runner.run(s).check()
    table = run.population["fissions"]
    outcomes = [division.POPULATION_OUTCOMES[o] for o in table["fission_outcome"]]
    assert outcomes == ["split", "split", "slots_full"]  # the third finds no free slot
    assert run.status == "slots_full" and table["fission_counter"].tolist() == [0, 0, -1]
    key = lambda s, c: (s << 32) + c  # noqa: E731
    assert table["fission_daughters"].tolist() == [[key(0, 1), key(0, 2)], [key(1, 1), key(1, 2)],
                                                   [-1, -1]]  # fmt: skip
    assert table["fission_daughter_slots"].tolist() == [[0, 2], [1, 3], [-1, -1]]
    lives = {life["key"]: life for life in population.lives(run)}
    assert lives[key(0, 0)]["end_reason"] == lives[key(1, 0)]["end_reason"] == "divided"
    # Daughter 0 continues its parent's sub-lineage; the second daughters open 2 and 3 in world
    # event order (the slot-0 split first). Planted: by generation they would tie.
    assert [lives[key(0, 1)]["lineage"], lives[key(0, 2)]["lineage"]] == [0, 2]
    assert [lives[key(1, 1)]["lineage"], lives[key(1, 2)]["lineage"]] == [1, 3]
    assert all(life["end_reason"] == "censored" for life in lives.values()
               if life["birth_kind"] == "division")  # fmt: skip
    rows = run.rows
    assert np.allclose(rows["schedule_work_kT"][:, 0], rows["shear_work_kT"], rtol=0, atol=0)
    assert run.closure["holds"] and rows["shear_work_kT"][-1] != 0
    records.write_run(tmp_path / "s", run)
    descriptor, tables = rel.read(tmp_path / "s")
    assert descriptor["format"] == rel.FORMAT_V2
    assert sum(1 for e in tables["events"] if e.kind == "fission") == 2


def test_a_transfer_keeps_a_uniform_sample_and_refreshes_the_pool(tmp_path):
    from cells.models.assembly_lineages_v2 import transfer

    founders = [dict(FOUNDER, **{"L@membrane": n}) for n in (8, 9, 10)]
    schedules = [{"index": 4, "kind": "transfer", "times_s": [1.0], "K_keep": 1,
                  "fresh_pool": [5, 2, 0]}]  # fmt: skip
    s = with_diagnostic(pop_spec(founders, 4, schedules=schedules, horizon=2.0))
    run = runner.run(s).check()
    (t,) = run.population["transfers"]
    # The diagnostic record: the world's draws at counters 0, 1, ...; the crossing draw at the
    # transfer is discarded, the last ends the run; the transfer's three draws are recorded.
    arrays, body = run.diagnostic["arrays"], run.diagnostic["body"]
    assert arrays["draw_counter"].tolist() == list(range(len(arrays["draw_counter"])))
    fates = arrays["draw_fate"].tolist()
    assert fates.count(diagnostic.DISCARDED) == 1 and fates[-1] == diagnostic.ENDED
    assert arrays["schedule_draw_use"].tolist() == [1, 1, 1]
    assert body["transfer_events"][0]["kept"] == t["kept"]
    from cells.models.assembly_lineages_v2.spec import stream_identity

    stated = stream_identity(s)  # a population draws on domain 5, a transfer on domain 6
    assert stated["domains"]["world"] == 5 and stated["domains"]["schedule"] == 6
    layout = model.layout(s)
    key = streams.stream_key_data(layout.base_key, 4, "schedule")
    us = [float(np.asarray(streams.uniforms(key, c, 1))[0]) for c in range(3)]
    assert [d[2] for d in t["draws"]] == us and [d[1] for d in t["draws"]] == [0, 1, 2]
    assert t["kept"] == [int(np.argmin(us))]  # the smallest; planted: the largest differs
    assert t["kept"] != [int(np.argmax(us))]
    event = body["transfer_events"][0]  # OL5's run rows: each draw's slot, the state after
    assert [(d["slot"], d["counter"], d["uniform"]) for d in event["draws"]] == list(
        zip(range(3), range(3), us, strict=True)
    )
    assert event["pool_after"][:3] == [5, 2, 0]
    assert [x["slot"] for x in event["slots_after"]] == t["kept"]
    assert sorted(t["removed"]) == sorted(set(range(3)) - set(t["kept"]))
    rows = run.rows
    after = np.flatnonzero(rows["row_kind"] == population.TRANSFER)[0]
    assert rows["pool_count"][after, :3].tolist() == [5, 2, 0]  # the fresh pool
    assert rows["schedule_work_kT"][after, 0] == pytest.approx(t["work_kT"], rel=1e-12)
    assert rows["discarded_free_energy_kT"][after] == pytest.approx(t["sink_kT"], rel=1e-12)
    assert run.closure["holds"]
    ends = {life["key"]: life["end_reason"] for life in population.lives(run)}
    assert sorted(ends.values()).count("removed") == 2
    records.write_run(tmp_path / "t", run)
    descriptor, tables = rel.read(tmp_path / "t")
    assert sum(1 for e in tables["events"] if e.kind == "transfer") == 1
    with pytest.raises(ConfigError, match="exceed c_ext"):
        too_many = [dict(schedules[0], fresh_pool=[10**9, 0, 0])]
        pop_spec(founders, 4, schedules=too_many)
    assert transfer.SERIAL_TRANSFER == "cells.operator.serial_transfer@1"


REFUSALS = {
    "population_mode_without_a_population": ({"mode": "single_lineage"}, "exactly when the world"),
    "a_population_declares_no_continuation": (
        {"schedules": [{"index": 0, "kind": "shear", "k": 2, "times_s": [1.0]}],
         "continuation": "first"}, "declares no continuation"),
    "a_fresh_pool_of_the_wrong_length": (
        {"schedules": [{"index": 0, "kind": "transfer", "times_s": [1.0], "K_keep": 1,
                        "fresh_pool": [1]}]}, "one count per finite pool place"),
    # FR-21 (§0.2f): the requester's binding on the one-particle fixture, its pair undeclared.
    "an_undeclared_site_binding": ({"binding": "undeclared"}, "crosses phases at the membrane"),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_the_shared_pool(case):
    change, message = REFUSALS[case]
    w = osmotic_world(L_pool=30, L_mem=0, S_pool=6, S_lumen=0, I_lumen=0, floor=4 * K_L)
    founder = FOUNDER
    if "binding" in change:
        site_binding(w, declared=change["binding"] == "declared")
        founder = dict(FOUNDER, **{"R@membrane": 4, "XR@membrane": 2})
    w["population"] = {"structure": SHARED_POOL, "slots": 2, "founders": [founder]}
    d = definition(w, molecules=128, horizon=5.0)
    d["execution"]["mode"] = change.get("mode", "population")
    if "schedules" in change:
        d["experiment"]["schedules"] = change["schedules"]
        d["model"]["world"]["division"] = {"law": division.SHEAR_FISSION}
    if "continuation" in change:
        d["model"]["world"]["division"]["continuation"] = change["continuation"]
    with pytest.raises(ConfigError, match=message):
        parse_spec(d)
