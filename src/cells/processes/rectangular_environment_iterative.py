"""Matrix-free projected CG for the Cells homogeneous-flux rectangle.

Solve L phi = rhs on the mean-zero subspace, with a zero-mean voltage reference.
The connected rectangular metric is the existing Cells law, not BETSE's native
scalar-delta convention. No dense matrix, inverse, masked domain or tissue owner
is constructed. Storage is O(batch size * number of cells).

Compatibility is checked on the original forcing. Only working search vectors
are projected; the final residual is the existing physical stencil applied to
the returned potential minus the ORIGINAL rhs. A small recurrence residual does
not establish convergence. Every batch member has independent status/counts.

An array backend may supply a functional while-loop (for example lax.while_loop).
The loop state has fixed shapes/dtypes and no array-to-host branch in its body.
This interface is not evidence of JAX/GPU qualification or differentiability.
"""

import math
from typing import NamedTuple

import numpy as np

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_stencil as stencil

LAW_ID = "cells.rectangular_zero_flux_projected_cg@1"
GAUGE_EPS_MULTIPLIER = 64


class SolveResult(NamedTuple):
    potential: object
    residual: object
    rhs_compatible: object
    residual_ok: object
    finite_result: object
    gauge_ok: object
    breakdown: object
    iterations: object  # Per member, including an attempted failing iteration.
    loop_iterations: object  # Shared loop count; not additive case/work credit.
    residual_inf: object
    tolerance: object
    gauge_mean: object

    @property
    def converged(self):
        return (
            self.rhs_compatible
            & self.residual_ok
            & self.finite_result
            & self.gauge_ok
            & ~self.breakdown
        )

    @property
    def usable(self):
        """Numerical gates for this declared law, not native/physical admission."""
        return self.converged


class _State(NamedTuple):
    step: object
    x: object
    r: object
    p: object
    rr: object
    active: object
    iterations: object
    breakdown: object


def _zero_mean(values, xp):
    # Scaling keeps the reduction from overflowing solely because many finite
    # entries are added. The full input and any arithmetic failure are retained.
    scale = xp.max(xp.abs(values), axis=-1, keepdims=True)
    divisor = xp.where(scale > 0, scale, 1.0)
    mean = xp.mean(values / divisor, axis=-1, keepdims=True) * scale
    return values - mean


def _positive_action(values, shape, weights, xp):
    """Apply -L/operator_scale without first overflowing a physical L product."""
    plane = values.reshape((*values.shape[:-1], *shape))
    x = (plane[..., 1:] - plane[..., :-1]) * weights[0]
    y = (plane[..., 1:, :] - plane[..., :-1, :]) * weights[1]
    zx, zy = xp.zeros_like(plane[..., :1]), xp.zeros_like(plane[..., :1, :])
    x = xp.concatenate((zx, x, zx), axis=-1)
    y = xp.concatenate((zy, y, zy), axis=-2)
    action = x[..., :-1] - x[..., 1:] + y[..., :-1, :] - y[..., 1:, :]
    return action.reshape(values.shape)


def _python_loop(condition, body, state):
    while condition(state):
        state = body(state)
    return state


def solve(
    rhs,
    grid,
    *,
    max_iterations,
    rtol,
    atol=0.0,
    initial_potential=None,
    xp=np,
    iteration_loop=None,
):
    """Return a candidate plus explicit numerical acceptance gates.

    ``max_iterations`` is an explicit nonnegative int32-sized budget. Tolerances
    are finite nonnegative host scalars, in the infinity norm:
    max(abs(L phi - rhs)) <= max(atol, rtol * max(abs(rhs))).
    No retry, tolerance relaxation, constant-source repair or rank heuristic is
    applied. Nonfinite/incompatible rows do no iterative work and remain refused.
    An optional binary64 ``initial_potential`` must have exactly the rhs shape.
    Its constant offset is removed, then CG solves the correction equation using
    the ORIGINAL rhs tolerance and compatibility gate. A supplied guess is only
    numerical input, not native ownership or a qualified checkpoint. Its bytes
    are never modified. Nonfinite guesses retain failed candidates, without a
    silent restart from zero. Without a guess the original zero-start path is
    unchanged.
    A non-NumPy backend must provide a callable ``(condition, body, state)`` loop;
    the Python default is intended only for the CPU implementation.
    """
    if type(max_iterations) is not int or not 0 <= max_iterations <= 2**31 - 1:
        raise ValueError("Require an explicit nonnegative int32 iteration budget")
    for value in (rtol, atol):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Require finite nonnegative host residual tolerances")
    if iteration_loop is None:
        if xp is not np:
            raise ValueError("A non-NumPy backend requires an explicit functional loop")
        iteration_loop = _python_loop
    elif not callable(iteration_loop):
        raise ValueError("Require a callable functional iteration loop")

    rhs = stencil._field(rhs, grid, xp)
    dx, dy = grid.spacing_xy_m
    coefficients = (1 / dx**2, 1 / dy**2)
    operator_scale = max(coefficients)
    weights = tuple(value / operator_scale for value in coefficients)
    if not all(math.isfinite(value) and value > 0 for value in weights):
        raise ValueError("Metric anisotropy cannot be represented in the scaled operator")

    finite_rhs = xp.all(xp.isfinite(rhs), axis=-1)
    magnitude = xp.max(xp.abs(rhs), axis=-1)
    divisor = xp.where(finite_rhs & (magnitude > 0), magnitude, 1.0)
    scaled = xp.where(finite_rhs[..., None], rhs, 0.0) / divisor[..., None]
    compatible = finite_rhs & (
        xp.abs(xp.sum(scaled, axis=-1)) <= field.RHS_RTOL * xp.sum(xp.abs(scaled), axis=-1)
    )
    tolerance = xp.maximum(atol, rtol * magnitude)
    eligible = compatible & xp.isfinite(tolerance)
    warm_input_finite = xp.ones_like(compatible)
    if initial_potential is not None:
        initial = stencil._field(initial_potential, grid, xp)
        if initial.shape != rhs.shape:
            raise ValueError("Initial potential must have exactly the rhs shape; no broadcasting")
        base = _zero_mean(initial, xp)
        correction_rhs = rhs - stencil.apply(base, grid, xp=xp)
        finite_correction = xp.all(xp.isfinite(correction_rhs), axis=-1)
        warm_input_finite = (
            xp.all(xp.isfinite(initial), axis=-1)
            & xp.all(xp.isfinite(base), axis=-1)
            & finite_correction
        )
        magnitude = xp.max(xp.abs(correction_rhs), axis=-1)
        divisor = xp.where(finite_correction & (magnitude > 0), magnitude, 1.0)
        scaled = xp.where(finite_correction[..., None], correction_rhs, 0.0) / divisor[..., None]
        eligible = eligible & warm_input_finite
    b = xp.where(eligible[..., None], -scaled, 0.0)
    scaled_tolerance = tolerance / divisor
    r = _zero_mean(b, xp)
    active = eligible & (xp.max(xp.abs(b), axis=-1) > scaled_tolerance)
    rr = xp.sum(r * r, axis=-1)
    state = _State(
        xp.asarray(0, dtype=xp.int32),
        xp.zeros_like(rhs),
        r,
        xp.where(active[..., None], r, 0.0),
        rr,
        active,
        xp.zeros_like(magnitude, dtype=xp.int32),
        xp.zeros_like(compatible),
    )

    def condition(current):
        return (current.step < max_iterations) & xp.any(current.active)

    def body(current):
        ap = _positive_action(current.p, grid.shape, weights, xp)
        curvature = xp.sum(current.p * ap, axis=-1)
        valid = (
            current.active
            & xp.isfinite(curvature)
            & (curvature > 0)
            & xp.isfinite(current.rr)
            & (current.rr > 0)
        )
        alpha = xp.where(valid, current.rr, 0.0) / xp.where(valid, curvature, 1.0)
        x = _zero_mean(current.x + alpha[..., None] * current.p, xp)
        r = _zero_mean(current.r - alpha[..., None] * ap, xp)
        rr = xp.sum(r * r, axis=-1)
        # Recompute the actual normalized operator residual, not the recurrence.
        error = b - _positive_action(x, grid.shape, weights, xp)
        finite = (
            xp.all(xp.isfinite(x), axis=-1)
            & xp.all(xp.isfinite(r), axis=-1)
            & xp.isfinite(rr)
            & xp.all(xp.isfinite(error), axis=-1)
        )
        failed = current.active & (~valid | ~finite)
        active = current.active & ~failed & (xp.max(xp.abs(error), axis=-1) > scaled_tolerance)
        beta = xp.where(active, rr, 0.0) / xp.where(active, current.rr, 1.0)
        p = _zero_mean(r + beta[..., None] * current.p, xp)
        return _State(
            current.step + xp.asarray(1, dtype=xp.int32),
            xp.where(current.active[..., None], x, current.x),
            xp.where(current.active[..., None], r, current.r),
            xp.where(active[..., None], p, 0.0),
            xp.where(current.active, rr, current.rr),
            active,
            current.iterations + current.active.astype(xp.int32),
            current.breakdown | failed,
        )

    final = iteration_loop(condition, body, state)
    # Use the actual physical stencil for the final, unmodified-input check.
    # Overflow/underflow in this conversion is a failed numerical result, not a
    # reason to rescale a grid, relax a tolerance or hide the raw residual.
    scale = xp.where(eligible, magnitude / operator_scale, 0.0)
    candidate = final.x * scale[..., None]
    if initial_potential is not None:
        candidate = base + candidate
    potential = _zero_mean(candidate, xp)
    residual = stencil.apply(potential, grid, xp=xp) - rhs
    residual_inf = xp.max(xp.abs(residual), axis=-1)
    voltage_scale = xp.max(xp.abs(potential), axis=-1)
    scaled_voltage = potential / xp.where(voltage_scale > 0, voltage_scale, 1.0)[..., None]
    mean_voltage = xp.mean(scaled_voltage, axis=-1)
    gauge_mean = mean_voltage * voltage_scale
    gauge_ok = xp.abs(mean_voltage) <= (
        GAUGE_EPS_MULTIPLIER * np.finfo(np.float64).eps * xp.mean(xp.abs(scaled_voltage), axis=-1)
    )
    finite_result = (
        finite_rhs
        & warm_input_finite
        & xp.isfinite(tolerance)
        & xp.all(xp.isfinite(potential), axis=-1)
        & xp.all(xp.isfinite(residual), axis=-1)
        & xp.isfinite(gauge_mean)
    )
    return SolveResult(
        potential,
        residual,
        compatible,
        residual_inf <= tolerance,
        finite_result,
        gauge_ok,
        final.breakdown,
        final.iterations,
        final.step,
        residual_inf,
        tolerance,
        gauge_mean,
    )


def compile_jax_solver(grid, *, max_iterations, rtol, atol=0.0):
    """Create a reusable binary64 JAX entry for one fixed metric and policy.

    The callable accepts ``(rhs, initial_potential=None)`` and returns the same
    complete SolveResult as solve(). The iteration loop is compiled, not a Python
    per-step callback. Numerical options and array contracts are checked by the
    original solve during tracing. Different array shapes or warm/cold signatures
    can require separate compilation; reuse this callable between timesteps.

    The caller must enable JAX binary64 and JIT, and controls device placement.
    This factory changes no global precision/platform settings and performs no
    solve at construction. Returned device arrays may be asynchronous: consumers
    must synchronize before timing or accepting saved results. No GPU throughput,
    differentiation, physical tissue or checkpoint authority is implied.
    """
    if type(grid) not in (field.GridBinding, field.MetricBinding):
        raise ValueError("Require an existing rectangular metric or dense grid binding")
    import jax
    import jax.numpy as jnp

    if not jax.config.x64_enabled:
        raise ValueError("Enable JAX binary64 before constructing a rectangular solver")
    if jax.config.jax_disable_jit:
        raise ValueError("JAX JIT must be enabled for a compiled rectangular solver")

    def run(rhs, initial_potential=None):
        if not jax.config.x64_enabled:
            raise ValueError("JAX binary64 must remain enabled when tracing the solver")
        if jax.config.jax_disable_jit:
            raise ValueError("JAX JIT must remain enabled for compiled solver calls")
        return solve(
            rhs,
            grid,
            max_iterations=max_iterations,
            rtol=rtol,
            atol=atol,
            initial_potential=initial_potential,
            xp=jnp,
            iteration_loop=jax.lax.while_loop,
        )

    return jax.jit(run)
