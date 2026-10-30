"""Held finite-fuel stage composition: full outputs and per-world isolation."""

import jax
import numpy as np
import pytest

from cells.models import physiology_active_temperature_arrays as arrays
from tests.unit.test_physiology_active_temperature_arrays import (
    check_world,
    evidence,
    exact_tree,
    fixtures,
)

FAMILY = "resolved_calcium_energy@5"


@pytest.fixture(scope="module")
def worlds():
    return fixtures("fuel", count=2)


def numpy_stages(calls=None):
    def invoke(name, function, state, layout, control, *prefix):
        if calls is not None:
            calls.append((name, id(state), id(layout), id(control)))
        return function(state, layout, control, *prefix, xp=np)

    return arrays.WorldStages(
        FAMILY,
        lambda p, c, u: arrays.prepare_numeric_world(p, c, u, family=FAMILY, xp=np),
        arrays.FuelPhysicsStages(
            lambda s, p, u: invoke("ionic", arrays.fuel_ionic_stage, s, p, u),
            lambda s, p, u, v: invoke("calcium", arrays.fuel_calcium_stage, s, p, u, v),
            lambda s, p, u, v: invoke("fuel", arrays.compact_fuel_completion, s, p, u, v),
        ),
        lambda s, p, u, h, v: arrays.check_physics_world(s, p, u, h, v, family=FAMILY, xp=np),
    )


def save_trees(name, record, **trees):
    columns, structures = {}, {}
    for label, tree in trees.items():
        leaves, structure = jax.tree.flatten(tree)
        structures[label] = str(structure)
        columns.update({f"{label}_{i:04}": np.asarray(value) for i, value in enumerate(leaves)})
    evidence(name, record | dict(tree_structures=structures), columns)


def evaluate(numeric, proposals, stages=None):
    return arrays.evaluate_batch_staged(
        numeric,
        proposals,
        family=FAMILY,
        xp=np,
        stages=numpy_stages() if stages is None else stages,
    )


def test_numpy_fuel_stages_preserve_complete_rates_fields_and_world_ownership(worlds):
    cases, cohort, proposals = worlds
    before = jax.tree.map(np.copy, (cohort.numeric, proposals))
    calls = []
    actual = evaluate(cohort.numeric, proposals, numpy_stages(calls))
    ordinary = arrays.evaluate_batch_staged(cohort.numeric, proposals, family=FAMILY, xp=np)
    save_trees(
        "split-fuel-numpy-complete",
        dict(physical_stage_order=[row[0] for row in calls], worlds=2),
        actual=actual,
        ordinary=ordinary,
    )
    exact_tree(actual, ordinary)
    exact_tree(before, (cohort.numeric, proposals))
    assert [row[0] for row in calls] == ["ionic", "calcium", "fuel"] * 2
    for start in (0, 3):
        assert len({row[1:] for row in calls[start : start + 3]}) == 1
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda v, i=i: v[i], proposals),
            jax.tree.map(lambda v, i=i: v[i], actual),
            f"split-fuel-numpy-{i}",
        )
    reversed_values = evaluate(
        jax.tree.map(lambda v: v[::-1], cohort.numeric),
        jax.tree.map(lambda v: v[::-1], proposals),
    )
    exact_tree(actual, jax.tree.map(lambda v: v[::-1], reversed_values))
    partitions = [
        evaluate(
            jax.tree.map(lambda v, i=i: v[i : i + 1], cohort.numeric),
            jax.tree.map(lambda v, i=i: v[i : i + 1], proposals),
        )
        for i in range(2)
    ]
    exact_tree(actual, jax.tree.map(lambda *v: np.concatenate(v), *partitions))


def test_rejected_fuel_temperature_retains_raw_values_and_other_world(worlds):
    _, cohort, proposals = worlds
    actual = evaluate(cohort.numeric, proposals)
    temperature = proposals.temperature_K.copy()
    temperature[0] = 0.0
    invalid = proposals._replace(temperature_K=temperature)
    rejected = evaluate(cohort.numeric, invalid)
    save_trees("split-fuel-numpy-rejected", dict(raw_invalid_retained=True), rejected=rejected)
    assert not rejected.valid[0] and rejected.valid[1]
    assert int(rejected.reason_mask[0]) & 4
    assert rejected.raw_proposal.temperature_K[0] == 0.0
    assert rejected.raw_runtime_layout.temperature[0] == 0.0
    np.testing.assert_array_equal(
        rejected.arithmetic_runtime_layout.temperature, cohort.numeric.certificate.temperature_K
    )
    exact_tree(
        jax.tree.map(lambda v: v[1], actual),
        jax.tree.map(lambda v: v[1], rejected),
    )


@pytest.mark.parametrize(
    "damage", ["missing_pool_state", "calcium_layout", "calcium_control", "ionic", "calcium"]
)
def test_fuel_stage_boundaries_refuse_other_families_and_incomplete_prefixes(worlds, damage):
    _, cohort, proposals = worlds
    world = jax.tree.map(lambda v: v[0], cohort.numeric)
    proposal = jax.tree.map(lambda v: v[0], proposals)
    inputs = arrays.prepare_numeric_world(
        world.layout, world.certificate, proposal, family=FAMILY, xp=np
    )
    state, layout, control = (
        world.state,
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
    )
    with pytest.raises(ValueError, match="Fuel"):
        if damage == "missing_pool_state":
            arrays.fuel_ionic_stage(arrays.fuel.prior_state(state), layout, control, xp=np)
        elif damage == "calcium_layout":
            arrays.fuel_ionic_stage(state, arrays.fuel.prior_layout(layout), control, xp=np)
        elif damage == "calcium_control":
            arrays.fuel_ionic_stage(state, layout, arrays.fuel.prior_control(control), xp=np)
        elif damage == "ionic":
            arrays.fuel_calcium_stage(state, layout, control, (), xp=np)
        else:
            arrays.compact_fuel_completion(state, layout, control, (), xp=np)
