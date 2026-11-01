"""Conservative transfer between declared current sites and a rectangle.

Each named site supplies amperes to one explicitly named grid cell. Positive
current enters the environment. Contributions add; division by the physical
cell volume gives A/m^3 for rectangular_environment_conduction. The transpose
readout returns that same cell's voltage, so the two transfers preserve the
discrete current-voltage power pairing in exact arithmetic.

Assignments are declared data, not native membrane/phase authority. This does
not choose nearest neighbours, interpolate, alter masks, balance a source, or
advance ions. Closed-domain source compatibility belongs to the field solve.
Floating summation errors remain visible under explicit aggregate tolerances;
these checks do not certify every individual accumulated cell current.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_conduction as conduction
from cells.processes import rectangular_environment_stencil as stencil

LAW_ID = "cells.declared_site_current_rectangle_transfer@1"
MAX_SITES = 2**20


@dataclass(frozen=True)
class CurrentMap:
    source_ids: tuple
    target_indices: tuple
    environment_ids: tuple
    grid_identity: str
    identity: str


class DepositResult(NamedTuple):
    site_current_A: object
    cell_current_A: object
    source_A_m3: object
    total_input_A: object
    total_accumulated_A: object
    total_grid_A: object
    conservation_error_A: object
    conservation_tolerance_A: object
    conservation_ok: object
    conversion_ok: object
    finite_result: object

    @property
    def usable(self):
        """Usable transfer; no assertion that the source is globally balanced."""
        return self.conservation_ok & self.conversion_ok & self.finite_result


def _identity(source_ids, indices, environment_ids, grid_identity):
    return hashlib.sha256(
        json.dumps(
            [LAW_ID, source_ids, indices, environment_ids, grid_identity],
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def bind(grid, *, source_ids, target_environment_ids):
    """Freeze explicit site assignments, allowing multiple sites per cell.

    All IDs are retained in order. The declared host cap is not tested-at-cap
    evidence; numerical storage is linear in sites plus grid cells.
    """
    if type(grid) not in (field.GridBinding, field.MetricBinding):
        raise ValueError("Require an existing physical rectangular grid binding")
    if (
        type(source_ids) is not tuple
        or type(target_environment_ids) is not tuple
        or not 0 < len(source_ids) <= MAX_SITES
        or len(target_environment_ids) != len(source_ids)
        or any(type(s) is not str or not s for s in source_ids)
        or len(set(source_ids)) != len(source_ids)
        or any(type(s) is not str for s in target_environment_ids)
    ):
        raise ValueError("Require unique named source sites and equally sized explicit target IDs")
    index = {name: i for i, name in enumerate(grid.environment_ids)}
    if any(name not in index for name in target_environment_ids):
        raise ValueError("A declared current target is outside this grid")
    indices = tuple(index[name] for name in target_environment_ids)
    return CurrentMap(
        source_ids,
        indices,
        grid.environment_ids,
        grid.identity,
        _identity(source_ids, indices, grid.environment_ids, grid.identity),
    )


def _mapping(mapping, grid):
    if (
        type(mapping) is not CurrentMap
        or type(grid) not in (field.GridBinding, field.MetricBinding)
        or mapping.grid_identity != grid.identity
        or mapping.environment_ids != grid.environment_ids
        or type(mapping.source_ids) is not tuple
        or not 0 < len(mapping.source_ids) <= MAX_SITES
        or any(type(s) is not str or not s for s in mapping.source_ids)
        or len(set(mapping.source_ids)) != len(mapping.source_ids)
        or type(mapping.target_indices) is not tuple
        or len(mapping.target_indices) != len(mapping.source_ids)
        or any(
            type(i) is not int or not 0 <= i < len(grid.environment_ids)
            for i in mapping.target_indices
        )
        or mapping.identity
        != _identity(
            mapping.source_ids,
            mapping.target_indices,
            mapping.environment_ids,
            mapping.grid_identity,
        )
    ):
        raise ValueError("Current map does not match its declared grid and assignments")
    return mapping.target_indices


def deposit(site_current_A, mapping, grid, *, depth_m, rtol, atol_A=0.0, xp=np):
    """Add signed site currents and normalize by volume; never centre or retry.

    Explicit aggregate conservation criterion:
    abs(volume*sum(source)-sum(site currents)) <= max(atol_A, rtol*sum(abs(I))).
    Inputs and converted sources must be finite zero-or-normal binary64; failed
    values are returned unchanged. Leading batch axes remain independent.
    """
    indices = _mapping(mapping, grid)
    _, _, volume, _, _ = conduction._medium(grid, 1.0, depth_m)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (rtol, atol_A)):
        raise ValueError("Require explicit finite nonnegative current tolerances")
    current = xp.asarray(site_current_A)
    if current.ndim < 1 or current.shape[-1] != len(indices) or str(current.dtype) != "float64":
        raise ValueError("Require binary64 site currents with the declared site axis last")
    cells = xp.zeros((*current.shape[:-1], len(grid.environment_ids)), dtype=current.dtype)
    targets = xp.asarray(indices, dtype=xp.int64)
    if xp is np:
        np.add.at(cells, (..., targets), current)
    else:
        cells = cells.at[..., targets].add(current)
    source = cells / volume
    input_total = xp.sum(current, axis=-1)
    accumulated_total = xp.sum(cells, axis=-1)
    grid_total = volume * xp.sum(source, axis=-1)
    error = grid_total - input_total
    tolerance = xp.maximum(atol_A, rtol * xp.sum(xp.abs(current), axis=-1))
    conversion = (
        xp.all(conduction._portable(current, xp), axis=-1)
        & xp.all(conduction._portable(cells, xp), axis=-1)
        & xp.all(conduction._portable(source, xp), axis=-1)
        & xp.all((conduction._bits(cells, xp) == 0) | (conduction._bits(source, xp) != 0), axis=-1)
    )
    finite = (
        xp.all(xp.isfinite(current), axis=-1)
        & xp.all(xp.isfinite(cells), axis=-1)
        & xp.all(xp.isfinite(source), axis=-1)
        & xp.isfinite(input_total)
        & xp.isfinite(accumulated_total)
        & xp.isfinite(grid_total)
        & xp.isfinite(error)
        & xp.isfinite(tolerance)
    )
    return DepositResult(
        current,
        cells,
        source,
        input_total,
        accumulated_total,
        grid_total,
        error,
        tolerance,
        xp.abs(error) <= tolerance,
        conversion,
        finite,
    )


def gather_potential(potential_V, mapping, grid, *, xp=np):
    """Transpose assignment: one voltage per source site, preserving duplicates.

    Raw nonfinite values are not repaired. In exact arithmetic,
    sum(site_current * gathered_voltage) equals sum(cell_current * voltage).
    The caller must retain the deposition/field flags for a coupled result.
    """
    indices = _mapping(mapping, grid)
    potential = stencil._field(potential_V, grid, xp)
    return xp.take(potential, xp.asarray(indices, dtype=xp.int64), axis=-1)
