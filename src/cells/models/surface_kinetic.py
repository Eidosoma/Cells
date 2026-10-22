"""Same-stage resolved electricity, intrinsic gates and ATP-driven Na/K transport.

Membrane processes are internal to each capacitor component, so they do not
alter its floating current equation. They DO alter capacitor derivatives and
both boundary sources. Junction conductance enters the nonlinear field solve.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_kinetic_spec import (
    MODEL_ID,  # noqa: F401
    SurfaceChannelModel,
    SurfaceHCNModel,
    SurfaceSodiumModel,
    model_id,
)
from cells.coupling.selective import selective_flux
from cells.models import kinetic_finite_extracellular as kinetic
from cells.models import surface_tissue as base
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes import (
    hcn_channels,
    junction_gate,
    potassium_channels,
    sodium_channels,
    voltage_gates,
)
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = "resolved_kinetic_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_intrinsic_gates_atp_actual_controls@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "channel_capacity")
STATE_AXES = base.STATE_AXES | {
    "channel_gate": ["gate", "channel_slot"],
    "channel_transferred": ["channel_slot"],
    "channel_dissipated_energy_pJ": ["channel_slot"],
    "junction_gate": ["edge_slot"],
    "pump_cycles": ["membrane_slot"],
    "pump_dissipated_energy_pJ": ["membrane_slot"],
    "metabolic_work_pJ": ["membrane_slot"],
}
STATE_TYPE = NamedTuple("SurfaceKineticState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceKineticLayout",
    [
        (k, object)
        for k in (
            *base.LAYOUT_TYPE._fields,
            "channel_active",
            "channel_membranes",
            "channel_species",
            "channel_permeability",
            "channel_abundance",
            "junction_threshold_voltage",
            "junction_minimum",
            "stoichiometry",
            "pump_capacity",
            "pump_drive",
            "pump_present",
            "pump_sodium_species",
            "pump_potassium_species",
            *("pump_" + k for k in pump.Parameters._fields[1:]),
        )
    ],
)
CHANNEL_LAYOUT_TYPE = NamedTuple(
    "SurfaceChannelLayout", [(k, object) for k in (*LAYOUT_TYPE._fields, "channel_laws")]
)
SODIUM_LAYOUT_TYPE = NamedTuple(
    "SurfaceSodiumLayout", [(k, object) for k in CHANNEL_LAYOUT_TYPE._fields]
)
SODIUM_OWNED_VIEW_TYPE = NamedTuple(
    "SurfaceSodiumOwnedView",
    [(k, object) for k in (*SODIUM_LAYOUT_TYPE._fields, "cytosol_amount")],
)
HCN_LAYOUT_TYPE = NamedTuple(
    "SurfaceHCNLayout",
    [
        (k, object)
        for k in (*SODIUM_LAYOUT_TYPE._fields, "channel_relative_permeability")
        if k != "channel_species"
    ],
)
HCN_OWNED_VIEW_TYPE = NamedTuple(
    "SurfaceHCNOwnedView",
    [(k, object) for k in (*HCN_LAYOUT_TYPE._fields, "cytosol_amount")],
)


def channel_process(layout):
    # Layout type is static through JAX transformations and complete checkpoints.
    # Older potassium/calcium layouts retain their restricted law catalog.
    if isinstance(layout, (HCN_LAYOUT_TYPE, HCN_OWNED_VIEW_TYPE)):
        return hcn_channels
    return (
        sodium_channels
        if isinstance(layout, (SODIUM_LAYOUT_TYPE, SODIUM_OWNED_VIEW_TYPE))
        else potassium_channels
    )


class Values(NamedTuple):
    field: object
    derivative: object
    channel_flux_fmol_s: object
    channel_targets: object
    channel_tau_s: object
    pump_affinity_J_mol: object
    valid: object


parameters = base.parameters
batch_signature = base.batch_signature
physical_amounts = base.physical_amounts


def working_size(spec):
    return base.working_size(spec) + 256 * (
        spec.execution.membrane_capacity
        + spec.execution.channel_capacity
        + spec.execution.edge_capacity
    )


def passive_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def initial_values(spec):
    state, layout = base.initial_values(spec)
    v, m, x = layout._asdict(), spec.model, spec.execution
    nc, nm, ne = x.channel_capacity, x.membrane_capacity, x.edge_capacity
    multi_ion = isinstance(m, SurfaceHCNModel)
    v.update(
        channel_active=np.arange(nc) < len(m.channels),
        channel_membranes=np.zeros(nc, dtype=np.int64),
        channel_species=np.zeros(nc, dtype=np.int64),
        channel_permeability=np.zeros(nc),
        channel_abundance=np.zeros(nc),
        junction_threshold_voltage=np.zeros(ne),
        junction_minimum=np.zeros(ne),
        stoichiometry=np.zeros((len(m.species_ids), nm)),
        pump_capacity=np.zeros(nm),
        pump_drive=np.zeros(nm),
    )
    if multi_ion:
        del v["channel_species"]
        v["channel_relative_permeability"] = np.zeros((len(m.species_ids), nc))
    cg, jg = np.zeros((2, nc)), np.zeros(ne)
    mids = [p.id for p in m.membranes]
    for i, p in enumerate(m.channels):
        v["channel_membranes"][i] = mids.index(p.membrane_id)
        if multi_ion:
            for ion in p.permeant_ions:
                v["channel_relative_permeability"][m.species_ids.index(ion.species_id), i] = (
                    ion.relative_permeability
                )
        else:
            v["channel_species"][i] = m.species_ids.index(p.species_id)
        v["channel_permeability"][i], v["channel_abundance"][i] = (
            p.max_permeability_m_per_s,
            p.abundance,
        )
        cg[:, i] = p.initial_gate
    for i, p in enumerate(m.junctions):
        v["junction_threshold_voltage"][i], v["junction_minimum"][i] = (
            p.threshold_voltage_V,
            p.minimum_open_fraction,
        )
        jg[i] = p.initial_gate
    kinetic.bind_pumps(spec, v)
    layout_type = LAYOUT_TYPE
    if isinstance(m, SurfaceChannelModel):
        v["channel_laws"] = np.zeros(nc, dtype=np.int64)
        laws = (
            hcn_channels.LAW_CODES
            if multi_ion
            else sodium_channels.LAW_CODES
            if isinstance(m, SurfaceSodiumModel)
            else potassium_channels.LAW_CODES
        )
        for i, channel in enumerate(m.channels):
            v["channel_laws"][i] = laws[channel.kinetic_law]
        layout_type = (
            HCN_LAYOUT_TYPE
            if multi_ion
            else SODIUM_LAYOUT_TYPE
            if isinstance(m, SurfaceSodiumModel)
            else CHANNEL_LAYOUT_TYPE
        )
    transfer_shape = (len(m.species_ids), nc) if multi_ion else (nc,)
    return (
        STATE_TYPE(
            *state,
            cg,
            np.zeros(transfer_shape),
            np.zeros(transfer_shape),
            jg,
            np.zeros(nm),
            np.zeros(nm),
            np.zeros(nm),
        ),
        layout_type(**v),
    )


def channel_to_membrane(value, p, *, xp):
    if hasattr(p, "channel_relative_permeability"):
        return scatter(value, xp.zeros_like(p.membrane_permeability), (p.channel_membranes,), xp=xp)
    return scatter(
        value,
        xp.zeros_like(p.membrane_permeability),
        (p.channel_species, p.channel_membranes),
        xp=xp,
    )


def junction_parameters(p):
    return junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum)


def readouts(state, control, p, *, xp=jnp):
    from cells.core.schedule import SurfaceControl

    v = base.field_values(
        state, SurfaceControl(control.membrane, control.junction * state.junction_gate), p, xp=xp
    )
    r, n = v.rates, p.active.size
    ci, co = physical_amounts(state, p)
    ci, co = (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )
    patch = p.channel_membranes
    cv = xp.where(p.channel_active, r.membrane_voltage_V[patch], 0.0)
    if hasattr(p, "channel_laws"):
        process = channel_process(p)
        target, tau = process.kinetics(cv, p.channel_laws, xp=xp)
        opened = process.opening(state.channel_gate, p.channel_laws, xp=xp)
    else:
        target, tau = voltage_gates.kinetics(cv, xp=xp)
        opened = state.channel_gate[0] * state.channel_gate[1]
    gate_rate = xp.where(p.channel_active, (target - state.channel_gate) / tau, 0.0)
    if hasattr(p, "channel_relative_permeability"):
        inside, outside = ci[:, p.membrane_cell[patch]], co[:, p.membrane_outside[patch]]
        valence = p.valence
        permeability = p.channel_permeability * p.channel_relative_permeability
        affinity = r.membrane_delta_mu_J_mol[:, patch]
    else:
        species = p.channel_species
        inside, outside = (
            ci[species, p.membrane_cell[patch]],
            co[species, p.membrane_outside[patch]],
        )
        valence = p.valence[species, 0]
        permeability = p.channel_permeability
        affinity = r.membrane_delta_mu_J_mol[species, patch]
    channel = selective_flux(
        inside,
        outside,
        cv,
        valence,
        p.temperature,
        p.membrane_area[patch],
        permeability,
        0.0,
        p.channel_abundance,
        opened * control.channel,
        xp=xp,
    )
    channel = xp.where(p.channel_active, channel, 0.0)
    channel_d = 1e-3 * channel * affinity
    args = (
        *kinetic.role_inputs(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            r.membrane_delta_mu_J_mol,
            p.temperature,
            p,
            xp=xp,
        ),
        kinetic.pump_parameters(p),
        control.pump,
    )
    pr = pump.kinetics(*args, xp=xp)
    cycles = xp.where(p.pump_present, pr.cycles_fmol_s, 0.0)
    pump_d = -1e-3 * cycles * pr.cycle_free_energy_J_mol
    metabolic = -1e-3 * cycles * pr.chemical_drive_J_mol
    jgate_rate = xp.where(
        p.junction_active,
        junction_gate.rhs(state.junction_gate, r.junction_voltage_V, junction_parameters(p), xp=xp),
        0.0,
    )

    # Outward-positive channel transport; pump stoichiometry is inward-positive.
    extra = channel_to_membrane(channel, p, xp=xp) - p.stoichiometry * cycles
    cell = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    out_extra = scatter(extra, r.outside_rate_fmol_s, (p.membrane_outside,), xp=xp)
    outside = r.outside_rate_fmol_s + xp.where(p.reservoir, 0.0, out_extra)
    supplied = r.reservoir_supply_fmol_s - xp.where(p.reservoir, out_extra, 0.0)
    total_flux = r.membrane_flux_fmol_s + extra
    channel_heat = (
        xp.sum(channel_d, axis=0) if hasattr(p, "channel_relative_permeability") else channel_d
    )
    total_membrane_d = (
        r.membrane_dissipation_pJ_s
        + pump_d
        + scatter(channel_heat, p.membrane_area, (patch,), xp=xp)
    )
    total_rates = r._replace(
        cell_rate_fmol_s=cell,
        outside_rate_fmol_s=outside,
        reservoir_supply_fmol_s=supplied,
        membrane_flux_fmol_s=total_flux,
        membrane_current_A=CHARGE_PER_FMOL * xp.sum(p.valence * total_flux, axis=0),
        membrane_dissipation_pJ_s=total_membrane_d,
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = field._capacitor_solve(qdot, xp.zeros_like(qdot), base.field_layout(p), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[p.membrane_cell] - dphi[n + p.membrane_outside], 0.0)
    electrode = xp.where(p.reservoir, (p.field_capacitor_matrix @ dphi)[n:], 0.0)
    chemical = 1e-3 * R * p.temperature * (xp.sum(xp.log(ci) * cell) + xp.sum(xp.log(co) * outside))
    capacitor = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    mu = R * p.temperature * xp.log(co) + p.valence * F * v.potential_V[n:]
    reservoir_work = 1e-3 * xp.sum(mu * supplied, axis=0)
    electrode_work = 1e12 * p.boundary_V * electrode
    dissipation = (
        xp.sum(total_membrane_d)
        + xp.sum(r.junction_dissipation_pJ_s)
        + xp.sum(r.face_dissipation_pJ_s)
    )
    energy = (
        chemical
        + capacitor
        + dissipation
        - xp.sum(reservoir_work + electrode_work)
        - xp.sum(metabolic)
    )
    result = STATE_TYPE(
        cell,
        outside,
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        r.face_flux_fmol_s,
        supplied,
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        r.face_dissipation_pJ_s,
        electrode,
        reservoir_work,
        electrode_work,
        gate_rate,
        channel,
        channel_d,
        jgate_rate,
        cycles,
        pump_d,
        metabolic,
    )
    valid = v.converged & xp.all(pump.domain_valid(*args, xp=xp))
    for value in control:
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
    valid &= xp.all(
        xp.where(
            p.channel_active,
            (cv >= voltage_gates.VOLTAGE_DOMAIN_V[0]) & (cv <= voltage_gates.VOLTAGE_DOMAIN_V[1]),
            True,
        )
    )
    valid &= xp.all(
        junction_gate.domain_valid(
            state.junction_gate,
            r.junction_voltage_V,
            junction_parameters(p),
            control.junction,
            xp=xp,
        )
    )
    for value in result:
        valid &= xp.all(xp.isfinite(value))
    for value in (qdot, dphi, chemical, capacitor, dissipation, energy):
        valid &= xp.all(xp.isfinite(value))
    valid &= domain_valid(state, p, p.active, xp=xp)
    total_rates = total_rates._replace(valid=valid)
    v = v._replace(
        rates=total_rates,
        electrode_current_A=electrode,
        reservoir_supply_charge_A=CHARGE_PER_FMOL * xp.sum(p.valence * supplied, axis=0),
        membrane_voltage_rate_V_s=dvm,
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor,
        reservoir_power_pJ_s=xp.sum(reservoir_work),
        electrode_power_pJ_s=xp.sum(electrode_work),
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=energy,
        converged=valid,
    )
    return Values(
        v,
        result,
        channel,
        target,
        tau,
        xp.where(p.pump_present, pr.cycle_free_energy_J_mol, 0.0),
        valid,
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


def domain_valid(state, p, active, *, xp=jnp):
    valid = base.domain_valid(passive_state(state), p, active, xp=xp)
    if hasattr(p, "channel_laws"):
        valid &= channel_process(p).valid_codes(p.channel_laws, xp=xp)
        valid &= xp.all(xp.where(p.channel_active, True, p.channel_laws == 0))
    masks = (
        p.channel_active,
        p.channel_active,
        p.channel_active,
        p.junction_active,
        p.pump_present,
        p.pump_present,
        p.pump_present,
    )
    for value, mask in zip(state[len(base.STATE_TYPE._fields) :], masks, strict=True):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all((state.channel_gate >= 0) & (state.channel_gate <= 1))
    valid &= xp.all((state.junction_gate >= p.junction_minimum) & (state.junction_gate <= 1))
    valid &= xp.all(
        xp.where(
            p.channel_permeability * p.channel_abundance > 0, True, state.channel_transferred == 0
        )
    )
    if hasattr(p, "channel_relative_permeability"):
        # Absent species routes must never carry hidden transfers or heat.
        route = p.channel_relative_permeability * p.channel_permeability * p.channel_abundance
        valid &= xp.all(xp.where(route > 0, True, state.channel_transferred == 0))
        valid &= xp.all(xp.where(route > 0, True, state.channel_dissipated_energy_pJ == 0))
    valid &= xp.all(xp.where(p.pump_capacity > 0, True, state.pump_cycles == 0))
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
    # The strict parser already checked active charge anchors and geometry.
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
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            if not control_domain_valid(
                state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
            ):
                raise ConfigError("Initial resolved channel/junction/pump domain invalid")


def check_steps(spec, steps, controls):
    base.check_steps(spec, steps, controls)
    if isinstance(spec.model, SurfaceSodiumModel) and np.max(steps, initial=0) > 2.5e-6 + 1e-16:
        raise ConfigError("Resolved sodium/potassium channels require RK4 steps <= 2.5 us")
    if isinstance(spec.model, SurfaceChannelModel) and np.max(steps, initial=0) > 25e-6 + 1e-16:
        raise ConfigError("Resolved mixed potassium channels require RK4 steps <= 25 us")
    bound = max(
        (1.3 * np.exp(77 * p.threshold_voltage_V) + 20 for p in spec.model.junctions), default=0.0
    )
    if np.max(steps, initial=0) * bound > 0.125:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


def balances(state, p):
    total = (
        state.membrane_transferred
        + channel_to_membrane(state.channel_transferred, p, xp=np)
        - p.stoichiometry * state.pump_cycles
    )
    result = base.balances(passive_state(state)._replace(membrane_transferred=total), p)
    result["energy"] += (
        np.sum(state.channel_dissipated_energy_pJ)
        + np.sum(state.pump_dissipated_energy_pJ)
        - np.sum(state.metabolic_work_pJ)
    )
    result["metabolic_work"] = state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {
        "max_" + k: 0.0
        for k in (
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
    }
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Invalid resolved kinetic inventory, gates or padding; no repair"
                )
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
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                3e-25,
                base.ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
                3e-12,
            )
            for (name, value), key, bound in zip(b.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError("Resolved kinetic accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Resolved kinetic dissipation cannot be negative or decrease")
    return diagnostics


OBSERVATION_FIELDS = (
    "times",
    *STATE_TYPE._fields,
    *(k for k in base.OBSERVATION_FIELDS if k not in ("times", *base.STATE_TYPE._fields)),
    "channel_flux_fmol_s",
    "channel_targets",
    "channel_tau_s",
    "pump_cycle_rate_fmol_s",
    "pump_affinity_J_mol",
    "metabolic_power_pJ_s",
    "channel_availability",
    "pump_availability",
)
Observations = make_dataclass(
    "SurfaceKineticObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved kinetic observations require accepted times")
    controls, records = control_values(spec, requested), []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state, control = (
            STATE_TYPE(*(v[i] for v in history)),
            type(controls)(*(v[j] for v in controls)),
        )
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Resolved kinetic observation domain invalid")
        v, n, r = w.field, p.active.size, w.field.rates
        records.append(
            (
                np.asarray(t),
                *state,
                *physical_amounts(state, p),
                v.potential_V[:n],
                v.potential_V[n:],
                r.membrane_voltage_V,
                r.junction_voltage_V,
                r.membrane_flux_fmol_s,
                r.junction_flux_fmol_s,
                r.face_flux_fmol_s,
                r.reservoir_supply_fmol_s,
                v.electrode_charge_C,
                v.electrode_current_A,
                np.atleast_1d(v.reservoir_power_pJ_s),
                np.atleast_1d(v.electrode_power_pJ_s),
                v.charge_residual_C,
                v.component_current_residual_A,
                np.atleast_1d(v.energy_balance_pJ_s),
                control.membrane,
                control.junction,
                w.channel_flux_fmol_s,
                w.channel_targets,
                w.channel_tau_s,
                w.derivative.pump_cycles,
                w.pump_affinity_J_mol,
                w.derivative.metabolic_work_pJ,
                control.channel,
                control.pump,
            )
        )
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
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not v.converged:
        raise NumericalError("Resolved kinetic ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, spec) | {
        "model": model_id(spec.model),
        "state_fields": list(STATE_TYPE._fields),
        **(
            {"channel_laws": {c.id: c.kinetic_law for c in spec.model.channels}}
            if isinstance(spec.model, SurfaceChannelModel)
            else {"channel_law": voltage_gates.LAW_ID}
        ),
        "junction_law": junction_gate.LAW_ID,
        "pump_law": pump.LAW_ID,
        "membrane_transfer_ledger": "baseline passive only; channel and pump ledgers separate",
    }
