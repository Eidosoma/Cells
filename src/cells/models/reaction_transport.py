"""Compose local reversible conversion and passive transport on shared amount state.

Two synthetic species are a property of this model, not of the graph or solver.
All contributions read the same RK stage state. No source assay or phenotype
selects behaviour. See docs/REACTION_TRANSPORT.md for the supported contract.
"""

from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import ReactionTransportLayout, ReactionTransportState
from cells.coupling.passive import ContactParameters, edge_flux, scatter_exchange
from cells.observers import sample_history
from cells.processes.reactions import reversible_rate

STATE_TYPE = ReactionTransportState
LAYOUT_TYPE = ReactionTransportLayout
OBSERVER_ID = "reaction_transport_amounts@1"
TRACE_COLUMNS = 24
TRACE_EDGE_COLUMNS = 16
OBSERVATION_COLUMNS = 12
OBSERVATION_EDGE_COLUMNS = 12
STATE_AXES = {
    "amount": ["species", "cell_slot"],
    "transferred": ["species", "edge_slot"],
    "converted": ["cell_slot"],
}


class Parameters(NamedTuple):
    contact: ContactParameters
    from_species: int
    to_species: int
    forward_rate: np.ndarray
    reverse_rate: np.ndarray


def initial_values(spec):
    model = spec.model
    size, edges = spec.execution.capacity, spec.execution.edge_capacity
    count, n_edges = len(model.cell_ids), len(model.contacts)
    amount = np.zeros((len(model.species), size), dtype=np.float64)
    amount[:, :count] = model.initial_amounts
    volume = np.ones(size, dtype=np.float64)
    volume[:count] = model.volumes
    ids = np.full(size, -1, dtype=np.int64)
    ids[:count] = model.cell_ids
    contact_ids = np.full(edges, -1, dtype=np.int64)
    senders, receivers = np.zeros(edges, dtype=np.int64), np.zeros(edges, dtype=np.int64)
    permeability = np.zeros((len(model.species), edges), dtype=np.float64)
    slots = {identity: slot for slot, identity in enumerate(model.cell_ids)}
    for index, contact in enumerate(model.contacts):
        contact_ids[index] = contact.contact_id
        senders[index] = slots[contact.from_cell_id]
        receivers[index] = slots[contact.to_cell_id]
        permeability[:, index] = contact.permeability
    forward, reverse = np.zeros(size), np.zeros(size)
    forward[:count], reverse[:count] = model.forward_rate, model.reverse_rate
    return (
        ReactionTransportState(amount, np.zeros_like(permeability), np.zeros(size)),
        ReactionTransportLayout(
            volume,
            np.arange(size) < count,
            ids,
            contact_ids,
            senders,
            receivers,
            np.arange(edges) < n_edges,
            permeability,
            forward,
            reverse,
        ),
    )


def parameters(spec, layout):
    return Parameters(
        ContactParameters(
            layout.volume,
            layout.senders,
            layout.receivers,
            layout.permeability,
            layout.contact_active,
        ),
        spec.model.species.index(spec.model.from_species),
        spec.model.species.index(spec.model.to_species),
        layout.forward_rate,
        layout.reverse_rate,
    )


def rhs(state, opening, params, active):
    # Neither process sees the other's updated state; the integrator owns staging.
    flux = edge_flux(state.amount, opening, params.contact, active)
    conversion = reversible_rate(
        state.amount[params.from_species],
        state.amount[params.to_species],
        params.forward_rate,
        params.reverse_rate,
        active,
    )
    local = jnp.zeros_like(state.amount).at[params.from_species].add(-conversion)
    local = local.at[params.to_species].add(conversion)
    exchange = scatter_exchange(
        flux, params.contact.senders, params.contact.receivers, state.amount
    )
    return ReactionTransportState(local + exchange, flux, conversion)


def check_steps(spec, steps, controls):
    initial, layout = initial_values(spec)
    params = parameters(spec, layout)
    total = np.sum(initial.amount)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        concentration_bound = total / layout.volume
    if not np.isfinite(concentration_bound).all():
        raise ConfigError("Graph concentration bound exceeds finite float64")
    # For this closed linear positive system, alpha bounds every coordinate's
    # exit rate. h*alpha <= 0.5 is conservative for both RK4 stages and endpoint.
    # Include final-time declarations in finite-value guards even if h is zero.
    for change in spec.experiment.contact:
        opening = np.zeros(spec.execution.edge_capacity)
        opening[: len(change.open_fractions)] = change.open_fractions
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            conductance = layout.permeability * opening
            loss = np.zeros_like(initial.amount)
            loss[params.from_species] = layout.forward_rate
            loss[params.to_species] = layout.reverse_rate
            np.add.at(loss, (..., layout.senders), conductance / layout.volume[layout.senders])
            np.add.at(loss, (..., layout.receivers), conductance / layout.volume[layout.receivers])
            alpha = np.max(loss)
            flux_bound = alpha * total
            # Conservative bounds for weighted RK sums and integrated ledgers.
            numerical_bounds = np.array(
                [alpha, flux_bound * 8, flux_bound * spec.experiment.end_time]
            )
            largest_step = np.max(steps[np.all(controls == opening, axis=1)], initial=0.0)
            stability = largest_step * alpha
        if not np.isfinite(numerical_bounds).all() or not np.isfinite(stability):
            raise ConfigError("Graph rate, flux, or ledger bound exceeds finite float64")
        if stability > 0.5 + 16 * np.finfo(np.float64).eps:
            raise ConfigError("Reaction/transport requires actual step * maximum exit rate <= 0.5")


def check_values(state, spec):
    amount, transferred, converted = state
    if not all(np.isfinite(v).all() for v in state) or np.any(amount < 0):
        raise NumericalError("Non-finite graph state or negative amount; refused without clipping")
    count, edges = len(spec.model.cell_ids), len(spec.model.contacts)
    if (
        np.any(amount[..., count:] != 0)
        or np.any(transferred[..., edges:] != 0)
        or np.any(converted[..., count:] != 0)
    ):
        raise NumericalError("Inactive species/cell/contact storage changed")
    initial, layout = initial_values(spec)
    params = parameters(spec, layout)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        received = np.zeros_like(amount)
        np.add.at(received, (..., layout.senders), -transferred)
        np.add.at(received, (..., layout.receivers), transferred)
        reacted = np.zeros_like(amount)
        reacted[..., params.from_species, :] = -converted
        reacted[..., params.to_species, :] = converted
        residual = amount - initial.amount - received - reacted
        total_initial = np.sum(initial.amount)
        balance = amount.sum(axis=(-2, -1)) - total_initial
        concentration = amount / layout.volume
        scale = np.maximum(1.0, np.abs(initial.amount) + np.abs(received) + np.abs(reacted))
    if not all(np.isfinite(v).all() for v in (balance, concentration, residual, scale)):
        raise NumericalError("Non-finite graph concentration or accounting")
    eps = np.finfo(np.float64).eps
    if np.any(np.abs(balance) > 512 * eps * max(1.0, total_initial)):
        raise NumericalError("Closed-world total amount conservation failed")
    if np.any(np.abs(residual) > 1024 * eps * scale):
        raise NumericalError("Per-species/cell reaction and contact accounting failed")
    return {
        "max_balance_error_fmol": float(np.max(np.abs(balance))),
        "max_process_accounting_error_fmol": float(np.max(np.abs(residual))),
    }


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount: np.ndarray
    concentration: np.ndarray
    transferred: np.ndarray
    converted: np.ndarray
    open_fraction: np.ndarray
    contact_flux: np.ndarray
    conversion_rate: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    amount, transferred, converted = (sample_history(times, field, requested) for field in history)
    opening = control_values(spec, requested)
    contact = ContactParameters(*(np.asarray(v) for v in parameters(spec, layout).contact))
    flux = edge_flux(amount, opening[:, None, :], contact, np.asarray(layout.active), xp=np)
    first = spec.model.species.index(spec.model.from_species)
    second = spec.model.species.index(spec.model.to_species)
    reaction = amount[:, first] * np.asarray(layout.forward_rate) - amount[:, second] * np.asarray(
        layout.reverse_rate
    )
    if not np.isfinite(flux).all() or not np.isfinite(reaction).all():
        raise NumericalError("Non-finite observed process rate")
    return Observations(
        requested, amount, amount / contact.volume, transferred, converted, opening, flux, reaction
    )


def summarize(history, diagnostics, spec):
    count, edges = len(spec.model.cell_ids), len(spec.model.contacts)
    amount = history.amount[-1, :, :count]
    return {
        "claim_scope": (
            "synthetic reaction/transport composition; not a bioelectric or heredity model"
        ),
        "species": list(spec.model.species),
        "state_axes": STATE_AXES,
        "physical_contacts": edges,
        "edge_capacity": spec.execution.edge_capacity,
        "contact_ids": [c.contact_id for c in spec.model.contacts],
        "final_amounts_fmol": amount.tolist(),
        "final_concentrations_fmol_per_pL": (amount / spec.model.volumes).tolist(),
        "final_species_totals_fmol": amount.sum(axis=-1).tolist(),
        "final_total_amount_fmol": float(amount.sum()),
        "final_signed_transferred_fmol": history.transferred[-1, :, :edges].tolist(),
        "final_signed_converted_fmol": history.converted[-1, :count].tolist(),
        "final_open_fractions": list(spec.experiment.contact[-1].open_fractions),
        **diagnostics,
    }
