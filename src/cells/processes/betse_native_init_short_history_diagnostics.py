"""Observation-only amount/domain summaries; these never issue source authority.

Native clipping, reservoirs, reaction terms and grid metrics are observations,
not repaired inputs. A finite amount change is not a conservation certificate.
"""

import math
from dataclasses import dataclass


def _numbers(values):
    if type(values) not in (list, tuple):
        raise TypeError("Explicit plain numeric evidence sequence required")
    if any(type(value) not in (int, float) for value in values):
        raise TypeError("Exact plain numeric evidence values required")
    return tuple(values)


def _sum(values):
    return math.fsum(values) if all(math.isfinite(value) for value in values) else None


def _volumes(values, size):
    if type(values) in (int, float):
        return (values,) * size, "original_scalar_per_element"
    result = _numbers(values)
    if len(result) != size:
        raise ValueError("Original volume and concentration shapes differ")
    return result, "original_vector"


@dataclass(frozen=True, slots=True)
class Amounts:
    intracellular: tuple
    environmental: tuple
    combined: tuple
    ionic_charge: object
    finite_concentrations: bool
    nonnegative_concentrations: bool
    finite_positive_volumes: bool
    finite_voltage: bool
    volume_modes: tuple
    physical_or_conservation_admission: bool = False


def amounts(*, cells, environment, cell_volumes, ecm_volumes, voltage, charges, faraday):
    """Keep invalid evidence; refuse shape ambiguity without coercing a mesh."""
    if type(cells) not in (tuple, list) or type(environment) not in (tuple, list):
        raise TypeError("Explicit species rows required")
    cell_rows, env_rows = tuple(map(_numbers, cells)), tuple(map(_numbers, environment))
    charge = _numbers(charges)
    if not cell_rows or len(cell_rows) != len(env_rows) or len(cell_rows) != len(charge):
        raise ValueError("One original cell/environment/charge row per species required")
    ncell, nenv = len(cell_rows[0]), len(env_rows[0])
    if not ncell or not nenv or any(len(row) != ncell for row in cell_rows):
        raise ValueError("Nonempty consistent cell row shapes required")
    if any(len(row) != nenv for row in env_rows):
        raise ValueError("Consistent environment row shapes required")
    cv, cell_mode = _volumes(cell_volumes, ncell)
    ev, env_mode = _volumes(ecm_volumes, nenv)
    vm = _numbers(voltage)
    if type(faraday) not in (int, float):
        raise TypeError("Original numeric Faraday value required")
    inside = tuple(_sum(tuple(c * v for c, v in zip(row, cv, strict=True))) for row in cell_rows)
    outside = tuple(_sum(tuple(c * v for c, v in zip(row, ev, strict=True))) for row in env_rows)
    combined = tuple(
        _sum((a, b)) if a is not None and b is not None else None
        for a, b in zip(inside, outside, strict=True)
    )
    ionic = (
        _sum(tuple(faraday * z * amount for z, amount in zip(charge, combined, strict=True)))
        if all(value is not None for value in combined)
        else None
    )
    concentrations = tuple(value for row in (*cell_rows, *env_rows) for value in row)
    return Amounts(
        inside,
        outside,
        combined,
        ionic,
        all(math.isfinite(value) for value in concentrations),
        all(math.isfinite(value) and value >= 0 for value in concentrations),
        all(math.isfinite(value) and value > 0 for value in (*cv, *ev)),
        bool(vm) and all(math.isfinite(value) for value in vm),
        (cell_mode, env_mode),
    )


def amount_change(before, after, *, expected_exchange=None):
    """Residual needs an explicit source/boundary budget, never an assumed zero."""
    if type(before) is not Amounts or type(after) is not Amounts:
        raise TypeError("Original diagnostic records required")
    if len(before.combined) != len(after.combined):
        raise ValueError("Original species roster changed")
    delta = tuple(
        b - a if a is not None and b is not None else None
        for a, b in zip(before.combined, after.combined, strict=True)
    )
    expected = None if expected_exchange is None else _numbers(expected_exchange)
    if expected is not None and len(expected) != len(delta):
        raise ValueError("Explicit exchange budget has the wrong species roster")
    residual = (
        None
        if expected is None
        else tuple(
            _sum((change, -budget)) if change is not None else None
            for change, budget in zip(delta, expected, strict=True)
        )
    )
    return dict(
        amount_change=delta,
        expected_exchange=expected,
        residual=residual,
        external_boundary_and_reaction_budget_missing=expected is None,
        conservation_passed=None,
        physical_admission=False,
        native_negative_clipping_and_boundary_overwrites_not_repaired=True,
    )


def clock_record(*, labels, dt, sampled, completed):
    values = _numbers(labels)
    if type(dt) not in (float, int) or type(completed) is not int:
        raise TypeError("Exact source dt/count evidence required")
    if completed < 0 or completed > len(values):
        raise ValueError("Completed ordinal lies outside the original calendar")
    selected = _numbers(sampled)
    if any(label not in values for label in selected):
        raise ValueError("Sampled label absent from original calendar")
    return dict(
        labels=values,
        dt=dt,
        completed=completed,
        label_differences=tuple(b - a for a, b in zip(values, values[1:], strict=False)),
        completed_labels=values[:completed],
        completed_sampled_labels=tuple(label for label in values[:completed] if label in selected),
        source_labels_are_numerical_dt=False,
        native_calendar_unchanged=True,
    )
