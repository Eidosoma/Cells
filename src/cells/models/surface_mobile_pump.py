"""Conserved neutral pump proteins coupled to resolved Na/K/ATP transport.

Turnover times the current owned amount gives local cycle capacity. Pumping
does not consume pump protein. Maintained ATP/ADP/Pi reservoirs supply signed
chemical work; neutral lateral diffusion has a separate mixing-energy ledger.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_mobile_pump_spec import MODEL_ID, prior_spec
from cells.models import surface_redistribution as prior
from cells.models import surface_tissue as base
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = "resolved_mobile_pump_readouts@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_mobile_pump_inventory_actual_control_charge_current@1"
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "pump_population_capacity")
PUMP_SURFACE_AXES = {
    "pump_surface_amount_increment": ["pump_population_slot", "membrane_slot"],
    "pump_surface_transferred": ["pump_population_slot", "surface_edge_slot"],
    "pump_surface_dissipated_energy_pJ": ["pump_population_slot", "surface_edge_slot"],
}
EXTRA_AXES = PUMP_SURFACE_AXES | {
    "pump_cycles": ["pump_population_slot", "membrane_slot"],
    "pump_dissipated_energy_pJ": ["pump_population_slot", "membrane_slot"],
    "metabolic_work_pJ": ["pump_population_slot", "membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceMobilePumpState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceMobilePumpLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "pump_active",
            "pump_amount_reference",
            "pump_reference_density",
            "pump_diffusivity",
            "pump_turnover",
            "pump_stoichiometry",
            "pump_sodium_species",
            "pump_potassium_species",
            "pump_drive",
            *("pump_" + k for k in pump.Parameters._fields[1:]),
        )
    ],
)
OBSERVATION_FIELDS = (
    *prior.OBSERVATION_FIELDS,
    *EXTRA_AXES,
    "pump_amount_fmol",
    "pump_density_fmol_um2",
    "pump_surface_flux_fmol_s",
    "pump_surface_energy_balance_pJ",
    "pump_cycle_rate_fmol_s",
    "pump_capacity_fmol_s",
    "pump_affinity_J_mol",
    "metabolic_power_pJ_s",
    "pump_availability",
)
Observations = make_dataclass(
    "SurfaceMobilePumpObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters


class Values(NamedTuple):
    field: object
    derivative: object
    capacity: object
    affinity: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def pump_surface_state(state):
    return prior.STATE_TYPE(
        *prior.base_state(state), *(getattr(state, k) for k in PUMP_SURFACE_AXES)
    )


def pump_surface_layout(p, *, xp=np):
    """View only: reuse surface diffusion/energy checks with distinct pump owners."""
    return prior_layout(p)._replace(
        surface_amount_reference=p.pump_amount_reference,
        reference_density=p.pump_reference_density,
        reference_permeability=xp.zeros_like(p.pump_stoichiometry),
        mobile_effective_charge_e=xp.zeros_like(p.pump_active, dtype=float),
        mobile_edge_diffusivity_um2_s=p.pump_diffusivity,
    )


def batch_signature(model):
    return (*prior.batch_signature(model), tuple((p.id, p.roles) for p in model.mobile_pumps))


def working_size(spec):
    x = spec.execution
    return prior.working_size(spec) + 192 * x.pump_population_capacity * (
        x.membrane_capacity + x.surface_edge_capacity + len(spec.model.species_ids)
    )


def initial_values(spec):
    state, original = prior.initial_values(prior_spec(spec))
    m, x = spec.model, spec.execution
    k, nm, ne = x.pump_population_capacity, x.membrane_capacity, x.surface_edge_capacity
    v = original._asdict() | dict(
        pump_active=np.arange(k) < len(m.mobile_pumps),
        pump_amount_reference=np.zeros((k, nm)),
        pump_reference_density=np.ones(k),
        pump_diffusivity=np.zeros((k, ne)),
        pump_turnover=np.zeros((k, 1)),
        pump_stoichiometry=np.zeros((len(m.species_ids), k)),
        pump_sodium_species=np.zeros(k, dtype=np.int64),
        pump_potassium_species=np.zeros(k, dtype=np.int64),
        pump_drive=np.zeros((k, 1)),
    )
    for key in pump.Parameters._fields[1:]:
        v["pump_" + key] = np.ones((k, 1)) if key != "delta_g0_J_mol" else np.zeros((k, 1))
    for i, p in enumerate(m.mobile_pumps):
        v["pump_amount_reference"][i, : len(m.membranes)] = p.initial_amount_fmol
        v["pump_reference_density"][i] = p.reference_density_fmol_per_um2
        v["pump_diffusivity"][i, : len(m.surface_edges)] = p.diffusivity_um2_per_s
        v["pump_turnover"][i, 0] = p.turnover_per_s
        v["pump_stoichiometry"][:, i] = p.stoichiometry
        v["pump_sodium_species"][i], v["pump_potassium_species"][i] = [
            m.species_ids.index(s) for s in p.roles
        ]
        for key in ("atp_mM", "adp_mM", "pi_mM"):
            v["pump_" + key][i, 0] = getattr(p.metabolism, key)
        for key in ("km_na_mM", "km_k_mM", "km_atp_mM"):
            v["pump_" + key][i, 0] = getattr(p, key)
        v["pump_delta_g0_J_mol"][i, 0] = p.metabolism.delta_g0_J_per_mol
    p = LAYOUT_TYPE(**v)
    drive = pump.chemical_drive(
        pump.Parameters(
            np.zeros((k, nm)), *(getattr(p, "pump_" + key) for key in pump.Parameters._fields[1:])
        ),
        p.temperature,
        xp=np,
    )
    p = p._replace(pump_drive=drive)
    return STATE_TYPE(
        *state,
        np.zeros((k, nm)),
        np.zeros((k, ne)),
        np.zeros((k, ne)),
        np.zeros((k, nm)),
        np.zeros((k, nm)),
        np.zeros((k, nm)),
    ), p


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= prior.surface_domain_valid(
        pump_surface_state(state), pump_surface_layout(p, xp=xp), xp=xp
    )
    support = (p.pump_amount_reference > 0) & (p.pump_turnover > 0)
    for value in (state.pump_cycles, state.pump_dissipated_energy_pJ, state.metabolic_work_pJ):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(support, True, value == 0))
    return valid


def readouts(state, control, p, *, xp=jnp, membrane_permeability=None):
    layout = prior.effective_layout(prior_state(state), p, xp=xp)
    if membrane_permeability is not None:
        # A composition may supply the current stage's complete permeability,
        # while p retains the union of routes needed to validate past ledgers.
        layout = layout._replace(membrane_permeability=membrane_permeability)
    v = base.field_values(prior.base_state(state), control, layout, xp=xp)
    r, n = v.rates, p.active.size
    ai, ao = base.physical_amounts(state, p)
    ci = xp.where(p.active, ai / p.volume, 1.0)
    co = xp.where(p.outside_active, ao / p.extracellular_volume, 1.0)
    support = p.pump_active[:, None] & p.membrane_active
    capacity = p.pump_turnover * (p.pump_amount_reference + state.pump_surface_amount_increment)
    params = pump.Parameters(
        capacity, *(getattr(p, "pump_" + key) for key in pump.Parameters._fields[1:])
    )
    na, ka = xp.asarray(p.pump_sodium_species), xp.asarray(p.pump_potassium_species)
    args = (
        xp.where(support, ci[na[:, None], p.membrane_cell], 1.0),
        xp.where(support, co[ka[:, None], p.membrane_outside], 1.0),
        xp.where(support, r.membrane_delta_mu_J_mol[na], 0.0),
        xp.where(support, r.membrane_delta_mu_J_mol[ka], 0.0),
        p.temperature,
        params,
        control.pump,
    )
    kinetic = pump.kinetics(*args, xp=xp)
    cycles = xp.where(support, kinetic.cycles_fmol_s, 0.0)
    heat = -1e-3 * cycles * kinetic.cycle_free_energy_J_mol
    work = -1e-3 * cycles * kinetic.chemical_drive_J_mol
    extra = -p.pump_stoichiometry @ cycles
    cell = r.cell_rate_fmol_s - ordered_scatter(
        extra, r.cell_rate_fmol_s, (xp.asarray(p.membrane_cell),), xp=xp
    )
    out_extra = ordered_scatter(
        extra, r.outside_rate_fmol_s, (xp.asarray(p.membrane_outside),), xp=xp
    )
    outside = r.outside_rate_fmol_s + xp.where(p.reservoir, 0.0, out_extra)
    supplied = r.reservoir_supply_fmol_s - xp.where(p.reservoir, out_extra, 0.0)
    flux = r.membrane_flux_fmol_s + extra
    membrane_heat = r.membrane_dissipation_pJ_s + xp.sum(heat, axis=0)
    total_rates = r._replace(
        cell_rate_fmol_s=cell,
        outside_rate_fmol_s=outside,
        reservoir_supply_fmol_s=supplied,
        membrane_flux_fmol_s=flux,
        membrane_current_A=CHARGE_PER_FMOL * xp.sum(p.valence * flux, axis=0),
        membrane_dissipation_pJ_s=membrane_heat,
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = field._capacitor_solve(qdot, xp.zeros_like(qdot), base.field_layout(layout), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[p.membrane_cell] - dphi[n + p.membrane_outside], 0.0)
    electrode = xp.where(p.reservoir, (p.field_capacitor_matrix @ dphi)[n:], 0.0)
    chemical = 1e-3 * R * p.temperature * (xp.sum(xp.log(ci) * cell) + xp.sum(xp.log(co) * outside))
    electric = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    mu = R * p.temperature * xp.log(co) + p.valence * F * v.potential_V[n:]
    reservoir_work = 1e-3 * xp.sum(mu * supplied, axis=0)
    electrode_work = 1e12 * p.boundary_V * electrode
    dissipation = (
        xp.sum(membrane_heat)
        + xp.sum(r.junction_dissipation_pJ_s)
        + xp.sum(r.face_dissipation_pJ_s)
    )
    energy = (
        chemical + electric + dissipation - xp.sum(reservoir_work + electrode_work) - xp.sum(work)
    )
    v = v._replace(
        rates=total_rates,
        electrode_current_A=electrode,
        reservoir_supply_charge_A=CHARGE_PER_FMOL * xp.sum(p.valence * supplied, axis=0),
        membrane_voltage_rate_V_s=dvm,
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=electric,
        reservoir_power_pJ_s=xp.sum(reservoir_work),
        electrode_power_pJ_s=xp.sum(electrode_work),
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=energy,
    )
    ionic = base.derivative_from_field(v, layout, xp=xp)._replace(
        membrane_transferred=r.membrane_flux_fmol_s,
        membrane_dissipated_energy_pJ=r.membrane_dissipation_pJ_s,
    )
    leak_move, leak_heat = prior.surface_readouts(prior_state(state), prior_layout(p), xp=xp)
    move, move_heat = prior.surface_readouts(
        pump_surface_state(state), pump_surface_layout(p, xp=xp), xp=xp
    )
    result = STATE_TYPE(
        *ionic,
        leak_move.amount_rate_fmol_s,
        leak_move.flux_fmol_s,
        leak_heat,
        move.amount_rate_fmol_s,
        move.flux_fmol_s,
        move_heat,
        cycles,
        heat,
        work,
    )
    valid = v.converged & xp.all(pump.domain_valid(*args, xp=xp)) & leak_move.valid & move.valid
    valid &= xp.all(xp.where(support, True, control.pump == 0))
    valid &= domain_valid(state, p, p.active, xp=xp)
    for value in (*result, qdot, dphi, chemical, electric, dissipation, energy):
        valid &= xp.all(xp.isfinite(value))
    return Values(
        v._replace(converged=valid, rates=total_rates._replace(valid=valid)),
        result,
        capacity,
        xp.where(support, kinetic.cycle_free_energy_J_mol, 0.0),
        valid,
    )


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


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
            population_capacity=max(1, len(m.mobile_populations)),
            surface_edge_capacity=len(m.surface_edges),
            pump_population_capacity=len(m.mobile_pumps),
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    for i in range(len(compact.experiment.changes)):
        control = type(controls)(*(v[i] for v in controls))
        if not control_domain_valid(state, control, p, p.active, xp=np):
            raise ConfigError("Initial mobile pump field, chemistry or protein domain invalid")


def check_steps(spec, steps, controls):
    # Retain pump-only event boundaries in the ordinary grid and observation check.
    base.check_steps(spec, steps, controls)
    loss = max(
        prior.surface_loss_bound(spec.model, spec.model.mobile_populations),
        prior.surface_loss_bound(spec.model, spec.model.mobile_pumps),
    )
    if np.max(steps, initial=0) * loss > prior.MAX_SURFACE_LOSS_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Mobile protein diffusion requires a smaller RK4 step")


def balances(state, p):
    total = state.membrane_transferred - p.pump_stoichiometry @ state.pump_cycles
    result = base.balances(prior.base_state(state)._replace(membrane_transferred=total), p)
    result["energy"] += np.sum(state.pump_dissipated_energy_pJ) - np.sum(state.metabolic_work_pJ)
    result["metabolic_work"] = state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles
    return result


def check_values(state, spec, *, layout=None):
    p = initial_values(spec)[1] if layout is None else layout
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
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
        "metabolic_work_error_pJ",
    )
    diagnostics = {"max_" + k: 0.0 for k in names}
    for prefix in ("surface", "pump_surface"):
        diagnostics.update(
            {
                "max_" + prefix + "_" + k: 0.0
                for k in (
                    "balance_error_fmol",
                    "cell_balance_error_fmol",
                    "energy_balance_error_pJ",
                )
            }
        )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid mobile pump inventory, history or padding; no repair")
        b = balances(row, p)
        tol = np.asarray(spec.execution.material_balance_atol_fmol)
        q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C] + base.charge_increment(
            row, p, xp=np
        )
        limits = (
            tol[:, None],
            tol[:, None],
            tol,
            field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(q),
            field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
            3e-25,
            base.ENERGY_ATOL_PJ,
            3e-12,
            3e-12,
            3e-12,
        )
        for name, value, bound in zip(names, b.values(), limits, strict=True):
            if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                raise NumericalError("Mobile pump accounting failed: " + name)
            diagnostics["max_" + name] = max(
                diagnostics["max_" + name], float(np.max(np.abs(value), initial=0))
            )
        for prefix, y, view in (
            ("surface", prior_state(row), prior_layout(p)),
            ("pump_surface", pump_surface_state(row), pump_surface_layout(p)),
        ):
            for suffix, value, bound in zip(
                ("balance_error_fmol", "cell_balance_error_fmol", "energy_balance_error_pJ"),
                prior.surface_balances(y, view).values(),
                (
                    prior.SURFACE_MATERIAL_ATOL_FMOL,
                    prior.SURFACE_MATERIAL_ATOL_FMOL,
                    prior.SURFACE_ENERGY_ATOL_PJ,
                ),
                strict=True,
            ):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError(
                        "Mobile pump surface accounting failed: " + prefix + " " + suffix
                    )
                key = "max_" + prefix + "_" + suffix
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Mobile pump dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    times, requested = np.asarray(times), np.asarray(requested)
    if any(t not in times for t in requested):
        raise ConfigError("Mobile pump observations require accepted integration boundaries")
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    controls = control_values(spec, requested)
    records = []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = type(controls)(*(v[j] for v in controls))
        observed = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(v[None] for v in prior_state(state))),
            prior_layout(p),
            [time],
            prior_spec(spec),
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Mobile pump observation failed its actual-control domain")
        v = w.field
        row.update(
            membrane_flux_fmol_s=v.rates.membrane_flux_fmol_s,
            reservoir_supply_fmol_s=v.rates.reservoir_supply_fmol_s,
            electrode_current_A=v.electrode_current_A,
            reservoir_power_pJ_s=np.atleast_1d(v.reservoir_power_pJ_s),
            electrode_power_pJ_s=np.atleast_1d(v.electrode_power_pJ_s),
            energy_balance_pJ_s=np.atleast_1d(v.energy_balance_pJ_s),
        )
        r = prior.surface_rates(pump_surface_state(state), pump_surface_layout(p), xp=np)
        row.update({k: getattr(state, k) for k in EXTRA_AXES})
        row.update(
            pump_amount_fmol=p.pump_amount_reference + state.pump_surface_amount_increment,
            pump_density_fmol_um2=r.density_fmol_um2,
            pump_surface_flux_fmol_s=r.flux_fmol_s,
            pump_surface_energy_balance_pJ=prior.surface_balances(
                pump_surface_state(state), pump_surface_layout(p)
            )["energy"],
            pump_cycle_rate_fmol_s=w.derivative.pump_cycles,
            pump_capacity_fmol_s=w.capacity,
            pump_affinity_J_mol=w.affinity,
            metabolic_power_pJ_s=w.derivative.metabolic_work_pJ,
            pump_availability=control.pump,
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

    controls = control_values(spec, [time])
    control = type(controls)(*(v[0] for v in controls))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    values = readouts(state, control, p, xp=np)
    if not values.valid:
        raise NumericalError("Mobile pump ensemble field invalid")
    return values.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(prior_state(history), diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        mobile_pumps=[p.id for p in spec.model.mobile_pumps],
        pump_law=pump.LAW_ID,
        metabolism="explicit maintained ATP/ADP/Pi reservoirs",
    )
