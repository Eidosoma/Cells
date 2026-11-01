"""Conservative steady conduction on the declared physical rectangle.

The homogeneous medium has explicitly supplied conductivity (S/m) and slab
depth (m). Faces point towards increasing x/y: E=-grad(phi), J=sigma*E.
Positive volumetric current injection s (A/m^3) satisfies div(J)=s, hence
L(phi)=-s/sigma. Outer normal current is zero; compatible sources must balance.

This composes the existing face stencil and projected solver, without a dense
matrix or new inverse. Original source compatibility, conversion failures and
the final current residual remain separate from the inner Poisson gates.
Complete failed candidates are returned, never centred or silently retried.
Power balance is a diagnostic, not an ionic/thermodynamic energy-closure claim.
No native tissue/phase, heterogeneous material, mask or checkpoint is admitted.
"""

import math
from typing import NamedTuple

import numpy as np

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_iterative as iterative
from cells.processes import rectangular_environment_stencil as stencil

LAW_ID = "cells.rectangular_uniform_steady_conduction@1"
MIN_NORMAL_BINARY64 = 2.0**-1022


class Fields(NamedTuple):
    potential_V: object
    electric_V_m: stencil.Faces
    current_density_A_m2: stencil.Faces
    face_current_A: stencil.Faces
    divergence_A_m3: object
    total_divergence_A: object
    boundary_current_A: object
    conservation_error_A: object
    dissipation_W: object
    zero_boundary: object
    arithmetic_representable: object
    finite_result: object

    @property
    def usable(self):
        """Finite uniform-material readout, not a solved continuity equation."""
        return self.finite_result & self.zero_boundary & self.arithmetic_representable


class SolveResult(NamedTuple):
    source_A_m3: object
    poisson_rhs_V_m2: object
    linear_solve: iterative.SolveResult
    fields: Fields
    continuity_residual_A_m3: object
    continuity_tolerance_A_m3: object
    source_compatible: object
    conversion_ok: object
    continuity_ok: object
    total_source_A: object
    source_power_W: object
    power_defect_W: object
    finite_result: object

    @property
    def usable(self):
        return (
            self.linear_solve.converged
            & self.fields.usable
            & self.source_compatible
            & self.conversion_ok
            & self.continuity_ok
            & self.finite_result
        )

    @property
    def converged(self):
        return self.usable


def _medium(grid, conductivity_S_m, depth_m):
    if type(grid) not in (field.GridBinding, field.MetricBinding):
        raise ValueError("Require an existing rectangular grid binding")
    for value in (conductivity_S_m, depth_m):
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < MIN_NORMAL_BINARY64
        ):
            raise ValueError(
                "Require explicit finite positive normal host conductivity and slab depth"
            )
    sigma, depth = float(conductivity_S_m), float(depth_m)
    dx, dy = grid.spacing_xy_m
    volume = grid.cell_area_m2 * depth
    area_x, area_y = dy * depth, dx * depth
    if any(not math.isfinite(v) or v < MIN_NORMAL_BINARY64 for v in (volume, area_x, area_y)):
        raise ValueError("Unrepresentable positive slab volume or face area")
    return sigma, depth, volume, area_x, area_y


def _policy(rtol, atol_A_m3, sigma):
    for value in (rtol, atol_A_m3):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Require explicit finite nonnegative current residual tolerances")
    atol = atol_A_m3 / sigma
    if not math.isfinite(atol) or (atol_A_m3 > 0 and atol == 0):
        raise ValueError("Unrepresentable absolute current-to-Poisson tolerance conversion")
    return atol


def _bits(value, xp):
    return xp.asarray(value).view(xp.uint64) & xp.uint64(0x7FFFFFFFFFFFFFFF)


def _portable(value, xp):
    bits = _bits(value, xp)
    return xp.isfinite(value) & ((bits == 0) | (bits >= xp.uint64(0x0010000000000000)))


def evaluate(potential_V, grid, *, conductivity_S_m, depth_m, xp=np):
    """Return staggered E/J, complete face currents and raw balance diagnostics.

    Internal face dual volumes equal the common cell volume dx*dy*depth.
    Outer E/J are zero by the declared boundary; no one-sided derivative or
    membrane/bath current is invented. Leading batch axes remain independent.
    Medium/measures must be normal binary64. A conservative range gate also
    refuses subnormal readout values or a nonzero gradient/current/power lost
    to zero, including backend flush-to-zero. Raw outputs remain intact. This
    gate does not certify rounding error or power closure.
    """
    sigma, depth, volume, area_x, area_y = _medium(grid, conductivity_S_m, depth_m)
    potential = stencil._field(potential_V, grid, xp)
    gradient = stencil.gradient(potential, grid, xp=xp)
    electric = stencil.Faces(-gradient.x, -gradient.y)
    current = stencil.Faces(sigma * electric.x, sigma * electric.y)
    faces = stencil.Faces(area_x * current.x, area_y * current.y)
    divergence = stencil.divergence(current, grid, xp=xp)
    total = depth * divergence.cell_integral
    boundary = depth * divergence.boundary_integral
    balance = total - boundary
    density_x, density_y = electric.x * current.x, electric.y * current.y
    power_density = xp.sum(density_x, axis=(-2, -1)) + xp.sum(density_y, axis=(-2, -1))
    dissipation = volume * power_density
    # Integer comparisons remain meaningful when the backend flushes floating
    # subnormals. Preserve sign on potentials, except for equivalent +/- zero.
    potential_bits = potential.view(xp.uint64)
    potential_bits = xp.where(_bits(potential, xp) == 0, xp.uint64(0), potential_bits)
    shaped_bits = potential_bits.reshape((*potential.shape[:-1], *grid.shape))
    representable = (
        xp.all(_portable(potential, xp), axis=-1)
        & xp.all(
            (shaped_bits[..., :, 1:] == shaped_bits[..., :, :-1])
            | (_bits(electric.x[..., :, 1:-1], xp) != 0),
            axis=(-2, -1),
        )
        & xp.all(
            (shaped_bits[..., 1:, :] == shaped_bits[..., :-1, :])
            | (_bits(electric.y[..., 1:-1, :], xp) != 0),
            axis=(-2, -1),
        )
    )
    for e, j, face, density in (
        (electric.x, current.x, faces.x, density_x),
        (electric.y, current.y, faces.y, density_y),
    ):
        representable = representable & xp.all(
            _portable(e, xp)
            & _portable(j, xp)
            & _portable(face, xp)
            & _portable(density, xp)
            & ((_bits(e, xp) == 0) | (_bits(j, xp) != 0))
            & ((_bits(j, xp) == 0) | (_bits(face, xp) != 0))
            & ((_bits(e, xp) == 0) | (_bits(j, xp) == 0) | (_bits(density, xp) != 0)),
            axis=(-2, -1),
        )
    representable = (
        representable
        & _portable(power_density, xp)
        & _portable(dissipation, xp)
        & ((_bits(power_density, xp) == 0) | (_bits(dissipation, xp) != 0))
    )
    finite = (
        xp.all(xp.isfinite(potential), axis=-1)
        & xp.all(xp.isfinite(electric.x), axis=(-2, -1))
        & xp.all(xp.isfinite(electric.y), axis=(-2, -1))
        & xp.all(xp.isfinite(faces.x), axis=(-2, -1))
        & xp.all(xp.isfinite(faces.y), axis=(-2, -1))
        & divergence.finite_result
        & xp.isfinite(total)
        & xp.isfinite(boundary)
        & xp.isfinite(balance)
        & xp.isfinite(dissipation)
    )
    return Fields(
        potential,
        electric,
        current,
        faces,
        divergence.values,
        total,
        boundary,
        balance,
        dissipation,
        divergence.zero_boundary,
        representable,
        finite,
    )


def _finish(source, rhs, numeric, grid, medium, rtol, atol_A_m3, xp):
    sigma, depth, volume, _, _ = medium
    values = evaluate(numeric.potential, grid, conductivity_S_m=sigma, depth_m=depth, xp=xp)
    finite_source = xp.all(xp.isfinite(source), axis=-1)
    magnitude = xp.max(xp.abs(source), axis=-1)
    divisor = xp.where(finite_source & (magnitude > 0), magnitude, 1.0)
    scaled = xp.where(finite_source[..., None], source, 0.0) / divisor[..., None]
    compatible = finite_source & (
        xp.abs(xp.sum(scaled, axis=-1)) <= field.RHS_RTOL * xp.sum(xp.abs(scaled), axis=-1)
    )
    # Use IEEE bits rather than floating comparisons: a compiled backend may
    # flush subnormals during comparison/arithmetic. This portable boundary
    # requires zero or normal binary64 forcing, preserving refused raw values.
    signless = xp.uint64(0x7FFFFFFFFFFFFFFF)
    minimum_normal = xp.uint64(0x0010000000000000)
    source_bits = source.view(xp.uint64) & signless
    rhs_bits = rhs.view(xp.uint64) & signless
    conversion = (
        finite_source
        & xp.all(xp.isfinite(rhs), axis=-1)
        & xp.all(
            ((source_bits == 0) | (source_bits >= minimum_normal))
            & ((rhs_bits == 0) | (rhs_bits >= minimum_normal))
            & ((source_bits == 0) | (rhs_bits != 0)),
            axis=-1,
        )
    )
    residual = values.divergence_A_m3 - source
    tolerance = xp.maximum(atol_A_m3, rtol * magnitude)
    current_ok = xp.max(xp.abs(residual), axis=-1) <= tolerance
    total_source = volume * xp.sum(source, axis=-1)
    source_power = volume * xp.sum(values.potential_V * source, axis=-1)
    power_defect = source_power - values.dissipation_W
    finite = (
        finite_source
        & values.finite_result
        & numeric.finite_result
        & xp.all(xp.isfinite(residual), axis=-1)
        & xp.isfinite(tolerance)
        & xp.isfinite(total_source)
        & xp.isfinite(source_power)
        & xp.isfinite(power_defect)
    )
    return SolveResult(
        source,
        rhs,
        numeric,
        values,
        residual,
        tolerance,
        compatible,
        conversion,
        current_ok,
        total_source,
        source_power,
        power_defect,
        finite,
    )


def solve(
    source_A_m3,
    grid,
    *,
    conductivity_S_m,
    depth_m,
    max_iterations,
    rtol,
    atol_A_m3=0.0,
    initial_potential_V=None,
    xp=np,
    iteration_loop=None,
):
    """Solve steady current continuity against the ORIGINAL volumetric source.

    Residual acceptance is max|div(J)-source| <= max(atol_A_m3, rtol*max|source|).
    The inner solver also retains its own unmodified Poisson gates. A nonzero
    source lost in conductivity conversion remains unusable even when below an
    absolute tolerance. Nonzero source/RHS entries must be normal binary64;
    subnormals remain in the raw outputs with conversion_ok=False for consistent
    NumPy/JAX admission. Failed/nonfinite warm guesses never silently restart.
    Constant conductivity/depth are host parameters; source/potential are
    binary64 arrays with the C-order grid axis last.
    """
    medium = _medium(grid, conductivity_S_m, depth_m)
    atol = _policy(rtol, atol_A_m3, medium[0])
    source = stencil._field(source_A_m3, grid, xp)
    rhs = -source / medium[0]
    numeric = iterative.solve(
        rhs,
        grid,
        max_iterations=max_iterations,
        rtol=rtol,
        atol=atol,
        initial_potential=initial_potential_V,
        xp=xp,
        iteration_loop=iteration_loop,
    )
    return _finish(source, rhs, numeric, grid, medium, rtol, atol_A_m3, xp)


def compile_jax_solver(grid, *, conductivity_S_m, depth_m, max_iterations, rtol, atol_A_m3=0.0):
    """Reusable compiled array entry; device placement remains caller-controlled.

    Uses the existing JAX solver's binary64/JIT requirements. Synchronize device
    outputs before timings or acceptance. This factory itself is not GPU evidence.
    """
    medium = _medium(grid, conductivity_S_m, depth_m)
    atol = _policy(rtol, atol_A_m3, medium[0])
    linear = iterative.compile_jax_solver(grid, max_iterations=max_iterations, rtol=rtol, atol=atol)
    import jax
    import jax.numpy as jnp

    def run(source_A_m3, initial_potential_V=None):
        source = stencil._field(source_A_m3, grid, jnp)
        rhs = -source / medium[0]
        numeric = linear(rhs, initial_potential_V)
        return _finish(source, rhs, numeric, grid, medium, rtol, atol_A_m3, jnp)

    return jax.jit(run)
