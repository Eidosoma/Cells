"""Complete open-bath CPU warmup, retained execution and provenance admission."""

from dataclasses import replace
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_active_temperature_open_compilation as compilation
from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_open_arrays as opened
from cells.models import physiology_active_temperature_view as host
from tests.unit.test_physiology_active_temperature_arrays import (
    check_world,
    evidence,
    exact_tree,
    fixtures,
)
from tests.unit.test_physiology_active_temperature_fuel_stages import save_trees


@pytest.mark.parametrize("kind", ("open-calcium", "open-fuel"))
def test_open_cpu_warmup_preserves_complete_worlds(kind, monkeypatch):
    cases, cohort, proposals = fixtures(kind, count=2)
    original = jax.tree.map(np.copy, (cohort.numeric, proposals))
    expected = ["inputs", "ionic", "calcium"]
    if kind == "open-fuel":
        expected.append("fuel-exchange")
    expected += ["reservoir", "checks"]
    events = []

    def observe(record):
        events.append(record)
        evidence(f"open-warmup-{kind}-{len(events):02d}", record)
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

    stages = compilation.compile_open_cpu_stages(
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
    assert all(
        callable(fn) and not hasattr(fn, "lower")
        for fn in [stages.inputs, *stages.physics, stages.checks]
    )
    event_count = len(events)
    monkeypatch.setattr(
        compilation,
        "_release_cpu_frontend",
        lambda: pytest.fail("Cohort execution repeated preparation cleanup"),
    )
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
            f"open-warmup-cpu-{kind}-{i}",
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
    partitioned = jax.tree.map(lambda *values: jnp.concatenate(values), *partitions)
    exact_tree(actual, partitioned)
    rejected = evaluate(numeric, raw._replace(temperature_K=raw.temperature_K.at[0].set(0.0)))
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
    exact_tree(original, (cohort.numeric, proposals))
    assert len(events) == event_count
    save_trees(
        f"open-warmup-{kind}-completed",
        dict(
            compiled_stages=expected,
            distinct_worlds=2,
            reorder_exact=True,
            partition_exact=True,
            raw_invalid_retained=True,
            numeric_host_admission_forbidden=True,
            observer_events=len(events),
            input_state_unchanged=True,
            gpu_qualified=False,
            trajectories_qualified=False,
        ),
        actual=actual,
        reversed_values=reversed_values,
        partitioned=partitioned,
        rejected=rejected,
    )


@pytest.fixture(scope="module")
def admitted_open():
    return fixtures("open-calcium", count=2)


@pytest.mark.parametrize(
    "damage",
    (
        "untrusted",
        "closed-ionic",
        "closed-calcium",
        "closed-fuel",
        "unknown",
        "identity",
        "family",
        "proposal_axis",
        "policy",
        "observer",
        "backend",
        "precision",
        "jit-disabled",
        "allocator",
    ),
)
def test_open_warmup_refuses_before_compiling(admitted_open, monkeypatch, damage):
    _, cohort, proposal = admitted_open
    if damage == "untrusted":
        cohort, message = object(), "trusted open"
    elif damage.startswith("closed-") or damage == "unknown":
        family = {
            "closed-ionic": "resolved_tissue@12",
            "closed-calcium": "resolved_calcium@11",
            "closed-fuel": "resolved_calcium_energy@5",
            "unknown": "unreviewed_family@1",
        }[damage]
        cohort, message = replace(cohort, family=family), "trusted open"
    elif damage == "identity":
        cohort, message = replace(cohort, identity="tampered"), "Stale trusted cohort"
    elif damage == "family":
        cohort, message = replace(cohort, family=opened.FUEL), "Stale trusted cohort"
    elif damage == "proposal_axis":
        proposal = proposal._replace(temperature_K=proposal.temperature_K[:1])
        message = "every prepared world exactly"
    elif damage in ("policy", "observer"):
        message = "boolean cache policy"
    elif damage == "backend":
        monkeypatch.setattr(jax, "default_backend", lambda: "gpu")
        message = "CPU, float64 and enabled compilation"
    elif damage in ("precision", "jit-disabled"):
        monkeypatch.setattr(
            jax,
            "config",
            SimpleNamespace(
                x64_enabled=damage != "precision", jax_disable_jit=damage == "jit-disabled"
            ),
        )
        message = "CPU, float64 and enabled compilation"
    else:
        monkeypatch.setattr(compilation.platform, "libc_ver", lambda: ("musl", ""))
        message = "declared glibc allocator"
    monkeypatch.setattr(
        opened, "compiled_world_stages", lambda *a: pytest.fail("Invalid warmup reached compiler")
    )
    monkeypatch.setattr(
        compilation, "_release_cpu_frontend", lambda: pytest.fail("Invalid warmup evicted caches")
    )
    events = []
    with pytest.raises(ValueError, match=message):
        compilation.compile_open_cpu_stages(
            cohort,
            proposal,
            release_frontend="true" if damage == "policy" else True,
            observer=object() if damage == "observer" else events.append,
        )
    assert not events
    evidence("open-warmup-refusal-" + damage, dict(refused_before_compiling=True, case=damage))
