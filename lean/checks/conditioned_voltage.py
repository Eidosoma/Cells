"""Check two-dose voltage extrapolation on synthetic membranes and the frozen BIO-002 readings."""

import json
from dataclasses import replace
from itertools import product

import jax
import numpy as np
from mixed_membrane import CI, IONS, F, Z, reversal, world

from cells.execution.runner import run
from scripts import evaluate_conditioned_voltage as protocol
from tests import reference_conditioned_voltage as ref


def membrane_series(weights):
    temperature = 298.15
    first, second, target = 10, 40, 70

    def outside(k):
        return (150 - k, k, 150)

    def reading(k):
        _, root_V = reversal(weights, CI, outside(k), temperature)
        return ref.Reading(f"synthetic-K{k}", k, 1000 * root_V, 0.0)

    r1, r2 = reading(first), reading(second)
    fitted = ref.fit_two_points(r1, r2, temperature, (first, target))
    prediction = fitted.voltage_at(target)
    r3 = reading(target)
    assert abs(prediction - r3.voltage_mV) < 1e-10
    change = r2.voltage_mV - r1.voltage_mV
    if weights[0] == weights[1]:
        assert abs(change) < 1e-10
    else:
        assert change * (weights[1] - weights[0]) > 0

    # Start the held-out world at the predicted reversal and observe all three ionic currents.
    spec = world(weights, prediction / 1000, CI, outside(target), temperature)
    result = run(spec)
    rows = [spec.model.species_ids.index(s) for s in IONS]
    current = Z * F * 1e-15 * np.asarray(result.observations.membrane_flux_fmol_s)[0, rows, 0]
    relative = abs(current.sum()) / np.abs(current).sum()
    assert current.min() < 0 < current.max() and relative < 2e-12
    return dict(
        relative_permeabilities=weights,
        fit_mV=[r1.voltage_mV, r2.voltage_mV],
        prediction_mV=prediction,
        third_engine_root_mV=r3.voltage_mV,
        checked_steps=len(result.times) - 1,
        initial_outward_currents_pA=(current * 1e12).tolist(),
        net_current_relative_to_sum_absolute=float(relative),
    )


def reading_box():
    plan, readings, _ = protocol.load_inputs()
    first, second = [readings[k] for k in plan["split"]["fit"]]
    measurement = readings[plan["split"]["evaluation"][0]]
    temperature = plan["boundary"]["temperature_K"]
    domain = tuple(plan["model"]["dose_domain_mM"])
    result = ref.forecast(first, second, measurement.potassium_mM, temperature, domain)
    check = protocol.numerical_crosscheck(
        result,
        first,
        second,
        temperature,
        plan["comparison"]["numerical_crosscheck_absolute_tolerance_mV"],
    )
    low, high = result["prediction_reading_box_mV"]
    delta_low, delta_high = result["change_reading_box_mV"]
    xs, ys = [
        np.linspace(r.voltage_mV - r.reading_bound_mV, r.voltage_mV + r.reading_bound_mV, 9)
        for r in (first, second)
    ]
    for x, y in product(xs, ys):
        curve = ref.fit_two_points(
            replace(first, voltage_mV=float(x)),
            replace(second, voltage_mV=float(y)),
            temperature,
            domain,
        )
        v = curve.voltage_at(measurement.potassium_mM)
        assert low <= v <= high and delta_low <= v - x <= delta_high
    # The theorem specifies which original readings supply both voltage and change extrema.
    corners = {tuple(c["fit_readings_mV"]): c for c in result["reading_corners"]}
    lower, upper = corners[xs[-1], ys[0]], corners[xs[0], ys[-1]]
    assert [c["prediction_mV"] for c in (lower, upper)] == [low, high]
    assert [c["change_from_first_fit_mV"] for c in (lower, upper)] == [delta_low, delta_high]
    scored = ref.compare_prediction(result, measurement)
    return dict(
        central_prediction_mV=result["prediction_mV"],
        prediction_reading_box_mV=[low, high],
        change_reading_box_mV=[delta_low, delta_high],
        residual_reading_box_mV=scored["signed_error_reading_box_mV"],
        checked_reading_pairs=len(xs) * len(ys),
        independent_checks=check["scalar_comparisons"],
        max_decimal_difference_mV=check["maximum_absolute_error_mV"],
    )


if __name__ == "__main__":
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    profiles = [(0.125, 1.0, 0.25), (1.0, 1.0, 0.25), (1.0, 0.25, 0.25)]
    print(
        json.dumps(
            dict(reading_box=reading_box(), membranes=[membrane_series(w) for w in profiles]),
            indent=2,
            allow_nan=False,
        )
    )
