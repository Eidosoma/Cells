from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.core.runner import NumericalError, run
from cells.core.specs import ExperimentSpec, InputChange
from cells.core.state import initialise
from cells.models.source_decay import rhs
from tests.reference import exact_amount


def test_derivative_and_padding(spec):
    spec = replace(spec, execution=replace(spec.execution, capacity=4))
    checkpoint = initialise(spec)
    derivative = rhs(checkpoint.state, 1.5, 0.4, checkpoint.layout.active)
    np.testing.assert_allclose(derivative.amount, [1.42, 0, 0, 0])
    np.testing.assert_allclose(derivative.supplied, [1.5, 0, 0, 0])
    np.testing.assert_allclose(derivative.degraded, [0.08, 0, 0, 0])
    assert checkpoint.state.amount.dtype == np.float64


def test_pulse_matches_analytic_solution(spec):
    result = run(spec)
    expected = exact_amount(spec, result.times)
    np.testing.assert_allclose(result.amount[:, 0], expected, atol=2e-8, rtol=0)
    assert 2.03 in result.times and 5.07 in result.times
    assert result.final.time == 12.0
    assert result.max_balance_error < 1e-12
    np.testing.assert_allclose(result.supplied[-1, 0], (5.07 - 2.03) * 1.5, atol=1e-14)
    assert all(value >= 0 for value in result.timings.values())


@pytest.mark.parametrize("rate,k,initial", [(0, 0.4, 1), (1, 0, 0), (0, 0, 1), (1, 0.4, 0)])
def test_constant_input_cases(spec, rate, k, initial):
    spec = replace(
        spec,
        model=replace(spec.model, decay_rate=k, initial_amount=initial),
        experiment=replace(spec.experiment, source=(InputChange(0, rate),)),
    )
    result = run(spec)
    np.testing.assert_allclose(
        result.amount[:, 0], exact_amount(spec, result.times), atol=2e-8, rtol=0
    )


def test_fourth_order_refinement(spec):
    spec = replace(
        spec,
        experiment=ExperimentSpec(2.0, (InputChange(0, 1.3),), (0.0, 2.0)),
        model=replace(spec.model, decay_rate=0.7),
    )
    errors = []
    for dt in (0.4, 0.2, 0.1):
        candidate = replace(spec, execution=replace(spec.execution, dt=dt))
        error = abs(run(candidate).amount[-1, 0] - exact_amount(candidate, [2])[0])
        errors.append(error)
    assert 14 < errors[0] / errors[1] < 20
    assert 14 < errors[1] / errors[2] < 20


def test_short_pulse_is_not_skipped(spec):
    spec = replace(
        spec,
        model=replace(spec.model, initial_amount=0, decay_rate=0),
        execution=replace(spec.execution, dt=0.2),
        experiment=ExperimentSpec(
            0.333, (InputChange(0, 0), InputChange(0.103, 1), InputChange(0.104, 0)), (0, 0.333)
        ),
    )
    result = run(spec)
    assert result.final.time == 0.333
    np.testing.assert_allclose(result.amount[-1, 0], 0.001, atol=1e-17, rtol=0)


def test_observer_frequency_does_not_change_dynamics(spec):
    sparse = replace(spec, experiment=replace(spec.experiment, observation_times=(0, 12)))
    dense = replace(
        spec, experiment=replace(spec.experiment, observation_times=tuple(np.linspace(0, 12, 1201)))
    )
    first, second = run(sparse), run(dense)
    for a, b in (
        (first.times, second.times),
        (first.amount, second.amount),
        (first.supplied, second.supplied),
        (first.degraded, second.degraded),
    ):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(
        second.observations.concentration, second.observations.amount / spec.model.volume
    )


def test_observer_interpolation_is_labelled_and_read_only(spec):
    spec = replace(spec, experiment=replace(spec.experiment, observation_times=(0.0125,)))
    result = run(spec)
    expected = np.interp(0.0125, result.times, result.amount[:, 0])
    assert result.observations.amount[0, 0] == expected
    with pytest.raises(ValueError):
        result.amount[0, 0] = 99
    result.observations.amount[0, 0] = 99  # A consumer's copy cannot alter the model.
    assert float(result.final.state.amount[0]) != 99


def test_padded_capacity_is_neutral(spec):
    single = run(spec)
    padded = run(replace(spec, execution=replace(spec.execution, capacity=8)))
    np.testing.assert_array_equal(single.amount[:, 0], padded.amount[:, 0])
    assert np.all(padded.amount[:, 1:] == 0)
    assert np.all(padded.observations.concentration[:, 1:] == 0)
    np.testing.assert_array_equal(padded.final.layout.ids, [1, -1, -1, -1, -1, -1, -1, -1])
    assert all(np.all(np.isfinite(v)) for v in padded.final.state)


def test_eager_and_jit_agree(spec):
    compiled = run(spec)
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    for a, b in zip(compiled.final.state, eager.final.state, strict=True):
        np.testing.assert_allclose(a, b, atol=2e-14, rtol=0)
    assert eager.timings["compile_or_cache_seconds"] == 0


def test_event_at_final_time_does_not_supply_material(spec):
    end_event = replace(
        spec,
        experiment=replace(spec.experiment, source=spec.experiment.source + (InputChange(12, 99),)),
    )
    original, changed = run(spec), run(end_event)
    np.testing.assert_array_equal(original.amount, changed.amount)
    assert changed.final.event_index == len(end_event.experiment.source) - 1


def test_numerical_overflow_fails_without_clipping(spec):
    spec = replace(
        spec,
        model=replace(spec.model, initial_amount=1e308, decay_rate=0),
        experiment=replace(spec.experiment, source=(InputChange(0, 1e308),)),
    )
    with pytest.raises(NumericalError, match="Non-finite"):
        run(spec)


def test_no_gpu_state_created(spec):
    result = run(spec)
    assert jax.config.jax_enable_x64
    assert all(v.device.platform == "cpu" for v in result.final.state)


def test_nonfinite_derived_state_is_refused_even_without_sampling(spec):
    spec = replace(
        spec,
        model=replace(spec.model, initial_amount=1e200, volume=1e-200),
        experiment=replace(spec.experiment, observation_times=(12,)),
    )
    with pytest.raises(NumericalError, match="derived concentration"):
        run(spec)
