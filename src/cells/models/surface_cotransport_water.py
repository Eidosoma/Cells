"""Shared salt, water and finite-energy evolution with once-owned transfers."""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_cotransport_water_spec import MODEL_ID, cotransport_spec, water_spec
from cells.models import surface_cotransport as transport
from cells.models import surface_energy_water as prior
from cells.models import surface_tissue as passive
from cells.numerics import surface_field as field
from cells.processes import cotransport

OBSERVER_ID = "resolved_cotransport_finite_energy_water_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_ions_pools_bounded_water_and_cotransport_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
BATCH_CAPACITIES = transport.BATCH_CAPACITIES
EXTRA_AXES = transport.EXTRA_AXES
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("CotransportWaterState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "CotransportWaterLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            *(k for k in transport.LAYOUT_TYPE._fields if k not in prior.LAYOUT_TYPE._fields),
        )
    ],
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *transport.READOUTS)
Observations = make_dataclass(
    "CotransportWaterObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
DIAGNOSTICS = transport.DIAGNOSTICS | dict(
    water_local="max_cell_water_balance_error_pL",
    water_outside="max_outside_water_balance_error_pL",
    water_total="max_global_water_balance_error_pL",
)
parameters, physical_amounts = prior.parameters, prior.physical_amounts


class Values(NamedTuple):
    field: object
    derivative: object
    water_energy: object
    cotransport: object
    exchange: object
    valid: object


def water_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def water_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def transport_state(state):
    return transport.STATE_TYPE(*(getattr(state, k) for k in transport.STATE_TYPE._fields))


def transport_layout(p):
    return transport.LAYOUT_TYPE(*(getattr(p, k) for k in transport.LAYOUT_TYPE._fields))


def effective_transport_layout(state, p):
    return transport_layout(p)._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
    )


def batch_signature(model):
    return (*prior.batch_signature(model), *transport.batch_signature(model)[-1:])


def working_size(spec):
    return (
        prior.working_size(water_spec(spec))
        + (128 + 24 * len(spec.model.species_ids)) * spec.execution.cotransport_capacity
    )


def initial_values(spec):
    w, p = prior.initial_values(water_spec(spec))
    c, q = transport.initial_values(cotransport_spec(spec))
    values = q._asdict() | p._asdict()
    return (STATE_TYPE(*w, *(getattr(c, k) for k in EXTRA_AXES)), LAYOUT_TYPE(**values))


def domain_valid(state, p, active, *, xp=jnp):
    return prior.domain_valid(
        water_state(state), water_layout(p), active, xp=xp
    ) & transport.domain_valid(
        transport_state(state), effective_transport_layout(state, p), active, xp=xp
    )


def readouts(state, control, p, *, xp=jnp):
    # A single shared ionic/pool/field solve. Cotransport is a neutral chemical
    # route and requires no second field or pool calculation at the same state.
    base = prior.readouts(water_state(state), control, water_layout(p), xp=xp)
    current = effective_transport_layout(state, p)
    topology = transport.topology(current, xp=xp)
    concentrations = transport.concentrations(state, current, xp=xp)
    params = transport.cotransport_parameters(current)
    rates = cotransport.rates(concentrations, topology, params, control.cotransport, xp=xp)
    exchange = cotransport.exchange_rates(rates.cycle_fmol_s, topology, xp=xp)
    n = p.active.size
    ordinary = base.derivative._replace(
        amount_increment=base.derivative.amount_increment + exchange.amount_fmol_s[:, :n],
        extracellular_amount_increment=base.derivative.extracellular_amount_increment
        + exchange.amount_fmol_s[:, n:],
    )
    derivative = STATE_TYPE(
        *ordinary, rates.cycle_fmol_s, rates.transported_fmol_s, rates.dissipated_power_pJ_s
    )
    valid = base.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= cotransport.domain_valid(concentrations, topology, params, control.cotransport, xp=xp)
    for value in (*derivative, *rates):
        valid &= xp.all(xp.isfinite(value))
    chemical, heat = xp.sum(rates.chemical_power_pJ_s), xp.sum(rates.dissipated_power_pJ_s)
    old = base.field
    updated = old.rates._replace(
        cell_rate_fmol_s=derivative.amount_increment,
        outside_rate_fmol_s=derivative.extracellular_amount_increment,
        membrane_flux_fmol_s=old.rates.membrane_flux_fmol_s
        - transport.route_to_membrane(rates.transported_fmol_s, current, xp=xp),
        membrane_dissipation_pJ_s=old.rates.membrane_dissipation_pJ_s
        + transport.route_to_membrane(rates.dissipated_power_pJ_s, current, xp=xp),
        valid=valid,
    )
    field_value = old._replace(
        chemical_energy_rate_pJ_s=old.chemical_energy_rate_pJ_s + chemical,
        dissipation_pJ_s=old.dissipation_pJ_s + heat,
        energy_balance_pJ_s=old.energy_balance_pJ_s + chemical + heat,
        converged=valid,
        rates=updated,
    )
    return Values(field_value, derivative, base, rates, exchange, valid)


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


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

    m = spec.model
    compact = replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
            regeneration_capacity=len(m.regeneration_ports),
            cotransport_capacity=len(m.cotransporters),
        ),
    )
    state, p = initial_values(compact)
    table = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(compact.experiment.changes)):
            if not control_domain_valid(
                state, type(table)(*(v[i] for v in table)), p, p.active, xp=np
            ):
                raise ConfigError(
                    "Initial cotransport/water state or actual control outside domain"
                )


def check_steps(spec, steps, controls):
    # These inherited initial turnover and water-block ceilings complement
    # strict coupled trial rejection; they do not bound the full Jacobian.
    # Retain the complete event union: dropping either clock would incorrectly
    # reject observations at that component's accepted control boundaries.
    prior.check_steps(spec, steps, controls)
    transport.check_steps(spec, steps, controls)


def balances(state, p):
    accounted = water_state(state)._replace(
        membrane_transferred=state.membrane_transferred
        - transport.route_to_membrane(state.cotransport_transferred_fmol, p, xp=np)
    )
    result = prior.balances(accounted, water_layout(p))
    result["energy"] += np.sum(state.cotransport_dissipated_energy_pJ)
    result["cotransport_material"] = (
        state.cotransport_transferred_fmol
        - p.cotransport_stoichiometry * state.cotransport_cycles_fmol
    )
    result["cotransport_charge"] = np.sum(p.valence * state.cotransport_transferred_fmol, axis=0)
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = dict.fromkeys(DIAGNOSTICS.values(), 0.0)
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Invalid cotransport/finite-energy/water state, bounds or padding"
                )
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(row, p, xp=np)
            limits = dict(
                local=tol[:, None],
                outside=tol[:, None],
                total=tol,
                charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                electrode=field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                global_charge=3e-25,
                energy=passive.ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                pool_material=transport.prior.POOL_MATERIAL_ATOL_FMOL,
                adenylate=transport.prior.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=transport.prior.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=passive.ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                cotransport_material=tol[:, None],
                cotransport_charge=2e-12,
                water_local=prior.VOLUME_ATOL_PL,
                water_outside=prior.VOLUME_ATOL_PL,
                water_total=prior.VOLUME_ATOL_PL,
            )
            for name, value in balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[name]):
                    raise NumericalError("Cotransport/water accounting failed: " + name)
                key = DIAGNOSTICS[name]
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for key in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Cotransport/water dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Cotransport/water observations require accepted boundaries")
    table, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(table)(*(v[j] for v in table))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid cotransport/water observation state or control")
        old = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(v[None] for v in water_state(state))),
            water_layout(p),
            np.asarray([time]),
            water_spec(spec),
        )
        row = {k: v[0] for k, v in vars(old).items()}
        row.update({k: getattr(state, k) for k in EXTRA_AXES})
        row.update(
            cotransport_cycle_rate_fmol_s=value.cotransport.cycle_fmol_s,
            cotransport_affinity_J_mol=value.cotransport.affinity_J_mol,
            cotransport_dissipation_pJ_s=value.cotransport.dissipated_power_pJ_s,
            cotransport_availability=control.cotransport,
            membrane_flux_fmol_s=value.field.rates.membrane_flux_fmol_s,
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(value.field.energy_balance_pJ_s),
        )
        records.append(tuple(row[k] for k in OBSERVATION_FIELDS))
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    table = control_values(spec, [time])
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    value = readouts(state, type(table)(*(v[0] for v in table)), p, xp=np)
    if not value.valid:
        raise NumericalError("Cotransport/water ensemble state or control outside domain")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(history, diagnostics, water_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        cotransport_laws=[v.law for v in spec.model.cotransporters],
        scope=(
            "Manufactured neutral cotransport, neutral pool osmolytes and compliant volumes; "
            "fixed interfaces/capacitance"
        ),
    )
