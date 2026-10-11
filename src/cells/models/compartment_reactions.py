"""Stage-consistent closed chemistry; finite calcium buffering is one input example."""

from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import R
from cells.processes.mass_action import reversible_flux

OBSERVER_ID = "closed_compartment_chemistry@1"
OBSERVATION_SAMPLING = "read_only_control_local_cubic_hermite_chemical_enclosed@1"
STAGE_DOMAIN_ID = "strictly_positive_closed_chemical_inventory@1"
BATCH_CAPACITIES = ("reaction_capacity",)
ENERGY_ATOL_PJ = 1e-9
ROUND_ATOL = 4096 * np.finfo(np.float64).eps
STATE_AXES = {
    "amount_increment": ["species", "compartment_slot"],
    "reaction_extent": ["reaction_slot"],
    "dissipated_energy_pJ": ["reaction_slot"],
}


class State(NamedTuple):
    amount_increment: object
    reaction_extent: object
    dissipated_energy_pJ: object


class Layout(NamedTuple):
    active: object
    ids: object
    volume: object
    initial_amount: object
    reactants: object
    products: object
    owners: object
    owner_matrix: object
    reaction_active: object
    forward_rate: object
    delta_mu_RT: object
    standard_mu_RT: object
    moieties: object
    valence: object
    temperature: object
    standard_concentration: object


STATE_TYPE, LAYOUT_TYPE = State, Layout


def batch_signature(model):
    return len(model.species), len(model.moieties)


def working_size(spec):
    s, q = len(spec.model.species), len(spec.model.moieties)
    c, r = spec.execution.capacity, spec.execution.reaction_capacity
    return 64 * (s * c + 2 * r + s * r + c * r + q * s + 1)


def initial_values(spec):
    m, x = spec.model, spec.execution
    s, c, r = len(m.species), x.capacity, x.reaction_capacity
    n, nr = len(m.compartments), len(m.reactions)
    initial = np.ones((s, c))  # Neutral finite padding for logs; never stored material.
    initial[:, :n] = np.array([p.initial_amount_fmol for p in m.compartments]).T
    volume = np.ones(c)
    volume[:n] = [p.volume_pL for p in m.compartments]
    reactants, products = np.zeros((s, r)), np.zeros((s, r))
    owners, owner_matrix = np.zeros(r, dtype=np.int64), np.zeros((r, c))
    forward = np.zeros(r)
    slots = {p.id: i for i, p in enumerate(m.compartments)}
    for i, reaction in enumerate(m.reactions):
        reactants[:, i], products[:, i] = reaction.reactants, reaction.products
        owners[i] = slots[reaction.compartment]
        owner_matrix[i, owners[i]] = 1
        forward[i] = reaction.forward_rate_per_s
    mu = np.array([p.standard_mu_RT for p in m.species])
    return State(np.zeros((s, c)), np.zeros(r), np.zeros(r)), Layout(
        np.arange(c) < n,
        np.where(np.arange(c) < n, np.arange(c), -1).astype(np.int64),
        volume,
        initial,
        reactants,
        products,
        owners,
        owner_matrix,
        np.arange(r) < nr,
        forward,
        mu @ (products - reactants),
        mu,
        np.array([p.moieties for p in m.species], dtype=np.float64).T,
        np.array([p.valence for p in m.species], dtype=np.float64),
        np.float64(m.temperature_K),
        np.float64(m.standard_concentration_mM),
    )


def parameters(spec, layout):
    return layout


def reaction_amount(extent, layout, *, xp=np):
    return xp.einsum(
        "sr,...r,rc->...sc", layout.products - layout.reactants, extent, layout.owner_matrix
    )


def rates(state, control, layout, *, xp=jnp):
    amount = layout.initial_amount + state.amount_increment
    activity = amount[..., :, layout.owners] / (
        layout.volume[layout.owners] * layout.standard_concentration
    )
    scale = (
        layout.volume[layout.owners] * layout.standard_concentration * layout.forward_rate * control
    )
    return reversible_flux(
        activity, layout.reactants, layout.products, layout.delta_mu_RT, scale, xp=xp
    )


def rhs(state, control, layout, active, *, xp=jnp):
    flux, affinity = rates(state, control, layout, xp=xp)
    return State(
        reaction_amount(flux, layout, xp=xp),
        flux,
        R * layout.temperature * 1e-3 * flux * affinity,
    )


def domain_valid(state, layout, active):
    n = layout.initial_amount + state.amount_increment
    return (
        jnp.all(jnp.stack([jnp.all(jnp.isfinite(v)) for v in state]))
        & jnp.all(n > 0)
        & jnp.all(jnp.where(active, 0.0, state.amount_increment) == 0)
        & jnp.all(jnp.where(layout.reaction_active, 0.0, state.reaction_extent) == 0)
        & jnp.all(jnp.where(layout.reaction_active, 0.0, state.dissipated_energy_pJ) == 0)
        & jnp.all(state.dissipated_energy_pJ >= 0)
    )


def loss_bound(spec):
    """Conservative concentration/exit-rate bound from every local conserved pool."""
    _, p = initial_values(spec)
    totals = p.moieties @ p.initial_amount
    upper = np.empty_like(p.initial_amount)
    for i in range(len(spec.model.species)):
        selected = p.moieties[:, i] > 0
        upper[i] = np.min(totals[selected] / p.moieties[selected, i, None], axis=0)
    activity = upper / (p.volume * p.standard_concentration)
    loss = np.zeros_like(upper)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for j in range(len(spec.model.reactions)):
            owner = p.owners[j]
            for side, rate in (
                (p.reactants[:, j], p.forward_rate[j]),
                (p.products[:, j], p.forward_rate[j] * np.exp(p.delta_mu_RT[j])),
            ):
                for i in np.flatnonzero(side):
                    powers = side.copy()
                    powers[i] -= 1
                    loss[i, owner] += side[i] * rate * np.prod(activity[:, owner] ** powers)
    if not np.isfinite(loss).all() or not np.isfinite(activity).all():
        raise ConfigError("Closed chemical rate/concentration bound is nonfinite")
    return float(loss.max(initial=0))


def check_definition(spec):
    loss_bound(spec)


def check_steps(spec, steps, controls):
    alpha = loss_bound(spec)
    if np.max(steps, initial=0) * alpha > 0.25 + 16 * np.finfo(np.float64).eps:
        raise ConfigError("Reaction integration requires actual step * bounded loss rate <= 0.25")


def free_energy_change(state, layout):
    delta, n0 = state.amount_increment, layout.initial_amount
    # Reference-increment form avoids subtracting two large free energies.
    change = delta * (
        layout.standard_mu_RT[:, None]
        + np.log(n0 / (layout.volume * layout.standard_concentration))
        - 1
    )
    change += (n0 + delta) * np.log1p(delta / n0)
    return R * layout.temperature * 1e-3 * np.sum(change, axis=-2)


def check_values(state, spec):
    if not all(np.isfinite(v).all() for v in state):
        raise NumericalError("Nonfinite chemical state")
    _, p = initial_values(spec)
    n = p.initial_amount + state.amount_increment
    if np.any(n <= 0):
        raise NumericalError("Nonpositive chemical amount; refused without clipping")
    if (
        np.any(state.amount_increment[..., ~p.active] != 0)
        or np.any(state.reaction_extent[..., ~p.reaction_active] != 0)
        or np.any(state.dissipated_energy_pJ[..., ~p.reaction_active] != 0)
    ):
        raise NumericalError("Inactive chemical storage changed")
    accounted = reaction_amount(state.reaction_extent, p)
    residual = state.amount_increment - accounted
    moiety = np.einsum("qs,...sc->...qc", p.moieties, state.amount_increment)
    charge = np.einsum("s,...sc->...c", p.valence, state.amount_increment)
    for name, value, inventory in (
        ("reaction ledger", residual, p.initial_amount),
        ("moiety", moiety, p.moieties @ p.initial_amount),
        ("charge", charge, np.abs(p.valence) @ p.initial_amount),
    ):
        tolerance = ROUND_ATOL * np.maximum(1.0, inventory)
        if not np.isfinite(value).all() or np.any(np.abs(value) > tolerance):
            raise NumericalError("Closed chemical " + name + " conservation failed")
    energy = free_energy_change(state, p) + state.dissipated_energy_pJ @ p.owner_matrix
    if not np.isfinite(energy).all() or np.max(np.abs(energy), initial=0) > ENERGY_ATOL_PJ:
        raise NumericalError("Closed chemical energy balance failed")
    if np.any(state.dissipated_energy_pJ < -ROUND_ATOL):
        raise NumericalError("Negative chemical dissipation")
    if state.dissipated_energy_pJ.ndim == 2 and np.any(
        np.diff(state.dissipated_energy_pJ, axis=0) < -ROUND_ATOL
    ):
        raise NumericalError("Chemical dissipation ledger decreased")
    return {
        "max_balance_error_fmol": float(np.max(np.abs(moiety), initial=0)),
        "max_process_accounting_error_fmol": float(np.max(np.abs(residual), initial=0)),
        "max_charge_balance_error_equivalent_fmol": float(np.max(np.abs(charge), initial=0)),
        "max_energy_balance_error_pJ": float(np.max(np.abs(energy), initial=0)),
    }


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount_increment: np.ndarray
    reaction_extent: np.ndarray
    dissipated_energy_pJ: np.ndarray
    amount: np.ndarray
    concentration_mM: np.ndarray
    reaction_rate_fmol_per_s: np.ndarray
    affinity_RT: np.ndarray
    free_energy_change_pJ: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    p = Layout(*(np.asarray(v) for v in layout))
    control = control_values(spec, times[:-1])
    left, right = (
        rhs(State(*(v[part] for v in history)), control, p, p.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    if len(times) > 1:
        low, _ = hermite_bounds(
            times, history.amount_increment, left.amount_increment, right.amount_increment
        )
        if np.any(p.initial_amount + low <= 0):
            raise NumericalError("Chemical observation cubic leaves the positive domain")
        low, high = hermite_bounds(
            times,
            history.dissipated_energy_pJ,
            left.dissipated_energy_pJ,
            right.dissipated_energy_pJ,
        )
        if np.any(low < history.dissipated_energy_pJ[:-1] - ROUND_ATOL) or np.any(
            high > history.dissipated_energy_pJ[1:] + ROUND_ATOL
        ):
            raise NumericalError("Chemical observation dissipation leaves its interval ledger")
    sampled = State(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, left, right, strict=True)
        )
    )
    check_values(sampled, spec)
    amount = np.where(p.active, p.initial_amount + sampled.amount_increment, 0.0)
    flux, affinity = rates(sampled, control_values(spec, requested), p, xp=np)
    return Observations(
        requested,
        *sampled,
        amount,
        amount / p.volume,
        flux,
        affinity,
        free_energy_change(sampled, p),
    )


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    n = len(spec.model.compartments)
    amount = (layout.initial_amount + history.amount_increment[-1])[:, :n]
    return {
        "claim_scope": (
            "Synthetic closed ideal chemistry; no ER transport, voltage feedback "
            "or biological calibration"
        ),
        "species": [s.id for s in spec.model.species],
        "compartments": [c.id for c in spec.model.compartments],
        "active_compartments": n,
        "legacy_cell_ids_mean": "compartment storage slots; not interacting biological cells",
        "reactions": [r.id for r in spec.model.reactions],
        "state_axes": STATE_AXES,
        "final_amounts_fmol": amount.tolist(),
        "final_concentrations_mM": (amount / layout.volume[:n]).tolist(),
        "final_reaction_extents_fmol": history.reaction_extent[
            -1, : len(spec.model.reactions)
        ].tolist(),
        "dissipated_energy_pJ": float(np.sum(history.dissipated_energy_pJ[-1])),
        **diagnostics,
    }
