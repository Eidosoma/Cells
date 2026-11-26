"""Seam D's booked heat (docs/CORE_SEAMS_DESIGN.md §6.2): the trapezoid, written once.

On the booking probe's crossing arm (test_heat_bookings_probe.py), the channel heat each step books
is 1/2 dt (q_start + q_end) from the powers at the step's start and end states, every increment is
non-negative, and the state is the tableau run's bit for bit. A declared kind's heat field (the
planted conversion kind, declared heat and monotone and admitting the trapezoid) is booked by the
same code; a kind that admits nothing is refused.

The faces' exact booking (cells.heat.exact_free_energy_heat@1, D280; CORE_SEAMS_DESIGN §6.5), on the trace
start that the tableau's face heat refuses (SECRETED_SPECIES_TRANSPORT_DESIGN §11.4): the default
refuses its energy ledger at row 1, the exact booking closes it to rounding at every row, and the
state is the default's bit for bit, at the trace and at 0.1 mM; a share planted below its floor
refuses the step. Host NumPy steps of @3 (no compile), under a second for these rows on one core:
the booking's claims at the step the engine runs, which the compiled runner shares.
"""

import copy
import dataclasses

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.schedule import control_values
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests.unit.test_heat_bookings import (
    CROSSED_STEPS,
    CROSSING,
    EXACT,
    TRAPEZOID,
    _clear_compiled,
    face_world,
    probe_world,
)
from validation.tissue import secreted_species_fixtures as sfx


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
    """tests.kind.conversion@1 with its heat declared heat and monotone, admitting the trapezoid."""
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


# ------------------------------------------------------------------ the faces' exact booking (D280)


def _host_steps(raw, count):
    """count steps of @3 on the host (NumPy), from the world's initial state: (spec, model, rows,
    p), each step valid."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    c = control_values(spec, [0.0])
    control = type(c)(*(np.asarray(v)[0] for v in c))
    rows = [state]
    for _ in range(count):
        state, valid = model.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid)
        rows.append(state)
    return spec, model, rows, p


def _stacked(rows):
    return type(rows[0])(
        *(np.stack([np.asarray(getattr(r, k)) for r in rows]) for k in rows[0]._fields)
    )


@pytest.mark.parametrize("low_mM,tableau_passes", [(sfx.TRACE_mM, False), (0.1, True)])
def test_the_exact_face_booking_closes_the_energy_ledger_and_keeps_the_state(
    low_mM, tableau_passes
):
    count = 5
    spec, model, plain, _ = _host_steps(face_world(low_mM, steps=count), count)
    spec_x, model_x, exact, p = _host_steps(
        face_world(low_mM, {"faces": EXACT}, steps=count), count
    )
    assert surface_pump_v3.exact_faces(model_x.structure)
    assert not surface_pump_v3.exact_faces(model.structure)
    steps = np.arange(count + 1)
    if tableau_passes:
        model.check_values(_stacked(plain), spec, steps=steps)
    else:  # The tableau's face heat at the trace start (SECRETED_SPECIES §11.4).
        with pytest.raises(NumericalError, match="accounting failed: energy"):
            model.check_values(_stacked(plain), spec, steps=steps)
    model_x.check_values(_stacked(exact), spec_x, steps=steps)
    eps = np.finfo(float).eps
    for row in exact[1:]:  # The energy ledger to rounding: the release is the ledger's own term.
        flows = float(np.abs(np.asarray(row.face_dissipated_energy_pJ)).sum())
        assert flows > 0 and abs(float(model_x.balances(row, p)["energy"])) <= 64 * eps * flows
    heat = np.asarray(_stacked(exact).face_dissipated_energy_pJ)
    assert np.all(np.diff(heat, axis=0) > 0)
    for a, b in zip(plain, exact, strict=True):  # Only the face heat's booking changes.
        for name in a._fields:
            if name != "face_dissipated_energy_pJ":
                np.testing.assert_array_equal(
                    np.asarray(getattr(a, name)), np.asarray(getattr(b, name))
                )


def test_a_share_below_its_floor_refuses_the_step():
    """No clamp and no other form: an end state planted past the two nodes' swap books a negative
    share and is refused; one short of equilibrium books a positive heat."""
    spec, _, (start,), p = _host_steps(face_world(0.5, {"faces": EXACT}, steps=1), 0)
    s = list(spec.model.species_ids).index(sfx.SPECIES)
    n1, n2 = (
        [o.id for o in spec.model.extracellular].index("n1"),
        [o.id for o in spec.model.extracellular].index("n2"),
    )
    for moved, booked in ((0.2, True), (0.6, False)):  # fmol: 0.25 reaches 0.75 mM each, 0.5 swaps.
        increment = np.array(start.extracellular_amount_increment)
        increment[s, n1] -= moved
        increment[s, n2] += moved
        transferred = np.array(start.face_transferred)
        transferred[s, 0] += moved
        end = start._replace(extracellular_amount_increment=increment, face_transferred=transferred)
        heat, ok = surface_pump_v3.exact_face_heat(start, end, p, xp=np)
        assert bool(ok) is booked and (float(np.asarray(heat).sum()) > 0) is booked
