"""Independent reaction histories, material conservation and complete replay; and a pool's switch
path, with the observable it is read by (G-7).

The path's references are the pool's kernel walked one event at a time on one world, a closed form,
and a search for rings that counts nothing. Its rows hold planted errors that must fail them (D187):
a pool given another pool's seed, a wrong comparison in the observable, and a level read on the
wrong side of its event. What a path drives is in test_composed_worlds.py.
"""

import functools
import itertools
import json
import os
from dataclasses import replace
from fractions import Fraction

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.assembly.graph import EDGES, FULL
from cells.assembly.kernel import random_pair
from cells.assembly.spec import AssemblyError
from cells.assembly_pool import kernel, observables, reference, schedule
from cells.assembly_pool.engine import initial_state, run, validate_state
from cells.assembly_pool.io import load_checkpoint, write_checkpoint
from cells.assembly_pool.spec import AVOGADRO, FULL_BONDS, parse_spec
from cells.definitions.specs import ConfigError
from cells.registry import laws as law_registry

BACKEND = os.environ.get("CELLS_POOL_TEST_BACKEND", "cpu")


def assert_same(a, b):
    for name, x, y in zip(a._fields, a, b, strict=True):
        assert np.asarray(x).tobytes() == np.asarray(y).tobytes(), name


def test_independent_event_histories():
    spec = parse_spec(
        {
            "worlds": 8,
            "end_time_s": 2.0,
            "recording": "events",
            "max_events_per_world": 3000,
            "event_chunk_size": 32,
            "k_on_M_inv_s": 1e9,
            "initial_free_trimers": 15,
            "k_fragment_dissolve_s_inv": 20.0,
        }
    )
    chunks = []
    state, result = run(
        spec,
        backend=BACKEND,
        callback=lambda _, s, t: chunks.append(tuple(np.asarray(x) for x in t)),
    )
    traces = [np.concatenate([chunk[j] for chunk in chunks]) for j in range(5)]
    assert all(value > 0 for value in result["reaction_counts"].values())
    device = device_for("cpu")
    for world in range(spec.worlds):
        count = int(state.event_count[world])
        with jax.default_device(device):
            variates = jax.vmap(
                lambda event, world=world: random_pair(
                    np.uint32(spec.seed), np.uint32(world), event
                )
            )(np.arange(count + 1, dtype=np.uint32))
        expected = reference.trajectory(spec, np.asarray(variates))
        observed = [x[:, world][traces[4][:, world] >= 0] for x in traces]
        assert len(expected) == count
        for j, column in enumerate(observed):
            target = [row[j] for row in expected]
            if j == 0:
                np.testing.assert_allclose(column, target, rtol=2e-12, atol=2e-14)
            else:
                np.testing.assert_array_equal(column, target)
        np.testing.assert_array_equal(state.fragments[world], expected[-1][5])
        assert state.removed[world] == sum(row[7] for row in expected)
        assert (
            state.free[world]
            + int(state.occupied[world]).bit_count()
            + sum(i * int(n) for i, n in enumerate(state.fragments[world]))
            == spec.total_trimers
        )


def test_cycles_break_and_full_cage_is_not_absorbing():
    fragments = [0] * 21
    cut = reference.transition(FULL, FULL_BONDS, 0, fragments, 30, 10)
    assert cut[:3] == (FULL, FULL_BONDS ^ 1, 0)
    assert cut[5] == 0
    spec = parse_spec(
        {
            "initial_nodes": list(range(20)),
            "initial_free_trimers": 0,
            "worlds": 8,
            "end_time_s": 0.1,
            "k_close_s_inv": 0.0,
        }
    )
    state, result = run(spec, backend=BACKEND)
    assert np.all(state.event_count > 0)
    assert np.all(state.bonds != FULL_BONDS)
    assert np.all(state.full_first_s == 0)
    assert result["ever_full_cages"] == 8 and result["currently_full_cages"] == 0
    assert 0 < result["full_cage_dwell_total_s"] < 0.8


def test_fragments_return_exact_material():
    # Root--0--1--2--3: cutting the root spoke releases one four-trimer fragment.
    spec = parse_spec({"initial_nodes": [10, 0, 1, 2, 3], "initial_free_trimers": 0})
    cut = 30 + EDGES.index((0, 10))
    a = reference.transition(spec.initial_mask, spec.initial_bonds, 0, [0] * 21, cut, 10)
    assert a[0] == 1 << 10 and a[2] == 0 and a[3][4] == 1 and a[5] == 4
    b = reference.transition(*a[:4], 58 + 4, 10)
    assert b[2] == 4 and sum(b[3]) == 0


def test_pool_depletion_and_zero_rate_clock():
    spec = parse_spec(
        {
            "initial_nodes": [10],
            "worlds": 8,
            "initial_free_trimers": 2,
            "k_on_M_inv_s": 1e10,
            "k_off_s_inv": 0.0,
            "end_time_s": 2.0,
        }
    )
    state, _ = run(spec, backend=BACKEND)
    assert np.all(state.free == 0)
    assert np.all(np.bitwise_count(state.occupied) == 3)
    assert np.all(np.isinf(state.pending_time_s)) and np.all(state.pending_event == -1)
    spec = replace(spec, initial_free_trimers=0)
    state, _ = run(spec, backend=BACKEND)
    assert np.all(state.event_count == 0) and np.all(state.time_s == 2.0)


def test_pending_checkpoint_partition_and_chunk_replay(tmp_path):
    spec = parse_spec({"worlds": 8, "end_time_s": 0.8, "k_fragment_dissolve_s_inv": 20.0})
    whole, _ = run(spec, backend=BACKEND)
    part, _ = run(spec, backend=BACKEND, until=0.237)
    assert np.all(part.pending_valid)
    checkpoint = tmp_path / "checkpoint"
    write_checkpoint(checkpoint, spec, part, execution={"backend": BACKEND})
    saved, restored, _ = load_checkpoint(checkpoint)
    assert_same(part, restored)
    resumed, _ = run(saved, backend=BACKEND, state=restored)
    assert_same(whole, resumed)
    rechunked, report = run(replace(spec, event_chunk_size=3), backend=BACKEND)
    assert report["chunks"] > 1  # The whole run is one: at most 11 events a world.
    assert_same(whole, rechunked)
    halves = [run(replace(spec, worlds=4, world_id_start=i), backend=BACKEND)[0] for i in (0, 4)]
    combined = type(whole)(*(np.concatenate((a, b)) for a, b in zip(*halves, strict=True)))
    assert_same(whole, combined)
    payload = checkpoint / "state.npz"
    data = bytearray(payload.read_bytes())
    data[50] ^= 1
    payload.write_bytes(data)
    with pytest.raises(AssemblyError, match="state_sha256"):
        load_checkpoint(checkpoint)


@pytest.mark.parametrize(
    "field", ["free", "fragments", "bonds", "reaction_counts", "pending_event"]
)
def test_corrupt_state_rejected(field):
    spec = parse_spec({"worlds": 1})
    state = initial_state(spec)
    value = getattr(state, field).copy()
    if field == "fragments":
        value[0, 2] = 1
    elif field == "reaction_counts":
        value[0, 0] = 1
    elif field == "bonds":
        value[0] = FULL_BONDS
    else:
        value[0] += 1
    with pytest.raises(AssemblyError):
        validate_state(spec, state._replace(**{field: value}))


@pytest.mark.parametrize(
    "changes",
    [
        {"initial_free_trimers": -1},
        {"initial_free_trimers": True},
        {"pool_volume_L": 0},
        {"k_close_s_inv": float("nan")},
        {"k_fragment_dissolve_s_inv": 1e14},
        {"initial_bond_indices": []},
        {"initial_bond_indices": [0]},
        {"worlds": 1000000},
        {"recording": "events", "max_output_bytes": 1024**2},
    ],
)
def test_invalid_definitions(changes):
    with pytest.raises(AssemblyError):
        parse_spec(changes)


def test_fault_evidence_reaches_callback():
    spec = parse_spec({"worlds": 8, "max_events_per_world": 1, "end_time_s": 2.0})
    evidence = []
    with pytest.raises(AssemblyError, match="fault"):
        run(spec, backend=BACKEND, callback=lambda _, state, trace: evidence.append(state))
    assert any(np.any(state.fault == 2) for state in evidence)


def test_public_cli_run_and_resume(tmp_path, capsys):
    from cells.__main__ import main

    spec = parse_spec({"worlds": 8, "end_time_s": 0.5})
    config = tmp_path / "pool.json"
    config.write_text(json.dumps(spec.to_dict()))
    assert main(["assembly-pool", "validate", str(config)]) == 0
    first, second = tmp_path / "first", tmp_path / "second"
    assert (
        main(
            [
                "assembly-pool",
                "run",
                str(config),
                "--backend",
                BACKEND,
                "--output",
                str(first),
                "--until",
                "0.123",
            ]
        )
        == 0
    )
    assert (first / "completion.json").exists()
    assert (
        main(
            [
                "assembly-pool",
                "resume",
                str(first / "checkpoint"),
                "--backend",
                BACKEND,
                "--output",
                str(second),
            ]
        )
        == 0
    )
    assert (second / "completion.json").exists()
    _, restored, _ = load_checkpoint(second / "checkpoint")
    whole, _ = run(spec, backend=BACKEND)
    assert_same(restored, whole)
    assert main(["assembly-pool", "run", str(config), "--output", str(first)]) == 2
    capsys.readouterr()


# ------------------------------------------------------------------ the switch path (G-7)

LEVELS = {"false": 0.0, "true": 1.0}
# Rings that close and break often, beside events that switch nothing.
DRIVING = {
    "worlds": 4,
    "end_time_s": 0.02,
    "recording": "events",
    "k_on_M_inv_s": 3e9,
    "k_close_s_inv": 4000.0,
    "k_off_s_inv": 400.0,
    "k_fragment_dissolve_s_inv": 50.0,
    "max_events_per_world": 4000,
    "event_chunk_size": 64,
}
SEEDS = (2027, 2028)  # Two pools of one world: a base seed and a stream's.
STEP = jax.jit(kernel.step)


def driving_pools():
    return [parse_spec(DRIVING | {"seed": seed}) for seed in SEEDS]


def ring(occupied, bonds):
    """Whether an assembly's bonds close a ring: their ends joined one bond at a time, with no count
    of bonds or of sites."""
    of = list(range(20))

    def root(n):
        while of[n] != n:
            n = of[n]
        return n

    for i, (a, b) in enumerate(EDGES):
        if bonds >> i & 1:
            assert occupied >> a & 1 and occupied >> b & 1
            a, b = root(a), root(b)
            if a == b:
                return True
            of[a] = b
    return False


@functools.lru_cache(maxsize=None)
def walked(pool, world):
    """([(time, occupied, bonds, free), ...] of the committed events, the final state) of one world
    of a pool, by kernel.step alone: one world's own state, one event at a time."""
    device_for("cpu")  # The pool's JAX settings.
    constants = np.array(
        [
            pool.k_on_M_inv_s / (AVOGADRO * pool.pool_volume_L),
            pool.k_close_s_inv,
            pool.k_off_s_inv,
            pool.k_fragment_dissolve_s_inv,
        ]
    )
    state = kernel.PoolState(*(v[0] for v in initial_state(replace(pool, worlds=1))))
    rows = []
    while state.time_s < pool.end_time_s:
        state, (time, occupied, bonds, free, event) = STEP(
            state,
            np.uint32(pool.world_id_start + world),
            np.uint32(pool.seed),
            np.uint32(pool.root_node),
            constants,
            pool.end_time_s,
            np.uint32(pool.max_events_per_world),
        )
        if event >= 0:
            rows.append((float(time), int(occupied), int(bonds), int(free)))
    return rows, state


def direct_path(pool, world, levels=LEVELS):
    """[(time, level, event count), ...] of a world's level, from walked and ring."""
    events = (row[:3] for row in walked(pool, world)[0])
    points = [(0.0, pool.initial_mask, pool.initial_bonds), *events]
    path = []
    for count, (time, occupied, bonds) in enumerate(points):
        level = levels["true" if ring(occupied, bonds) else "false"]
        if not path or path[-1][1] != level:
            path.append((time, level, count))
    return path


def path_points(path):
    return list(zip(path.times, path.levels, path.counts, strict=True))


def record(pool, **options):
    """(final state, Trace) of a pool's run through the engine, its recorded events joined."""
    chunks = []
    state, _ = run(
        pool, callback=lambda _, s, t: chunks.append([np.asarray(x) for x in t]), **options
    )
    return state, schedule.joined(chunks)


@pytest.fixture(scope="module")
def driven():
    """[(pool, final state, Trace), ...] of the two driving pools."""
    return [(pool, *record(pool)) for pool in driving_pools()]


def driver_path(pool, trace, world, *, law=observables.LAW, levels=LEVELS):
    return schedule.switch_path(
        law, levels, schedule.initial_fields(pool), trace, world, pool.end_time_s
    )


def connected_assemblies(bonds):
    """{(occupied, bonds)} of every connected assembly around node 10 of at most `bonds` bonds."""
    found = {(1 << 10, 0)}
    grown = set(found)
    for _ in range(bonds):
        grown = {
            (occupied | 1 << a | 1 << b, given | 1 << i)
            for occupied, given in grown
            for i, (a, b) in enumerate(EDGES)
            if not given >> i & 1 and (occupied >> a & 1 or occupied >> b & 1)
        }
        found |= grown
    return found


def test_the_cycle_observable_is_the_cycle_rank_of_every_connected_assembly():
    law = observables.resolve("root_component_has_cycle@1")
    assert law is observables.LAW and law.errors() == []
    assert law_registry.active().module(law.law_id) == "cells.assembly_pool.observables"
    # Moved, not calibrated; its Citation says that it is a readout with no number and no work.
    assert law.provenance == "parity" and law.source.works == ()
    assert "a topology readout, no number" in law.source.source
    assemblies = sorted(connected_assemblies(7)) + [(FULL, FULL_BONDS), (FULL, FULL_BONDS ^ 1)]
    occupied, bonds = np.array(assemblies, dtype=np.uint32).T
    expected = np.array([ring(*row) for row in assemblies])
    assert len(assemblies) > 1000 and 0 < expected.sum() < len(assemblies)
    assert np.array_equal(law.evaluate(occupied, bonds), expected)
    assert np.array_equal(law.evaluate(jnp.asarray(occupied), jnp.asarray(bonds), xp=jnp), expected)
    e, v = np.bitwise_count(bonds), np.bitwise_count(occupied)
    for planted in (e < v, e > v, v >= e):  # `<`, two rings for one, and the counts exchanged.
        assert not np.array_equal(planted, expected)
    # What the interface refuses of a declaration, and an ID that no registry holds.
    for field, value, reason in (
        ("host", "cells.transporter@1", "hosted by finite_bond_assembly@1"),
        ("reads", (), "its reads are at least 1 distinct names"),
        ("values", ("true", "true"), "its values are at least 2 distinct names"),
        ("evaluate", None, "its evaluate is callable"),
    ):
        assert any(reason in e for e in replace(law, **{field: value}).errors())
    with pytest.raises(ConfigError, match=f"observable 'ring'; registered: {law.law_id}"):
        observables.resolve("ring")


def test_the_driver_s_path_is_a_direct_walk_of_the_pool_s_kernel(driven):
    both = [
        [(driver_path(pool, trace, w), direct_path(pool, w)) for w in range(pool.worlds)]
        for pool, _, trace in driven
    ]
    for (pool, state, _), rows in zip(driven, both, strict=True):
        for world, (path, expected) in enumerate(rows):
            assert path_points(path) == expected  # Bit for bit: times, levels, event counts.
            assert path.events == state.event_count[world] > len(path.switches) >= 1
            assert path.end == pool.end_time_s
        assert sum(len(path.switches) for path, _ in rows) >= 10
    for mine, other in itertools.permutations(both):  # Planted: the other pool's seed, or owner.
        for (path, _), (_, theirs) in zip(mine, other, strict=True):
            assert path_points(path) != theirs
    pool, _, trace = driven[0]

    def planted(law=observables.LAW, trace=trace):
        return [path_points(driver_path(pool, trace, w, law=law)) for w in range(pool.worlds)]

    expected = [rows for _, rows in both[0]]
    assert planted() == expected
    for wrong in (np.less, np.greater):  # Planted: `<`, and `>`, in place of `>=`.
        law = replace(
            observables.LAW,
            evaluate=lambda occupied, bonds, xp, wrong=wrong: wrong(
                np.bitwise_count(bonds), np.bitwise_count(occupied)
            ).astype(int),
        )
        assert planted(law=law) != expected
    for shift in (1, -1):  # Planted: the level before the event, and the next event's, early.
        late = {k: np.array(getattr(trace, k)) for k in ("occupied", "bonds")}
        for world in range(pool.worlds):
            rows = np.flatnonzero(trace.event[:, world] >= 0)
            for name, initial in (("occupied", pool.initial_mask), ("bonds", pool.initial_bonds)):
                states = np.r_[initial, late[name][rows, world], late[name][rows[-1], world]]
                late[name][rows, world] = states[:-2] if shift > 0 else states[2:]
        assert planted(trace=trace._replace(**late)) != expected
    # A longer horizon keeps the path up to the old one.
    longer = replace(pool, end_time_s=2 * pool.end_time_s)
    _, further = record(longer)
    for world, (path, _) in enumerate(both[0]):
        kept = path_points(driver_path(longer, further, world))[: len(path.times)]
        assert kept == path_points(path)
    # A level of one value for both is no switch, and levels are data: they change no time.
    flat = driver_path(pool, trace, 0, levels={"false": 0.5, "true": 0.5})
    assert path_points(flat) == [(0.0, 0.5, 0)]
    half = driver_path(pool, trace, 0, levels={"false": 0.25, "true": 0.5})
    assert half.times == both[0][0][0].times and set(half.levels) == {0.25, 0.5}


def test_a_path_s_final_state_and_exposure_are_the_pool_s_own(driven):
    for pool, state, trace in driven:
        for world in range(pool.worlds):
            rows, final = walked(pool, world)
            for name, value in state._asdict().items():  # The engine's, bit for bit.
                assert value[world].tobytes() == np.asarray(getattr(final, name)).tobytes(), name
            committed = np.flatnonzero(trace.event[:, world] >= 0)
            assert rows == [
                tuple(getattr(trace, k)[i, world] for k in ("time_s", "occupied", "bonds", "free"))
                for i in committed
            ]
            for levels in (LEVELS, {"false": 0.25, "true": 0.5}):  # Then every interval weighs.
                path = driver_path(pool, trace, world, levels=levels)
                points = direct_path(pool, world, levels)
                ends = [p[0] for p in points[1:]] + [pool.end_time_s]
                exact = sum(
                    Fraction(level * (end - time))
                    for (time, level, _), end in zip(points, ends, strict=True)
                )
                assert path.exposure() == float(exact)
                assert path.at(path.end) == path.levels[-1]


def test_a_ring_that_only_breaks_switches_once_at_the_closed_form_time():
    """Nothing associates or closes, so a ring of five breaks for good at its first event, whose
    wait is -ln u / (5 k_off) for the stream's first uniform."""
    closed = {"initial_free_trimers": 0, "k_on_M_inv_s": 0.0, "k_close_s_inv": 0.0}
    pools = [parse_spec(DRIVING | closed | {"seed": seed}) for seed in SEEDS]

    def first(pool, world):
        uniforms = random_pair(np.uint32(pool.seed), np.uint32(world), np.uint32(0))
        return -np.log(float(uniforms[0])) / (5 * pool.k_off_s_inv)

    times = []
    for pool in pools:
        _, trace = record(pool)
        times.append([])
        for world in range(pool.worlds):
            path = driver_path(pool, trace, world)
            assert path.levels == (1.0, 0.0) and path.counts == (0, 1) and path.events > 1
            np.testing.assert_allclose(path.times[1], first(pool, world), rtol=1e-14)
            times[-1].append(path.times[1])
            assert path.exposure() == path.times[1]
    for world in range(4):  # Planted: the base seed without the stream.
        assert abs(times[1][world] / first(pools[0], world) - 1) > 1e-3


@pytest.mark.skipif(BACKEND != "gpu", reason="Explicit real-GPU qualification only")
def test_cpu_gpu_agreement():
    spec = parse_spec({"worlds": 48, "end_time_s": 1.0, "k_fragment_dissolve_s_inv": 20.0})
    cpu, _ = run(spec, backend="cpu")
    gpu, result = run(spec, backend="gpu")
    assert result["backend"] == "gpu"
    for name, a, b in zip(cpu._fields, cpu, gpu, strict=True):
        if a.dtype.kind == "f":
            np.testing.assert_allclose(a, b, rtol=2e-12, atol=2e-14, err_msg=name)
        else:
            np.testing.assert_array_equal(a, b, err_msg=name)
