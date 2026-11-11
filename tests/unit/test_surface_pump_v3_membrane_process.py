"""resolved_pump_tissue@3's opt-in membrane-process hook (for composing models).

Default off: without a process the step, readouts and explicit rates are the
unchanged code (the existing @3 tests). With a process that returns zero flux
and zero heat, the step reproduces the plain step (bitwise uncompiled), with
and without the trapezoid junction-heat booking. With a constant electroneutral
K/M flux the step returns the tableau-applied transfer dt x flux and the
trapezoid heat dt (q_start + q_end)/2, the amounts move by the transfer, and
readouts' derivative and dissipation include the process. An invalid process
refuses the step and leaves the state unchanged.
"""

import copy

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.core.surface_pump_v3_spec import Control, control_values
from cells.models import surface_pump_v3 as model
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from validation.stationary import worlds
from validation.tissue import surface_pump_v3_fixtures as fixtures


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, Control(*(v[0] for v in controls))


def sheet(junction_heat=False):
    cells, edges = worlds.hexagon(1)
    states = [fixtures.HEREDITY_STATES["D" if worlds.ring(c) == 0 else "H"][:4] for c in cells]
    raw = worlds.e07_sheet_definition(states, edges, dt=1e-3, end_time=0.01)
    raw["execution"]["solver"] = imex.ARS222_ID
    if junction_heat:
        raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    return copy.deepcopy(raw)


def zero_process(ci, co, volume, voltage, *, xp):
    return model.MembraneProcess(xp.zeros_like(ci), xp.zeros_like(volume), xp.asarray(True))


def constant_process(rate):
    def process(ci, co, volume, voltage, *, xp):
        flux = xp.zeros_like(ci).at[1].set(rate).at[2].set(rate) if xp is jnp else None
        if flux is None:
            flux = np.zeros_like(ci)
            flux[1], flux[2] = rate, rate  # K and M outward, 1:1 (species order Na, K, M, P).
        heat = 1e-3 * rate * 1000.0 * xp.ones_like(volume) * (1 + 0 * voltage)
        return model.MembraneProcess(flux, heat, xp.asarray(True))

    return process


@pytest.mark.parametrize("junction_heat", [False, True])
def test_zero_process_reproduces_the_plain_step(junction_heat):
    _, state, p, control = initial(sheet(junction_heat))
    with jax.disable_jit():
        plain, ok = model.imex_step(state, 1e-3, control, p)
        hooked, ok2, (transfer, heat) = model.imex_step(
            state, 1e-3, control, p, membrane_process=zero_process
        )
    assert ok and ok2
    for a, b in zip(hooked, plain, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert not np.any(np.asarray(transfer)) and not np.any(np.asarray(heat))
    if junction_heat:
        assert p.junction_heat_trapezoid.shape == (1,)


def test_constant_process_books_its_transfer_and_trapezoid_heat():
    _, state, p, control = initial(sheet())
    rate, dt = 1e-5, 1e-3
    step = jax.jit(model.imex_step, static_argnames=("membrane_process",))
    plain, _ = step(state, dt, control, p)
    moved, ok, (transfer, heat) = step(
        state, dt, control, p, membrane_process=constant_process(rate)
    )
    assert ok
    active = np.asarray(p.membrane_active)
    np.testing.assert_allclose(np.asarray(transfer)[1:3, active], dt * rate, rtol=1e-12)
    assert not np.any(np.asarray(transfer)[[0, 3]])
    np.testing.assert_allclose(np.asarray(heat)[active], dt * 1e-3 * rate * 1000.0, rtol=1e-12)
    # The cells lost K and M by the transfer, to the accuracy of the response of
    # the other routes to it over one step.
    lost = np.asarray(plain.amount_increment) - np.asarray(moved.amount_increment)
    cells = np.asarray(p.membrane_cell)[active]
    np.testing.assert_allclose(lost[1:3][:, cells], dt * rate, rtol=1e-3)
    # readouts include the process in the derivative and the dissipation.
    base = model.readouts(state, control, p, xp=np)
    hooked = model.readouts(state, control, p, xp=np, membrane_process=constant_process(rate))
    np.testing.assert_allclose(
        base.derivative.amount_increment[1:3][:, cells]
        - hooked.derivative.amount_increment[1:3][:, cells],
        rate,
        rtol=1e-9,
    )
    assert hooked.field.dissipation_pJ_s - base.field.dissipation_pJ_s == pytest.approx(
        active.sum() * 1e-3 * rate * 1000.0, rel=1e-9
    )


def test_invalid_process_refuses_the_step():
    _, state, p, control = initial(sheet())

    def invalid(ci, co, volume, voltage, *, xp):
        return model.MembraneProcess(xp.zeros_like(ci), xp.zeros_like(volume), xp.asarray(False))

    step = jax.jit(model.imex_step, static_argnames=("membrane_process",))
    kept, ok, _ = step(state, 1e-3, control, p, membrane_process=invalid)
    assert not ok
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
