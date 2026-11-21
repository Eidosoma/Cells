"""Compare FR-30's compiled constant-voltage law with its four-term scalar expansion."""

import itertools
import json
import math

import jax
import numpy as np

from cells.laws.junctions import junction_series_gates as series
from cells.laws.junctions import junction_voltage_relaxation as single


def parameters(kind, i):
    if kind == "threshold_relaxation":
        return single.Parameters((0.04, 0.06)[i], (0.15, 0.30)[i])
    return series.BoltzmannEyring((8.0, 0.7)[i], (60.0, 90.0)[i], (0.04, 0.06)[i],
                                  (0.2, 0.8)[i], (0.15, 0.30)[i])


def scalar(kind, p, v):
    if kind == "threshold_relaxation":
        threshold, residual = p
        shift = abs(v) - threshold
        alpha = 1.3 * math.exp(-77 * shift)
        b = 0.0013 * math.exp(140 * shift)
        beta = 1000 * b / (1 + 50 * b)
    else:
        rate, slope, midpoint, split, residual = p
        u = slope * (abs(v) - midpoint)
        alpha = rate * math.exp(-split * u)
        beta = rate * math.exp((1 - split) * u)
    return (alpha + residual * beta) / (alpha + beta), alpha + beta


def check(kinds):
    params = tuple(parameters(kind, i) for i, kind in enumerate(kinds))
    initial = (0.92, 0.72)
    residuals = (0.15, 0.30)
    times = np.array([0, 1 / 256, 1 / 32, 0.25, 1, 4])

    @jax.jit
    def trace(v, t):
        gates = series.advance_clamped(initial, v, params, t, kinds=kinds)
        return (series.conductance(gates), series.route_factor(gates, params, residuals, kinds=kinds),
                series.route_factor(gates, params, (0.0, 0.0), kinds=kinds))

    error = identity = 0.0
    for v in (-0.08, -0.04, 0, 0.04, 0.08):
        (p, k), (q, l) = [scalar(kind, par, v) for kind, par in zip(kinds, params, strict=True)]
        a, b = initial[0] - p, initial[1] - q
        plateau, fast, slow, mixed = p * q, a * q, p * b, a * b
        expected = plateau + fast * np.exp(-k * times) + slow * np.exp(-l * times)
        expected += mixed * np.exp(-(k + l) * times)
        g, ions, tracer = trace(v, times)
        x = (p + a * np.exp(-k * times) - residuals[0]) / (1 - residuals[0])
        y = (q + b * np.exp(-l * times) - residuals[1]) / (1 - residuals[1])
        for measured, target in ((g, expected), (ions, expected), (tracer, x * y)):
            error = max(error, float(np.max(np.abs(measured - target))))
        identity = max(identity, abs(plateau * mixed - fast * slow))
    assert error <= 2e-15 and identity <= 2e-16
    return dict(kinds=kinds, clamp_samples=5 * len(times), max_absolute_error=error,
                max_amplitude_identity_residual=identity)


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    print(json.dumps([check(kinds) for kinds in itertools.product(series.KINDS, repeat=2)], indent=2))
