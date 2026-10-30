"""Open stage composition preserves complete reservoir, calcium and fuel owners."""

import jax
import numpy as np
import pytest

from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_open_arrays as opened
from tests.unit.test_physiology_active_temperature_arrays import (
    check_world,
    evidence,
    exact_tree,
    fixtures,
)
from tests.unit.test_physiology_active_temperature_fuel_stages import save_trees


@pytest.fixture(scope="module", params=("open-calcium", "open-fuel"))
def worlds(request):
    return request.param, fixtures(request.param, count=2)


def stages_with_calls(family, calls):
    stages = opened.world_stages(family, xp=np)
    names = (
        ["ionic", "calcium", "fuel", "reservoir"]
        if family == opened.FUEL
        else ["ionic", "calcium", "reservoir"]
    )

    def wrap(name, fn):
        def call(state, layout, control, *prefix):
            calls.append((name, id(state), id(layout), id(control)))
            return fn(state, layout, control, *prefix)

        return call

    return stages._replace(
        physics=type(stages.physics)(
            *[wrap(name, fn) for name, fn in zip(names, stages.physics, strict=True)]
        )
    ), names


def test_open_stages_preserve_complete_worlds_and_reservoir_owners(worlds):
    kind, (cases, cohort, proposals) = worlds
    family = cohort.family
    before = jax.tree.map(np.copy, (cohort.numeric, proposals))
    calls = []
    stages, names = stages_with_calls(family, calls)

    def evaluate(numeric, raw, selected=None):
        return arrays.evaluate_batch_staged(
            numeric,
            raw,
            family=family,
            xp=np,
            stages=opened.world_stages(family, xp=np) if selected is None else selected,
        )

    actual = evaluate(cohort.numeric, proposals, stages)
    original = arrays.evaluate_batch_staged(cohort.numeric, proposals, family=family, xp=np)
    save_trees(
        f"split-{kind}-complete",
        dict(physical_stage_order=[row[0] for row in calls], worlds=2),
        actual=actual,
        original=original,
    )
    exact_tree(actual, original)
    exact_tree(before, (cohort.numeric, proposals))
    assert [row[0] for row in calls] == names * 2
    for start in (0, len(names)):
        assert len({row[1:] for row in calls[start : start + len(names)]}) == 1
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda v, i=i: v[i], proposals),
            jax.tree.map(lambda v, i=i: v[i], actual),
            f"split-open-numpy-{kind}-{i}",
        )
    reversed_values = evaluate(
        jax.tree.map(lambda v: v[::-1], cohort.numeric),
        jax.tree.map(lambda v: v[::-1], proposals),
    )
    partitions = [
        evaluate(
            jax.tree.map(lambda v, i=i: v[i : i + 1], cohort.numeric),
            jax.tree.map(lambda v, i=i: v[i : i + 1], proposals),
        )
        for i in range(2)
    ]
    partitioned = jax.tree.map(lambda *v: np.concatenate(v), *partitions)
    exact_tree(actual, jax.tree.map(lambda v: v[::-1], reversed_values))
    exact_tree(actual, partitioned)
    temperature = proposals.temperature_K.copy()
    temperature[0] = 0.0
    rejected = evaluate(cohort.numeric, proposals._replace(temperature_K=temperature))
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
    save_trees(
        f"split-{kind}-batch-controls",
        dict(reorder_exact=True, partition_exact=True, invalid_neighbor_isolated=True),
        reversed_values=reversed_values,
        partitioned=partitioned,
        rejected=rejected,
    )


def test_open_stages_empty_reservoir_reduction_retains_parent_exactly(worlds):
    kind, (_, cohort, proposals) = worlds
    family = cohort.family
    model = arrays.IMPLEMENTATIONS[family]
    world = jax.tree.map(lambda v: v[0], cohort.numeric)
    raw = jax.tree.map(lambda v: v[0], proposals)
    inputs = arrays.prepare_numeric_world(
        world.layout, world.certificate, raw, family=family, xp=np
    )
    layout = inputs.arithmetic_runtime_layout._replace(
        reservoir=np.zeros_like(world.layout.reservoir), open_reservoir_world=np.asarray(False)
    )
    control = inputs.arithmetic_control
    actual = opened.world_stages(family, xp=np).physics(world.state, layout, control)
    parent = model._adapter.base.readouts(
        model.parent_state(world.state), control, model.parent_layout(layout), xp=np
    )
    exact_tree(actual.field, parent.field)
    exact_tree(tuple(actual.derivative), tuple(parent.derivative))
    assert bool(actual.valid) == bool(parent.valid)
    if family == opened.FUEL:
        exact_tree(actual.gross_hydrolysis_fmol_s, parent.exchange.gross_hydrolysis_fmol_s)
        exact_tree(actual.gross_synthesis_fmol_s, parent.exchange.gross_synthesis_fmol_s)
    save_trees(
        f"split-{kind}-empty-reservoir-control",
        dict(conditional_numeric_control=True, new_admitted_cohort=False, parent_exact=True),
        actual=actual,
        parent=parent,
    )


@pytest.mark.parametrize("damage", ("state", "layout", "control", "ionic", "calcium", "reservoir"))
def test_open_stages_refuse_missing_owners_and_prefixes(worlds, damage):
    kind, (_, cohort, proposals) = worlds
    family = cohort.family
    model = arrays.IMPLEMENTATIONS[family]
    world = jax.tree.map(lambda v: v[0], cohort.numeric)
    raw = jax.tree.map(lambda v: v[0], proposals)
    inputs = arrays.prepare_numeric_world(
        world.layout, world.certificate, raw, family=family, xp=np
    )
    state, layout, control = (
        world.state,
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
    )
    with pytest.raises(ValueError, match="Open|Fuel"):
        if damage == "state":
            opened.ionic_stage(model.parent_state(state), layout, control, family=family, xp=np)
        elif damage == "layout":
            opened.ionic_stage(state, model.parent_layout(layout), control, family=family, xp=np)
        elif damage == "control":
            opened.ionic_stage(state, layout, tuple(control), family=family, xp=np)
        elif damage == "ionic":
            opened.calcium_stage(state, layout, control, (), family=family, xp=np)
        elif damage == "calcium":
            opened.fuel_stage(state, layout, control, (), family=family, xp=np)
        else:
            opened.reservoir_stage(state, layout, control, (), family=family, xp=np)
    evidence(f"split-{kind}-refused-{damage}", dict(case=damage, refused=True))


@pytest.mark.parametrize(
    "family", ("resolved_tissue@12", "resolved_calcium@11", "resolved_calcium_energy@5", "bad")
)
def test_open_stage_factory_refuses_other_families_before_jit(family, monkeypatch):
    monkeypatch.setattr(jax, "jit", lambda *a, **k: pytest.fail("Unsupported family reached JIT"))
    with pytest.raises(ValueError, match="exact open"):
        opened.compiled_world_stages(family)
    evidence("open-stage-family-refusal-" + family, dict(family=family, refused=True))
