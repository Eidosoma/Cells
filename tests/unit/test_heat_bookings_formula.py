"""Seam D's booked heat (docs/CORE_SEAMS_DESIGN.md §6.2): the trapezoid, written once.

On the booking probe's crossing arm (test_heat_bookings_probe.py), the channel heat each step books
is 1/2 dt (q_start + q_end) from the powers at the step's start and end states, every increment is
non-negative, and the state is the tableau run's bit for bit. A declared kind's heat field (the
planted conversion kind, declared heat and monotone and admitting the trapezoid) is booked by the
same code; a kind that admits nothing is refused.
"""

import copy
import dataclasses

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.schedule import control_values
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests.unit.test_heat_bookings import (
    CROSSED_STEPS,
    CROSSING,
    TRAPEZOID,
    _clear_compiled,
    probe_world,
)


def _steps(raw, count):
    """count checked steps of the world's model from its initial state: [(state, valid)]."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    c = control_values(spec, [0.0])
    control = type(c)(*(jnp.asarray(np.asarray(v)[0]) for v in c))
    state, p = jax.tree.map(jnp.asarray, (state, p))
    dt = jnp.asarray(spec.execution.dt)
    step = jax.jit(lambda s: model.checked_step(s, dt, control, p, p.active))
    rhs = jax.jit(lambda s: model.rhs(s, control, p, p.active))
    rows = [state]
    for _ in range(count):
        state, valid = step(state)
        assert bool(valid)
        rows.append(state)
    return spec, rows, rhs


def test_the_booked_heat_is_the_trapezoid_and_the_state_is_the_tableaus():
    count = CROSSED_STEPS  # Through the crossing at this rung (STEP0's step 22).
    booked = probe_world(CROSSING, bookings={"channels": TRAPEZOID}, steps=count)
    spec, rows, rhs = _steps(booked, count)
    _, plain, _ = _steps(probe_world(CROSSING, steps=count), count)
    dt = spec.execution.dt
    for start, end in zip(rows, rows[1:], strict=False):
        booked = np.asarray(end.channel_dissipated_energy_pJ - start.channel_dissipated_energy_pJ)
        q0 = np.asarray(rhs(start).channel_dissipated_energy_pJ)
        q1 = np.asarray(rhs(end).channel_dissipated_energy_pJ)
        np.testing.assert_allclose(booked, 0.5 * dt * (q0 + q1), rtol=1e-9, atol=1e-24)
        assert np.all(booked >= 0)
    for a, b in zip(rows, plain, strict=True):  # Only the heat fields' quadrature changes.
        for name in a._fields:
            if name != "channel_dissipated_energy_pJ":
                np.testing.assert_array_equal(
                    np.asarray(getattr(a, name)), np.asarray(getattr(b, name))
                )


# ------------------------------------------------------------------ a kind's routes, by its ID


def _booked_conversion():
    """tests.conversion@1 with its heat declared heat and monotone, admitting the trapezoid."""
    base = kf.conversion()
    return dataclasses.replace(
        base,
        energy_roles={"conversion_heat_pJ": kind_registry.EnergyRole("heat", True)},
        heat_bookings=(TRAPEZOID,),
    )


def _conversion_world(bookings=None):
    from tests.unit.test_kind_stored_rate import world

    raw = copy.deepcopy(world())
    if bookings is not None:
        raw["model"][spec3.HEAT_BOOKINGS_KEY] = dict(bookings)
    return raw


def test_a_kinds_declared_heat_is_booked_by_the_same_trapezoid():
    _clear_compiled()
    try:
        with kind_registry.scope(kf.registry(_booked_conversion())):
            spec, rows, rhs = _steps(_conversion_world({kf.CONVERSION_ID: TRAPEZOID}), 3)
            structure = surface_pump_v3.structure(spec.model)
            assert structure.heat_bookings == ((kf.CONVERSION_ID, TRAPEZOID),)
            assert surface_pump_v3.trapezoid_fields(structure) == ("conversion_heat_pJ",)
            assert "conversion_heat_pJ" in surface_pump_v3.dissipation_fields(structure)
            dt = spec.execution.dt
            for start, end in zip(rows, rows[1:], strict=False):
                booked = np.asarray(end.conversion_heat_pJ - start.conversion_heat_pJ)
                q0 = np.asarray(rhs(start).conversion_heat_pJ)
                q1 = np.asarray(rhs(end).conversion_heat_pJ)
                np.testing.assert_allclose(booked, 0.5 * dt * (q0 + q1), rtol=1e-9, atol=1e-24)
        with kind_registry.scope(kf.registry(kf.conversion())):  # It admits nothing by default.
            with pytest.raises(ConfigError, match="admits no heat booking"):
                parse_spec(_conversion_world({kf.CONVERSION_ID: TRAPEZOID}))
    finally:
        _clear_compiled()
