"""Owned calcium/fuel with literal None-energy configured transport rates.

External cycle work, actual chemical/electrical transfer work and physical heat
are separate. Native signed regulation is retained without clipping; negative
physical dissipation refuses the trial. Configured routes do not consume ATP.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_irreversible_transport_spec import (
    ACCOUNTING,
    MODEL_ID,
    base_spec,
)
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy_hcn_extra as prior
from cells.models import surface_calcium_energy_transport as legacy
from cells.models import surface_tissue as surface
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes import betse_network_transport as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = {
    "network_chemical_work_pJ": ["network_transport_slot"],
    "network_electrical_work_pJ": ["network_transport_slot"],
}
STATE_AXES = legacy.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple(
    "SurfaceCalciumEnergyIrreversibleTransportState", [(key, object) for key in STATE_AXES]
)
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyIrreversibleTransportLayout",
    [(key, object) for key in legacy.LAYOUT_TYPE._fields],
)
BATCH_CAPACITIES = legacy.BATCH_CAPACITIES
OBSERVER_ID = "owned_calcium_fuel_irreversible_transport_physical_work@1"
STAGE_DOMAIN_ID = "actual_owned_ions_fuel_native_none_rate_nonnegative_physical_heat@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
READOUTS = (
    "network_cycle_rate_fmol_s",
    "network_source_reaction_energy_J_mol",
    "network_physical_chemical_energy_J_mol",
    "network_physical_electrical_energy_J_mol",
    "network_physical_transfer_energy_J_mol",
    "network_chemical_power_pJ_s",
    "network_electrical_power_pJ_s",
    "network_dissipation_pJ_s",
    "network_supplied_power_pJ_s",
    "network_availability",
    "network_regulation",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *legacy.EXTRA_AXES, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyIrreversibleTransportObservations",
    [(key, np.ndarray) for key in OBSERVATION_FIELDS],
    frozen=True,
)
parameters, ENERGY_ATOL_PJ = prior.parameters, prior.ENERGY_ATOL_PJ
base_state, base_layout, base_control = legacy.base_state, legacy.base_layout, legacy.base_control
topology, network_parameters = legacy.topology, legacy.network_parameters
batch_signature, route_to_membrane = legacy.batch_signature, legacy.route_to_membrane
physical_amounts, concentrations = legacy.physical_amounts, legacy.concentrations
accounting_state = legacy.accounting_state
cytosol_amount = prior.cytosol_amount
store_state, store_layout, er = prior.store_state, prior.store_layout, prior.er
ip3_readouts = prior.ip3_readouts


class Values(NamedTuple):
    field: object
    derivative: object
    kinetic: object
    energy: object
    regeneration: object
    exchange: object
    network: object
    network_heat_pJ_s: object
    network_work_pJ_s: object
    network_chemical_power_pJ_s: object
    network_electrical_power_pJ_s: object
    network_chemical_energy_J_mol: object
    network_electrical_energy_J_mol: object
    valid: object


def legacy_state(state):
    return legacy.STATE_TYPE(*(getattr(state, key) for key in legacy.STATE_AXES))


def working_size(spec):
    return legacy.working_size(spec) + 16 * spec.execution.network_transport_capacity


def initial_values(spec):
    state, layout = legacy.initial_values(spec)
    zeros = np.zeros(spec.execution.network_transport_capacity)
    return STATE_TYPE(*state, zeros.copy(), zeros.copy()), LAYOUT_TYPE(*layout)


def domain_valid(state, p, active, *, xp=jnp):
    valid = legacy.domain_valid(state, p, active, xp=xp)
    for key in EXTRA_AXES:
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(p.network_active, True, value == 0))
    valid &= xp.all(state.network_dissipated_energy_pJ >= 0)
    valid &= xp.all(
        xp.abs(
            state.network_supplied_work_pJ
            - state.network_chemical_work_pJ
            - state.network_electrical_work_pJ
            - state.network_dissipated_energy_pJ
        )
        <= 3e-12
    )
    valid &= xp.all(~p.network_reversible)
    return valid


def transfer_energies(c, voltage, p, *, xp):
    t, nu = topology(p), p.network_stoichiometry
    inside, outside = xp.take(c, t.inside, axis=-1), xp.take(c, t.outside, axis=-1)
    # Only nonparticipating terms receive neutral values. Active transported
    # concentrations are neither floored nor replaced, including blocked routes.
    inside, outside = (xp.where(nu != 0, value, 1.0) for value in (inside, outside))
    chemical = R * p.temperature * xp.sum(nu * (xp.log(outside) - xp.log(inside)), axis=0)
    electrical = -F * xp.sum(p.valence * nu, axis=0) * voltage
    return chemical, electrical


def readouts(state, control, p, *, xp=jnp):
    q = base_layout(p)
    w = prior.readouts(base_state(state), base_control(control), q, xp=xp)
    v, rates, parent_rate = w.field, w.field.rates, w.derivative
    c, t, params = concentrations(state, p, xp=xp), topology(p), network_parameters(p)
    voltage = xp.where(p.network_active, rates.membrane_voltage_V[p.network_membrane], 0.0)
    native = process.rates(
        c, voltage, t, params, control.network_transport, p.network_density, xp=xp
    )
    extent = native.extent_fmol_s
    chemical_per_cycle, electrical_per_cycle = transfer_energies(c, voltage, p, xp=xp)
    chemical_power, electrical_power = (
        1e-3 * extent * value for value in (chemical_per_cycle, electrical_per_cycle)
    )
    work = 1e-3 * extent * p.network_supplied_energy_J_mol
    heat = (
        1e-3
        * extent
        * (p.network_supplied_energy_J_mol - chemical_per_cycle - electrical_per_cycle)
    )
    transported = p.network_stoichiometry * extent
    flux = route_to_membrane(transported, p, xp=xp)
    cell = -scatter(flux, parent_rate.amount_increment, (p.membrane_cell,), xp=xp)
    outside = scatter(
        flux, parent_rate.extracellular_amount_increment, (p.membrane_outside,), xp=xp
    )
    chemical_amount = xp.stack(
        [
            (p.free_ion_selector @ cell[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = calcium.field._capacitor_solve(qdot, xp.zeros_like(qdot), surface.field_layout(q), xp=xp)
    n, a, b = p.active.size, p.membrane_cell, p.membrane_outside
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[n + b], 0.0)
    safe = xp.where(t.compartment_active, c, 1.0)
    chemical_rate = (
        1e-3 * R * p.temperature * xp.sum(xp.log(safe) * xp.concatenate((cell, outside), axis=1))
    )
    electric_rate = 1e12 * xp.sum(p.membrane_capacitance * rates.membrane_voltage_V * dvm)
    derivative = STATE_TYPE(
        *parent_rate._replace(
            amount_increment=parent_rate.amount_increment + cell,
            extracellular_amount_increment=parent_rate.extracellular_amount_increment + outside,
            chemical_amount_increment=parent_rate.chemical_amount_increment + chemical_amount,
        ),
        extent,
        transported,
        heat,
        work,
        chemical_power,
        electrical_power,
    )
    valid = w.valid & domain_valid(state, p, active=p.active, xp=xp)
    valid &= process.domain_valid(
        c, voltage, t, params, control.network_transport, p.network_density, xp=xp
    )
    valid &= xp.all(heat >= 0)
    # Preserve native signed regulation/rates. Their sign is not a substitute
    # for physical dissipation; only the actual physical heat admits a trial.
    for value in (
        *derivative,
        chemical_rate,
        electric_rate,
        chemical_per_cycle,
        electrical_per_cycle,
        dvm,
    ):
        valid &= xp.all(xp.isfinite(value))
    rates = rates._replace(
        cell_rate_fmol_s=rates.cell_rate_fmol_s + cell,
        outside_rate_fmol_s=rates.outside_rate_fmol_s + outside,
        membrane_flux_fmol_s=rates.membrane_flux_fmol_s + flux,
        membrane_current_A=rates.membrane_current_A
        + CHARGE_PER_FMOL * xp.sum(p.valence * flux, axis=0),
        membrane_dissipation_pJ_s=rates.membrane_dissipation_pJ_s
        + route_to_membrane(heat, p, xp=xp),
        valid=valid,
    )
    v = v._replace(
        rates=rates,
        membrane_voltage_rate_V_s=v.membrane_voltage_rate_V_s + dvm,
        chemical_energy_rate_pJ_s=v.chemical_energy_rate_pJ_s + chemical_rate,
        capacitor_energy_rate_pJ_s=v.capacitor_energy_rate_pJ_s + electric_rate,
        dissipation_pJ_s=v.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=v.energy_balance_pJ_s
        + chemical_rate
        + electric_rate
        + xp.sum(heat - work),
        converged=valid,
    )
    return Values(
        v,
        derivative,
        w.kinetic,
        w.energy,
        w.regeneration,
        w.exchange,
        native,
        heat,
        work,
        chemical_power,
        electrical_power,
        chemical_per_cycle,
        electrical_per_cycle,
        valid,
    )


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, value, xp.nan) for value in values.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    table = control_values(spec, [change.time for change in spec.experiment.changes])
    for i in range(len(table.network_transport)):
        if not control_domain_valid(
            state, type(table)(*(value[i] for value in table)), p, p.active, xp=np
        ):
            raise ConfigError("Initial irreversible transport has invalid physical heat/domain")


def check_steps(spec, steps, controls):
    from cells.core.schedule import control_values

    prior.check_steps(replace(base_spec(spec), experiment=spec.experiment), steps, controls)
    state, p = initial_values(spec)
    inside, outside = physical_amounts(state, p)
    amount = np.concatenate((inside, outside), axis=-1)
    t = topology(p)
    safe = np.where(t.compartment_active, amount, 1.0)
    table = control_values(spec, [change.time for change in spec.experiment.changes])
    for i in range(len(table.network_transport)):
        values = readouts(state, type(table)(*(value[i] for value in table)), p, xp=np)
        gross = np.abs(values.derivative.network_transferred_fmol)
        turnover = ordered_scatter(gross, np.zeros_like(amount), (t.inside,), xp=np)
        turnover += ordered_scatter(gross, np.zeros_like(amount), (t.outside,), xp=np)
        fractional = np.max(np.where(t.compartment_active, turnover / safe, 0.0), initial=0)
        if (
            not values.valid
            or not np.isfinite(fractional)
            or np.max(steps, initial=0) * fractional > legacy.MAX_INITIAL_ION_CHANGE_PER_STEP
        ):
            raise ConfigError(
                "Initial irreversible transport requires a smaller RK4 step/valid physical heat"
            )


def balances(state, p):
    result = legacy.balances(state, p)
    result["network_physical_work"] = (
        state.network_chemical_work_pJ
        + state.network_electrical_work_pJ
        + state.network_dissipated_energy_pJ
        - state.network_supplied_work_pJ
    )
    return result


def check_values(state, spec):
    diagnostics = legacy.check_values(legacy_state(state), spec)
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [
            STATE_TYPE(*(value[i] for value in state)) for i in range(len(state.amount_increment))
        ]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid irreversible transport physical work/domain")
        residual = balances(row, p)["network_physical_work"]
        if not np.isfinite(residual).all() or np.max(np.abs(residual), initial=0) > 3e-12:
            raise NumericalError("Irreversible chemical/electrical/heat/work ledger failed")
        diagnostics["max_network_physical_work_error"] = max(
            diagnostics.get("max_network_physical_work_error", 0.0),
            float(np.max(np.abs(residual), initial=0)),
        )
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(value) for value in layout))
    requested = np.asarray(requested, dtype=float)
    if any(time not in times for time in requested):
        raise ConfigError("Irreversible transport observations require accepted times")
    observed = prior.observe_history(
        times, base_state(history), base_layout(p), requested, base_spec(spec)
    )
    table, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        index = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(value[index] for value in history))
        values = readouts(state, type(table)(*(value[j] for value in table)), p, xp=np)
        if not values.valid:
            raise NumericalError("Irreversible transport observation domain invalid")
        row = {key: value[j] for key, value in vars(observed).items()}
        row.update({key: getattr(state, key) for key in (*legacy.EXTRA_AXES, *EXTRA_AXES)})
        row.update(
            membrane_flux_fmol_s=values.field.rates.membrane_flux_fmol_s,
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(values.field.energy_balance_pJ_s),
            network_cycle_rate_fmol_s=values.network.extent_fmol_s,
            network_source_reaction_energy_J_mol=values.network.source_reaction_energy_J_mol,
            network_physical_chemical_energy_J_mol=values.network_chemical_energy_J_mol,
            network_physical_electrical_energy_J_mol=values.network_electrical_energy_J_mol,
            network_physical_transfer_energy_J_mol=values.network_chemical_energy_J_mol
            + values.network_electrical_energy_J_mol,
            network_chemical_power_pJ_s=values.network_chemical_power_pJ_s,
            network_electrical_power_pJ_s=values.network_electrical_power_pJ_s,
            network_dissipation_pJ_s=values.network_heat_pJ_s,
            network_supplied_power_pJ_s=values.network_work_pJ_s,
            network_availability=table.network_transport[j],
            network_regulation=values.network.regulation,
        )
        records.append(row)
    if records:
        return Observations(
            *(np.stack([row[key] for row in records]) for key in OBSERVATION_FIELDS)
        )
    sample = observe_history(
        times[:1], STATE_TYPE(*(value[:1] for value in history)), p, times[:1], spec
    )
    return Observations(
        *(np.empty((0, *value.shape[1:]), dtype=value.dtype) for value in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    return prior.ensemble_voltage(base_state(state), base_layout(layout), base_spec(spec), time)


def summarize(history, diagnostics, spec):
    return prior.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        network_transport_law=process.LAW_ID,
        network_transport_accounting=ACCOUNTING,
        network_transport_ids=[row.id for row in spec.model.network_transporters],
        network_transfer_direction="outward positive",
        network_drive="explicit signed maintained work; no direct ATP demand",
        network_heat=(
            "external work minus actual chemical/electrical transfer work; native diagnostic unused"
        ),
        network_final_supplied_work_pJ=float(np.sum(history.network_supplied_work_pJ[-1])),
        claim_scope=(
            "synthetic None-energy species-preserving configured transport; "
            "no native whole-tissue or GPU claim"
        ),
    )
