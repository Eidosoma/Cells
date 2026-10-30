"""Complete ionic/calcium warmup, retained execution and closed-family admission."""

from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_active_temperature_compilation as compilation
from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_view as host
from tests.unit.test_physiology_active_temperature_arrays import (
    check_world,
    evidence,
    exact_tree,
    fixtures,
)


@pytest.mark.parametrize("kind", ("ionic", "calcium"))
def test_closed_cpu_warmup_preserves_complete_worlds(kind, monkeypatch):
    cases, cohort, proposals = fixtures(kind, count=2)
    expected = (
        ["inputs", "physics", "checks"]
        if kind == "ionic"
        else ["inputs", "ionic", "calcium", "checks"]
    )
    events = []

    def observe(record):
        events.append(record)
        evidence(f"closed-warmup-{kind}-{len(events):02d}", record)
        if record["stage"] == "admission" and record["status"] == "validated":
            for name in ("initial_values", "check_values", "check_steps"):
                monkeypatch.setattr(
                    arrays.IMPLEMENTATIONS[cohort.family],
                    name,
                    lambda *a, **k: pytest.fail("Numeric stage re-entered host admission"),
                )
            monkeypatch.setattr(
                host, "_runtime", lambda *a, **k: pytest.fail("Numeric stage used host projection")
            )

    stages = compilation.compile_cpu_stages(
        cohort, proposals, release_frontend=True, observer=observe
    )
    assert type(stages) is arrays.WorldStages and stages.family == cohort.family
    assert [r["stage"] for r in events if r["status"] == "compile_started"] == expected
    assert [r["stage"] for r in events if r["status"] == "compiled_executed"] == expected
    assert [r["stage"] for r in events if r["status"] == "cache_released"] == [
        "host-preparation",
        *expected,
    ]
    assert events[-1]["compiled_stages"] == len(expected)
    assert not events[-1]["world_state_advanced"]
    physics = [stages.physics] if kind == "ionic" else list(stages.physics)
    assert all(
        callable(fn) and not hasattr(fn, "lower") for fn in [stages.inputs, *physics, stages.checks]
    )
    event_count = len(events)
    numeric, raw = jax.tree.map(jnp.asarray, (cohort.numeric, proposals))

    def evaluate(values, proposed):
        result = arrays.evaluate_batch_staged(values, proposed, family=cohort.family, stages=stages)
        jax.block_until_ready(result)
        return result

    actual = evaluate(numeric, raw)
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), proposals),
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), actual),
            f"closed-warmup-cpu-{kind}-{i}",
        )
    reversed_values = evaluate(
        jax.tree.map(lambda value: value[::-1], numeric),
        jax.tree.map(lambda value: value[::-1], raw),
    )
    exact_tree(actual, jax.tree.map(lambda value: value[::-1], reversed_values))
    partitions = [
        evaluate(
            jax.tree.map(lambda value, i=i: value[i : i + 1], numeric),
            jax.tree.map(lambda value, i=i: value[i : i + 1], raw),
        )
        for i in range(2)
    ]
    exact_tree(actual, jax.tree.map(lambda *values: jnp.concatenate(values), *partitions))
    rejected = evaluate(numeric, raw._replace(temperature_K=raw.temperature_K.at[0].set(0.0)))
    evidence(
        f"closed-warmup-{kind}-raw-invalid",
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
        rejected.arithmetic_runtime_layout.temperature, numeric.certificate.temperature_K
    )
    exact_tree(
        jax.tree.map(lambda value: value[1], actual),
        jax.tree.map(lambda value: value[1], rejected),
    )
    assert len(events) == event_count
    evidence(
        f"closed-warmup-{kind}-completed",
        dict(
            compiled_stages=expected,
            distinct_worlds=2,
            reorder_exact=True,
            partition_exact=True,
            raw_invalid_retained=True,
            numeric_host_admission_forbidden=True,
            observer_events=len(events),
            gpu_qualified=False,
            trajectories_qualified=False,
        ),
    )


@pytest.fixture(scope="module")
def admitted_ionic():
    return fixtures("ionic", count=2)


@pytest.mark.parametrize(
    "damage",
    ("untrusted", "open-calcium", "open-fuel", "unknown", "identity", "family", "observer"),
)
def test_closed_warmup_refuses_before_compiling(admitted_ionic, monkeypatch, damage):
    _, cohort, proposal = admitted_ionic
    if damage == "untrusted":
        cohort, message = object(), "trusted closed active"
    elif damage in ("open-calcium", "open-fuel", "unknown"):
        family = {
            "open-calcium": "resolved_open_calcium@1",
            "open-fuel": "resolved_open_calcium_energy@1",
            "unknown": "unreviewed_family@1",
        }[damage]
        cohort, message = replace(cohort, family=family), "trusted closed active"
    elif damage == "identity":
        cohort, message = replace(cohort, identity="tampered"), "Stale trusted cohort"
    elif damage == "family":
        cohort, message = replace(cohort, family="resolved_calcium@11"), "Stale trusted cohort"
    else:
        message = "optional callable observer"
    for name in (
        "compiled_world_stages",
        "compiled_calcium_world_stages",
        "compiled_fuel_world_stages",
    ):
        monkeypatch.setattr(
            arrays, name, lambda *a, **k: pytest.fail("Invalid warmup reached compiler")
        )
    events = []
    with pytest.raises(ValueError, match=message):
        compilation.compile_cpu_stages(
            cohort,
            proposal,
            release_frontend=True,
            observer=object() if damage == "observer" else events.append,
        )
    assert not events
    evidence("closed-warmup-refusal-" + damage, dict(refused_before_compiling=True, case=damage))
