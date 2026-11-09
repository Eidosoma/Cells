"""stationary_continuation_analysis@1 solves on the default-world cell (@1).

The pre-screen's default-world cell (validation/stationary/worlds.py) on
resolved_pump_tissue@1: ledgers never enter a rate; Newton on the law's own
derivative reaches its pump-leak state; the engine's IMEX step map has the same
fixed point (to its rounding floor) and its multipliers give the same growth
rates; refused steps can never pose as fixed points; and the fast mode holds
the composition while solving for the charge. One problem is shared so each
formulation compiles once.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.analysis import stationary as sa
from cells.core.specs import parse_spec
from validation.stationary import worlds


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def cell():
    spec = parse_spec(worlds.default_world_cell())
    pb = sa.problem(spec, mode="slow", formulation="rhs")
    solution = sa.newton(pb, pb.anchor)
    return spec, pb, solution


def numpy_rates(pb, u):
    """The model's own derivative, evaluated with numpy (no JAX tracing)."""
    state, p, control = pb.embed(jnp.asarray(u))
    state, p = sa._numpy(state), sa._numpy(p)
    control = type(control)(*(np.asarray(v) for v in control))
    with np.errstate(all="ignore"):
        derivative = pb.model.rhs(state, control, p, p.active, xp=np)
    return np.asarray(pb._rates(derivative, p)), state, p, control


def test_ledgers_do_not_enter_rates(cell):
    _, pb, solution = cell
    rates, state, p, control = numpy_rates(pb, solution.u)
    stepped = state
    with np.errstate(all="ignore"):
        for _ in range(3):
            stepped, ok = pb.model.imex_step(stepped, pb.dt, control, p, xp=np)
            assert ok
        # The same dynamical entries with the ledgers of three real steps.
        mixed = stepped._replace(**{k: getattr(state, k) for k in sa.DYNAMIC_FIELDS})
        ledgers = [k for k in mixed._fields if k not in sa.DYNAMIC_FIELDS]
        assert any(np.any(np.asarray(getattr(mixed, k)) != 0) for k in ledgers)
        derivative = pb.model.rhs(mixed, control, p, p.active, xp=np)
    np.testing.assert_array_equal(np.asarray(pb._rates(derivative, p)), rates)


def test_default_cell_slow_state(cell):
    _, pb, solution = cell
    assert solution.converged and solution.error_estimate <= sa.NEWTON_TOLERANCE
    rates, *_ = numpy_rates(pb, solution.u)
    # The model's own derivative (numpy path) vanishes to rounding (u units/s)
    # and equals the jitted residual the solver used.
    assert np.max(np.abs(rates)) < 1e-12
    np.testing.assert_allclose(pb.evaluate(solution.u)[0], rates, rtol=0, atol=1e-15)
    red = pb.reduction()
    # P is impermeant: its cell amount is the only law (a neutral direction).
    assert [law["species"] for law in red.laws] == ["P"] and red.size == pb.size - 1
    record = sa.describe(pb, solution.u)
    c = record["cell_concentration_mM"]["cell_0"]
    assert c["P"] == pytest.approx(worlds.FIXED_ANION_mM, rel=1e-15)
    # The pre-screen's pump-leak state (prescreen-03.json): -6.07 mV, K 239 mM.
    assert record["membrane_voltage_V"]["membrane_0"] == pytest.approx(-6.0737e-3, abs=1e-6)
    assert c["K"] == pytest.approx(239.211, abs=1e-3)


def test_stability_and_step_map_agree(cell):
    _, pb, solution = cell
    continuous = sa.stability(pb, solution.u)
    assert continuous["classification"] == "stable"
    assert [law["species"] for law in continuous["neutral_directions"]] == ["P"]
    times = sorted(continuous["relaxation_times_s"])
    assert len(times) == 3 and 0.2 < times[0] < 0.3 and times[-1] > 1e4
    discrete = sa.stability(pb, solution.u, formulation="step_map", steps=1)
    a = np.array(continuous["eigenvalues_per_s"])[:, 0]
    b = np.array(discrete["eigenvalues_per_s"])[:, 0]
    # log(mu)/dt matches lambda to O((lambda dt)^2) for the second-order step.
    assert np.all(np.abs(a - b) <= 4 * (a * pb.dt) ** 2 * np.abs(a) + 1e-9)
    checks = sa.consistency(pb, solution.u)
    assert checks["rhs"]["correction"] <= sa.NEWTON_TOLERANCE
    for k in ("step_map_1", "step_map_2"):
        assert checks[k]["correction"] <= checks[k]["rounding_floor"]
    # Newton on the step map itself stops at its rounding floor, near the rhs state.
    mapped = sa.newton(pb, pb.anchor, formulation="step_map", steps=2)
    assert mapped.converged
    floor = checks["step_map_2"]["rounding_floor"]
    assert np.max(np.abs(mapped.u - solution.u)) <= 2 * floor


def test_refused_steps_are_not_fixed_points(cell):
    _, pb, solution = cell

    class Refusing:
        def __getattr__(self, name):
            return getattr(pb.model, name)

        @staticmethod
        def checked_step(state, dt, control, p, active):
            return state, jnp.asarray(False)

    refusing = sa.Problem(**{**pb.__dict__, "model": Refusing(), "_cache": {}})
    residual = refusing.step_residual(jnp.asarray(solution.u), 0.0, 1)
    assert np.all(np.isnan(np.asarray(residual)))
    assert not sa.newton(refusing, solution.u, formulation="step_map", steps=1).converged


def test_fast_mode_freezes_composition(cell):
    spec, _, _ = cell
    fast = sa.problem(spec, mode="fast")
    assert [b.kind for b in fast.blocks] == ["charge"]
    result = sa.newton(fast, fast.anchor)
    assert result.converged
    state, _, _ = fast.embed(jnp.asarray(result.u))
    np.testing.assert_array_equal(np.asarray(state.amount_increment), fast.base.amount_increment)
    rates, *_ = numpy_rates(fast, result.u)
    assert np.max(np.abs(rates)) < 1e-9  # 10 mV units per second
    voltage = sa.describe(fast, result.u)["membrane_voltage_V"]["membrane_0"]
    # The pre-screen's zero of the INIT-end I-V on its 0.05 mV grid: -23.35 mV.
    assert voltage == pytest.approx(-23.35e-3, abs=0.06e-3)
