"""Diagnose the existing Cells flux-grid gauge solve on retained input data.

This is a separate numerical convention, not a repair of the retained BETSE
inverse or a live native owner. Complete rectangular C-order grids only; no
masked/disconnected domain, value/mixed boundary or tissue-field admission.
The existing bind_grid solver is reused. Its legacy pseudoinverse is deliberately
ignored: pinv(M)*delta**2 need not equal native pinv(M/delta**2).
"""

import math
from dataclasses import replace

import numpy as np

from cells.processes import betse_geometry as geometry
from validation.betse import native_single_cell_poisson_algebra as algebra

KIND = "cells.saved_flux_compatible_gauge_diagnostic@1"
MAX_POINTS = 625
MAX_RHS = 32
RHS_RTOL = 2e-12  # Existing geometry.environment_rhs_valid convention.


def _array(value, shape, label, *, finite=True):
    if type(value) is not np.ndarray or value.dtype != np.dtype("float64") or value.shape != shape:
        raise ValueError("Require complete float64 " + label)
    result = np.array(value, copy=True, order="K")
    result.setflags(write=False)
    if finite and not np.isfinite(result).all():
        raise ValueError("Require finite " + label)
    return result


def _sum(values):
    result = math.fsum(float(v) for v in values)
    if not math.isfinite(result):
        raise ValueError("Nonfinite diagnostic reduction")
    return result


def _algebra(binding, indices, operator, inverse):
    return algebra.diagnose(
        shape=list(binding.shape),
        indices=[list(pair) for pair in indices],
        delta=binding.delta_m,
        operator=operator.ravel(order="C").tolist(),
        inverse=inverse.ravel(order="C").tolist(),
        boundary="flux",
    )


def diagnose(spec, *, indices, operator, native_inverse, rhs):
    """Keep native A/G separate; report each forcing without mean-centering it.

    Invalid/nonfinite/overflowing RHS rows get explicit refusals and no solve;
    valid rows in the same batch remain distinct probes of this one grid case.
    Residuals are observations, not a new numerical acceptance tolerance.
    """
    if type(spec) is not geometry.GridSpec:
        raise ValueError("Require a declared GridSpec, not a live or supplied native owner")
    rows = algebra._grid(spec.shape, indices)
    n = len(rows)
    if n > MAX_POINTS or tuple(rows) != tuple(np.ndindex(spec.shape)):
        raise ValueError("Require complete C-order grid mapping, at most625 points")
    if spec.boundaries != dict.fromkeys(("N", "S", "E", "W"), "flux"):
        raise ValueError("Only the complete all-flux grid is declared")
    if type(rhs) is not np.ndarray or rhs.ndim not in (1, 2):
        raise ValueError("Require a float64 RHS vector or bounded matrix of probes")
    count = 1 if rhs.ndim == 1 else rhs.shape[0]
    if not 1 <= count <= MAX_RHS or rhs.shape[-1] != n:
        raise ValueError("RHS extent exceeds the declared grid/probe bound")
    incoming = _array(rhs, rhs.shape, "RHS", finite=False)
    retained_a = _array(operator, (n, n), "retained native operator")
    retained_g = _array(native_inverse, (n, n), "retained native inverse")
    coordinates = _array(spec.coordinates_m, (n, 2), "grid coordinates")
    binding = geometry.bind_grid(replace(spec, coordinates_m=coordinates))
    if retained_a.tobytes(order="C") != binding.kernel.laplacian.tobytes(order="C"):
        raise ValueError("Retained native operator disagrees with the declared grid/stencil")
    gauge = _array(binding.kernel.compatible_inverse, (n, n), "compatible-gauge inverse")
    native_algebra = _algebra(binding, indices, retained_a, retained_g)
    compatible_algebra = _algebra(binding, indices, retained_a, gauge)
    reports, solutions = [], []
    for index, values in enumerate(incoming.reshape(count, n)):
        row = dict(
            rhs_index=index,
            status="refused",
            compatibility_rtol=RHS_RTOL,
            input_mean_subtracted=False,
            solve_attempted=False,
            numerical_acceptance=False,
        )
        solution = None
        try:
            if not np.isfinite(values).all():
                raise ValueError("Nonfinite RHS")
            total, magnitude = _sum(values), _sum(abs(float(v)) for v in values)
            row.update(rhs_sum=total, rhs_absolute_sum=magnitude, rhs_mean=total / n)
            if abs(total) > RHS_RTOL * magnitude:
                raise ValueError("Incompatible all-flux RHS; input was not projected")
            row["solve_attempted"] = True
            raw = geometry.environment_poisson(
                values, binding, convention="compatible_gauge", xp=np
            )
            # Retain complete returned bits even if the solve is nonfinite.
            solution = _array(raw, (n,), "returned solution", finite=False)
            if not np.isfinite(solution).all():
                raise ValueError("Nonfinite compatible solution")
            applied = retained_a @ solution
            if not np.isfinite(applied).all():
                raise ValueError("Nonfinite residual product")
            residual = [_sum((a, -float(b))) for a, b in zip(applied, values, strict=True)]
            row.update(
                status="diagnosed",
                solution_sum=_sum(solution),
                residual_inf=max(map(abs, residual)),
                constant_rhs_component=total / n,
                residual_against_original_rhs=True,
            )
        except (ValueError, OverflowError, FloatingPointError) as error:
            row.update(error_type=type(error).__name__, error=str(error))
        reports.append(row)
        solutions.append(solution)
    return dict(
        kind=KIND,
        grid_identity=binding.identity,
        grid_shape=binding.shape,
        indices=tuple(rows),
        native_operator=retained_a,
        native_inverse=retained_g,
        rhs=incoming,
        compatible_inverse=gauge,
        solutions=tuple(solutions),
        rhs_reports=reports,
        native_algebra=native_algebra,
        compatible_algebra=compatible_algebra,
        declared_convention="compatible_gauge",
        legacy_bind_grid_pseudoinverse_used=False,
        source_correspondence_claim=False,
        physical_or_checkpoint_admission=False,
        independent_biological_cases=0,
        numerical_acceptance=False,
        new_residual_acceptance_tolerance=None,
    )
