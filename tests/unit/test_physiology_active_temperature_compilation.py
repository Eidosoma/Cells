"""Reusable host warmup retains complete finite-fuel physics and admission."""

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


@pytest.fixture(scope="module")
def complete_worlds():
    return fixtures("fuel", count=2)


def test_public_cpu_warmup_preserves_complete_worlds(complete_worlds, monkeypatch):
    cases, cohort, proposals = complete_worlds
    events = []

    def observe(record):
        events.append(record)
        evidence(f"public-warmup-{len(events):02d}", record)
        if record["stage"] == "admission" and record["status"] == "validated":
            # Source admission belongs before warmup. Neither compilation nor
            # subsequent numeric execution may re-enter host admission.
            for name in ("initial_values", "check_values", "check_steps"):
                monkeypatch.setattr(
                    arrays.IMPLEMENTATIONS[cohort.family],
                    name,
                    lambda *a, **k: pytest.fail("Numeric stage re-entered host admission"),
                )
            monkeypatch.setattr(
                host, "_runtime", lambda *a, **k: pytest.fail("Numeric stage used host projection")
            )

    stages = compilation.compile_fuel_cpu_stages(
        cohort, proposals, release_frontend=True, observer=observe
    )
    assert type(stages) is arrays.WorldStages and stages.family == cohort.family
    expected = ["inputs", "fuel-ionic", "fuel-calcium", "fuel-exchange", "checks"]
    assert [r["stage"] for r in events if r["status"] == "compile_started"] == expected
    assert [r["stage"] for r in events if r["status"] == "compiled_executed"] == expected
    assert [r["stage"] for r in events if r["status"] == "cache_released"] == [
        "host-preparation",
        *expected,
    ]
    assert events[-1]["status"] == "completed" and not events[-1]["world_state_advanced"]
    # Retain exactly these executable objects. They cannot lower or compile a
    # new graph while the ordinary cohort orchestrator calls them again.
    executables = [stages.inputs, *stages.physics, stages.checks]
    assert all(callable(fn) and not hasattr(fn, "lower") for fn in executables)
    event_count = len(events)
    numeric, raw = jax.tree.map(jnp.asarray, (cohort.numeric, proposals))

    def evaluate(values, proposed):
        result = arrays.evaluate_batch_staged(
            values, proposed, family=cohort.family, stages=stages
        )
        jax.block_until_ready(result)
        return result

    actual = evaluate(numeric, raw)
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), proposals),
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), actual),
            f"public-warmup-cpu-fuel-{i}",
        )
    reverse = evaluate(
        jax.tree.map(lambda value: value[::-1], numeric),
        jax.tree.map(lambda value: value[::-1], raw),
    )
    exact_tree(actual, jax.tree.map(lambda value: value[::-1], reverse))
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
        "public-warmup-raw-invalid",
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
    assert len(events) == event_count  # No observer/cache work during evaluation.
    evidence(
        "public-warmup-completed",
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


@pytest.mark.parametrize("damage", ("untrusted", "family", "identity", "proposal_axis", "policy"))
def test_public_warmup_refuses_before_compiling(complete_worlds, monkeypatch, damage):
    _, cohort, proposal = complete_worlds
    if damage == "untrusted":
        cohort, message = object(), "trusted closed finite-fuel cohort"
    elif damage == "family":
        cohort, message = replace(cohort, family="resolved_open_calcium_energy@1"), "trusted closed"
    elif damage == "identity":
        cohort, message = replace(cohort, identity="tampered"), "Stale trusted cohort"
    elif damage == "proposal_axis":
        proposal = proposal._replace(temperature_K=proposal.temperature_K[:1])
        message = "every prepared world exactly"
    else:
        message = "boolean cache policy"
    monkeypatch.setattr(
        arrays, "compiled_fuel_world_stages", lambda: pytest.fail("Invalid warmup reached compiler")
    )
    events = []
    with pytest.raises(ValueError, match=message):
        compilation.compile_fuel_cpu_stages(
            cohort,
            proposal,
            release_frontend="true" if damage == "policy" else True,
            observer=events.append,
        )
    assert not events
    evidence("public-warmup-refusal-" + damage, dict(refused_before_compiling=True, case=damage))
