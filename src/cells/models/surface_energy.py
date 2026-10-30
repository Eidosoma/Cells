"""Resolved active ions with finite shared cellular ATP/ADP/Pi and supply ports.

Existing metabolic_work_pJ is an internal pump/pool transfer diagnostic. The
combined transformed balance owns finite pool free energy and counts only the
declared regeneration supply as external energetic input. Geometry stays fixed.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_energy_spec import (
    MODEL_ID,  # noqa: F401
    SurfaceEnergyMorrisLecarModel,
    initial_ionic_spec,
    model_id,
)
from cells.models import kinetic_finite_extracellular as pump_layout
from cells.models import surface_cav as prior
from cells.models import surface_kinetic as kinetic
from cells.models import surface_tissue as passive
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import finite_energy as energy
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_finite_energy_accepted_grid_readouts@1"
STAGE_DOMAIN_ID = "positive_ions_and_finite_cellular_atp_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "regeneration_capacity")
POOL_MATERIAL_ATOL_FMOL = 2e-12
MAX_INITIAL_POOL_CHANGE_PER_STEP = 0.05
EXTRA_AXES = {
    "energy_amount_increment_fmol": ["energy_species", "cell_slot"],
    "regeneration_cycles_fmol": ["regeneration_slot"],
    "regeneration_dissipated_energy_pJ": ["regeneration_slot"],
    "regeneration_supplied_work_pJ": ["regeneration_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceEnergyState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceEnergyLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "energy_initial_amount_fmol",
            "energy_delta_g0_J_mol",
            "regeneration_active",
            "regeneration_owner",
            "regeneration_capacity_fmol_s",
            "regeneration_supplied_energy_J_mol",
        )
    ],
)
MORRIS_LECAR_LAYOUT_TYPE = NamedTuple(
    "SurfaceEnergyMorrisLecarLayout",
    [(k, object) for k in (*LAYOUT_TYPE._fields, "channel_calcium_species")],
)
READOUTS = (
    "energy_amount_fmol",
    "energy_concentration_mM",
    "energy_chemical_potential_J_mol",
    "energy_hydrolysis_free_energy_J_mol",
    "energy_free_energy_change_pJ",
    "adenylate_fmol",
    "phosphorus_fmol",
    "regeneration_cycle_rate_fmol_s",
    "regeneration_affinity_J_mol",
    "regeneration_power_pJ_s",
    "regeneration_dissipation_pJ_s",
    "regeneration_availability",
    "energy_balance_pJ",
    "pool_internal_transfer_balance_pJ",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceEnergyObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters
physical_amounts = prior.physical_amounts


class Values(NamedTuple):
    field: object
    derivative: object
    kinetic: object
    energy: object
    regeneration: object
    exchange: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(layout):
    kind = (
        kinetic.MORRIS_LECAR_LAYOUT_TYPE
        if isinstance(layout, MORRIS_LECAR_LAYOUT_TYPE)
        else prior.LAYOUT_TYPE
    )
    return kind(*(getattr(layout, k) for k in kind._fields))


def prior_control(control):
    from cells.core.schedule import SurfaceKineticControl

    return SurfaceKineticControl(*(getattr(control, k) for k in SurfaceKineticControl._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple((p.id, p.cell_id) for p in model.energy_pools),
        tuple((p.id, p.pool_id) for p in model.regeneration_ports),
    )


def working_size(spec):
    return prior.working_size(spec) + 256 * (
        spec.execution.capacity + spec.execution.regeneration_capacity
    )


def pool_parameters(p, *, xp=np):
    return energy.Parameters(
        xp.where(p.active, p.temperature, 298.15), p.energy_delta_g0_J_mol, p.active
    )


def pump_routes(p):
    return energy.Routes(p.membrane_cell, p.pump_present)


def regeneration_routes(p):
    return energy.Routes(p.regeneration_owner, p.regeneration_active)


def regeneration_parameters(p):
    return energy.RegenerationParameters(
        p.regeneration_capacity_fmol_s, p.regeneration_supplied_energy_J_mol
    )


def energy_amounts(state, p):
    return p.energy_initial_amount_fmol + state.energy_amount_increment_fmol


def initial_values(spec):
    state, p = prior.initial_values(initial_ionic_spec(spec))
    n, r = spec.execution.capacity, spec.execution.regeneration_capacity
    values = p._asdict() | dict(
        energy_initial_amount_fmol=np.zeros((3, n)),
        energy_delta_g0_J_mol=np.zeros(n),
        regeneration_active=np.arange(r) < len(spec.model.regeneration_ports),
        regeneration_owner=np.zeros(r, dtype=np.int64),
        regeneration_capacity_fmol_s=np.zeros(r),
        regeneration_supplied_energy_J_mol=np.zeros(r),
    )
    owners = {cell.id: i for i, cell in enumerate(spec.model.cells)}
    pools = {}
    for pool in spec.model.energy_pools:
        i = owners[pool.cell_id]
        pools[pool.id] = i
        values["energy_initial_amount_fmol"][:, i] = pool.initial_amount_fmol
        values["energy_delta_g0_J_mol"][i] = pool.delta_g0_J_per_mol
    for i, port in enumerate(spec.model.regeneration_ports):
        values["regeneration_owner"][i] = pools[port.pool_id]
        values["regeneration_capacity_fmol_s"][i] = port.capacity_fmol_per_s
        values["regeneration_supplied_energy_J_mol"][i] = port.supplied_energy_J_per_mol
    kind = (
        MORRIS_LECAR_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceEnergyMorrisLecarModel)
        else LAYOUT_TYPE
    )
    layout = kind(**values)
    energy.validate_parameters(pool_parameters(layout))
    energy.validate_routes(pump_routes(layout), pool_parameters(layout))
    energy.validate_routes(regeneration_routes(layout), pool_parameters(layout))
    return STATE_TYPE(*state, np.zeros((3, n)), np.zeros(r), np.zeros(r), np.zeros(r)), layout


def stage_layout(state, p, *, xp=jnp):
    """Retain the versioned ionic layout while gathering current cellular fuel."""
    original = prior_layout(p)
    current = energy.pump_parameters(
        energy_amounts(state, p),
        p.volume,
        pool_parameters(p, xp=xp),
        pump_routes(p),
        pump_layout.pump_parameters(original),
        xp=xp,
    )
    return original._replace(
        pump_capacity=current.capacity_fmol_s,
        pump_drive=pump.chemical_drive(current, p.temperature, xp=xp),
        **{"pump_" + key: getattr(current, key) for key in pump.Parameters._fields[1:]},
    )


def readouts(state, control, p, *, xp=jnp):
    current = stage_layout(state, p, xp=xp)
    ionic = prior.readouts(prior_state(state), prior_control(control), current, xp=xp)
    params = pool_parameters(p, xp=xp)
    amount = energy_amounts(state, p)
    pools = energy.thermodynamics(amount, p.volume, params, xp=xp)
    regeneration = energy.regeneration_rates(
        amount,
        p.volume,
        params,
        regeneration_routes(p),
        regeneration_parameters(p),
        control.regeneration,
        xp=xp,
    )
    exchange = energy.exchange_rates(
        ionic.derivative.pump_cycles,
        pump_routes(p),
        regeneration.synthesis_fmol_s,
        regeneration_routes(p),
        params,
        xp=xp,
    )
    derivative = STATE_TYPE(
        *ionic.derivative,
        exchange.amount_fmol_s,
        regeneration.synthesis_fmol_s,
        regeneration.dissipated_power_pJ_s,
        regeneration.supplied_power_pJ_s,
    )
    chemical = xp.sum(energy.chemical_power_pJ_s(exchange.amount_fmol_s, pools, xp=xp))
    v = ionic.field
    dissipation = v.dissipation_pJ_s + xp.sum(regeneration.dissipated_power_pJ_s)
    balance = (
        v.chemical_energy_rate_pJ_s
        + v.capacitor_energy_rate_pJ_s
        + chemical
        + dissipation
        - v.reservoir_power_pJ_s
        - v.electrode_power_pJ_s
        - xp.sum(regeneration.supplied_power_pJ_s)
    )
    valid = ionic.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= energy.regeneration_domain_valid(
        amount,
        p.volume,
        params,
        regeneration_routes(p),
        regeneration_parameters(p),
        control.regeneration,
        xp=xp,
    )
    valid &= energy.exchange_domain_valid(
        ionic.derivative.pump_cycles,
        pump_routes(p),
        regeneration.synthesis_fmol_s,
        regeneration_routes(p),
        params,
        xp=xp,
    )
    for value in (*derivative, chemical, dissipation, balance):
        valid &= xp.all(xp.isfinite(value))
    v = v._replace(
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=balance,
        converged=valid,
        rates=v.rates._replace(valid=valid),
    )
    return Values(v, derivative, ionic, pools, regeneration, exchange, valid)


def rhs(state, control, p, active, *, xp=jnp):
    result = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(result.valid, value, xp.nan) for value in result.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= energy.domain_valid(
        energy_amounts(state, p), p.volume, pool_parameters(p, xp=xp), xp=xp
    )
    valid &= xp.all(xp.isfinite(state.energy_amount_increment_fmol))
    valid &= xp.all(xp.where(p.active, True, state.energy_amount_increment_fmol == 0))
    supported = p.regeneration_active & (p.regeneration_capacity_fmol_s > 0)
    for key in tuple(EXTRA_AXES)[1:]:
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
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
                    "Initial finite-energy/ionic state or actual control outside domain"
                )


def check_steps(spec, steps, controls):
    # Keep the complete regeneration-clock grid and every existing ionic ceiling.
    ionic = replace(initial_ionic_spec(spec), experiment=spec.experiment, execution=spec.execution)
    prior.check_steps(ionic, steps, controls)
    state, p = initial_values(spec)
    amount = np.where(p.active, energy_amounts(state, p), 1.0)
    from cells.core.schedule import control_values

    table = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(spec.experiment.changes)):
        value = readouts(state, type(table)(*(v[i] for v in table)), p, xp=np)
        gross = value.exchange.gross_hydrolysis_fmol_s + value.exchange.gross_synthesis_fmol_s
        fractional = np.max(np.where(p.active, gross / np.min(amount, axis=0), 0.0), initial=0)
        if (
            not np.isfinite(fractional)
            or np.max(steps, initial=0) * fractional > MAX_INITIAL_POOL_CHANGE_PER_STEP
        ):
            raise ConfigError("Finite-energy initial gross turnover requires a smaller RK4 step")


def pool_free_energy_change_pJ(state, p):
    """Stable fixed-volume change, preserving small stored amount increments."""
    anchor = np.where(p.active, p.energy_initial_amount_fmol, 1.0)
    delta = np.asarray(state.energy_amount_increment_fmol)
    mixing = delta * (np.log(anchor / p.volume / energy.STANDARD_STATE_mM) - 1)
    mixing += (anchor + delta) * np.log1p(delta / anchor)
    return 1e-3 * (R * p.temperature * np.sum(mixing, axis=0) - p.energy_delta_g0_J_mol * delta[0])


def balances(state, p):
    qp = prior_layout(p)
    total = (
        state.membrane_transferred
        + kinetic.channel_to_membrane(state.channel_transferred, qp, xp=np)
        - qp.stoichiometry * state.pump_cycles
    )
    result = passive.balances(
        kinetic.passive_state(prior_state(state))._replace(membrane_transferred=total), qp
    )
    free = pool_free_energy_change_pJ(state, p)
    result["energy"] += (
        np.sum(state.channel_dissipated_energy_pJ)
        + np.sum(state.pump_dissipated_energy_pJ)
        + np.sum(free)
        + np.sum(state.regeneration_dissipated_energy_pJ)
        - np.sum(state.regeneration_supplied_work_pJ)
    )
    material = energy.material_balances(
        p.energy_initial_amount_fmol,
        energy_amounts(state, p),
        state.pump_cycles,
        pump_routes(p),
        state.regeneration_cycles_fmol,
        regeneration_routes(p),
        pool_parameters(p),
        xp=np,
    )
    result.update(
        pool_material=material.amount_residual_fmol,
        adenylate=material.adenylate_residual_fmol,
        phosphorus=material.phosphorus_residual_fmol,
    )
    transferred = ordered_scatter(
        state.metabolic_work_pJ, np.zeros_like(p.volume), (p.membrane_cell,), xp=np
    )
    port = ordered_scatter(
        state.regeneration_dissipated_energy_pJ - state.regeneration_supplied_work_pJ,
        np.zeros_like(p.volume),
        (p.regeneration_owner,),
        xp=np,
    )
    result["pool_energy"] = free + transferred + port
    result["regeneration_work"] = (
        state.regeneration_supplied_work_pJ
        - 1e-3 * p.regeneration_supplied_energy_J_mol * state.regeneration_cycles_fmol
    )
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [
            STATE_TYPE(*(value[i] for value in state)) for i in range(len(state.amount_increment))
        ]
    )
    names = (
        "balance_error_fmol",
        "extracellular_balance_error_fmol",
        "global_balance_error_fmol",
        "capacitor_charge_error_C",
        "electrode_charge_error_C",
        "global_charge_error_C",
        "energy_balance_error_pJ",
        "reservoir_work_error_pJ",
        "electrode_work_error_pJ",
        "pool_material_error_fmol",
        "adenylate_error_fmol",
        "phosphorus_error_fmol",
        "pool_internal_transfer_error_pJ",
        "regeneration_work_error_pJ",
    )
    diagnostics = {"max_" + key: 0.0 for key in names}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid finite-energy/ionic state, exhaustion or padding")
            current = balances(row, p)
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(row, p, xp=np)
            limits = (
                tolerance[:, None],
                tolerance[:, None],
                tolerance,
                field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                3e-25,
                passive.ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
                POOL_MATERIAL_ATOL_FMOL,
                POOL_MATERIAL_ATOL_FMOL,
                POOL_MATERIAL_ATOL_FMOL,
                passive.ENERGY_ATOL_PJ,
                3e-12,
            )
            for (key, value), name, limit in zip(current.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > limit):
                    raise NumericalError("Finite-energy accounting failed: " + key)
                diagnostics[name] = max(diagnostics[name], float(np.max(np.abs(value), initial=0)))
    for key in (name for name in STATE_AXES if name.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Finite-energy dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Finite-energy observations require accepted integration boundaries")
    controls = control_values(spec, requested)
    records = []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid finite-energy observation state/control")
        observed = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(np.asarray([v]) for v in prior_state(state))),
            stage_layout(state, p, xp=np),
            np.asarray([time]),
            initial_ionic_spec(spec),
        )
        row = {key: v[0] for key, v in vars(observed).items()}
        row.update({key: getattr(state, key) for key in EXTRA_AXES})
        conserved = energy.invariants(energy_amounts(state, p), xp=np)
        balance = balances(state, p)
        row.update(
            energy_amount_fmol=energy_amounts(state, p),
            energy_concentration_mM=value.energy.concentration_mM,
            energy_chemical_potential_J_mol=value.energy.chemical_potential_J_mol,
            energy_hydrolysis_free_energy_J_mol=value.energy.hydrolysis_free_energy_J_mol,
            energy_free_energy_change_pJ=pool_free_energy_change_pJ(state, p),
            adenylate_fmol=conserved.adenylate_fmol,
            phosphorus_fmol=conserved.phosphorus_fmol,
            regeneration_cycle_rate_fmol_s=value.regeneration.synthesis_fmol_s,
            regeneration_affinity_J_mol=value.regeneration.reaction_free_energy_J_mol,
            regeneration_power_pJ_s=value.regeneration.supplied_power_pJ_s,
            regeneration_dissipation_pJ_s=value.regeneration.dissipated_power_pJ_s,
            regeneration_availability=control.regeneration,
            energy_balance_pJ=np.atleast_1d(balance["energy"]),
            pool_internal_transfer_balance_pJ=balance["pool_energy"],
            energy_balance_pJ_s=np.atleast_1d(value.field.energy_balance_pJ_s),
        )
        records.append(tuple(row[key] for key in OBSERVATION_FIELDS))
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    p = type(layout)(*(np.asarray(v) for v in layout))
    value = readouts(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not value.valid:
        raise NumericalError("Finite-energy ensemble endpoint outside domain")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return passive.summarize(history, diagnostics, spec) | dict(
        model=model_id(spec.model),
        state_fields=list(STATE_TYPE._fields),
        energy_species=list(energy.SPECIES),
        energy_law=energy.LAW_ID,
        regeneration_law=energy.REGENERATION_LAW_ID,
        metabolic_work_role="Internal pump/pool transfer diagnostic, not external chemical supply",
        scope="Transformed finite energy with buffered pH/Mg/solvent; fixed geometry and volume",
    )
