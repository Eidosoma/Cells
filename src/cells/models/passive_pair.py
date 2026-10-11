"""Two fixed-volume cells, one passive contact, no production or degradation.

An analytical engineering fixture, not BITSEY's selective bioelectric coupling.
See docs/PASSIVE_CONTACT.md for units, event semantics, and acceptance scope.
"""

from dataclasses import dataclass

import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import ExchangeLayout, ExchangeState
from cells.coupling.passive import ContactParameters, edge_flux, scatter_exchange
from cells.observers import sample_history

STATE_TYPE = ExchangeState
LAYOUT_TYPE = ExchangeLayout
OBSERVER_ID = "passive_pair_amount_contact@1"
TRACE_COLUMNS = 12
TRACE_EDGE_COLUMNS = 8
OBSERVATION_COLUMNS = 6
OBSERVATION_EDGE_COLUMNS = 10


def initial_values(spec):
    size, edges = spec.execution.capacity, spec.execution.edge_capacity
    model = spec.model
    amount = np.zeros(size, dtype=np.float64)
    amount[:2] = model.initial_amounts
    volume = np.ones(size, dtype=np.float64)
    volume[:2] = model.volumes
    active = np.arange(size) < 2
    ids = np.full(size, -1, dtype=np.int64)
    ids[:2] = model.cell_ids
    contact_ids = np.full(edges, -1, dtype=np.int64)
    contact_ids[0] = model.contact_id
    senders = np.zeros(edges, dtype=np.int64)
    receivers = np.zeros(edges, dtype=np.int64)
    senders[0] = model.cell_ids.index(model.from_cell_id)
    receivers[0] = model.cell_ids.index(model.to_cell_id)
    contact_active = np.arange(edges) < 1
    permeability = np.zeros(edges, dtype=np.float64)
    permeability[0] = model.permeability
    return (
        ExchangeState(amount, np.zeros(edges, dtype=np.float64)),
        ExchangeLayout(
            volume, active, ids, contact_ids, senders, receivers, contact_active, permeability
        ),
    )


def parameters(spec, layout):
    return ContactParameters(
        layout.volume, layout.senders, layout.receivers, layout.permeability, layout.contact_active
    )


def check_steps(spec, steps, controls):
    va, vb = spec.model.volumes
    g = spec.model.permeability
    # Bound derived initial concentrations and every declared instantaneous
    # flux, including a final-time change that does not integrate any material.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        concentration = np.array(spec.model.initial_amounts) / np.array([va, vb])
        maximum_control = max(p.open_fraction for p in spec.experiment.contact)
        maximum_flux = (g * maximum_control) * abs(concentration[0] - concentration[1])
        rate = g * controls / va + g * controls / vb
        stiffness_steps = steps * rate
    if not np.isfinite(concentration).all() or not np.isfinite(maximum_flux):
        raise ConfigError("Pair derived concentration/flux bound exceeds finite float64")
    if not np.isfinite(rate).all() or not np.isfinite(stiffness_steps).all():
        raise ConfigError("Pair exchange rate/step exceeds finite float64")
    if np.any(stiffness_steps > 1 + 16 * np.finfo(np.float64).eps):
        raise ConfigError(
            "Passive pair requires step * permeability * open_fraction * (1/Va + 1/Vb) <= 1"
        )


def rhs(state, open_fraction, contact, active):
    flux = edge_flux(state.amount, open_fraction, contact, active)
    return ExchangeState(
        scatter_exchange(flux, contact.senders, contact.receivers, state.amount), flux
    )


def check_values(state, spec):
    amount, transferred = state
    if not np.isfinite(amount).all() or np.any(amount < 0):
        raise NumericalError("Non-finite or negative amount; pair run refused without clipping")
    if not np.isfinite(transferred).all():
        raise NumericalError("Non-finite signed contact transfer")
    if np.any(amount[..., 2:] != 0) or np.any(transferred[..., 1:] != 0):
        raise NumericalError("Inactive cell or contact slots changed")
    initial, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        concentration = amount / layout.volume
        total_initial = sum(spec.model.initial_amounts)
        balance = np.sum(amount, axis=-1) - total_initial
        received = np.zeros_like(amount)
        received[..., layout.senders[0]] -= transferred[..., 0]
        received[..., layout.receivers[0]] += transferred[..., 0]
        accounting = (amount - initial.amount) - received
    if not all(np.isfinite(v).all() for v in (concentration, balance, accounting)):
        raise NumericalError("Non-finite pair concentration or accounting residual")
    tolerance = 256 * np.finfo(np.float64).eps * max(1.0, total_initial)
    if np.any(np.abs(balance) > tolerance):
        raise NumericalError("Pair total amount conservation failed")
    if np.any(np.abs(accounting) > tolerance):
        raise NumericalError("Pair per-cell/contact transfer accounting failed")
    return {
        "max_balance_error_fmol": float(np.max(np.abs(balance))),
        "max_exchange_accounting_error_fmol": float(np.max(np.abs(accounting))),
    }


@dataclass(frozen=True)
class ExchangeObservations:
    times: np.ndarray
    amount: np.ndarray
    concentration: np.ndarray
    transferred: np.ndarray
    open_fraction: np.ndarray
    contact_flux: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    amount = sample_history(times, history.amount, requested)
    transferred = sample_history(times, history.transferred, requested)
    opening = control_values(spec, requested)[:, None] * np.asarray(layout.contact_active)
    contact = ContactParameters(*(np.asarray(v) for v in parameters(spec, layout)))
    flux = edge_flux(amount, opening, contact, np.asarray(layout.active), xp=np)
    if not np.isfinite(flux).all():
        raise NumericalError("Non-finite observed contact flux")
    return ExchangeObservations(
        requested, amount, amount / contact.volume, transferred, opening, flux
    )


def summarize(history, diagnostics, spec):
    amounts = history.amount[-1, :2]
    return {
        "claim_scope": (
            "synthetic passive two-cell transport; not voltage-selective or regulatory coupling"
        ),
        "physical_contacts": 1,
        "edge_capacity": spec.execution.edge_capacity,
        "contact_id": spec.model.contact_id,
        "from_cell_id": spec.model.from_cell_id,
        "to_cell_id": spec.model.to_cell_id,
        "permeability_pL_per_s": spec.model.permeability,
        "final_amounts_fmol": amounts.tolist(),
        "final_concentrations_fmol_per_pL": (amounts / spec.model.volumes).tolist(),
        "final_total_amount_fmol": float(np.sum(amounts)),
        "final_signed_transferred_fmol": float(history.transferred[-1, 0]),
        "final_open_fraction": spec.experiment.contact[-1].open_fraction,
        **diagnostics,
    }
