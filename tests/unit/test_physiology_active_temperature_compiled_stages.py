"""Complete compiled stage checks, distinct from the earlier fused CPU test."""

import ctypes
import gc
import os
import platform
import time
from pathlib import Path

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


def test_split_fuel_cpu_executables_preserve_complete_worlds(monkeypatch):
    complete_cpu_case("fuel", monkeypatch, split_fuel=True)


def test_split_fuel_cpu_executables_release_frontend_caches(monkeypatch):
    complete_cpu_case("fuel", monkeypatch, split_fuel=True, release_frontend=True)


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
        cohort.numeric,
        proposals,
        family=family,
        xp=np,
        stages=stages,
    )
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda value, i=i: value[i], proposals),
            jax.tree.map(lambda value, i=i: value[i], result),
            f"split-calcium-numpy-{i}",
        )


def complete_cpu_case(
    kind, monkeypatch, *, split_calcium=False, split_fuel=False, release_frontend=False
):
    assert not (split_calcium and split_fuel)
    assert not release_frontend or (kind == "fuel" and split_fuel)
    cases, cohort, proposals = fixtures(kind, count=2)
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    assert not jax.config.jax_disable_jit
    numeric, raw = jax.tree.map(jnp.asarray, (cohort.numeric, proposals))
    stages = (
        arrays.compiled_fuel_world_stages()
        if split_fuel
        else arrays.compiled_calcium_world_stages()
        if split_calcium
        else arrays.compiled_world_stages(cohort.family)
    )
    assert stages.family == cohort.family
    label = "split-fuel" if split_fuel else "split-calcium" if split_calcium else "separate"
    if release_frontend:
        label += "-cache-managed"
    world = jax.tree.map(lambda value: value[0], numeric)
    proposal = jax.tree.map(lambda value: value[0], raw)

    # Host admission is complete. Compiled functions must not call it again.
    for name in ("initial_values", "check_values", "check_steps"):
        monkeypatch.setattr(
            arrays.IMPLEMENTATIONS[cohort.family],
            name,
            lambda *a, **k: pytest.fail("Numeric stage invoked host admission"),
        )
    monkeypatch.setattr(
        host, "_runtime", lambda *a, **k: pytest.fail("Numeric stage invoked host projection")
    )

    def release_completed_compilation(name):
        # Dedicated CPU qualification worker only. Executable objects and all
        # live state/output buffers stay owned by the caller. This reuses the
        # cache/allocator policy of the protein-interval array checks, without
        # changing the default factories or inserting work into simulation steps.
        allocator = platform.libc_ver()
        assert allocator[0] == "glibc"

        def memory():
            values = {}
            for line in Path("/proc/self/status").read_text().splitlines():
                if line.startswith(("VmRSS:", "VmHWM:")):
                    key, amount, unit = line.split()
                    assert unit == "kB"
                    values[key.rstrip(":") + "_bytes"] = int(amount) * 1024
            assert set(values) == {"VmRSS_bytes", "VmHWM_bytes"}
            return dict(monotonic_s=time.monotonic(), **values)

        before = memory()
        jax.clear_caches()
        collected = gc.collect()
        trim = ctypes.CDLL(None).malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        trim_result = trim(0)
        evidence(
            f"{label}-{kind}-{name}-cache-release",
            dict(
                stage=name,
                allocator=allocator,
                before=before,
                after=memory(),
                collected_objects=collected,
                malloc_trim_result=trim_result,
                compiled_executables_retained=True,
                memory_limit_unchanged=True,
                policy="Explicit CPU warmup cache release; no steady-step cache eviction",
            ),
        )

    if release_frontend:
        release_completed_compilation("host-preparation")

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
        if release_frontend:
            release_completed_compilation(name)
        return executable, value

    inputs_fn, inputs = execute(
        "inputs",
        stages.inputs,
        world.layout,
        world.certificate,
        proposal,
    )
    if split_fuel:
        ionic_fn, ionic = execute(
            "fuel-ionic",
            stages.physics.ionic,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
        )
        calcium_fn, calcium_values = execute(
            "fuel-calcium",
            stages.physics.calcium,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
            ionic,
        )
        completion_fn, physics = execute(
            "fuel-exchange",
            stages.physics.completion,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
            calcium_values,
        )
        physics_fn = arrays.FuelPhysicsStages(ionic_fn, calcium_fn, completion_fn)
    elif split_calcium:
        ionic_fn, ionic = execute(
            "ionic",
            stages.physics.ionic,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
        )
        completion_fn, physics = execute(
            "calcium",
            stages.physics.completion,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
            ionic,
        )
        physics_fn = arrays.CalciumPhysicsStages(ionic_fn, completion_fn)
    else:
        physics_fn, physics = execute(
            "physics",
            stages.physics,
            world.state,
            inputs.arithmetic_runtime_layout,
            inputs.arithmetic_control,
        )
    checks_fn, _ = execute(
        "checks",
        stages.checks,
        world.state,
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
        inputs.arithmetic_step_s,
        physics,
    )
    # These are already compiled executable objects. The cohort wrapper cannot
    # trace through them and silently fuse the three full physical stages.
    executables = arrays.WorldStages(cohort.family, inputs_fn, physics_fn, checks_fn)

    def evaluate(values, proposed):
        result = arrays.evaluate_batch_staged(
            values,
            proposed,
            family=cohort.family,
            stages=executables,
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
            f"{label}-cpu-{kind}-{i}",
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
        rejected.arithmetic_runtime_layout.temperature,
        numeric.certificate.temperature_K,
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
                ["inputs", "fuel-ionic", "fuel-calcium", "fuel-exchange", "checks"]
                if split_fuel
                else ["inputs", "ionic", "calcium", "checks"]
                if split_calcium
                else ["inputs", "physics", "checks"]
            ),
            distinct_worlds=2,
            reorder_exact=True,
            partition_exact=True,
            raw_invalid_retained=True,
            cpu_warmup_cache_release=release_frontend,
            gpu_qualified=False,
            trajectories_qualified=False,
        ),
    )
