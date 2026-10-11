"""State-bearing channel composed with the maintained-bath ionic assembly.

One real cell/membrane/channel in this identity, independently padded numeric
axes. Amounts remain the only mobile charge inventory. No assay, name-based law
selection, reference imports, gate clipping, or equilibrium reinitialization.
"""

from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import VoltageGatedControl, control_values
from cells.core.specs import ConfigError
from cells.core.state import MultispeciesState, VoltageGatedLayout, VoltageGatedState
from cells.models import multispecies_membrane as ionic
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    MOL_PER_FMOL,
    electrochemical_potential,
    ghk_leak,
)
from cells.processes.voltage_gates import VOLTAGE_DOMAIN_V, kinetics

STATE_TYPE = VoltageGatedState
LAYOUT_TYPE = VoltageGatedLayout
OBSERVER_ID = "voltage_gated_membrane_physical_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_species_mh_in_0_1_channel_voltage_minus120_plus60mV@1"
MAX_STEP = 0.0005
BATCH_CAPACITIES = ("channel_capacity",)
STATE_AXES = ionic.STATE_AXES | {
    "gate": ["gate_m_h", "channel_slot"],
    "channel_transferred": ["channel_slot"],
}
batch_signature = ionic.batch_signature
parameters = ionic.parameters
membrane_voltage = ionic.membrane_voltage


def working_size(spec):
    """Float64-equivalent buffers, including channel/cubic host temporaries.

    Preflight uses scalar extents only, before allocating any capacity arrays.
    Compiler/runtime/OS overhead is outside this conservative array estimate.
    """
    cells, _, membranes = ionic.working_columns(spec)
    return (
        cells * spec.execution.capacity
        + (membranes + 16 * len(spec.model.species_ids)) * spec.execution.membrane_capacity
        + 160 * spec.execution.channel_capacity
    )


def initial_values(spec):
    state, layout = ionic.initial_values(spec)
    c, capacity = spec.model.channel, spec.execution.channel_capacity
    active = np.arange(capacity) == 0
    gate = np.zeros((2, capacity))
    gate[:, 0] = c.initial_gate
    return VoltageGatedState(*state, gate, np.zeros(capacity)), VoltageGatedLayout(
        *layout,
        np.where(active, 1, -1).astype(np.int64),
        active,
        np.zeros(capacity, dtype=np.int64),
        np.where(active, spec.model.species_ids.index(c.species_id), 0).astype(np.int64),
        np.where(active, 1, -1).astype(np.int64),
        np.where(active, c.max_permeability_m_per_s, 0.0),
        np.where(active, c.abundance, 0.0),
    )


def ionic_state(state):
    return MultispeciesState(*state[:4])


class ChannelReadouts(NamedTuple):
    gate_inf: object
    gate_tau_s: object
    gate_rate_per_s: object
    open_probability: object
    effective_permeability_m_per_s: object
    flux_fmol_per_s: object
    delta_mu_J_per_mol: object
    dissipation_rate_pJ_per_s: object


def channel_readouts(state, availability, layout, *, xp=jnp):
    active, membranes, species = (
        layout.channel_active,
        layout.channel_membranes,
        layout.channel_species,
    )
    owners, baths = layout.owners[membranes], layout.membrane_baths[membranes]
    # Only actual padding is sanitized. An unavailable real channel must still
    # have valid chemistry/voltage/gates and keeps evolving its intrinsic state.
    voltage = xp.where(active, membrane_voltage(state.amount, layout, xp=xp)[..., membranes], 0.0)
    ci = xp.where(active, state.amount[..., species, owners], 1.0) / xp.where(
        active, layout.volume[owners], 1.0
    )
    co = xp.where(active, layout.bath_concentration[species, baths], 1.0)
    targets, tau = kinetics(voltage, xp=xp)
    gate = xp.where(active, state.gate, 0.0)
    rate = (targets - gate) / tau
    opened = gate[..., 0, :] * gate[..., 1, :]
    permeability = layout.channel_permeability * layout.channel_abundance * availability * opened
    valence, temperature = layout.valence[species, 0], layout.temperature[baths]
    flux = ghk_leak(
        ci, co, voltage, valence, temperature, layout.area[membranes], permeability, 1.0, xp=xp
    )
    mu = electrochemical_potential(ci, co, voltage, valence, temperature, xp=xp)
    return ChannelReadouts(
        *(
            xp.where(active, v, 0.0)
            for v in (targets, tau, rate, opened, permeability, flux, mu, -1e-3 * flux * mu)
        )
    )


def scatter(values, target, indices, *, xp=jnp):
    result = xp.zeros_like(target)
    if xp is np:
        np.add.at(result, (Ellipsis, *indices), values)
        return result
    return result.at[(Ellipsis, *indices)].add(values)


def channel_species(values, target, layout, *, xp=np):
    """Project a channel-owned transfer/rate onto [species, membrane]; not new state."""
    return scatter(values, target, (layout.channel_species, layout.channel_membranes), xp=xp)


def rhs(state, control, layout, active, *, xp=jnp):
    base = ionic.rhs(ionic_state(state), control.membrane, layout, active, xp=xp)
    channel = channel_readouts(state, control.channel, layout, xp=xp)
    amount = base.amount + scatter(
        channel.flux_fmol_per_s,
        state.amount,
        (layout.channel_species, layout.owners[layout.channel_membranes]),
        xp=xp,
    )
    dissipated = base.dissipated_energy_pJ + scatter(
        channel.dissipation_rate_pJ_per_s,
        state.dissipated_energy_pJ,
        (layout.channel_membranes,),
        xp=xp,
    )
    return VoltageGatedState(
        amount,
        base.leak_transferred,
        base.pump_cycles,
        dissipated,
        channel.gate_rate_per_s,
        channel.flux_fmol_per_s,
    )


def domain_valid(state, layout, active, *, xp=jnp):
    valid = ionic.domain_valid(ionic_state(state), layout, active, xp=xp)
    gates = xp.isfinite(state.gate) & xp.where(
        layout.channel_active, (state.gate >= 0) & (state.gate <= 1), state.gate == 0
    )
    ledger = xp.isfinite(state.channel_transferred) & xp.where(
        layout.channel_active, True, state.channel_transferred == 0
    )
    absent = xp.where(
        (layout.channel_permeability == 0) | (layout.channel_abundance == 0),
        state.channel_transferred == 0,
        True,
    )
    voltage = membrane_voltage(state.amount, layout, xp=xp)[..., layout.channel_membranes]
    vmin, vmax = VOLTAGE_DOMAIN_V
    voltage_ok = xp.where(layout.channel_active, (voltage >= vmin) & (voltage <= vmax), True)
    return valid & xp.all(gates) & xp.all(ledger) & xp.all(absent) & xp.all(voltage_ok)


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Gated membrane RK4 requires largest actual step <= 0.0005 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for index in range(len(held.channel)):
            control = VoltageGatedControl(*(v[index] for v in held))
            slopes = rhs(state, control, layout, layout.active, xp=np)
            values = channel_readouts(state, control.channel, layout, xp=np)
            base = ionic.readouts(state, control.membrane, layout, xp=np)
            if not all(np.isfinite(v).all() for v in (*slopes, *values, *base)):
                raise ConfigError("Initial gated membrane rates/readouts exceed finite float64")


def balances(state, layout):
    # Reuse ionic accounting algebra on a read-only projection. The serialized
    # baseline leak ledger is never relabelled or overwritten by channel flow.
    exchanged = state.leak_transferred + channel_species(
        state.channel_transferred, state.leak_transferred, layout
    )
    return ionic.balances(ionic_state(state)._replace(leak_transferred=exchanged), layout)


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError(
                "Invalid gated membrane state: positive species, finite storage, "
                "m/h in [0,1] and channel voltage domain required; no clipping"
            )
        residual, charge, energy = balances(state, layout)
        maxima = [float(np.max(np.abs(v), initial=0)) for v in (residual, charge, energy)]
        outside = np.any(np.abs(residual) > np.asarray(spec.execution.material_balance_atol_fmol))
    if not np.isfinite(maxima).all() or outside or maxima[1] > 1e-8 or maxima[2] > 1e-6:
        raise NumericalError("Gated membrane material/charge/resolved-energy accounting failed")
    d = state.dissipated_energy_pJ
    if np.min(d, initial=0) < -1e-10 or (
        d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -1e-10
    ):
        raise NumericalError("Diagnostic dissipation must not decrease")
    return dict(
        zip(
            ("max_balance_error_fmol", "max_charge_balance_error_V", "max_energy_balance_error_pJ"),
            maxima,
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    ionic.check_interpolants(times, history, f0, f1, layout)
    if len(times) < 2:
        return
    lo, hi = hermite_bounds(times, history.gate, f0.gate, f1.gate)
    if np.any(lo[..., layout.channel_active] < 0) or np.any(hi[..., layout.channel_active] > 1):
        raise NumericalError("Cubic interior violates gate [0,1] domain; no clipping")
    voltage = membrane_voltage(history.amount, layout, xp=np)[..., layout.channel_membranes]
    slopes = [
        CHARGE_PER_FMOL
        / layout.capacitance[layout.channel_membranes]
        * np.sum(
            layout.valence * f.amount[..., :, layout.owners[layout.channel_membranes]], axis=-2
        )
        for f in (f0, f1)
    ]
    lo, hi = hermite_bounds(times, voltage, *slopes)
    if np.any(lo[..., layout.channel_active] < VOLTAGE_DOMAIN_V[0]) or np.any(
        hi[..., layout.channel_active] > VOLTAGE_DOMAIN_V[1]
    ):
        raise NumericalError("Cubic interior exceeds channel voltage domain")


@dataclass(frozen=True)
class Observations(ionic.Observations):
    gate: np.ndarray
    channel_transferred: np.ndarray
    channel_availability: np.ndarray
    channel_open_probability: np.ndarray
    gate_inf: np.ndarray
    gate_tau_s: np.ndarray
    gate_rate_per_s: np.ndarray
    channel_effective_permeability_m_per_s: np.ndarray
    channel_flux_fmol_per_s: np.ndarray
    channel_delta_mu_J_per_mol: np.ndarray
    channel_dissipation_rate_pJ_per_s: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = VoltageGatedLayout(*(np.asarray(v) for v in layout))
    control = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(VoltageGatedState(*(v[part] for v in history)), control, layout, layout.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = VoltageGatedState(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, leak, cycles, mu, energy = ionic.readouts(sampled, control.membrane, layout, xp=np)
    channel = channel_readouts(sampled, control.channel, layout, xp=np)
    pump_flux = layout.stoichiometry * cycles[..., None, :]
    channel_flux = channel_species(channel.flux_fmol_per_s, leak, layout)
    dissipation = ionic.dissipation_rate(leak, cycles, mu, energy, xp=np) + scatter(
        channel.dissipation_rate_pJ_per_s, cycles, (layout.channel_membranes,), xp=np
    )
    exchanged = (
        sampled.leak_transferred
        + layout.stoichiometry * sampled.pump_cycles[..., None, :]
        + channel_species(sampled.channel_transferred, sampled.leak_transferred, layout)
    )
    result = Observations(
        requested,
        *ionic_state(sampled),
        sampled.amount / layout.volume,
        voltage,
        control.membrane[:, :-1],
        control.membrane[:, -1],
        leak,
        cycles,
        pump_flux,
        mu,
        energy,
        CHARGE_PER_FMOL * np.sum(layout.valence * (leak + pump_flux + channel_flux), axis=-2),
        -MOL_PER_FMOL * layout.pump_drive * cycles,
        -MOL_PER_FMOL * layout.pump_drive * sampled.pump_cycles,
        dissipation,
        -exchanged,
        *balances(sampled, layout),
        sampled.gate,
        sampled.channel_transferred,
        control.channel,
        channel.open_probability,
        channel.gate_inf,
        channel.gate_tau_s,
        channel.gate_rate_per_s,
        channel.effective_permeability_m_per_s,
        channel.flux_fmol_per_s,
        channel.delta_mu_J_per_mol,
        channel.dissipation_rate_pJ_per_s,
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite gated membrane observation; refused without clipping")
    return result


def summarize(history, diagnostics, spec):
    result = ionic.summarize(history, diagnostics, spec)
    result.update(
        {
            "claim_scope": (
                "synthetic state-bearing ionic channel engineering; not calibrated biology, "
                "BETSE parity, organs or GPU execution"
            ),
            "numerical_scope": (
                "NUM-007 qualifies fourteen short trajectories at 0.5 ms; "
                "runtime guards are not a parameter-box error guarantee"
            ),
            "state_axes": STATE_AXES,
            "channel_id": spec.model.channel.id,
            "channel_law": spec.model.channel.kinetic_law,
            "channel_species": spec.model.channel.species_id,
            "physical_channels": 1,
            "channel_capacity": spec.execution.channel_capacity,
            "gate_labels": ["m", "h"],
            "final_gate": history.gate[-1, :, 0].tolist(),
            "final_channel_transferred_fmol": float(history.channel_transferred[-1, 0]),
            "energy_scope": (
                "ionic/capacitor accounting; neglects gating charge, "
                "channel conformational energy and protein turnover"
            ),
        }
    )
    result["identity_labels"]["channel"] = {"1": spec.model.channel.id}
    return result
