"""Fixed-volume finite-energy tissue with explicit neutral symport ledgers."""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_cotransport_spec import MODEL_ID, energy_spec, route_stoichiometry
from cells.models import surface_energy as prior
from cells.models import surface_tissue as passive
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import cotransport

OBSERVER_ID = "resolved_cotransport_finite_energy_accepted_grid_readouts@1"
STAGE_DOMAIN_ID = "positive_ions_finite_pools_and_actual_cotransport_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "cotransport_capacity")
EXTRA_AXES = {
    "cotransport_cycles_fmol": ["cotransport_slot"],
    "cotransport_transferred_fmol": ["species", "cotransport_slot"],
    "cotransport_dissipated_energy_pJ": ["cotransport_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCotransportState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCotransportLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "cotransport_valence",
            "cotransport_active",
            "cotransport_membrane",
            "cotransport_stoichiometry",
            "cotransport_capacity_fmol_s",
        )
    ],
)
READOUTS = (
    "cotransport_cycle_rate_fmol_s",
    "cotransport_affinity_J_mol",
    "cotransport_dissipation_pJ_s",
    "cotransport_availability",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCotransportObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters, physical_amounts = prior.parameters, prior.physical_amounts
MAX_INITIAL_ION_CHANGE_PER_STEP = 0.05
DIAGNOSTICS = dict(
    local="max_balance_error_fmol",
    outside="max_extracellular_balance_error_fmol",
    total="max_global_balance_error_fmol",
    charge="max_capacitor_charge_error_C",
    electrode="max_electrode_charge_error_C",
    global_charge="max_global_charge_error_C",
    energy="max_energy_balance_error_pJ",
    reservoir_work="max_reservoir_work_error_pJ",
    electrode_work="max_electrode_work_error_pJ",
    pool_material="max_pool_material_error_fmol",
    adenylate="max_adenylate_error_fmol",
    phosphorus="max_phosphorus_error_fmol",
    pool_energy="max_pool_internal_transfer_error_pJ",
    regeneration_work="max_regeneration_work_error_pJ",
    cotransport_material="max_cotransport_material_error_fmol",
    cotransport_charge="max_cotransport_charge_error_equivalent_fmol",
)


class Values(NamedTuple):
    field: object
    derivative: object
    energy: object
    cotransport: object
    exchange: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def prior_control(control):
    from cells.core.surface_energy_spec import Control

    return Control(*(getattr(control, k) for k in Control._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple(
            (r.id, r.membrane_id, r.law, r.roles.potassium, r.roles.chloride, r.roles.sodium)
            for r in model.cotransporters
        ),
    )


def working_size(spec):
    return (
        prior.working_size(energy_spec(spec))
        + (128 + 24 * len(spec.model.species_ids)) * spec.execution.cotransport_capacity
    )


def topology(p, *, xp=np):
    patch, n = p.cotransport_membrane, p.active.size
    return cotransport.Topology(
        p.cotransport_valence,
        xp.concatenate((p.active, p.outside_active)),
        p.membrane_cell[patch],
        n + p.membrane_outside[patch],
        p.cotransport_stoichiometry,
        p.cotransport_active,
    )


def cotransport_parameters(p):
    return cotransport.Parameters(p.cotransport_capacity_fmol_s, p.temperature)


def concentrations(state, p, *, xp):
    inside, outside = physical_amounts(state, p)
    return xp.concatenate((inside / p.volume, outside / p.extracellular_volume), axis=-1)


def route_to_membrane(value, p, *, xp):
    return ordered_scatter(
        value,
        xp.zeros(value.shape[:-1] + p.membrane_active.shape, dtype=value.dtype),
        (p.cotransport_membrane,),
        xp=xp,
    )


def initial_values(spec):
    state, p = prior.initial_values(energy_spec(spec))
    r, s = spec.execution.cotransport_capacity, len(spec.model.species_ids)
    values = p._asdict() | dict(
        cotransport_valence=np.asarray(spec.model.valence, dtype=np.int64),
        cotransport_active=np.arange(r) < len(spec.model.cotransporters),
        cotransport_membrane=np.zeros(r, np.int64),
        cotransport_stoichiometry=np.zeros((s, r), np.int64),
        cotransport_capacity_fmol_s=np.zeros(r),
    )
    patches = {patch.id: i for i, patch in enumerate(spec.model.membranes)}
    for i, route in enumerate(spec.model.cotransporters):
        values["cotransport_membrane"][i] = patches[route.membrane_id]
        values["cotransport_stoichiometry"][:, i] = route_stoichiometry(route, spec.model)
        values["cotransport_capacity_fmol_s"][i] = route.capacity_fmol_per_s
    layout = LAYOUT_TYPE(**values)
    cotransport.validate_topology(topology(layout))
    cotransport.validate_parameters(cotransport_parameters(layout), topology(layout))
    return STATE_TYPE(*state, np.zeros(r), np.zeros((s, r)), np.zeros(r)), layout


def readouts(state, control, p, *, xp=jnp):
    old = prior.readouts(prior_state(state), prior_control(control), prior_layout(p), xp=xp)
    t = topology(p, xp=xp)
    c = concentrations(state, p, xp=xp)
    rates = cotransport.rates(c, t, cotransport_parameters(p), control.cotransport, xp=xp)
    exchange = cotransport.exchange_rates(rates.cycle_fmol_s, t, xp=xp)
    n = p.active.size
    ionic = old.derivative._replace(
        amount_increment=old.derivative.amount_increment + exchange.amount_fmol_s[:, :n],
        extracellular_amount_increment=old.derivative.extracellular_amount_increment
        + exchange.amount_fmol_s[:, n:],
    )
    derivative = STATE_TYPE(
        *ionic, rates.cycle_fmol_s, rates.transported_fmol_s, rates.dissipated_power_pJ_s
    )
    chemical, heat = xp.sum(rates.chemical_power_pJ_s), xp.sum(rates.dissipated_power_pJ_s)
    valid = old.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= cotransport.domain_valid(c, t, cotransport_parameters(p), control.cotransport, xp=xp)
    for v in (*derivative, chemical, heat):
        valid &= xp.all(xp.isfinite(v))
    field_rates = old.field.rates._replace(
        cell_rate_fmol_s=derivative.amount_increment,
        outside_rate_fmol_s=derivative.extracellular_amount_increment,
        membrane_flux_fmol_s=old.field.rates.membrane_flux_fmol_s
        - route_to_membrane(rates.transported_fmol_s, p, xp=xp),
        membrane_dissipation_pJ_s=old.field.rates.membrane_dissipation_pJ_s
        + route_to_membrane(rates.dissipated_power_pJ_s, p, xp=xp),
        valid=valid,
    )
    v = old.field._replace(
        chemical_energy_rate_pJ_s=old.field.chemical_energy_rate_pJ_s + chemical,
        dissipation_pJ_s=old.field.dissipation_pJ_s + heat,
        energy_balance_pJ_s=old.field.energy_balance_pJ_s + chemical + heat,
        converged=valid,
        rates=field_rates,
    )
    return Values(v, derivative, old, rates, exchange, valid)


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= xp.all(p.valence[:, 0] == p.cotransport_valence)
    supported = p.cotransport_active & (p.cotransport_capacity_fmol_s > 0)
    for key in EXTRA_AXES:
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
    valid &= xp.all(
        xp.where(p.cotransport_stoichiometry != 0, True, state.cotransport_transferred_fmol == 0)
    )
    valid &= cotransport.exchange_domain_valid(
        state.cotransport_cycles_fmol, topology(p, xp=xp), xp=xp
    )
    return valid


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
    from cells.core.schedule import control_values

    table = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(compact.experiment.changes)):
            if not control_domain_valid(
                state, type(table)(*(v[i] for v in table)), p, p.active, xp=np
            ):
                raise ConfigError(
                    "Initial cotransport/finite-energy ionic state or control outside domain"
                )


def check_steps(spec, steps, controls):
    prior.check_steps(spec, steps, controls)
    state, p = initial_values(spec)
    t = topology(p)
    amounts = np.concatenate(physical_amounts(state, p), axis=-1)
    safe = np.where(t.compartment_active, amounts, 1)
    from cells.core.schedule import control_values

    table = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(spec.experiment.changes)):
        value = readouts(state, type(table)(*(v[i] for v in table)), p, xp=np)
        gross = np.abs(value.cotransport.transported_fmol_s)
        target = np.zeros_like(amounts)
        turnover = ordered_scatter(gross, target, (t.inside,), xp=np) + ordered_scatter(
            gross, target, (t.outside,), xp=np
        )
        fraction = np.max(np.where(t.compartment_active, turnover / safe, 0), initial=0)
        if (
            not np.isfinite(fraction)
            or np.max(steps, initial=0) * fraction > MAX_INITIAL_ION_CHANGE_PER_STEP
        ):
            raise ConfigError("Initial gross cotransport requires a smaller RK4 step")


def balances(state, p):
    # Legacy membrane transfer is outward-positive; cotransport is inward-positive.
    accounted = prior_state(state)._replace(
        membrane_transferred=state.membrane_transferred
        - route_to_membrane(state.cotransport_transferred_fmol, p, xp=np)
    )
    result = prior.balances(accounted, prior_layout(p))
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
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Invalid cotransport/finite-energy state, exhaustion or padding"
                )
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(row, p, xp=np)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                electrode=field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                global_charge=3e-25,
                energy=passive.ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                pool_material=prior.POOL_MATERIAL_ATOL_FMOL,
                adenylate=prior.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=prior.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=passive.ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                cotransport_material=tolerance[:, None],
                cotransport_charge=2e-12,
            )
            for key, value in balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Cotransport accounting failed: " + key)
                name = DIAGNOSTICS[key]
                diagnostics[name] = max(
                    diagnostics.get(name, 0), float(np.max(np.abs(value), initial=0))
                )
    for key in (name for name in STATE_AXES if name.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError(
                "Cotransport/finite-energy dissipation cannot be negative or decrease"
            )
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Cotransport observations require accepted integration boundaries")
    controls = control_values(spec, requested)
    records = []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid cotransport observation state/control")
        old = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(np.asarray([v]) for v in prior_state(state))),
            prior_layout(p),
            np.asarray([time]),
            energy_spec(spec),
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
    value = readouts(
        STATE_TYPE(*(np.asarray(v) for v in state)), type(table)(*(v[0] for v in table)), p, xp=np
    )
    if not value.valid:
        raise NumericalError("Cotransport ensemble endpoint outside domain")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(history, diagnostics, energy_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        cotransport_laws=[r.law for r in spec.model.cotransporters],
        scope="Manufactured electroneutral cotransport with fixed-volume finite-energy tissue",
    )
