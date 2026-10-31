"""Explicit CPU warmup for complete open-bath active cohorts.

Preparation retains compiled executables and complete reservoir ownership.
Optional frontend cache release belongs to a dedicated preparation worker.
"""

import os
import platform

import jax
import jax.numpy as jnp

from cells.core import physiology_active_temperature_arrays as prepared
from cells.core.physiology_active_temperature_compilation import _release_cpu_frontend
from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_open_arrays as opened

KIND = "cells.physiology_active_temperature_open_cpu_warmup@1"


def compile_open_cpu_stages(cohort, proposal, *, release_frontend=False, observer=None):
    """Admit an open calcium/fuel cohort and retain five/six CPU executables.

    Revalidate complete cohort provenance before compiling one world's shapes.
    Reservoir flags and all material, electrode, work and fuel owners reach
    the original physical stages. Preparation does not advance simulation time.

    Reuse the result through ``evaluate_batch_staged(..., stages=stages)`` for
    host-admitted cohorts with matching per-world shapes. Set
    ``release_frontend=True`` explicitly to release process-wide JAX frontend
    caches and unused glibc pages between stages. No cleanup or observation
    occurs during subsequent numerical evaluation. Caller-owned process guards
    enforce memory/time limits; this API does not qualify a backend by itself.
    """
    if type(release_frontend) is not bool or (observer is not None and not callable(observer)):
        raise ValueError("Declare a boolean cache policy and optional callable observer")
    if type(cohort) is not prepared.Cohort or cohort.family not in opened.FAMILIES:
        raise ValueError("CPU warmup requires a trusted open calcium or finite-fuel cohort")
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
    functions = opened.compiled_world_stages(family)

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
    ionic_fn, ionic = compile_stage("ionic", functions.physics.ionic, *args)
    calcium_fn, parent = compile_stage("calcium", functions.physics.calcium, *args, ionic)
    if family == opened.FUEL:
        fuel_fn, parent = compile_stage("fuel-exchange", functions.physics.fuel, *args, parent)
    reservoir_fn, physics = compile_stage("reservoir", functions.physics.reservoir, *args, parent)
    physics_fn = (
        opened.FuelPhysicsStages(ionic_fn, calcium_fn, fuel_fn, reservoir_fn)
        if family == opened.FUEL
        else opened.CalciumPhysicsStages(ionic_fn, calcium_fn, reservoir_fn)
    )
    checks_fn, _ = compile_stage(
        "checks", functions.checks, *args, inputs.arithmetic_step_s, physics
    )
    stages = arrays.WorldStages(family, inputs_fn, physics_fn, checks_fn)
    emit("warmup", "completed", compiled_stages=len(physics_fn) + 2, world_state_advanced=False)
    return stages
