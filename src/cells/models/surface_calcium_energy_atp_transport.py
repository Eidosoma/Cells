"""Native configurable ion transport sharing finite neutral ATP/ADP/Pi owners.

ATP -> ADP + Pi is internal to the membrane's cytosolic pool. The numeric
native standard energy equals that pool's transformed 1-M standard energy;
the source quotient is unchanged. Actual pool, ionic and electric energies
determine heat. Released fuel work is an internal diagnostic, never supply.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_atp_transport_spec import ACCOUNTING, MODEL_ID, base_spec
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel_model
from cells.models import surface_calcium_energy_hcn_extra as prior
from cells.models import surface_calcium_energy_transport as legacy
from cells.models import surface_tissue as surface
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes import betse_network_transport as process
from cells.processes import finite_energy as fuel
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = {
    "network_cycles_fmol": ["network_transport_slot"],
    "network_transferred_fmol": ["species", "network_transport_slot"],
    "network_dissipated_energy_pJ": ["network_transport_slot"],
    "network_fuel_work_pJ": ["network_transport_slot"],
    "network_chemical_work_pJ": ["network_transport_slot"],
    "network_electrical_work_pJ": ["network_transport_slot"],
    "network_gross_hydrolysis_fmol": ["network_transport_slot"],
    "network_gross_synthesis_fmol": ["network_transport_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumEnergyATPTransportState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyATPTransportLayout",
    [
        (key, object)
        for key in (
            *prior.LAYOUT_TYPE._fields,
            *("network_" + key for key in legacy.TOPOLOGY_FIELDS),
            *("network_" + key for key in process.Parameters._fields),
            "network_membrane",
            "network_stoichiometry",
            "network_density",
            "network_pool_owner",
        )
    ],
)
BATCH_CAPACITIES = legacy.BATCH_CAPACITIES
OBSERVER_ID = "owned_calcium_fuel_native_atp_transport@1"
STAGE_DOMAIN_ID = "actual_owned_ions_fuel_native_atp_conversion_nonnegative_heat@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
READOUTS = (
    "network_cycle_rate_fmol_s",
    "network_source_reaction_energy_J_mol",
    "network_physical_reaction_energy_J_mol",
    "network_fuel_hydrolysis_energy_J_mol",
    "network_physical_chemical_energy_J_mol",
    "network_physical_electrical_energy_J_mol",
    "network_chemical_power_pJ_s",
    "network_electrical_power_pJ_s",
    "network_fuel_power_pJ_s",
    "network_dissipation_pJ_s",
    "network_gross_hydrolysis_fmol_s",
    "network_gross_synthesis_fmol_s",
    "pool_gross_hydrolysis_fmol_s",
    "pool_gross_synthesis_fmol_s",
    "network_availability",
    "network_regulation",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyATPTransportObservations",
    [(key, np.ndarray) for key in OBSERVATION_FIELDS],
    frozen=True,
)
parameters, ENERGY_ATOL_PJ = prior.parameters, prior.ENERGY_ATOL_PJ
base_state, base_layout, base_control = legacy.base_state, legacy.base_layout, legacy.base_control
topology, network_parameters = legacy.topology, legacy.network_parameters
route_to_membrane, physical_amounts = legacy.route_to_membrane, legacy.physical_amounts
cytosol_amount, store_state, store_layout, er = (
    prior.cytosol_amount,
    prior.store_state,
    prior.store_layout,
    prior.er,
)
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
    network_fuel_power_pJ_s: object
    network_chemical_power_pJ_s: object
    network_electrical_power_pJ_s: object
    network_chemical_energy_J_mol: object
    network_electrical_energy_J_mol: object
    network_fuel_energy_J_mol: object
    network_reaction_energy_J_mol: object
    valid: object


def batch_signature(model):
    return (
        legacy.batch_signature(model),
        tuple(
            (row.drive.kind, row.drive.pool_id, row.drive.atp_per_cycle)
            for row in model.network_transporters
        ),
    )


def working_size(spec):
    # Include the three fuel substrate rows and both directional ledgers before
    # allocating padded state/topology. This remains a conservative byte bound.
    x = spec.execution
    return legacy.working_size(spec) + 8 * (
        12 * (x.capacity + x.extracellular_capacity) + 32 * x.network_transport_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(base_spec(spec))
    rows, count = spec.model.network_transporters, spec.execution.network_transport_capacity
    patch, owner, density = np.zeros(count, int), np.zeros(count, int), np.zeros(count)
    names = [row.id for row in spec.model.membranes]
    for i, row in enumerate(rows):
        patch[i] = names.index(row.membrane_id)
        owner[i], density[i] = p.membrane_cell[patch[i]], row.density_multiplier
    t, q = process.bind(
        [row.configuration for row in rows],
        (*spec.model.species_ids, *fuel.SPECIES),
        np.r_[p.valence[:, 0].astype(int), 0, 0, 0],
        p.membrane_cell[patch[: len(rows)]],
        p.active.size + p.membrane_outside[patch[: len(rows)]],
        np.r_[p.active, p.outside_active],
        area_m2=p.membrane_area[patch[: len(rows)]],
        temperature_K=spec.model.temperature_K,
        route_capacity=count,
    )
    nu = np.zeros((len(spec.model.species_ids), count))
    for sign, terms in ((-1, t.reactants), (1, t.products)):
        for term in range(terms.species.shape[0]):
            for route in range(count):
                if terms.outside[term, route]:
                    nu[terms.species[term, route], route] += sign * terms.coefficient[term, route]
    flat = (*t[:5], *t.reactants, *t.products, *t.influencers, *q)
    extra = [
        np.zeros_like(nu) if key == "network_transferred_fmol" else np.zeros(count)
        for key in EXTRA_AXES
    ]
    return STATE_TYPE(*state, *extra), LAYOUT_TYPE(*p, *flat, patch, nu, density, owner)


def concentrations(state, p, *, xp):
    """A native substrate view, with no extra physical inventory or fuel exterior."""
    ionic = legacy.concentrations(state, p, xp=xp)
    amount = fuel_model.energy_amounts(state, p)
    internal = xp.where(p.active, amount / p.volume, 0.0)
    fuel_rows = xp.concatenate((internal, xp.zeros((3, p.outside_active.size))), axis=-1)
    return xp.concatenate((ionic, fuel_rows), axis=0)


def pool_routes(p):
    return fuel.Routes(p.network_pool_owner, p.network_active)


def route_pool_exchange(cycles, p, *, xp):
    return fuel.exchange_rates(
        cycles,
        pool_routes(p),
        xp.zeros((0,)),
        fuel.Routes(xp.zeros((0,), dtype=int), xp.zeros((0,), dtype=bool)),
        fuel_model.pool_parameters(p, xp=xp),
        xp=xp,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(base_state(state), base_layout(p), active, xp=xp)
    for key in EXTRA_AXES:
        value = getattr(state, key)
        supported = p.network_active
        if key == "network_transferred_fmol":
            supported = supported & (p.network_stoichiometry != 0)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
    for key in (
        "network_dissipated_energy_pJ",
        "network_gross_hydrolysis_fmol",
        "network_gross_synthesis_fmol",
    ):
        valid &= xp.all(getattr(state, key) >= 0)
    valid &= xp.all(
        xp.abs(state.network_transferred_fmol - p.network_stoichiometry * state.network_cycles_fmol)
        <= calcium.chemistry.ROUND_ATOL
    )
    valid &= xp.all(
        xp.abs(
            state.network_chemical_work_pJ
            + state.network_electrical_work_pJ
            + state.network_dissipated_energy_pJ
            - state.network_fuel_work_pJ
        )
        <= 3e-12
    )
    valid &= xp.all(
        xp.abs(
            state.network_cycles_fmol
            - state.network_gross_hydrolysis_fmol
            + state.network_gross_synthesis_fmol
        )
        <= fuel_model.POOL_MATERIAL_ATOL_FMOL
    )
    valid &= xp.all(p.network_reversible == p.network_active)
    valid &= xp.all(
        xp.where(
            p.network_active,
            (p.network_pool_owner == p.membrane_cell[p.network_membrane])
            & (
                p.network_standard_free_energy_J_mol
                == p.energy_delta_g0_J_mol[p.network_pool_owner]
            ),
            p.network_pool_owner == 0,
        )
    )
    return valid


def transfer_energies(c, voltage, p, *, xp):
    t, nu = topology(p), p.network_stoichiometry
    ionic = c[: p.valence.shape[0]]
    inside, outside = xp.take(ionic, t.inside, axis=-1), xp.take(ionic, t.outside, axis=-1)
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
    chemical, electrical = transfer_energies(c, voltage, p, xp=xp)
    hydrolysis = xp.where(
        p.network_active, w.energy.hydrolysis_free_energy_J_mol[p.network_pool_owner], 0.0
    )
    reaction = hydrolysis + chemical + electrical
    chemical_power, electrical_power = (1e-3 * extent * x for x in (chemical, electrical))
    released = -1e-3 * extent * hydrolysis
    heat = -1e-3 * extent * reaction
    route_exchange = route_pool_exchange(extent, p, xp=xp)
    exchange = fuel.ExchangeRates(*(a + b for a, b in zip(w.exchange, route_exchange, strict=True)))
    pool_power = xp.sum(fuel.chemical_power_pJ_s(route_exchange.amount_fmol_s, w.energy, xp=xp))
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
    safe = xp.where(t.compartment_active, c[: p.valence.shape[0]], 1.0)
    chemical_rate = (
        1e-3 * R * p.temperature * xp.sum(xp.log(safe) * xp.concatenate((cell, outside), axis=1))
    )
    electric_rate = 1e12 * xp.sum(p.membrane_capacitance * rates.membrane_voltage_V * dvm)
    derivative = STATE_TYPE(
        *parent_rate._replace(
            amount_increment=parent_rate.amount_increment + cell,
            extracellular_amount_increment=parent_rate.extracellular_amount_increment + outside,
            chemical_amount_increment=parent_rate.chemical_amount_increment + chemical_amount,
            energy_amount_increment_fmol=exchange.amount_fmol_s,
        ),
        extent,
        transported,
        heat,
        released,
        chemical_power,
        electrical_power,
        xp.maximum(extent, 0),
        xp.maximum(-extent, 0),
    )
    valid = w.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= process.domain_valid(
        c, voltage, t, params, control.network_transport, p.network_density, xp=xp
    )
    valid &= xp.all(heat >= 0)
    valid &= xp.all(
        xp.abs(native.source_reaction_energy_J_mol - reaction) <= 3e-9 + 3e-12 * xp.abs(reaction)
    )
    for value in (
        *derivative,
        pool_power,
        chemical_rate,
        electric_rate,
        chemical,
        electrical,
        hydrolysis,
        reaction,
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
        + pool_power
        + xp.sum(heat),
        converged=valid,
    )
    return Values(
        v,
        derivative,
        w.kinetic,
        w.energy,
        w.regeneration,
        exchange,
        native,
        heat,
        released,
        chemical_power,
        electrical_power,
        chemical,
        electrical,
        hydrolysis,
        reaction,
        valid,
    )


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, x, xp.nan) for x in value.derivative))


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
        if not control_domain_valid(state, type(table)(*(x[i] for x in table)), p, p.active, xp=np):
            raise ConfigError("Initial ATP transport has invalid owned fuel/physical dissipation")


def check_steps(spec, steps, controls):
    from cells.core.schedule import control_values

    prior.check_steps(replace(base_spec(spec), experiment=spec.experiment), steps, controls)
    state, p = initial_values(spec)
    ci, co = physical_amounts(state, p)
    amount = np.concatenate((ci, co), axis=-1)
    safe = np.where(topology(p).compartment_active, amount, 1.0)
    fuel_amount = np.where(p.active, fuel_model.energy_amounts(state, p), 1.0)
    table = control_values(spec, [change.time for change in spec.experiment.changes])
    for i in range(len(table.network_transport)):
        value = readouts(state, type(table)(*(x[i] for x in table)), p, xp=np)
        gross = np.abs(value.derivative.network_transferred_fmol)
        turnover = ordered_scatter(gross, np.zeros_like(amount), (p.network_inside,), xp=np)
        turnover += ordered_scatter(gross, np.zeros_like(amount), (p.network_outside,), xp=np)
        ionic = np.max(np.where(topology(p).compartment_active, turnover / safe, 0), initial=0)
        pool_gross = value.exchange.gross_hydrolysis_fmol_s + value.exchange.gross_synthesis_fmol_s
        pool = np.max(np.where(p.active, pool_gross / np.min(fuel_amount, axis=0), 0), initial=0)
        if (
            not value.valid
            or not np.isfinite([ionic, pool]).all()
            or np.max(steps, initial=0) * ionic > legacy.MAX_INITIAL_ION_CHANGE_PER_STEP
            or np.max(steps, initial=0) * pool > fuel_model.MAX_INITIAL_POOL_CHANGE_PER_STEP
        ):
            raise ConfigError("Initial gross ionic/fuel turnover requires a smaller valid RK4 step")


def accounting_state(state, p):
    return base_state(state)._replace(
        membrane_transferred=state.membrane_transferred
        + route_to_membrane(state.network_transferred_fmol, p, xp=np),
        membrane_dissipated_energy_pJ=state.membrane_dissipated_energy_pJ
        + route_to_membrane(state.network_dissipated_energy_pJ, p, xp=np),
    )


def balances(state, p):
    # Retain all parent ionic/charge/chemical/fuel balances. Extend its explicit
    # pump extent accounting by the actual configured pool reaction, once.
    result = prior.balances(accounting_state(state, p), base_layout(p))
    extra = route_pool_exchange(state.network_cycles_fmol, p, xp=np).amount_fmol_s
    result["pool_material"] -= extra
    result["pool_energy"] += ordered_scatter(
        state.network_fuel_work_pJ, np.zeros_like(p.volume), (p.network_pool_owner,), xp=np
    )
    result.update(
        network_material=state.network_transferred_fmol
        - p.network_stoichiometry * state.network_cycles_fmol,
        network_physical_work=state.network_chemical_work_pJ
        + state.network_electrical_work_pJ
        + state.network_dissipated_energy_pJ
        - state.network_fuel_work_pJ,
        network_gross=state.network_cycles_fmol
        - state.network_gross_hydrolysis_fmol
        + state.network_gross_synthesis_fmol,
    )
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(x[i] for x in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid finite ATP transport state/ledger")
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
            charge += surface.charge_increment(row, p, xp=np)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=fuel_model.field.CHARGE_ATOL_C
                + fuel_model.field.CHARGE_RTOL * np.abs(charge),
                electrode=fuel_model.field.CHARGE_ATOL_C,
                global_charge=3e-25,
                energy=ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                chemical_ledger=calcium.chemistry.ROUND_ATOL,
                ownership=calcium.chemistry.ROUND_ATOL,
                pool_material=fuel_model.POOL_MATERIAL_ATOL_FMOL,
                adenylate=fuel_model.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=fuel_model.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                network_material=tolerance[:, None],
                network_physical_work=3e-12,
                network_gross=fuel_model.POOL_MATERIAL_ATOL_FMOL,
            )
            for key, value in balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Finite ATP transport accounting failed: " + key)
                name = "max_" + key + "_error"
                diagnostics[name] = max(
                    diagnostics.get(name, 0.0), float(np.max(np.abs(value), initial=0))
                )
    monotone = [key for key in STATE_AXES if key.endswith("_dissipated_energy_pJ")]
    for key in (*monotone, "network_gross_hydrolysis_fmol", "network_gross_synthesis_fmol"):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Dissipation/gross turnover cannot decrease: " + key)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(x) for x in layout))
    requested = np.asarray(requested, dtype=float)
    if any(time not in times for time in requested):
        raise ConfigError("ATP transport observations require accepted times")
    observed = prior.observe_history(
        times, base_state(history), base_layout(p), requested, base_spec(spec)
    )
    table, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        index = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(x[index] for x in history))
        value = readouts(state, type(table)(*(x[j] for x in table)), p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid ATP transport observation state/control")
        row = {key: x[j] for key, x in vars(observed).items()}
        row.update({key: getattr(state, key) for key in EXTRA_AXES})
        row.update(
            membrane_flux_fmol_s=value.field.rates.membrane_flux_fmol_s,
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            pool_internal_transfer_balance_pJ=balances(state, p)["pool_energy"],
            energy_balance_pJ_s=np.atleast_1d(value.field.energy_balance_pJ_s),
            network_cycle_rate_fmol_s=value.network.extent_fmol_s,
            network_source_reaction_energy_J_mol=value.network.source_reaction_energy_J_mol,
            network_physical_reaction_energy_J_mol=value.network_reaction_energy_J_mol,
            network_fuel_hydrolysis_energy_J_mol=value.network_fuel_energy_J_mol,
            network_physical_chemical_energy_J_mol=value.network_chemical_energy_J_mol,
            network_physical_electrical_energy_J_mol=value.network_electrical_energy_J_mol,
            network_chemical_power_pJ_s=value.network_chemical_power_pJ_s,
            network_electrical_power_pJ_s=value.network_electrical_power_pJ_s,
            network_fuel_power_pJ_s=value.network_fuel_power_pJ_s,
            network_dissipation_pJ_s=value.network_heat_pJ_s,
            network_gross_hydrolysis_fmol_s=np.maximum(value.network.extent_fmol_s, 0),
            network_gross_synthesis_fmol_s=np.maximum(-value.network.extent_fmol_s, 0),
            pool_gross_hydrolysis_fmol_s=value.exchange.gross_hydrolysis_fmol_s,
            pool_gross_synthesis_fmol_s=value.exchange.gross_synthesis_fmol_s,
            network_availability=table.network_transport[j],
            network_regulation=value.network.regulation,
        )
        records.append(row)
    if records:
        return Observations(
            *(np.stack([row[key] for row in records]) for key in OBSERVATION_FIELDS)
        )
    sample = observe_history(times[:1], STATE_TYPE(*(x[:1] for x in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *x.shape[1:]), dtype=x.dtype) for x in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    return prior.ensemble_voltage(base_state(state), base_layout(layout), base_spec(spec), time)


def summarize(history, diagnostics, spec):
    return prior.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        network_transport_law=process.LAW_ID,
        network_transport_accounting=ACCOUNTING,
        network_transport_ids=[row.id for row in spec.model.network_transporters],
        network_fuel_owners=[row.drive.pool_id for row in spec.model.network_transporters],
        network_fuel_stoichiometry=dict(ATP=-1, ADP=1, Pi=1),
        network_transfer_direction="outward positive",
        network_standard_states_mM=dict(ionic=1.0, transformed_fuel=fuel.STANDARD_STATE_mM),
        network_drive="live finite pool hydrolysis; released fuel work is internal",
        network_final_gross_hydrolysis_fmol=float(
            np.sum(history.network_gross_hydrolysis_fmol[-1])
        ),
        network_final_gross_synthesis_fmol=float(np.sum(history.network_gross_synthesis_fmol[-1])),
        claim_scope="synthetic native-subset finite-fuel coupling; no whole-native or GPU claim",
    )
