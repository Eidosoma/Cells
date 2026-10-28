"""Owned calcium and finite ATP with reversible native configured transport.

The supported subset preserves every ionic species. Each route's declared
maintained work is external; it never silently consumes the cellular ATP pool.
Native source constants match the explicitly declared Cells SI constants.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_transport_spec import ACCOUNTING, MODEL_ID, base_spec
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_calcium_energy_hcn_extra as prior
from cells.models import surface_tissue as surface
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes import betse_network_transport as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = {
    "network_cycles_fmol": ["network_transport_slot"],
    "network_transferred_fmol": ["species", "network_transport_slot"],
    "network_dissipated_energy_pJ": ["network_transport_slot"],
    "network_supplied_work_pJ": ["network_transport_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumEnergyTransportState", [(k, object) for k in STATE_AXES])
TOPOLOGY_FIELDS = (
    *process.Topology._fields[:5],
    *(
        f"{group}_{key}"
        for group, cls in (
            ("reactants", process.Terms),
            ("products", process.Terms),
            ("influencers", process.Influencers),
        )
        for key in cls._fields
    ),
)
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyTransportLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            *("network_" + k for k in TOPOLOGY_FIELDS),
            *("network_" + k for k in process.Parameters._fields),
            "network_membrane",
            "network_stoichiometry",
            "network_density",
            "network_supplied_energy_J_mol",
        )
    ],
)
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "network_transport_capacity")
OBSERVER_ID = "resolved_calcium_energy_transport_accepted_grid@1"
STAGE_DOMAIN_ID = "owned_calcium_finite_atp_reversible_native_transport_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
READOUTS = (
    "network_cycle_rate_fmol_s",
    "network_reaction_energy_J_mol",
    "network_dissipation_pJ_s",
    "network_supplied_power_pJ_s",
    "network_availability",
    "network_regulation",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyTransportObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
MAX_INITIAL_ION_CHANGE_PER_STEP = 0.05
parameters = prior.parameters
ENERGY_ATOL_PJ = prior.ENERGY_ATOL_PJ
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
    valid: object


def base_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def base_layout(p):
    # The HCN layout tag selects the 56-law parent rather than an older catalog.
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def base_control(control):
    from cells.core.surface_calcium_energy_spec import Control

    return Control(*(getattr(control, k) for k in Control._fields))


def topology(p):
    groups = [
        cls(*(getattr(p, f"network_{group}_{k}") for k in cls._fields))
        for group, cls in (
            ("reactants", process.Terms),
            ("products", process.Terms),
            ("influencers", process.Influencers),
        )
    ]
    return process.Topology(
        *(getattr(p, "network_" + k) for k in process.Topology._fields[:5]), *groups
    )


def network_parameters(p):
    return process.Parameters(*(getattr(p, "network_" + k) for k in process.Parameters._fields))


def batch_signature(model):
    routes = model.network_transporters
    shapes = tuple(
        max(
            (
                len(r.configuration.get(k) or []) if isinstance(r.configuration.get(k), list) else 0
                for r in routes
            ),
            default=0,
        )
        for k in ("reactants", "products")
    )
    influencers = max(
        (
            sum(
                len(r.configuration.get(k) or []) if isinstance(r.configuration.get(k), list) else 0
                for k in ("transporter activators", "transporter inhibitors")
            )
            for r in routes
        ),
        default=0,
    )
    return (
        prior.batch_signature(model),
        tuple((r.id, r.membrane_id) for r in routes),
        shapes,
        influencers,
    )


def working_size(spec):
    # Refuse oversized plans before allocating padded layout/state arrays.
    _, _, shapes, influencers = batch_signature(spec.model)
    species, x = len(spec.model.species_ids), spec.execution
    extra = 256 + 16 * (species + x.capacity + x.extracellular_capacity)
    extra += x.network_transport_capacity * (256 + 32 * species + 64 * (sum(shapes) + influencers))
    return prior.working_size(base_spec(spec)) + 8 * extra


def initial_values(spec):
    state, p = prior.initial_values(base_spec(spec))
    routes, count = spec.model.network_transporters, spec.execution.network_transport_capacity
    patch = np.zeros(count, dtype=int)
    rho, work = np.zeros(count), np.zeros(count)
    names = [m.id for m in spec.model.membranes]
    for i, route in enumerate(routes):
        patch[i], rho[i], work[i] = (
            names.index(route.membrane_id),
            route.density_multiplier,
            route.drive.supplied_energy_J_per_mol,
        )
    t, q = process.bind(
        [r.configuration for r in routes],
        spec.model.species_ids,
        np.asarray(p.valence[:, 0], dtype=int),
        p.membrane_cell[patch[: len(routes)]],
        p.active.size + p.membrane_outside[patch[: len(routes)]],
        np.r_[p.active, p.outside_active],
        area_m2=p.membrane_area[patch[: len(routes)]],
        temperature_K=spec.model.temperature_K,
        route_capacity=count,
    )
    nu = np.zeros((len(spec.model.species_ids), count))
    for sign, terms in ((-1, t.reactants), (1, t.products)):
        for term in range(terms.species.shape[0]):
            for r in range(count):
                if terms.outside[term, r]:
                    nu[terms.species[term, r], r] += sign * terms.coefficient[term, r]
    flat = (*t[:5], *t.reactants, *t.products, *t.influencers, *q)
    return STATE_TYPE(
        *state, np.zeros(count), np.zeros_like(nu), np.zeros(count), np.zeros(count)
    ), LAYOUT_TYPE(*p, *flat, patch, nu, rho, work)


def route_to_membrane(value, p, *, xp):
    return ordered_scatter(
        value,
        xp.zeros(value.shape[:-1] + p.membrane_active.shape, dtype=value.dtype),
        (p.network_membrane,),
        xp=xp,
    )


def accounting_state(state, p, *, xp=np):
    return base_state(state)._replace(
        membrane_transferred=state.membrane_transferred
        + route_to_membrane(state.network_transferred_fmol, p, xp=xp),
        membrane_dissipated_energy_pJ=state.membrane_dissipated_energy_pJ
        + route_to_membrane(state.network_dissipated_energy_pJ, p, xp=xp),
    )


def physical_amounts(state, p, *, xp=np):
    return (
        prior.cytosol_amount(base_state(state), base_layout(p), xp=xp),
        p.extracellular_amount_reference + state.extracellular_amount_increment,
    )


def concentrations(state, p, *, xp):
    inner, outer = physical_amounts(state, p, xp=xp)
    return xp.concatenate(
        (
            xp.where(p.active, inner / p.volume, 0.0),
            xp.where(p.outside_active, outer / p.extracellular_volume, 0.0),
        ),
        axis=-1,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(base_state(state), base_layout(p), active, xp=xp)
    for name in EXTRA_AXES:
        value = getattr(state, name)
        supported = (
            p.network_active & (p.network_stoichiometry != 0)
            if name == "network_transferred_fmol"
            else p.network_active
        )
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
    valid &= xp.all(state.network_dissipated_energy_pJ >= -calcium.chemistry.ROUND_ATOL)
    valid &= xp.all(
        xp.abs(state.network_transferred_fmol - p.network_stoichiometry * state.network_cycles_fmol)
        <= calcium.chemistry.ROUND_ATOL
    )
    valid &= xp.all(
        xp.abs(
            state.network_supplied_work_pJ
            - 1e-3 * p.network_supplied_energy_J_mol * state.network_cycles_fmol
        )
        <= 3e-12
    )
    return valid


def readouts(state, control, p, *, xp=jnp):
    q = base_layout(p)
    w = prior.readouts(base_state(state), base_control(control), q, xp=xp)
    v, r, dr = w.field, w.field.rates, w.derivative
    c, t, parameters = concentrations(state, p, xp=xp), topology(p), network_parameters(p)
    voltage = xp.where(p.network_active, r.membrane_voltage_V[p.network_membrane], 0.0)
    native = process.rates(
        c, voltage, t, parameters, control.network_transport, p.network_density, xp=xp
    )
    extent = native.extent_fmol_s
    transported = p.network_stoichiometry * extent
    heat = -1e-3 * extent * native.source_reaction_energy_J_mol
    work = 1e-3 * extent * p.network_supplied_energy_J_mol
    flux = route_to_membrane(transported, p, xp=xp)
    cell = -scatter(flux, dr.amount_increment, (p.membrane_cell,), xp=xp)
    outside = scatter(flux, dr.extracellular_amount_increment, (p.membrane_outside,), xp=xp)
    chemical = xp.stack(
        [
            (p.free_ion_selector @ cell[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = calcium.field._capacitor_solve(qdot, xp.zeros_like(qdot), surface.field_layout(q), xp=xp)
    n, a, b = p.active.size, p.membrane_cell, p.membrane_outside
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[n + b], 0.0)
    # Padded owners contribute exactly zero. No active concentration is floored.
    safe = xp.where(t.compartment_active, c, 1.0)
    chemical_power = (
        1e-3 * R * p.temperature * xp.sum(xp.log(safe) * xp.concatenate((cell, outside), axis=1))
    )
    electric_power = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    derivative = STATE_TYPE(
        *dr._replace(
            amount_increment=dr.amount_increment + cell,
            extracellular_amount_increment=dr.extracellular_amount_increment + outside,
            chemical_amount_increment=dr.chemical_amount_increment + chemical,
        ),
        extent,
        transported,
        heat,
        work,
    )
    valid = w.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= process.domain_valid(
        c, voltage, t, parameters, control.network_transport, p.network_density, xp=xp
    )
    # Native direct regulation can reverse a rate's thermodynamic direction;
    # preserve its algebra but reject that state even when availability is zero.
    valid &= xp.all(native.regulation >= 0) & xp.all(heat >= -1e-12)
    for value in (*derivative, chemical_power, electric_power, dvm):
        valid &= xp.all(xp.isfinite(value))
    r = r._replace(
        cell_rate_fmol_s=r.cell_rate_fmol_s + cell,
        outside_rate_fmol_s=r.outside_rate_fmol_s + outside,
        membrane_flux_fmol_s=r.membrane_flux_fmol_s + flux,
        membrane_current_A=r.membrane_current_A
        + CHARGE_PER_FMOL * xp.sum(p.valence * flux, axis=0),
        membrane_dissipation_pJ_s=r.membrane_dissipation_pJ_s + route_to_membrane(heat, p, xp=xp),
        valid=valid,
    )
    v = v._replace(
        rates=r,
        membrane_voltage_rate_V_s=v.membrane_voltage_rate_V_s + dvm,
        chemical_energy_rate_pJ_s=v.chemical_energy_rate_pJ_s + chemical_power,
        capacitor_energy_rate_pJ_s=v.capacitor_energy_rate_pJ_s + electric_power,
        dissipation_pJ_s=v.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=v.energy_balance_pJ_s
        + chemical_power
        + electric_power
        + xp.sum(heat - work),
        converged=valid,
    )
    return Values(
        v, derivative, w.kinetic, w.energy, w.regeneration, w.exchange, native, heat, work, valid
    )


def rhs(state, control, p, active, *, xp=jnp):
    w = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(w.valid, value, xp.nan) for value in w.derivative))


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
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(controls.network_transport)):
        if not control_domain_valid(
            state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
        ):
            raise ConfigError(
                "Initial network transport state/control is outside the coupled domain"
            )


def check_steps(spec, steps, controls):
    # Route-only events must survive every parent projection.
    prior.check_steps(replace(base_spec(spec), experiment=spec.experiment), steps, controls)
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    inner, outer = physical_amounts(state, p)
    amount = np.concatenate((inner, outer), axis=-1)
    t = topology(p)
    safe = np.where(t.compartment_active, amount, 1.0)
    table = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(table.network_transport)):
        w = readouts(state, type(table)(*(v[i] for v in table)), p, xp=np)
        gross = np.abs(w.derivative.network_transferred_fmol)
        turnover = ordered_scatter(
            gross, np.zeros_like(amount), (t.inside,), xp=np
        ) + ordered_scatter(gross, np.zeros_like(amount), (t.outside,), xp=np)
        fractional = np.max(np.where(t.compartment_active, turnover / safe, 0.0), initial=0)
        if (
            not np.isfinite(fractional)
            or np.max(steps, initial=0) * fractional > MAX_INITIAL_ION_CHANGE_PER_STEP
        ):
            raise ConfigError("Initial gross network transport requires a smaller RK4 step")


def balances(state, p):
    result = prior.balances(accounting_state(state, p), base_layout(p))
    result["energy"] -= np.sum(state.network_supplied_work_pJ)
    result["network_material"] = (
        state.network_transferred_fmol - p.network_stoichiometry * state.network_cycles_fmol
    )
    result["network_work"] = (
        state.network_supplied_work_pJ
        - 1e-3 * p.network_supplied_energy_J_mol * state.network_cycles_fmol
    )
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid coupled network transport state or ledger")
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + surface.charge_increment(row, p, xp=np)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=fuel.field.CHARGE_ATOL_C + fuel.field.CHARGE_RTOL * np.abs(charge),
                electrode=fuel.field.CHARGE_ATOL_C,
                global_charge=3e-25,
                energy=ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                chemical_ledger=calcium.chemistry.ROUND_ATOL,
                ownership=calcium.chemistry.ROUND_ATOL,
                pool_material=fuel.POOL_MATERIAL_ATOL_FMOL,
                adenylate=fuel.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=fuel.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                network_material=tolerance[:, None],
                network_work=3e-12,
            )
            for key, value in balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Coupled network transport accounting failed: " + key)
                name = "max_" + key + "_error"
                diagnostics[name] = max(
                    diagnostics.get(name, 0.0), float(np.max(np.abs(value), initial=0))
                )
    for key in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Dissipated energy cannot be negative or decrease: " + key)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Network transport observations require accepted times")
    observed = prior.observe_history(
        times, base_state(history), base_layout(p), requested, base_spec(spec)
    )
    controls, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Network transport observation domain invalid")
        row = {key: value[j] for key, value in vars(observed).items()}
        row.update({key: getattr(state, key) for key in EXTRA_AXES})
        row.update(
            membrane_flux_fmol_s=w.field.rates.membrane_flux_fmol_s,
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(w.field.energy_balance_pJ_s),
            network_cycle_rate_fmol_s=w.network.extent_fmol_s,
            network_reaction_energy_J_mol=w.network.source_reaction_energy_J_mol,
            network_dissipation_pJ_s=w.network_heat_pJ_s,
            network_supplied_power_pJ_s=w.network_work_pJ_s,
            network_availability=control.network_transport,
            network_regulation=w.network.regulation,
        )
        records.append(row)
    if records:
        return Observations(*(np.stack([row[k] for row in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    return prior.ensemble_voltage(base_state(state), base_layout(layout), base_spec(spec), time)


def summarize(history, diagnostics, spec):
    return prior.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        network_transport_law=process.LAW_ID,
        network_transport_accounting=ACCOUNTING,
        network_transport_ids=[r.id for r in spec.model.network_transporters],
        network_transport_constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
        network_transfer_direction="outward positive",
        network_drive="explicit maintained external work; no implicit ATP consumption",
        network_final_supplied_work_pJ=float(np.sum(history.network_supplied_work_pJ[-1])),
        claim_scope=(
            "Fixed geometry reversible species-preserving transport; native factory constants, "
            "irreversible reactions and tissue calibration remain separate"
        ),
    )
