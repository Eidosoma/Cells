"""Fission, continuation and the lineage table (cells.operator.size_threshold_fission@1,
cells.operator.daughter_continuation@1): exact sizes, conservation, rules and carrier keys.

Planted errors it must catch:
- a split at 0.55 where 1/2 is declared (the first daughter's size is checked exactly);
- a dropped molecule (the integer identity count = founder + joined - left - discarded);
- a continuation that ignores its rule (first, second, uniform, and the empty fallback).
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import continuation, fission, runner
from tests.assembly_lineage_fixtures import definition, world


def _split(parent, rule, value, seed):
    places = jax.random.uniform(jax.random.key(seed), (128,), jnp.float64, 1e-12, 1.0)
    first = fission.split(jnp.asarray(parent), jnp.int64(int(np.sum(parent))), places, rule, value)
    return np.asarray(first)


def _exact_half_violations(parents, fraction, declared=0.5):
    """Splits whose first daughter is not floor(declared N), or that make or lose molecules."""
    bad = 0
    for k, parent in enumerate(parents):
        first = _split(parent, "exact_fraction", fraction, k)
        size = int(parent.sum())
        bad += (
            first.sum() != np.floor(declared * size) or np.any(first < 0) or np.any(first > parent)
        )
    return bad


def test_exact_fraction_gives_floor_f_n_and_conserves():
    rng = np.random.default_rng(1)
    parents = [rng.multinomial(int(rng.integers(2, 120)), np.ones(9) / 9) for _ in range(40)]
    assert _exact_half_violations(parents, 0.5) == 0
    assert _exact_half_violations(parents, 0.55) > 0  # Planted: the 0.55 split is caught.


def test_binomial_conserves_and_varies():
    parent = np.asarray([30, 0, 25, 25])
    firsts = [_split(parent, "binomial", 0.5, k) for k in range(20)]
    assert all(np.all((f >= 0) & (f <= parent)) for f in firsts)
    assert all(f[1] == 0 for f in firsts) and len({int(f.sum()) for f in firsts}) > 3


@pytest.mark.parametrize(
    "daughter, empty, uniform, sizes, expected",
    [
        ("first", "extinct", 0.9, (3, 4), 0),
        ("second", "extinct", 0.1, (3, 4), 1),
        ("uniform", "extinct", 0.49, (3, 4), 0),
        ("uniform", "extinct", 0.51, (3, 4), 1),
        ("first", "extinct", 0.9, (0, 4), 0),  # Followed empty: the lineage ends.
        ("first", "other", 0.9, (0, 4), 1),  # The nonempty fallback.
        ("second", "other", 0.9, (4, 0), 0),
        ("first", "other", 0.9, (0, 0), 0),
    ],
)
def test_continuation_rules(daughter, empty, uniform, sizes, expected):
    sizes = tuple(jnp.int64(s) for s in sizes)
    assert int(continuation.choose(daughter, empty, jnp.float64(uniform), sizes)) == expected


def _identity_breaks(rows, founder):
    count = rows["assembly_count"][:, :, 0]
    total = founder + rows["joined_total"][:, :, 0] - rows["left_total"][:, :, 0]
    return np.count_nonzero(total - rows["discarded_total"][:, :, 0] != count)


def test_a_lineage_conserves_and_keys_its_carriers():
    spec = parse_spec(definition(world(), fissions=6))
    run = runner.run(spec)
    rows, table = run.rows, run.fissions
    founder = np.asarray(spec.model.world.founder)
    assert _identity_breaks(rows, founder) == 0
    planted = dict(rows, discarded_total=rows["discarded_total"].copy())
    planted["discarded_total"][-1, 0, 0] += 1  # A dropped molecule.
    assert _identity_breaks(planted, founder) == 1
    kinds = rows["row_kind"].tolist()
    assert kinds[0] == 0 and kinds[1:13] == [1, 2] * 6
    parents = rows["assembly_count"][rows["row_kind"] == 1, :, 0]
    daughters = rows["assembly_count"][rows["row_kind"] == 2, :, 0]
    assert np.all(parents.sum(1) == 12) and np.all(daughters.sum(1) == 6)
    assert np.array_equal(daughters, table["fission_split"])  # The first daughter continues.
    assert np.array_equal(table["fission_daughters"], np.arange(1, 13).reshape(6, 2))
    assert table["fission_parent"].tolist() == [0, 1, 3, 5, 7, 9]
    assert rows["occupant"][rows["row_kind"] == 2, 0].tolist() == [1, 3, 5, 7, 9, 11]
    assert rows["generation"][-1, 0] == 6 and run.status == "complete"
    sim = table["fission_similarity"]
    p = parents.astype(float)
    for k in range(6):
        for d, child in enumerate(
            (table["fission_split"][k], parents[k] - table["fission_split"][k])
        ):
            expect = p[k] @ child / np.sqrt((p[k] @ p[k]) * (child @ child))
            assert sim[k, d] == pytest.approx(expect, rel=1e-15)
    assert run.trace["events_per_growth"].sum() == len(run.trace["event_channel"])


def _oversize(rows, size):
    """Rows whose assembly exceeds the fission size (empty: none)."""
    return np.flatnonzero(rows["assembly_count"][:, :, 0].sum(1) > size).tolist()


def test_a_daughter_born_at_the_fission_size_splits_at_once():
    """A binomial partition can give one daughter every molecule (p = 0.25 at size 4): that
    daughter splits at its birth, before any event, so no assembly ever exceeds the size; the
    kernel and the host oracle agree on such lineages (common random variates). Planted: a
    lineage whose daughter grew past the size (the trigger missed) is caught."""
    from cells.models.assembly_lineages import reference

    the_world = world(
        count=3,
        size=4,
        founder_size=2,
        daughter="uniform",
        empty="other",
        partition={"rule": "binomial", "probability": 0.25},
    )
    born_at_size = 0
    for seed in range(1, 30):
        run = runner.run(
            parse_spec(definition(the_world, fissions=10, seed=seed, uniforms=True, limit=400))
        )
        rows = run.rows
        assert _oversize(rows, 4) == [] and run.status in ("complete", "extinct")
        daughters = rows["assembly_count"][rows["row_kind"] == 2, :, 0].sum(1)
        born_at_size += int(np.sum(daughters == 4))
        d = run.diagnostics
        oracle = reference.replay(
            run.spec, d["event_uniforms"], d["partition_uniforms"], d["continuation_uniform"]
        )
        assert oracle["channel"] == run.trace["event_channel"].tolist()
        assert oracle["followed"] == run.fissions["fission_followed"].tolist()
        assert oracle["status"] == run.status
    assert born_at_size > 0  # The case occurred.
    planted = dict(rows, assembly_count=rows["assembly_count"].copy())
    planted["assembly_count"][-1, 0, 0] += 4  # A daughter that grew past the size.
    assert _oversize(planted, 4) == [len(rows["row_kind"]) - 1]


def test_the_fission_pass_alone_splits_as_the_run_does():
    """runner.fission_pass on a lineage's parent states, keyed by its lineage word, gives the
    run's own splits at its first fission. Planted: the same parents keyed by another lineage
    word split differently."""
    spec = parse_spec(definition(world(), fissions=1, uniforms=True, lineage=6))
    run = runner.run(spec)
    parent = run.rows["assembly_count"][run.rows["row_kind"] == 1, :, 0]
    count = spec.model.world.types.count
    alone = runner.fission_pass(spec, parent[:, :count], [6])
    assert np.array_equal(alone["first"], run.fissions["fission_split"])
    assert np.array_equal(alone["followed"], run.fissions["fission_followed"])
    assert np.array_equal(alone["partition_uniforms"], run.diagnostics["partition_uniforms"])
    other = runner.fission_pass(spec, parent[:, :count], [7])
    assert not np.array_equal(other["partition_uniforms"], alone["partition_uniforms"])
