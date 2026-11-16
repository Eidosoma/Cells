"""Sums over species in one declared order (A7; the operators stream's summation SPEC.md §2).

D165, amended by D176: a sum over the species axis is a serial left fold in declared species
order, the same code for NumPy and jax.numpy, so that bitwise-equal terms give bitwise-equal sums
on the host and the device.

- species_sum(values, *, xp): the sum over the leading species axis of a species-leading array
  [S, ...], as total = values[0], then total = total + values[s] for s = 1 .. S-1. It is never a
  reduce, and never xp.sum inside. On the device its input passes through
  jax.lax.optimization_barrier, so that XLA cannot fuse the callers' products into the adds and
  contract them (FMA), which was measured to make host and device differ at 8 species. On the
  host it is the identity.
- entity_sum(values, axis=None, *, xp): xp.sum under a name, for sums that never include the
  species axis. Its axis is written at every call.
- A full reduce over a species-leading array is entity_sum(species_sum(values, xp=xp), xp=xp),
  the species first.

The caller forms the terms (p.valence * flux, mu * supplied); the helper takes no weights.

This module imports nothing from cells.models. Since A7's sweep, every sum in @3's module, the
operators and the kinds goes through species_sum or entity_sum (the summation SITES.md's 37
species-axis sums, 10 full reduces and 7 former row_sum folds), and
tests/unit/test_species_sum_sites.py refuses any other sum there and freezes the entity sums. The
shared modules (surface_tissue, surface_pump, numerics/surface_imex and others) keep their own
sums (the lead's manifest ruling, docs/INNER_MODEL_V4_DESIGN.md §10.6).
"""

import numpy as np


def _barrier(values, xp):
    """jax.lax.optimization_barrier on the device; the identity on the host."""
    if xp is np:
        return values
    import jax

    return jax.lax.optimization_barrier(values)


def species_sum(values, *, xp, barrier=True):
    """The serial left fold of values [S, ...] over its leading species axis, S >= 1.

    barrier: put the device barrier on the input (the default). D182 (16 November, from the GPU
    column) keeps it at every listed species-axis sum and full reduce. The former row_sum folds
    pass False, as A7's tolerance rehearsal ran them (species_turnover.ROW_BARRIER); the fold
    itself never changes.
    """
    if values.shape[0] < 1:
        raise ValueError("species_sum requires at least one species")
    if barrier:
        values = _barrier(values, xp)
    total = values[0]
    for s in range(1, values.shape[0]):
        total = total + values[s]
    return total


def entity_sum(values, axis=None, *, xp):
    """xp.sum over entities (never the species axis); the axis is written at every call."""
    return xp.sum(values, axis=axis)
