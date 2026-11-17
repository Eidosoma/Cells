"""Synthetic open-system amount balance, not a calibrated biological cell."""

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.state import CellLayout, CellState, identity_arrays
from cells.observers import observe

STATE_TYPE = CellState
LAYOUT_TYPE = CellLayout
OBSERVER_ID = "amount_concentration@1"
TRACE_COLUMNS = 12
TRACE_EDGE_COLUMNS = 0
OBSERVATION_COLUMNS = 5
OBSERVATION_EDGE_COLUMNS = 0


def initial_values(spec):
    amount = np.zeros(spec.execution.capacity, dtype=np.float64)
    amount[0] = spec.model.initial_amount
    volume = np.ones_like(amount)
    volume[0] = spec.model.volume
    return (
        CellState(amount, np.zeros_like(amount), np.zeros_like(amount)),
        CellLayout(volume, *identity_arrays(spec)),
    )


def parameters(spec, layout=None):
    return np.float64(spec.model.decay_rate)


def check_steps(spec, steps, controls):
    if np.max(steps) * spec.model.decay_rate > 1.0:
        raise ConfigError("M1a requires decay_rate * largest actual step <= 1; reduce dt")


def rhs(state: CellState, source_rate, decay_rate, active) -> CellState:
    supplied = jnp.where(active, source_rate, 0.0)
    degraded = jnp.where(active, decay_rate * state.amount, 0.0)
    return CellState(supplied - degraded, supplied, degraded)


def check_values(state, spec):
    amount, supplied, degraded = state
    for name, values in zip(STATE_TYPE._fields, state, strict=True):
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise NumericalError(f"Non-finite or negative {name}; run refused without clipping")
        if np.any(values[..., 1:] != 0):
            raise NumericalError(f"Inactive slots changed in {name}")
    initial = np.zeros(spec.execution.capacity)
    initial[0] = spec.model.initial_amount
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        residual = (amount - initial) - (supplied - degraded)
        concentration = amount[..., 0] / spec.model.volume
    if not np.all(np.isfinite(residual)) or not np.all(np.isfinite(concentration)):
        raise NumericalError("Non-finite accounting residual or derived concentration")
    scale = np.maximum(1.0, np.maximum(amount, np.maximum(supplied, degraded)))
    scale = np.maximum(scale, initial)
    if np.any(np.abs(residual) > 128 * np.finfo(np.float64).eps * scale):
        raise NumericalError("Source-minus-decay accounting failed")
    return {"max_balance_error_fmol": float(np.max(np.abs(residual)))}


def observe_history(times, history, layout, requested, spec=None):
    result = observe(times, *history, np.asarray(layout.volume), requested)
    if not np.all(np.isfinite(result.concentration)):
        raise NumericalError("Non-finite derived concentration")
    return result


def summarize(history, diagnostics, spec):
    return {
        "claim_scope": "synthetic one-cell engineering fixture; not biological memory or heredity",
        "final_amount_fmol": float(history.amount[-1, 0]),
        "final_concentration_fmol_per_pL": float(history.amount[-1, 0] / spec.model.volume),
        "total_supplied_fmol": float(history.supplied[-1, 0]),
        "total_degraded_fmol": float(history.degraded[-1, 0]),
        **diagnostics,
    }
