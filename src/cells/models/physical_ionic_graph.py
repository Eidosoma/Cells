"""Sparse physical ionic graph: shared local laws and one owner per junction.

No assay/reference imports, independent voltage inventory or gate repair. All
routes see the same complete solver stage; internal transfers remain separate
from maintained-bath exchange. Host guards include full cubic interiors.
"""

from dataclasses import dataclass, replace
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError
from cells.core.state import PhysicalIonicGraphLayout, PhysicalIonicGraphState
from cells.coupling.selective import gate_target, selective_flux
from cells.models import multispecies_membrane as ionic
from cells.models import voltage_gated_membrane as gated
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R

STATE_TYPE = PhysicalIonicGraphState
LAYOUT_TYPE = PhysicalIonicGraphLayout
OBSERVER_ID = "physical_ionic_graph_physical_readouts@1"
OBSERVATION_SAMPLING = gated.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_species_unit_mh_junction_gates_channel_and_all_valence_edge_domains@1"
MAX_STEP = 0.002
MAX_ABS_X = 50.0
BATCH_CAPACITIES = gated.BATCH_CAPACITIES
STATE_AXES = gated.STATE_AXES | {
    "junction_gate": ["edge_slot"],
    "junction_transferred": ["species", "edge_slot"],
    "junction_dissipated_energy_pJ": ["edge_slot"],
}
batch_signature = ionic.batch_signature
parameters = ionic.parameters
membrane_voltage = ionic.membrane_voltage


def working_size(spec):
    return (
        gated.working_size(spec)
        + (64 * len(spec.model.species_ids) + 160) * spec.execution.edge_capacity
    )


def check_definition(model):
    for cell in model.cells:
        ionic.check_definition(cell)
    first, ids = model.cells[0], [c.cell_id for c in model.cells]
    for edge in model.junctions:
        a, b = (model.cells[ids.index(i)] for i in (edge.from_cell, edge.to_cell))
        with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
            rt = R * np.float64(first.temperature_K)
            x = (
                np.asarray(first.valence)
                * F
                * (np.float64(a.initial_voltage_V) - b.initial_voltage_V)
                / rt
            )
            coefficients = (
                np.float64(edge.area_m2) * np.asarray(edge.permeability_m_per_s) / MOL_PER_FMOL
            )
            inverse_tau = 1 / np.float64(edge.tau_s)
            bound = np.float64(edge.sensitivity_per_V) * (MAX_ABS_X * rt / F + edge.half_voltage_V)
        if not np.isfinite(np.r_[x, coefficients, inverse_tau, bound]).all() or inverse_tau <= 0:
            raise ConfigError("Derived junction/gate coefficients exceed finite float64")
        if np.any(np.abs(x) > MAX_ABS_X):
            raise ConfigError("Initial junction voltage exceeds an all-valence physical domain")


def initial_values(spec):
    m, x = spec.model, spec.execution
    n, s, k, e = len(m.cells), len(m.species_ids), len(m.channels), len(m.junctions)
    base, layout = ionic.initial_values(replace(spec, model=m.cells[0]))
    values = layout._asdict()
    values["stoichiometry"] = np.zeros((s, x.membrane_capacity), dtype=np.int64)
    for slot, c in enumerate(m.cells):
        values["active"][slot], values["ids"][slot] = True, slot + 1
        base.amount[:, slot] = c.initial_amount_fmol
        values["amount_reference"][:, slot] = c.initial_amount_fmol
        for key, value in (
            ("volume", c.volume_pL),
            ("voltage_reference", c.initial_voltage_V),
            ("fixed_charge_equivalent", c.fixed_charge_equivalent_fmol),
        ):
            values[key][slot] = value
        for key, value in (
            ("membrane_ids", slot + 1),
            ("membrane_active", True),
            ("owners", slot),
            ("area", c.area_m2),
            ("specific_capacitance", c.specific_capacitance_F_per_m2),
            ("capacitance", c.area_m2 * c.specific_capacitance_F_per_m2),
            ("pump_capacity", c.capacity_fmol_per_s),
            ("pump_drive", c.drive_J_per_mol),
        ):
            values[key][slot] = value
        values["permeability"][:, slot] = c.permeability_m_per_s
        values["stoichiometry"][:, slot] = c.stoichiometry
    membrane_ids, cell_ids = [c.membrane_id for c in m.cells], [c.cell_id for c in m.cells]
    channel_gate = np.zeros((2, x.channel_capacity))
    channel_membranes = np.zeros(x.channel_capacity, dtype=np.int64)
    channel_species = np.zeros(x.channel_capacity, dtype=np.int64)
    channel_p, channel_a = np.zeros(x.channel_capacity), np.zeros(x.channel_capacity)
    for slot, c in enumerate(m.channels):
        channel_gate[:, slot] = c.initial_gate
        channel_membranes[slot] = membrane_ids.index(c.membrane_id)
        channel_species[slot] = m.species_ids.index(c.species_id)
        channel_p[slot], channel_a[slot] = c.max_permeability_m_per_s, c.abundance
    cell_membranes = np.zeros(x.capacity, dtype=np.int64)
    cell_membranes[:n] = np.arange(n)
    senders, receivers = (
        np.zeros(x.edge_capacity, dtype=np.int64),
        np.zeros(x.edge_capacity, dtype=np.int64),
    )
    area, sensitivity, tau = (
        np.ones(x.edge_capacity),
        np.ones(x.edge_capacity),
        np.ones(x.edge_capacity),
    )
    half, gate = np.zeros(x.edge_capacity), np.zeros(x.edge_capacity)
    permeability, residual = np.zeros((s, x.edge_capacity)), np.zeros((s, x.edge_capacity))
    for slot, edge in enumerate(m.junctions):
        senders[slot], receivers[slot] = (
            cell_ids.index(edge.from_cell),
            cell_ids.index(edge.to_cell),
        )
        area[slot], sensitivity[slot], tau[slot] = edge.area_m2, edge.sensitivity_per_V, edge.tau_s
        half[slot], gate[slot] = edge.half_voltage_V, edge.initial_gate
        permeability[:, slot], residual[:, slot] = edge.permeability_m_per_s, edge.residual_fraction
    real_channel, real_edge = np.arange(x.channel_capacity) < k, np.arange(x.edge_capacity) < e
    return STATE_TYPE(
        *base,
        channel_gate,
        np.zeros(x.channel_capacity),
        gate,
        np.zeros((s, x.edge_capacity)),
        np.zeros(x.edge_capacity),
    ), LAYOUT_TYPE(
        *values.values(),
        np.where(real_channel, np.arange(x.channel_capacity) + 1, -1),
        real_channel,
        channel_membranes,
        channel_species,
        np.where(real_channel, 1, -1),
        channel_p,
        channel_a,
        cell_membranes,
        np.where(real_edge, np.arange(x.edge_capacity) + 1, -1),
        real_edge,
        senders,
        receivers,
        area,
        permeability,
        residual,
        sensitivity,
        half,
        tau,
    )


def cell_voltage(amount, layout, *, xp=jnp):
    return xp.where(
        layout.active, membrane_voltage(amount, layout, xp=xp)[..., layout.cell_membranes], 0.0
    )


class JunctionReadouts(NamedTuple):
    delta_voltage_V: object
    gate_inf: object
    gate_rate_per_s: object
    open_fraction: object
    effective_permeability_m_per_s: object
    flux_fmol_per_s: object
    delta_mu_J_per_mol: object
    current_A: object
    dissipation_rate_pJ_per_s: object


def junction_readouts(state, availability, layout, *, xp=jnp):
    active, src, dst = layout.junction_active, layout.senders, layout.receivers
    voltage = cell_voltage(state.amount, layout, xp=xp)
    dv = xp.where(active, voltage[..., src] - voltage[..., dst], 0.0)
    ca = xp.where(active, state.amount[..., :, src], 1.0) / xp.where(
        active, layout.volume[src], 1.0
    )
    cb = xp.where(active, state.amount[..., :, dst], 1.0) / xp.where(
        active, layout.volume[dst], 1.0
    )
    gate = xp.where(active, state.junction_gate, 0.0)
    target = gate_target(dv, layout.junction_sensitivity, layout.junction_half_voltage, xp=xp)
    rate = (target - gate) / layout.junction_tau
    opened = layout.junction_residual + (1 - layout.junction_residual) * gate[..., None, :]
    effective = layout.junction_permeability * availability[..., None, :] * opened
    flux = selective_flux(
        ca,
        cb,
        dv[..., None, :],
        layout.valence,
        layout.temperature[0],
        layout.junction_area,
        layout.junction_permeability,
        layout.junction_residual,
        gate[..., None, :],
        availability[..., None, :],
        xp=xp,
    )
    mu = (
        R * layout.temperature[0] * (xp.log(cb) - xp.log(ca))
        - layout.valence * F * dv[..., None, :]
    )
    return JunctionReadouts(
        *(
            xp.where(active, v, 0.0)
            for v in (
                dv,
                target,
                rate,
                opened,
                effective,
                flux,
                mu,
                CHARGE_PER_FMOL * xp.sum(layout.valence * flux, axis=-2),
                -1e-3 * xp.sum(flux * mu, axis=-2),
            )
        )
    )


def scatter_edges(values, like, layout, *, xp=np):
    return gated.scatter(-values, like, (layout.senders,), xp=xp) + gated.scatter(
        values, like, (layout.receivers,), xp=xp
    )


def rhs(state, control, layout, active, *, xp=jnp):
    base = gated.rhs(state, control, layout, active, xp=xp)
    edge = junction_readouts(state, control.junction, layout, xp=xp)
    amount = base.amount + scatter_edges(edge.flux_fmol_per_s, state.amount, layout, xp=xp)
    return STATE_TYPE(
        xp.where(active, amount, 0.0),
        *base[1:],
        edge.gate_rate_per_s,
        edge.flux_fmol_per_s,
        edge.dissipation_rate_pJ_per_s,
    )


def domain_valid(state, layout, active, *, xp=jnp):
    valid = gated.domain_valid(state, layout, active, xp=xp)
    for value in state[6:]:
        valid = (
            valid
            & xp.all(xp.isfinite(value))
            & xp.all(xp.where(layout.junction_active, True, value == 0))
        )
    gate = state.junction_gate
    valid = valid & xp.all((gate >= 0) & (gate <= 1))
    valid = valid & xp.all(
        xp.where(layout.junction_permeability == 0, state.junction_transferred == 0, True)
    )
    edge_possible = xp.any(layout.junction_permeability != 0, axis=-2)
    channel_possible = (
        gated.scatter(
            xp.where(
                (layout.channel_permeability != 0) & (layout.channel_abundance != 0), 1.0, 0.0
            ),
            layout.pump_capacity,
            (layout.channel_membranes,),
            xp=xp,
        )
        != 0
    )
    membrane_possible = (
        xp.any(layout.permeability != 0, axis=-2) | (layout.pump_capacity != 0) | channel_possible
    )
    valid = valid & xp.all(xp.where(edge_possible, True, state.junction_dissipated_energy_pJ == 0))
    valid = valid & xp.all(xp.where(membrane_possible, True, state.dissipated_energy_pJ == 0))
    voltage = cell_voltage(state.amount, layout, xp=xp)
    dv = voltage[..., layout.senders] - voltage[..., layout.receivers]
    x = layout.valence * F * dv[..., None, :] / (R * layout.temperature[0])
    return valid & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Physical ionic graph requires largest actual RK4 step <= 0.002 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for i in range(len(held.membrane)):
            control = PhysicalIonicGraphControl(*(v[i] for v in held))
            slope = rhs(state, control, layout, layout.active, xp=np)
            values = (
                *ionic.readouts(state, control.membrane, layout, xp=np),
                *gated.channel_readouts(state, control.channel, layout, xp=np),
                *junction_readouts(state, control.junction, layout, xp=np),
            )
            if not domain_valid(state, layout, layout.active, xp=np) or not all(
                np.isfinite(v).all() for v in (*slope, *values)
            ):
                raise ConfigError(
                    "Initial graph state/rates/readouts violate finite physical domains"
                )


def membrane_exchange(state, layout):
    return (
        state.leak_transferred
        + layout.stoichiometry * state.pump_cycles[..., None, :]
        + gated.channel_species(state.channel_transferred, state.leak_transferred, layout)
    )


def balances(state, layout):
    local = membrane_exchange(state, layout)
    exchange = gated.scatter(local, state.amount, (layout.owners,), xp=np)
    delta = state.amount - layout.amount_reference
    residual = delta - exchange - scatter_edges(state.junction_transferred, state.amount, layout)
    cap = layout.capacitance[layout.cell_membranes]
    charge = np.where(
        layout.active, CHARGE_PER_FMOL / cap * np.sum(layout.valence * residual, axis=-2), 0.0
    )
    global_material = np.sum(delta - exchange, axis=-1)
    dv = np.where(
        layout.active, CHARGE_PER_FMOL / cap * np.sum(layout.valence * delta, axis=-2), 0.0
    )
    global_charge = np.sum(cap * dv, axis=-1) - CHARGE_PER_FMOL * np.sum(
        layout.valence[:, 0] * np.sum(local, axis=-1), axis=-1
    )
    n0, n = (
        np.where(layout.active, layout.amount_reference, 1.0),
        np.where(layout.active, state.amount, 1.0),
    )
    chemical = (
        1e-3
        * R
        * layout.temperature[0]
        * np.sum(
            delta * (np.log(n0 / layout.volume) - np.log(layout.bath_concentration[:, :1]) - 1)
            + n * np.log1p(delta / n0),
            axis=(-2, -1),
        )
    )
    electric = 0.5e12 * np.sum(cap * dv * (2 * layout.voltage_reference + dv), axis=-1)
    work = -1e-3 * np.sum(layout.pump_drive * state.pump_cycles, axis=-1)
    energy = (
        chemical
        + electric
        + np.sum(state.dissipated_energy_pJ, axis=-1)
        + np.sum(state.junction_dissipated_energy_pJ, axis=-1)
        - work
    )
    return residual, charge, energy, global_material, global_charge


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError(
                "Invalid physical ionic graph state/domain; no clipping or history repair"
            )
        material, charge, energy, global_material, global_charge = balances(state, layout)
        tol = np.asarray(spec.execution.material_balance_atol_fmol)
        outside = np.any(np.abs(material) > tol[:, None]) or np.any(np.abs(global_material) > tol)
        maxima = [
            float(np.max(np.abs(v), initial=0))
            for v in (material, charge, energy, global_material, global_charge)
        ]
    if (
        not np.isfinite(maxima).all()
        or outside
        or maxima[1] > 1e-8
        or maxima[2] > 1e-6
        or maxima[4] > 1e-19
    ):
        raise NumericalError(
            "Graph local/global material, charge or resolved-energy accounting failed"
        )
    for d in (state.dissipated_energy_pJ, state.junction_dissipated_energy_pJ):
        if np.min(d, initial=0) < -1e-10 or (
            d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -1e-10
        ):
            raise NumericalError("Membrane/junction diagnostic dissipation must not decrease")
    return dict(
        zip(
            (
                "max_balance_error_fmol",
                "max_charge_balance_error_V",
                "max_energy_balance_error_pJ",
                "max_global_balance_error_fmol",
                "max_global_charge_balance_error_C",
            ),
            maxima,
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    gated.check_interpolants(times, history, f0, f1, layout)
    if len(times) < 2:
        return
    lo, hi = hermite_bounds(times, history.junction_gate, f0.junction_gate, f1.junction_gate)
    if np.any(lo[..., layout.junction_active] < 0) or np.any(hi[..., layout.junction_active] > 1):
        raise NumericalError("Cubic interior violates junction gate [0,1] domain")
    v = cell_voltage(history.amount, layout, xp=np)
    dv = v[..., layout.senders] - v[..., layout.receivers]
    slopes = []
    for f in (f0, f1):
        vdot = (
            CHARGE_PER_FMOL
            / layout.capacitance[layout.cell_membranes]
            * np.sum(layout.valence * f.amount, axis=-2)
        )
        slopes.append(vdot[..., layout.senders] - vdot[..., layout.receivers])
    lo, hi = hermite_bounds(times, dv, *slopes)
    bound = (
        np.max(np.abs(layout.valence))
        * F
        * np.maximum(np.abs(lo), np.abs(hi))
        / (R * layout.temperature[0])
    )
    if not np.isfinite(bound).all() or np.any(bound > MAX_ABS_X):
        raise NumericalError("Cubic interior exceeds an all-valence junction voltage domain")


@dataclass(frozen=True)
class Observations(gated.Observations):
    junction_gate: np.ndarray
    junction_transferred: np.ndarray
    junction_dissipated_energy_pJ: np.ndarray
    junction_availability: np.ndarray
    junction_delta_voltage_V: np.ndarray
    junction_gate_inf: np.ndarray
    junction_gate_rate_per_s: np.ndarray
    junction_open_fraction: np.ndarray
    junction_effective_permeability_m_per_s: np.ndarray
    junction_flux_fmol_per_s: np.ndarray
    junction_delta_mu_J_per_mol: np.ndarray
    junction_current_A: np.ndarray
    junction_dissipation_rate_pJ_per_s: np.ndarray
    global_species_balance_fmol: np.ndarray
    global_charge_balance_C: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    control = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(STATE_TYPE(*(v[part] for v in history)), control, layout, layout.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = STATE_TYPE(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, leak, cycles, mu, energy = ionic.readouts(sampled, control.membrane, layout, xp=np)
    channel = gated.channel_readouts(sampled, control.channel, layout, xp=np)
    edge = junction_readouts(sampled, control.junction, layout, xp=np)
    pump_flux = layout.stoichiometry * cycles[..., None, :]
    channel_flux = gated.channel_species(channel.flux_fmol_per_s, leak, layout)
    dissipation = ionic.dissipation_rate(leak, cycles, mu, energy, xp=np) + gated.scatter(
        channel.dissipation_rate_pJ_per_s, cycles, (layout.channel_membranes,), xp=np
    )
    material, charge, balance, global_material, global_charge = balances(sampled, layout)
    result = Observations(
        requested,
        *gated.ionic_state(sampled),
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
        -membrane_exchange(sampled, layout),
        material,
        charge,
        balance,
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
        sampled.junction_gate,
        sampled.junction_transferred,
        sampled.junction_dissipated_energy_pJ,
        control.junction,
        *edge,
        global_material,
        global_charge,
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite graph observation; refused without clipping")
    return result


def summarize(history, diagnostics, spec):
    m, x = spec.model, spec.execution
    _, layout = initial_values(spec)
    return {
        "claim_scope": (
            "synthetic fixed physical ionic graph engineering; not calibrated biology, "
            "BETSE parity, organs or GPU execution"
        ),
        "numerical_scope": (
            "NUM-008 twelve short single/disconnected/pair/star cases at 2 ms; runtime guards "
            "are not an arbitrary-graph or parameter-box error guarantee"
        ),
        "state_axes": STATE_AXES,
        "identity_labels": {
            "cell": {str(i + 1): c.cell_id for i, c in enumerate(m.cells)},
            "membrane": {str(i + 1): c.membrane_id for i, c in enumerate(m.cells)},
            "channel": {str(i + 1): c.id for i, c in enumerate(m.channels)},
            "junction": {str(i + 1): c.id for i, c in enumerate(m.junctions)},
            "species": {str(i + 1): c for i, c in enumerate(m.species_ids)},
            "bath": {"1": m.cells[0].bath_id},
        },
        "physical_counts": {
            "cells": len(m.cells),
            "membranes": len(m.cells),
            "channels": len(m.channels),
            "junctions": len(m.junctions),
        },
        "capacities": {
            k: getattr(x, k)
            for k in ("capacity", "membrane_capacity", "channel_capacity", "edge_capacity")
        },
        "boundary": (
            "common maintained bath at zero potential; bath ledger excludes internal "
            "junction flow and is not an inventory"
        ),
        "external_support": [
            "bath chemistry/background charge",
            "temperature",
            "fixed volumes/geometries",
            "pump chemical drive",
        ],
        "energy_scope": (
            "ionic/capacitor/pump work only; no gating charge, "
            "protein energy/turnover or metabolism"
        ),
        "final_amounts_fmol": history.amount[-1, :, : len(m.cells)].tolist(),
        "final_voltage_V": cell_voltage(history.amount[-1], layout, xp=np)[: len(m.cells)].tolist(),
        **diagnostics,
    }
