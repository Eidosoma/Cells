"""The scalar runner's numerics on a small live world, against a closed form.

Two cells exchange two species through one contact on a schedule, without reactions
(tests/reference.py's world, from tests/conftest.py's), so the events, the order of the method, the
observers, the padding and the refusals are the runner's own.
"""

from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.definitions.specs import GraphContactChange
from cells.execution.runner import NumericalError, run
from cells.execution.state import initialise
from cells.models import reaction_transport as model
from tests.reference import exact_exchange


@pytest.fixture
def exchange(spec):
    """The shared world without its reactions."""
    return replace(
        spec, model=replace(spec.model, forward_rate=(0.0, 0.0), reverse_rate=(0.0, 0.0))
    )


def open_from_zero(spec, *, open_fraction=1.0, end=None, **model_changes):
    """One constant opening over the horizon (to `end` with its two rows, or the spec's own)."""
    experiment = replace(spec.experiment, contact=(GraphContactChange(0.0, (open_fraction,)),))
    if end is not None:
        experiment = replace(experiment, end_time=end, observation_times=(0.0, end))
    return replace(spec, experiment=experiment, model=replace(spec.model, **model_changes))


def assert_exact(result, *, atol=2e-8):
    amount, moved = exact_exchange(result.spec, result.times)
    np.testing.assert_allclose(result.amount, amount, atol=atol, rtol=0)
    np.testing.assert_allclose(result.history.transferred[..., 0], moved, atol=atol, rtol=0)


def test_derivative_and_padding(spec):
    """Every term by hand at the initial state, in a padded layout: A moves 0.4 (8/1 - 0/3), B
    0.1 (0/1 - 2/3), and A becomes B at 0.2 x 8 in the first cell and B A at 0.03 x 2 in the
    second."""
    spec = replace(spec, execution=replace(spec.execution, capacity=4, edge_capacity=3))
    checkpoint = initialise(spec)
    parameters = model.parameters(spec, checkpoint.layout)
    derivative = model.rhs(
        checkpoint.state, np.array([1.0, 0, 0]), parameters, checkpoint.layout.active
    )
    moved, converted = np.array([3.2, -0.2 / 3]), np.array([1.6, -0.06])
    amount = np.stack([-moved, moved], axis=-1) + [-converted, converted]
    for actual, expected in (
        (derivative.transferred, [[m, 0, 0] for m in moved]),
        (derivative.converted, [*converted, 0, 0]),
        (derivative.amount, [[*row, 0, 0] for row in amount]),
    ):
        np.testing.assert_allclose(actual, expected, atol=1e-15, rtol=0)
    assert checkpoint.state.amount.dtype == np.float64


def test_pulse_matches_analytic_solution(exchange):
    result = run(exchange)
    assert_exact(result)
    assert 2.03 in result.times and 5.07 in result.times
    assert result.final.time == 12.0
    assert result.max_balance_error < 1e-12
    shut = (result.times >= 2.03) & (result.times <= 5.07)  # Nothing moves while it is closed.
    for values in (result.amount, result.history.transferred):
        np.testing.assert_array_equal(
            values[shut], np.broadcast_to(values[shut][0], values[shut].shape)
        )
    assert all(value >= 0 for value in result.timings.values())


@pytest.mark.parametrize(
    "open_fraction,permeability,amounts",
    [
        (0.0, 0.4, ((8, 0), (0, 2))),  # A closed contact.
        (1.0, 0.0, ((8, 0), (0, 2))),  # An impermeable one.
        (1.0, 0.4, ((3, 9), (1, 3))),  # At equilibrium: equal concentrations.
        (1.0, 0.4, ((0, 8), (2, 0))),  # From the receiver to the sender.
    ],
)
def test_constant_input_cases(exchange, open_fraction, permeability, amounts):
    (contact,) = exchange.model.contacts
    contact = replace(contact, permeability=(permeability, permeability))
    result = run(
        open_from_zero(
            exchange, open_fraction=open_fraction, initial_amounts=amounts, contacts=(contact,)
        )
    )
    assert_exact(result)
    if not open_fraction * permeability:
        np.testing.assert_array_equal(
            result.amount, np.broadcast_to(result.amount[0], result.amount.shape)
        )


def test_fourth_order_refinement(exchange):
    spec = open_from_zero(exchange, end=2.0)
    errors = []
    for dt in (0.4, 0.2, 0.1):
        candidate = run(replace(spec, execution=replace(spec.execution, dt=dt)))
        errors.append(np.abs(candidate.amount[-1] - exact_exchange(spec, [2.0])[0][0])[0, 0])
    assert 14 < errors[0] / errors[1] < 20
    assert 14 < errors[1] / errors[2] < 20


def test_short_pulse_is_not_skipped(exchange):
    pulse = (
        GraphContactChange(0.0, (0.0,)),
        GraphContactChange(0.103, (1.0,)),
        GraphContactChange(0.104, (0.0,)),
    )
    spec = replace(
        exchange,
        execution=replace(exchange.execution, dt=0.2),
        experiment=replace(
            exchange.experiment, end_time=0.333, contact=pulse, observation_times=(0, 0.333)
        ),
    )
    result = run(spec)
    assert result.final.time == 0.333
    _, moved = exact_exchange(spec, [0.333])
    assert moved[0, 0] > 3e-3  # 3.2 fmol/s for a millisecond, in a step of 0.2 s.
    np.testing.assert_allclose(result.history.transferred[-1, :, 0], moved[0], atol=1e-17, rtol=0)


def test_observer_frequency_does_not_change_dynamics(spec):
    sparse = replace(spec, experiment=replace(spec.experiment, observation_times=(0, 12)))
    dense = replace(
        spec, experiment=replace(spec.experiment, observation_times=tuple(np.linspace(0, 12, 1201)))
    )
    first, second = run(sparse), run(dense)
    for a, b in zip((first.times, *first.history), (second.times, *second.history), strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(
        second.observations.concentration, second.observations.amount / spec.model.volumes
    )


def test_observer_interpolation_is_labelled_and_read_only(spec):
    spec = replace(spec, experiment=replace(spec.experiment, observation_times=(0.0125,)))
    result = run(spec)
    expected = np.interp(0.0125, result.times, result.amount[:, 0, 0])
    assert result.observations.amount[0, 0, 0] == expected
    with pytest.raises(ValueError):
        result.amount[0, 0, 0] = 99
    result.observations.amount[0, 0, 0] = 99  # A consumer's copy cannot alter the model.
    assert float(result.final.state.amount[0, 0]) != 99


def test_padded_capacity_is_neutral(spec):
    """To the 1e-13 fmol of test_reaction_transport.py's padding row: a program of another shape
    rounds its sums in another order. Inactive storage stays exactly zero."""
    single = run(spec)
    padded = run(replace(spec, execution=replace(spec.execution, capacity=8, edge_capacity=3)))
    for name, count in (("amount", 2), ("transferred", 1), ("converted", 2)):
        values, plain = getattr(padded.history, name), getattr(single.history, name)
        np.testing.assert_allclose(plain, values[..., :count], atol=1e-13, rtol=0)
        assert np.all(values[..., count:] == 0)
    assert np.all(padded.observations.concentration[..., 2:] == 0)
    np.testing.assert_array_equal(padded.final.layout.ids, [101, 202, *[-1] * 6])
    np.testing.assert_array_equal(padded.final.layout.contact_ids, [7, -1, -1])
    assert all(np.all(np.isfinite(v)) for v in padded.final.state)


def test_eager_and_jit_agree(spec):
    spec = open_from_zero(spec, end=0.5)  # Ten steps: an eager one takes about 0.1 s.
    compiled = run(spec)
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    for a, b in zip(compiled.final.state, eager.final.state, strict=True):
        np.testing.assert_allclose(a, b, atol=2e-14, rtol=0)
    assert eager.timings["compile_or_cache_seconds"] == 0


def test_event_at_final_time_does_not_supply_material(spec):
    changes = (*spec.experiment.contact, GraphContactChange(12.0, (0.0,)))
    end_event = replace(spec, experiment=replace(spec.experiment, contact=changes))
    original, changed = run(spec), run(end_event)
    for a, b in zip(original.history, changed.history, strict=True):
        np.testing.assert_array_equal(a, b)
    assert changed.final.event_index == len(changes) - 1


def test_numerical_overflow_fails_without_clipping(spec, monkeypatch):
    original = model.rhs

    def overflowing(*args):
        slope = original(*args)
        return slope._replace(amount=slope.amount * 1e308 * 1e308)

    monkeypatch.setattr(model, "rhs", overflowing)
    with pytest.raises(NumericalError, match="Non-finite"):
        run(spec)


def test_no_gpu_state_created(spec):
    result = run(spec)
    assert jax.config.jax_enable_x64
    assert all(v.device.platform == "cpu" for v in result.final.state)
