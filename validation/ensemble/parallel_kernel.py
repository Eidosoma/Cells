"""Experimental parallel-world execution; never selected by production defaults.

Fixed-width tiles keep the inner world dimension constant for partial batches.
The field-protected variant applies scalar batching only to the extracellular
field calculation implicated in the previous partition mismatch. Acceptance
requires exact comparisons; neither strategy is assumed to preserve rounding.
"""

from contextlib import contextmanager
from functools import partial
from types import SimpleNamespace
from unittest.mock import patch

import jax
import jax.numpy as jnp
import numpy as np
from jax.custom_batching import sequential_vmap

from cells.assembly_cluster import engine, kernel
from cells.numerics import extracellular_field as field

TILE_WIDTH = 32
DEFAULT_VARIANTS = ("parallel", "parallel_scalar_field")
VARIANTS = (*DEFAULT_VARIANTS, "parallel_scalar_linear", "parallel_scalar_linear_sums")


def tile_map(function, inputs, *, width=TILE_WIDTH):
    """Batch independent worlds, preserving order and discarding padding replicas."""
    if type(width) is not int or width < 1:
        raise ValueError("Tile width must be a positive integer")
    leaves = jax.tree.leaves(inputs)
    if not leaves or any(v.ndim < 1 for v in leaves):
        raise ValueError("Require nonempty world arrays")
    worlds = leaves[0].shape[0]
    if worlds < 1 or any(v.shape[0] != worlds for v in leaves):
        raise ValueError("Every input must contain the same nonempty world axis")
    padding = (-worlds) % width

    def pack(value):
        # Replicate a complete valid world, including its ID. It has no shared
        # state or RNG stream consumption; its output is discarded. No sentinel
        # concentrations, repaired states or extra physical worlds are introduced.
        if padding:
            value = jnp.concatenate((value, jnp.repeat(value[-1:], padding, axis=0)), axis=0)
        return value.reshape((-1, width, *value.shape[1:]))

    result = jax.lax.map(jax.vmap(function), jax.tree.map(pack, inputs))
    return jax.tree.map(lambda v: v.reshape((-1, *v.shape[2:]))[:worlds], result)


def make_advance(*, width=TILE_WIDTH):
    @partial(jax.jit, static_argnames=("model",))
    def advance(
        state,
        ids,
        seeds,
        roots,
        constants,
        limits,
        dt,
        levels,
        owners,
        layout,
        control,
        *,
        ticks,
        model,
    ):
        def world_window(inputs):
            current, world_id = inputs

            def body(_, current):
                return kernel.one_tick(
                    current,
                    world_id,
                    seeds,
                    roots,
                    constants,
                    limits,
                    dt,
                    levels,
                    owners,
                    layout,
                    control,
                    model=model,
                )

            return jax.lax.fori_loop(0, ticks, body, current)

        return tile_map(world_window, (state, ids), width=width)

    return advance


class _FieldBackend:
    """Keep selected operations scalar without copying any field equations."""

    def __init__(self, *, scalar_sums):
        self.linalg = SimpleNamespace(solve=sequential_vmap(jnp.linalg.solve))
        self.scalar_sums = scalar_sums

    def __getattr__(self, name):
        return getattr(jnp, name)

    def sum(self, values, axis=None, **kwargs):
        if not self.scalar_sums:
            return jnp.sum(values, axis=axis, **kwargs)
        return sequential_vmap(lambda v: jnp.sum(v, axis=axis, **kwargs))(values)


def make_field_solver(variant):
    """Return an isolated experimental wrapper; NumPy host checks are unchanged."""
    if variant not in VARIANTS:
        raise ValueError("Unknown parallel-world candidate")
    original_solve = field.solve
    if variant == "parallel":
        return original_solve

    @sequential_vmap
    def scalar_solve(concentration, layout):
        return original_solve(concentration, layout, xp=jnp)

    backend = _FieldBackend(scalar_sums=variant == "parallel_scalar_linear_sums")

    def protected_solve(concentration, layout, *, xp=jnp):
        if xp is np:
            return original_solve(concentration, layout, xp=xp)
        if variant == "parallel_scalar_field":
            return scalar_solve(concentration, layout)
        return original_solve(concentration, layout, xp=backend)

    return protected_solve


@contextmanager
def candidate(variant, *, width=TILE_WIDTH):
    protected = make_field_solver(variant)
    with patch.object(engine, "advance", make_advance(width=width)):
        if variant != "parallel":
            with patch.object(field, "solve", protected):
                yield
        else:
            yield
