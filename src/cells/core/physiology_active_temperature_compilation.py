"""Explicit CPU warmup for complete, host-admitted closed active cohorts.

Keep this preparation outside the array kernels and simulation steps. Optional
cache release is process-wide and belongs in a dedicated preparation worker.
Returned executable objects remain reusable across compatible cohort shapes.
"""

import ctypes
import gc
import os
import platform
import time
from pathlib import Path

import jax
import jax.numpy as jnp

from cells.core import physiology_active_temperature_arrays as prepared
from cells.models import physiology_active_temperature_arrays as arrays

KIND = "cells.physiology_active_temperature_cpu_warmup@1"
FAMILY = "resolved_calcium_energy@5"
CLOSED_FAMILIES = ("resolved_tissue@12", "resolved_calcium@11", FAMILY)


def _release_cpu_frontend():
    """Release completed staging/scratch storage, keeping all live objects."""
    allocator = platform.libc_ver()
    if allocator[0] != "glibc":
        raise ValueError("CPU frontend release requires the declared glibc allocator")

    def memory():
        values = {}
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                key, amount, unit = line.split()
                if unit != "kB":
                    raise ValueError("Unexpected process-memory measurement unit")
                values[key.rstrip(":") + "_bytes"] = int(amount) * 1024
        if set(values) != {"VmRSS_bytes", "VmHWM_bytes"}:
            raise ValueError("CPU warmup requires current RSS and high-water measurements")
        return dict(monotonic_s=time.monotonic(), **values)

    before = memory()
    jax.clear_caches()
    collected = gc.collect()
    trim = ctypes.CDLL(None).malloc_trim
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    trim_result = trim(0)
    return dict(
        allocator=allocator,
        before=before,
        after=memory(),
        collected_objects=collected,
        malloc_trim_result=trim_result,
        compiled_executables_retained=True,
    )


def compile_cpu_stages(cohort, proposal, *, release_frontend=False, observer=None):
    """Admit a closed active cohort and compile its reusable CPU stages.

    Ionic, calcium and finite-fuel families use three, four and five retained
    executables respectively, with their original complete physics and checks.

    ``proposal`` has the same leading world axis as the trusted ``cohort``.
    World zero supplies shapes and runtime values for warmup; its state is not
    advanced. All cohort provenance is checked before compiling. Later calls
    use ``evaluate_batch_staged(..., stages=returned_stages)`` and the existing
    per-world numeric admission flags. This function never advances simulation time.

    ``release_frontend=True`` explicitly permits process-wide JAX cache release
    and glibc free-page trimming during warmup only. Keep unrelated compilation
    out of that worker. ``observer`` receives small preparation records and may
    write durable evidence; records contain no state buffers or executables.
    Resource limits belong to the caller's existing guarded process runner.
    """
    if type(release_frontend) is not bool or (observer is not None and not callable(observer)):
        raise ValueError("Declare a boolean cache policy and optional callable observer")
    if type(cohort) is not prepared.Cohort or cohort.family not in CLOSED_FAMILIES:
        raise ValueError("CPU warmup requires a trusted closed active cohort")
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled or jax.config.jax_disable_jit:
        raise ValueError("CPU warmup requires CPU, float64 and enabled compilation")
    if release_frontend and platform.libc_ver()[0] != "glibc":
        raise ValueError("CPU frontend release requires the declared glibc allocator")

    prepared.validate_cohort(cohort)
    family = cohort.family
    count = arrays._batch_world_count(cohort.numeric, proposal, family)
    world = jax.tree.map(lambda value: jnp.asarray(value[0]), cohort.numeric)
    raw = jax.tree.map(lambda value: jnp.asarray(value[0]), proposal)
    arrays._world_protocol(world.layout, world.certificate, raw, family, xp=jnp)

    def emit(stage, status, **fields):
        if observer is not None:
            observer(dict(kind=KIND, stage=stage, status=status, **fields))

    emit(
        "admission",
        "validated",
        cohort_identity=cohort.identity,
        worlds=count,
        family=family,
        release_frontend=release_frontend,
        affinity=sorted(os.sched_getaffinity(0)),
    )
    if release_frontend:
        emit("host-preparation", "cache_released", **_release_cpu_frontend())
    functions = (
        arrays.compiled_fuel_world_stages()
        if family == FAMILY
        else arrays.compiled_calcium_world_stages()
        if family == "resolved_calcium@11"
        else arrays.compiled_world_stages(family)
    )

    def compile_stage(name, function, *args):
        emit(name, "compile_started")
        try:
            executable = function.lower(*args).compile()
            value = executable(*args)
            jax.block_until_ready(value)
            emit(name, "compiled_executed", output_leaves=len(jax.tree.leaves(value)))
            if release_frontend:
                emit(name, "cache_released", **_release_cpu_frontend())
            return executable, value
        except Exception as error:
            emit(name, "failed", error_type=type(error).__name__, message=str(error))
            raise

    inputs_fn, inputs = compile_stage(
        "inputs", functions.inputs, world.layout, world.certificate, raw
    )
    args = (world.state, inputs.arithmetic_runtime_layout, inputs.arithmetic_control)
    if family == FAMILY:
        ionic_fn, ionic = compile_stage("fuel-ionic", functions.physics.ionic, *args)
        calcium_fn, calcium = compile_stage("fuel-calcium", functions.physics.calcium, *args, ionic)
        fuel_fn, physics = compile_stage(
            "fuel-exchange", functions.physics.completion, *args, calcium
        )
        physics_fn = arrays.FuelPhysicsStages(ionic_fn, calcium_fn, fuel_fn)
        stage_count = 5
    elif family == "resolved_calcium@11":
        ionic_fn, ionic = compile_stage("ionic", functions.physics.ionic, *args)
        calcium_fn, physics = compile_stage("calcium", functions.physics.completion, *args, ionic)
        physics_fn = arrays.CalciumPhysicsStages(ionic_fn, calcium_fn)
        stage_count = 4
    else:
        physics_fn, physics = compile_stage("physics", functions.physics, *args)
        stage_count = 3
    checks_fn, _ = compile_stage(
        "checks", functions.checks, *args, inputs.arithmetic_step_s, physics
    )
    stages = arrays.WorldStages(family, inputs_fn, physics_fn, checks_fn)
    emit("warmup", "completed", compiled_stages=stage_count, world_state_advanced=False)
    return stages


def compile_fuel_cpu_stages(cohort, proposal, *, release_frontend=False, observer=None):
    """Keep the fuel-only entry point and admission contract for existing callers."""
    if type(release_frontend) is not bool or (observer is not None and not callable(observer)):
        raise ValueError("Declare a boolean cache policy and optional callable observer")
    if type(cohort) is not prepared.Cohort or cohort.family != FAMILY:
        raise ValueError("CPU warmup requires a trusted closed finite-fuel cohort")
    return compile_cpu_stages(
        cohort, proposal, release_frontend=release_frontend, observer=observer
    )
