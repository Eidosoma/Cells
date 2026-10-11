"""Isolated, scaled miR200/Zeb/ZEB equations identified in pinned BITSEY.

Independent JAX expression of the regulatory mathematics, not a vendored copy
of BITSEY. See docs/EMT_REFERENCE.md for equations, provenance and limitations.
No ions, voltage, contacts, physical concentration conversion, or ITERATE=True.
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.state import EMTState, RegulatoryLayout, identity_arrays
from cells.observers import sample_history

STATE_TYPE = EMTState
LAYOUT_TYPE = RegulatoryLayout
OBSERVER_ID = "emt_scaled_markers@1"
TRACE_COLUMNS = 32  # Includes temporary algebraic checks; not just primary storage.
TRACE_EDGE_COLUMNS = 0
OBSERVATION_COLUMNS = 24
OBSERVATION_EDGE_COLUMNS = 0
UPSTREAM_REVISION = "b2cb370aaecbc8299f259bc4251d5396c81f19a6"


def initial_values(spec):
    values = []
    for initial in (
        spec.model.initial_mir200_total,
        spec.model.initial_zeb_mrna_total,
        spec.model.initial_zeb_protein,
    ):
        value = np.zeros(spec.execution.capacity, dtype=np.float64)
        value[0] = initial
        values.append(value)
    return EMTState(*values), RegulatoryLayout(*identity_arrays(spec))


def parameters(spec, layout=None):
    return np.float64(spec.model.snail)


def check_steps(spec, steps, controls):
    # Tested conservative contract for this isolated circuit, not for bioelectric
    # coupling and not an adaptive error guarantee for arbitrary initial states.
    if np.max(steps) > 0.25 * (1 + 8 * np.finfo(np.float64).eps):
        raise ConfigError("Isolated EMT requires largest actual step <= 0.25; reduce dt")


def complexes(mir200, zeb_mrna, *, xp=jnp):
    """Seven per-configuration complexes, before binomial multiplicities.

    p**i * q**(6-i) equals r**i/(1+r)**6 but avoids large sixth powers.
    This deliberately uses TOTAL miRNA, matching the source's simple variant.
    """
    occupied = mir200 / (40.0 + mir200)
    vacant = 40.0 / (40.0 + mir200)
    return xp.stack([zeb_mrna * occupied**i * vacant ** (6 - i) for i in range(7)], axis=-1)


def _hill(signal, threshold, power, fold):
    return fold + (1.0 - fold) / (1.0 + (signal / threshold) ** power)


def rhs(state: EMTState, unused_source, snail, active, *, xp=jnp) -> EMTState:
    mir, mrna, protein = state
    bound = complexes(mir, mrna, xp=xp)
    # Six binding sites, binomial multiplicity times translation efficiency.
    weights = xp.asarray([1.0, 3.0, 3.0, 0.4, 0.3, 0.12, 0.02])
    translation = xp.sum(bound * weights, axis=-1) / 6.0
    generation_mir = 6.0 * _hill(snail, 72.0, 2, 0.4) * _hill(protein, 100.0 / 9.0, 3, 0.1)
    generation_mrna = (
        (5.0 / 12.0) * _hill(snail, 72.0, 2, 10.0) * _hill(protein, 25.0 / 9.0, 2, 15.0)
    )
    derivative = EMTState(
        generation_mir - 0.05 * mir,
        generation_mrna - 0.5 * mrna,
        translation - 0.1 * protein,
    )
    return EMTState(*(xp.where(active, value, 0.0) for value in derivative))


def check_values(state, spec):
    for name, values in zip(STATE_TYPE._fields, state, strict=True):
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise NumericalError(f"Non-finite or negative {name}; run refused without clipping")
        if np.any(values[..., 1:] != 0):
            raise NumericalError(f"Inactive slots changed in {name}")
    bound = complexes(state.mir200_total, state.zeb_mrna_total, xp=np)
    partition = np.sum(bound * [1, 6, 15, 20, 15, 6, 1], axis=-1)
    residual = np.abs(partition - state.zeb_mrna_total)
    if not np.isfinite(bound).all() or not np.isfinite(residual).all():
        raise NumericalError("Non-finite EMT algebraic state")
    if np.any(residual > 128 * np.finfo(np.float64).eps * np.maximum(1, partition)):
        raise NumericalError("EMT mRNA complex partition identity failed")
    return {"max_complex_partition_error_scaled": float(np.max(residual))}


def labels(mir200, zeb_mrna, active):
    # Upstream comparison convention only; not a classifier of actual cancer.
    mir200, zeb_mrna = np.asarray(mir200, dtype=np.float64), np.asarray(zeb_mrna, dtype=np.float64)
    result = np.where(zeb_mrna > mir200 + 2, "M", np.where(mir200 > zeb_mrna + 2, "E", "X"))
    return np.where(active, result, "-")


@dataclass(frozen=True)
class EMTObservations:
    times: np.ndarray
    mir200_total: np.ndarray
    zeb_mrna_total: np.ndarray
    zeb_protein: np.ndarray
    mir200_free_proxy: np.ndarray
    bound_complexes: np.ndarray
    label: np.ndarray


def observe_history(times, history, layout, requested, spec=None):
    requested = np.asarray(requested, dtype=np.float64)
    sampled = EMTState(*(sample_history(times, v, requested) for v in history))
    # Refresh algebraic quantities FROM the sampled primary state. Do not
    # independently interpolate complexes or integrate them as extra state.
    bound = complexes(sampled.mir200_total, sampled.zeb_mrna_total, xp=np)
    return EMTObservations(
        requested,
        *sampled,
        sampled.mir200_total.copy(),
        bound,
        labels(sampled.mir200_total, sampled.zeb_mrna_total, np.asarray(layout.active)),
    )


def summarize(history, diagnostics, spec):
    return {
        "claim_scope": (
            "isolated source-backed regulatory equations; not a full cell or paper replication"
        ),
        "final_scaled_state": {
            name: float(value[-1, 0])
            for name, value in zip(STATE_TYPE._fields, history, strict=True)
        },
        "final_label": str(
            labels(history.mir200_total[-1, 0], history.zeb_mrna_total[-1, 0], True)
        ),
        "fixed_snail_scaled": spec.model.snail,
        "upstream_revision": UPSTREAM_REVISION,
        "binding_approximation": "total_mirna_in_mass_action; free_proxy_equals_total",
        **diagnostics,
    }
