"""Keyed random streams: the RNG contract's keys, and replay independent of lanes and chunks.

Planted errors it must catch:
- a carrier key folded once (fold_in narrows it to 32 bits, so two carriers differing only above
  bit 31 would share a stream): shown to collide, and the family's two-word fold keeps them apart;
- a stream keyed by lane position instead of world identity: a world run alone, and as either
  lane of a batch, must give the same records bit for bit;
- a stream that ignores the branch word: two branches of one world must differ.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import runner, streams
from tests.assembly_lineage_fixtures import definition, world


def _base():
    return jnp.asarray(streams.base_key_data(7, 1, 2, 3))


def test_carrier_keys_fold_as_two_words():
    base = jax.random.wrap_key_data(_base(), impl=streams.GENERATOR)
    low, high = 5, 5 + 2**32
    narrowed = [jax.random.key_data(jax.random.fold_in(base, jnp.int64(v))) for v in (low, high)]
    assert np.array_equal(narrowed[0], narrowed[1])  # The planted single fold collides.
    ours = [
        np.asarray(streams.stream_key_data(_base(), jnp.int64(v), "exchange")) for v in (low, high)
    ]
    assert not np.array_equal(ours[0], ours[1])


def test_domains_and_counters_are_separate_streams():
    drawn = [d for d in streams.DOMAINS if d not in streams.RESERVED]
    keys = {d: np.asarray(streams.stream_key_data(_base(), jnp.int64(0), d)) for d in drawn}
    assert len({k.tobytes() for k in keys.values()}) == len(drawn) == 4
    first = np.asarray(streams.uniforms(jnp.asarray(keys["exchange"]), jnp.int64(0), 2))
    again = np.asarray(streams.uniforms(jnp.asarray(keys["exchange"]), jnp.int64(0), 2))
    later = np.asarray(streams.uniforms(jnp.asarray(keys["exchange"]), jnp.int64(1), 2))
    assert np.array_equal(first, again) and not np.array_equal(first, later)


def test_uniforms_follow_the_declared_convention():
    stream = streams.stream_key_data(_base(), jnp.int64(3), "partition")
    values = np.asarray(streams.uniforms(stream, jnp.int64(9), 4096))
    assert np.all((values > 0) & (values < 1))
    key = jax.random.wrap_key_data(stream, impl=streams.GENERATOR)
    for word in (jnp.uint32(9), jnp.uint32(0)):  # The counter's low word, then its high word.
        key = jax.random.fold_in(key, word)
    bits = np.asarray(jax.random.bits(key, (4096,), jnp.uint64))
    expected = ((bits & np.uint64(2**52 - 1)).astype(np.float64) + 0.5) * 2.0**-52
    assert np.array_equal(values, expected)


def _records(run):
    return {**run.rows, **run.fissions, **run.trace}


def _same(a, b):
    return set(a) == set(b) and all(np.array_equal(a[k], b[k], equal_nan=True) for k in a)


@pytest.fixture(scope="module")
def worlds():
    a = parse_spec(definition(world(seed=3), fissions=3, environment=11))
    b = parse_spec(definition(world(seed=4), fissions=3, environment=12))
    return a, b


def test_a_world_replays_alone_and_in_either_lane(worlds):
    a, b = worlds
    alone = _records(runner.run(a))
    first = runner.run_lanes([a, b])
    second = runner.run_lanes([b, a])
    assert _same(alone, _records(first[0])) and _same(alone, _records(second[1]))
    assert _same(_records(first[1]), _records(second[0]))
    assert not _same(alone, _records(first[1]))


def test_chunk_size_changes_no_value(worlds):
    a, _ = worlds
    data = a.to_dict()
    data["execution"]["chunk_events"] = 5
    assert _same(_records(runner.run(a)), _records(runner.run(parse_spec(data))))


def test_branches_are_independent(worlds):
    a, _ = worlds
    data = a.to_dict()
    data["execution"]["stream"]["branch"] = 1
    other = runner.run(parse_spec(data))
    mine = runner.run(a)
    n = min(len(other.trace["event_channel"]), len(mine.trace["event_channel"]))
    assert not np.array_equal(other.trace["event_time"][:n], mine.trace["event_time"][:n])
