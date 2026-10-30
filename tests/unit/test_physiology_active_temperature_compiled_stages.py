"""Complete compiled stage checks, distinct from the earlier fused CPU test."""

import os

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_view as host
from tests.unit.test_physiology_active_temperature import KINDS
from tests.unit.test_physiology_active_temperature_arrays import (
    check_world,
    evidence,
    exact_tree,
    fixtures,
)


@pytest.mark.parametrize("kind", KINDS)
def test_separate_cpu_executables_preserve_complete_worlds(kind, monkeypatch):
    complete_cpu_case(kind, monkeypatch)


def test_split_calcium_cpu_executables_preserve_complete_worlds(monkeypatch):
    complete_cpu_case("calcium", monkeypatch, split_calcium=True)


def test_split_calcium_numpy_complete_rates_match_independent_reference():
    cases, cohort, proposals = fixtures("calcium", count=2)
    family = cohort.family
    stages = arrays.WorldStages(
        family,
        lambda p, c, u: arrays.prepare_numeric_world(p, c, u, family=family, xp=np),
        arrays.CalciumPhysicsStages(
            lambda s, p, u: arrays.calcium.ionic_stage(s, u, p, xp=np),
            lambda s, p, u, ionic: arrays.compact_calcium_completion(s, p, u, ionic, xp=np),
        ),
        lambda s, p, u, h, v: arrays.check_physics_world(s, p, u, h, v, family=family, xp=np),
    )
    result = arrays.evaluate_batch_staged(
        cohort.numeric, proposals, family=family, xp=np, stages=stages,
    )
    for i, case in enumerate(cases):
        check_world(
            case, cohort.worlds[i],
            jax.tree.map(lambda value, i=i: value[i], proposals),
            jax.tree.map(lambda value, i=i: value[i], result),
            f"split-calcium-numpy-{i}",
        )


def complete_cpu_case(kind, monkeypatch, *, split_calcium=False):
    cases, cohort, proposals = fixtures(kind, count=2)
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    assert not jax.config.jax_disable_jit
    numeric, raw = jax.tree.map(jnp.asarray, (cohort.numeric, proposals))
    stages = (
        arrays.compiled_calcium_world_stages()
        if split_calcium else arrays.compiled_world_stages(cohort.family)
    )
    assert stages.family == cohort.family
    label = "split-calcium" if split_calcium else "separate"
    world = jax.tree.map(lambda value: value[0], numeric)
    proposal = jax.tree.map(lambda value: value[0], raw)

    # Host admission is complete. Compiled functions must not call it again.
    for name in ("initial_values", "check_values", "check_steps"):
        monkeypatch.setattr(
            arrays.IMPLEMENTATIONS[cohort.family], name,
            lambda *a, **k: pytest.fail("Numeric stage invoked host admission"),
        )
    monkeypatch.setattr(
        host, "_runtime", lambda *a, **k: pytest.fail("Numeric stage invoked host projection")
    )

    def execute(name, function, *args):
        evidence(
            f"{label}-{kind}-{name}-start",
            dict(stage=name, status="compile_started", affinity=sorted(os.sched_getaffinity(0))),
        )
        executable = function.lower(*args).compile()
        value = executable(*args)
        jax.block_until_ready(value)
        evidence(
            f"{label}-{kind}-{name}-complete",
            dict(stage=name, status="compiled_executed", output_leaves=len(jax.tree.leaves(value))),
        )
        return executable, value

    inputs_fn, inputs = execute(
        "inputs", stages.inputs, world.layout, world.certificate, proposal,
    )
    if split_calcium:
        ionic_fn, ionic = execute(
            "ionic", stages.physics.ionic, world.state,
            inputs.arithmetic_runtime_layout, inputs.arithmetic_control,
        )
        completion_fn, physics = execute(
            "calcium", stages.physics.completion, world.state,
            inputs.arithmetic_runtime_layout, inputs.arithmetic_control, ionic,
        )
        physics_fn = arrays.CalciumPhysicsStages(ionic_fn, completion_fn)
    else:
        physics_fn, physics = execute(
            "physics", stages.physics, world.state,
            inputs.arithmetic_runtime_layout, inputs.arithmetic_control,
        )
    checks_fn, _ = execute(
        "checks", stages.checks, world.state,
        inputs.arithmetic_runtime_layout, inputs.arithmetic_control,
        inputs.arithmetic_step_s, physics,
    )
    # These are already compiled executable objects. The cohort wrapper cannot
    # trace through them and silently fuse the three full physical stages.
    executables = arrays.WorldStages(cohort.family, inputs_fn, physics_fn, checks_fn)

    def evaluate(values, proposed):
        result = arrays.evaluate_batch_staged(
            values, proposed, family=cohort.family, stages=executables,
        )
        jax.block_until_ready(result)
        return result

    actual = evaluate(numeric, raw)
    for i, case in enumerate(cases):
        check_world(
            case, cohort.worlds[i],
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), proposals),
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), actual),
            f"{label}-cpu-{kind}-{i}",
        )
    reversed_values = evaluate(
        jax.tree.map(lambda value: value[::-1], numeric),
        jax.tree.map(lambda value: value[::-1], raw),
    )
    exact_tree(actual, jax.tree.map(lambda value: value[::-1], reversed_values))
    partitions = [
        evaluate(
            jax.tree.map(lambda value, i=i: value[i:i + 1], numeric),
            jax.tree.map(lambda value, i=i: value[i:i + 1], raw),
        )
        for i in range(2)
    ]
    exact_tree(actual, jax.tree.map(lambda *values: jnp.concatenate(values), *partitions))
    invalid = raw._replace(temperature_K=raw.temperature_K.at[0].set(0.0))
    rejected = evaluate(numeric, invalid)
    evidence(
        f"{label}-{kind}-raw-invalid",
        dict(reason_mask=np.asarray(rejected.reason_mask), valid=np.asarray(rejected.valid)),
        dict(
            raw_temperature_K=np.asarray(rejected.raw_proposal.temperature_K),
            raw_runtime_temperature=np.asarray(rejected.raw_runtime_layout.temperature),
            arithmetic_temperature=np.asarray(rejected.arithmetic_runtime_layout.temperature),
        ),
    )
    assert not bool(rejected.valid[0]) and bool(rejected.valid[1])
    assert int(rejected.reason_mask[0]) & 4
    assert float(rejected.raw_proposal.temperature_K[0]) == 0.0
    assert float(rejected.raw_runtime_layout.temperature[0]) == 0.0
    np.testing.assert_array_equal(
        rejected.arithmetic_runtime_layout.temperature, numeric.certificate.temperature_K,
    )
    exact_tree(
        jax.tree.map(lambda value: value[1], actual),
        jax.tree.map(lambda value: value[1], rejected),
    )
    evidence(
        f"{label}-{kind}-completed",
        dict(
            family=cohort.family,
            compiled_stages=(
                ["inputs", "ionic", "calcium", "checks"]
                if split_calcium else ["inputs", "physics", "checks"]
            ),
            distinct_worlds=2, reorder_exact=True, partition_exact=True,
            raw_invalid_retained=True, gpu_qualified=False, trajectories_qualified=False,
        ),
    )
