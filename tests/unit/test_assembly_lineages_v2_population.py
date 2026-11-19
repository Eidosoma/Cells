"""OL2 milestone 3 in cells.assembly_lineages@2: the diagnostic record, Poisson shear times and
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
  every species is conserved, the books close, and relations@2 carries the lysed life.

World-compiling cost: one program (the division test's world, three runs of one structure); its
seconds on the timed lane are stated with its tier row. Reason: the record is the run's own.
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
from tests.assembly_lineage_v2_fixtures import definition
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


def pop_spec(founders, slots, *, sigma_max=1e3, horizon=5.0, mu_bilayer=-2.0):
    w = osmotic_world(L_pool=30, L_mem=0, S_pool=6, S_lumen=0, I_lumen=0, floor=4 * K_L,
                      sigma_max=sigma_max, mu_bilayer=mu_bilayer)  # fmt: skip
    w["population"] = {"structure": SHARED_POOL, "slots": slots, "founders": founders}
    d = definition(w, molecules=128, horizon=horizon, event_limit=20000, row_every=20,
                   uniforms=True)  # fmt: skip
    d["execution"]["mode"] = "population"
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

    s1 = pop_spec([FOUNDER], 1)
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
    s = pop_spec([FOUNDER, dict(FOUNDER, **{"L@membrane": 6})], 4)
    run = runner.run(s).check()
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
