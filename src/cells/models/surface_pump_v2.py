"""resolved_pump_tissue@2: resolved_pump_tissue@1 with a plasma-membrane Ca-ATPase.

The calcium pump (ca_atp_mass_action_positive@1) is one more explicit membrane
process, evaluated at the same stage potentials as every other membrane rate.
Its cycles move Ca from the cell to the patch's outside node, so they charge
both capacitor components; they have their own cycle, dissipation and
metabolic-work ledgers. The field law, the factored solver, the IMEX schemes
(face electromigration implicit), the junction gate and every @1 rate and
check are those of models/surface_pump.py. Each rate below is @1's sequence of
operations with the calcium terms appended, so with no calcium pump this
identity reproduces resolved_pump_tissue@1.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_pump_v2_spec import MODEL_ID, Control
from cells.models import kinetic_finite_extracellular as pumps
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import calcium_atpase, junction_gate
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = kinetic.OBSERVER_ID
OBSERVATION_SAMPLING = kinetic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = kinetic.STAGE_DOMAIN_ID
BATCH_CAPACITIES = first.BATCH_CAPACITIES
CALCIUM_STATE_FIELDS = (
    "calcium_pump_cycles",
    "calcium_pump_dissipated_energy_pJ",
    "calcium_metabolic_work_pJ",
)
STATE_AXES = kinetic.STATE_AXES | {k: ["membrane_slot"] for k in CALCIUM_STATE_FIELDS}
STATE_TYPE = NamedTuple("SurfacePumpCalciumState", [(k, object) for k in STATE_AXES])
CALCIUM_LAYOUT_FIELDS = (
    "calcium_stoichiometry",
    "calcium_pump_present",
    "calcium_pump_species",
    "calcium_pump_drive",
    "calcium_pump_capacity",
    *("calcium_pump_" + k for k in calcium_atpase.Parameters._fields[1:]),
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpCalciumLayout",
    [(k, object) for k in (*first.LAYOUT_TYPE._fields, *CALCIUM_LAYOUT_FIELDS)],
)
ENERGY_RTOL = first.ENERGY_RTOL
EXPLICIT_STEP_BOUND = first.EXPLICIT_STEP_BOUND

parameters = first.parameters
batch_signature = first.batch_signature
physical_amounts = first.physical_amounts
global_charge_bound = first.global_charge_bound
node_charge = first.node_charge
rebind = first.rebind


class Values(NamedTuple):
    field: object
    derivative: object
    pump_affinity_J_mol: object
    calcium_pump_affinity_J_mol: object
    valid: object


def working_size(spec):
    return first.working_size(spec) + 16 * spec.execution.membrane_capacity


def _view(state):
    """The resolved_pump_tissue@1 fields of a state, in @1's state type."""
    return kinetic.STATE_TYPE(*(getattr(state, k) for k in kinetic.STATE_TYPE._fields))


def calcium_parameters(p):
    return calcium_atpase.Parameters(
        p.calcium_pump_capacity,
        *(getattr(p, "calcium_pump_" + k) for k in calcium_atpase.Parameters._fields[1:]),
    )


def initial_values(spec):
    state, layout = first.initial_values(spec)
    v, m = layout._asdict(), spec.model
    nm, s = spec.execution.membrane_capacity, len(m.species_ids)
    v.update(
        calcium_stoichiometry=np.zeros((s, nm)),
        calcium_pump_present=np.zeros(nm, dtype=bool),
        calcium_pump_species=np.zeros(nm, dtype=np.int64),
        calcium_pump_drive=np.zeros(nm),
        calcium_pump_capacity=np.zeros(nm),
    )
    # Absent routes: neutral pools with zero chemical drive (as for the Na/K pump).
    for name in calcium_atpase.Parameters._fields[1:]:
        neutral = 0.0 if name == "delta_g0_J_mol" else 1000.0 if name == "pi_mM" else 1.0
        v["calcium_pump_" + name] = np.full(nm, neutral)
    for i, membrane in enumerate(m.membranes):
        c = membrane.calcium_pump
        if c is None:
            continue
        pools = c.metabolism
        declared = calcium_atpase.Parameters(
            c.capacity_fmol_per_s,
            pools.atp_mM,
            pools.adp_mM,
            pools.pi_mM,
            c.km_ca_mM,
            c.km_atp_mM,
            pools.delta_g0_J_per_mol,
        )
        k = m.species_ids.index(c.role)
        v["calcium_pump_present"][i], v["calcium_pump_species"][i] = True, k
        v["calcium_stoichiometry"][k, i] = calcium_atpase.CALCIUM_PER_CYCLE
        v["calcium_pump_capacity"][i] = c.capacity_fmol_per_s
        v["calcium_pump_drive"][i] = calcium_atpase.chemical_drive(declared, m.temperature_K, xp=np)
        for name, value in zip(declared._fields[1:], declared[1:], strict=True):
            v["calcium_pump_" + name][i] = value
    zero = np.zeros(nm)
    return STATE_TYPE(*state, zero, zero.copy(), zero.copy()), LAYOUT_TYPE(**v)


def calcium_inputs(ci, co, voltage, temperature, p, *, xp):
    """Role gathers before masking; only absent routes receive neutral arguments."""
    slots = xp.arange(p.calcium_pump_capacity.shape[-1])
    present, k = p.calcium_pump_present, p.calcium_pump_species
    return (
        xp.where(present, ci[..., k, slots], 1.0),
        xp.where(present, co[..., k, slots], 1.0),
        xp.where(present, voltage, 0.0),
        xp.where(present, temperature, 298.15),
    )


def calcium_rates(ci, co, voltage, control, p, *, xp):
    """(cycles, dissipation, metabolic power, affinity, args) at given patch inputs."""
    args = (
        *calcium_inputs(ci, co, voltage, p.temperature, p, xp=xp),
        calcium_parameters(p),
        control.calcium_pump,
    )
    rate = calcium_atpase.kinetics(*args, xp=xp)
    cycles = xp.where(p.calcium_pump_present, rate.cycles_fmol_s, 0.0)
    affinity = xp.where(p.calcium_pump_present, rate.cycle_free_energy_J_mol, 0.0)
    return (
        cycles,
        -1e-3 * cycles * rate.cycle_free_energy_J_mol,
        -1e-3 * cycles * rate.chemical_drive_J_mol,
        affinity,
        args,
    )


def readouts(state, control, p, *, xp=jnp):
    """surface_kinetic.readouts for an empty channel set, with the calcium pump."""
    from cells.core.schedule import SurfaceControl

    v = tissue.field_values(
        state, SurfaceControl(control.membrane, control.junction * state.junction_gate), p, xp=xp
    )
    r, n = v.rates, p.active.size
    ci, co = physical_amounts(state, p)
    ci, co = (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )
    args = (
        *pumps.role_inputs(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            r.membrane_delta_mu_J_mol,
            p.temperature,
            p,
            xp=xp,
        ),
        pumps.pump_parameters(p),
        control.pump,
    )
    pr = pump.kinetics(*args, xp=xp)
    cycles = xp.where(p.pump_present, pr.cycles_fmol_s, 0.0)
    pump_d = -1e-3 * cycles * pr.cycle_free_energy_J_mol
    metabolic = -1e-3 * cycles * pr.chemical_drive_J_mol
    ca_cycles, ca_d, ca_metabolic, ca_affinity, ca_args = calcium_rates(
        ci[:, p.membrane_cell], co[:, p.membrane_outside], r.membrane_voltage_V, control, p, xp=xp
    )
    jgate_rate = xp.where(
        p.junction_active,
        junction_gate.rhs(
            state.junction_gate, r.junction_voltage_V, kinetic.junction_parameters(p), xp=xp
        ),
        0.0,
    )
    # Inward-positive pump stoichiometries; both pumps transfer at the patch.
    extra = -p.stoichiometry * cycles - p.calcium_stoichiometry * ca_cycles
    cell = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    out_extra = scatter(extra, r.outside_rate_fmol_s, (p.membrane_outside,), xp=xp)
    outside = r.outside_rate_fmol_s + xp.where(p.reservoir, 0.0, out_extra)
    supplied = r.reservoir_supply_fmol_s - xp.where(p.reservoir, out_extra, 0.0)
    total_flux = r.membrane_flux_fmol_s + extra
    total_membrane_d = r.membrane_dissipation_pJ_s + pump_d + ca_d
    total_rates = r._replace(
        cell_rate_fmol_s=cell,
        outside_rate_fmol_s=outside,
        reservoir_supply_fmol_s=supplied,
        membrane_flux_fmol_s=total_flux,
        membrane_current_A=CHARGE_PER_FMOL * xp.sum(p.valence * total_flux, axis=0),
        membrane_dissipation_pJ_s=total_membrane_d,
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = field._capacitor_solve(qdot, xp.zeros_like(qdot), tissue.field_layout(p), xp=xp)
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
        - xp.sum(ca_metabolic)
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
        xp.zeros_like(state.channel_gate),
        xp.zeros_like(state.channel_transferred),
        xp.zeros_like(state.channel_dissipated_energy_pJ),
        jgate_rate,
        cycles,
        pump_d,
        metabolic,
        ca_cycles,
        ca_d,
        ca_metabolic,
    )
    valid = v.converged & xp.all(pump.domain_valid(*args, xp=xp))
    valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    for value in control:
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
    valid &= xp.all(
        junction_gate.domain_valid(
            state.junction_gate,
            r.junction_voltage_V,
            kinetic.junction_parameters(p),
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
        xp.where(p.pump_present, pr.cycle_free_energy_J_mol, 0.0),
        ca_affinity,
        valid,
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


def domain_valid(state, p, active, *, xp=jnp):
    valid = kinetic.domain_valid(_view(state), p, active, xp=xp)
    for name in CALCIUM_STATE_FIELDS:
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(
            xp.where(p.calcium_pump_present, True, value == 0)
        )
    valid &= xp.all(xp.where(p.calcium_pump_capacity > 0, True, state.calcium_pump_cycles == 0))
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


def explicit_rates(state, potential, control, p, *, xp=jnp):
    """surface_pump.explicit_rates with the calcium pump at the same potentials."""
    s, n = tissue.field_layout(p).surface, p.active.size
    ci, co = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    r = surface.transport(
        ci,
        co,
        potential[:n],
        potential[n:],
        control.membrane,
        control.junction * state.junction_gate,
        s,
        xp=xp,
    )
    weight, log = imex.face_weights(co, s, xp=xp)
    diffusion = weight * log
    args = (
        *pumps.role_inputs(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            r.membrane_delta_mu_J_mol,
            p.temperature,
            p,
            xp=xp,
        ),
        pumps.pump_parameters(p),
        control.pump,
    )
    rate = pump.kinetics(*args, xp=xp)
    cycles = xp.where(p.pump_present, rate.cycles_fmol_s, 0.0)
    ca_cycles, ca_d, ca_metabolic, _, ca_args = calcium_rates(
        ci[:, p.membrane_cell], co[:, p.membrane_outside], r.membrane_voltage_V, control, p, xp=xp
    )
    extra = -p.stoichiometry * cycles - p.calcium_stoichiometry * ca_cycles
    zero = xp.zeros_like(co)
    inflow = (
        scatter(r.membrane_flux_fmol_s + extra, zero, (p.membrane_outside,), xp=xp)
        - scatter(diffusion, zero, (p.face_sender,), xp=xp)
        + scatter(diffusion, zero, (p.face_receiver,), xp=xp)
    )
    gate = junction_gate.rhs(
        state.junction_gate, r.junction_voltage_V, kinetic.junction_parameters(p), xp=xp
    )
    outside_zero = xp.zeros_like(p.boundary_V)
    rates = STATE_TYPE(
        r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp),
        xp.where(p.reservoir, 0.0, inflow),
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        diffusion,
        xp.where(p.reservoir, -inflow, 0.0),
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        xp.zeros_like(state.face_dissipated_energy_pJ),
        outside_zero,
        outside_zero,
        outside_zero,
        xp.zeros_like(state.channel_gate),
        xp.zeros_like(state.channel_transferred),
        xp.zeros_like(state.channel_dissipated_energy_pJ),
        xp.where(p.junction_active, gate, 0.0),
        cycles,
        -1e-3 * cycles * rate.cycle_free_energy_J_mol,
        -1e-3 * cycles * rate.chemical_drive_J_mol,
        ca_cycles,
        ca_d,
        ca_metabolic,
    )
    valid = r.valid & xp.all(pump.domain_valid(*args, xp=xp))
    valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    valid &= xp.all(
        junction_gate.domain_valid(
            state.junction_gate,
            r.junction_voltage_V,
            kinetic.junction_parameters(p),
            control.junction,
            xp=xp,
        )
    )
    for value in (*control, *rates):
        valid &= xp.all(xp.isfinite(value))
    for value in control:
        valid &= xp.all((value >= 0) & (value <= 1))
    return rates, valid


def implicit_rates(weight, potential, state, p, *, xp=jnp):
    """Face electromigration rates with frozen face weights; zero elsewhere."""
    s, n = tissue.field_layout(p).surface, p.active.size
    flux = imex.drift_flux(weight, potential[n:], s, xp=xp)
    zero = xp.zeros_like(state.extracellular_amount_increment)
    inflow = scatter(flux, zero, (p.face_receiver,), xp=xp) - scatter(
        flux, zero, (p.face_sender,), xp=xp
    )
    rates = STATE_TYPE(*(xp.zeros_like(v) for v in state))
    return rates._replace(
        extracellular_amount_increment=xp.where(p.reservoir, 0.0, inflow),
        face_transferred=flux,
        reservoir_supplied=xp.where(p.reservoir, -inflow, 0.0),
    )


def imex_step(state, dt, control, p, *, xp=jnp):
    """surface_pump.imex_step with this identity's rates (same tableau and checks)."""
    f = tissue.field_layout(p)
    s, explicit_matrix, implicit_matrix = f.surface, p.imex_explicit, p.imex_implicit
    stages = explicit_matrix.shape[0]
    first_values = readouts(state, control, p, xp=xp)
    start = first_values.field.potential_V
    valid = first_values.valid
    amount = p.extracellular_amount_reference + state.extracellular_amount_increment
    predicted = (
        amount + p.imex_operator_time * dt * first_values.derivative.extracellular_amount_increment
    )
    predicted = xp.where(p.outside_active, predicted / p.extracellular_volume, 1.0)
    valid &= xp.all(xp.isfinite(predicted) & (predicted > 0))
    weight, _ = imex.face_weights(xp.where(predicted > 0, predicted, 1.0), s, xp=xp)
    operator, ok = imex.factor_operator(
        implicit_matrix[-1, -1] * dt, imex.face_laplacian(weight, s, xp=xp), p.boundary_V, f, xp=xp
    )
    valid &= ok
    rates, ok = explicit_rates(state, start, control, p, xp=xp)
    explicit, implicit, valid = [rates], [None], valid & ok
    potential, stage = start, state
    for i in range(1, stages):
        known = first._combine(
            state,
            dt,
            [(explicit_matrix[i, j], explicit[j]) for j in range(i)]
            + [(implicit_matrix[i, j], implicit[j]) for j in range(1, i)],
        )
        charge = node_charge(known, p, xp=xp)
        potential, residual = imex.solve_operator(charge, operator, xp=xp)
        scale = xp.maximum(xp.abs(charge), xp.abs(operator.matrix @ potential))
        valid &= xp.all(xp.isfinite(potential))
        valid &= xp.all(xp.abs(residual) <= field.CHARGE_ATOL_C + field.CHARGE_RTOL * scale)
        drift = implicit_rates(weight, potential, state, p, xp=xp)
        implicit.append(drift)
        stage = first._combine(known, dt, [(implicit_matrix[i, i], drift)])
        if i < stages - 1:
            rates, ok = explicit_rates(stage, potential, control, p, xp=xp)
            explicit.append(rates)
            valid &= ok
    last = stages - 1

    def applied(name):
        return sum(
            explicit_matrix[last, j] * getattr(explicit[j], name) for j in range(stages - 1)
        ) + sum(implicit_matrix[last, j] * getattr(implicit[j], name) for j in range(1, stages))

    # Dissipation of the applied average face flux, J^2 RT / W >= 0.
    flux = applied("face_transferred")
    heat = (
        1e-3
        * R
        * p.temperature
        * xp.sum(xp.where(weight > 0, flux * flux / xp.where(weight > 0, weight, 1.0), 0.0), axis=0)
    )
    electrode = first.electrode_increment(state, stage, p, xp=xp)
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    stage = stage._replace(
        face_dissipated_energy_pJ=state.face_dissipated_energy_pJ + dt * heat,
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        reservoir_work_pJ=state.reservoir_work_pJ
        + 1e-3 * xp.sum(mu * (dt * applied("reservoir_supplied")), axis=0),
        electrode_work_pJ=state.electrode_work_pJ + 1e12 * p.boundary_V * electrode,
    )
    valid &= domain_valid(stage, p, p.active, xp=xp)
    for value in stage:
        valid &= xp.all(xp.isfinite(value))
    return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage), valid


def checked_step(state, dt, control, p, active):
    """RK4 for an empty tableau (reference runs); otherwise the declared IMEX step."""
    if p.imex_explicit.shape[0] == 0:
        return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p)


def check_definition(spec):
    from cells.core.surface_pump_v2_spec import control_values

    if spec.model.channels or spec.execution.channel_capacity:
        raise ConfigError("Resolved pump tissue has no channel population")
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
        ),
    )
    state, p = initial_values(compact)
    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            if not control_domain_valid(
                state, Control(*(v[i] for v in controls)), p, p.active, xp=np
            ):
                raise ConfigError("Initial resolved junction/pump/calcium pump domain invalid")


def calcium_rate_bound(spec):
    """Bound (1/s) on the calcium pump's relaxation of cytosolic Ca: 2 sum C/(Km V)."""
    _, p = initial_values(spec)
    rate = np.where(p.calcium_pump_present, p.calcium_pump_capacity / p.calcium_pump_km_ca_mM, 0.0)
    cells = scatter(rate, np.zeros(p.active.size), (p.membrane_cell,), xp=np)
    return 2 * float(np.max(np.where(p.active, cells / p.volume, 0.0), initial=0.0))


def check_steps(spec, steps, controls):
    first.check_steps(spec, steps, controls)
    if spec.execution.solver != "rk4" and (
        np.max(steps, initial=0) * calcium_rate_bound(spec) > EXPLICIT_STEP_BOUND
    ):
        raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")


def balances(state, p):
    total = (
        state.membrane_transferred
        - p.stoichiometry * state.pump_cycles
        - p.calcium_stoichiometry * state.calcium_pump_cycles
    )
    result = tissue.balances(kinetic.passive_state(state)._replace(membrane_transferred=total), p)
    result["energy"] += (
        np.sum(state.pump_dissipated_energy_pJ)
        + np.sum(state.calcium_pump_dissipated_energy_pJ)
        - np.sum(state.metabolic_work_pJ)
        - np.sum(state.calcium_metabolic_work_pJ)
    )
    result["metabolic_work"] = np.concatenate(
        (
            state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles,
            state.calcium_metabolic_work_pJ
            + 1e-3 * p.calcium_pump_drive * state.calcium_pump_cycles,
        )
    )
    return result


DISSIPATION_FIELDS = tuple(k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ"))


def check_values(state, spec):
    """surface_pump.check_values with the calcium pump ledgers."""
    _, p = initial_values(spec)
    return first.checked_rows(
        state, spec, p, domain=domain_valid, balances=balances, dissipation=DISSIPATION_FIELDS
    )


# Device checks (cells.core.vector_windows): check_values' tests per accepted row.
DEVICE_CHECKS = first.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = first.DEVICE_DIAGNOSTICS
device_failure_message = first.device_failure_message
device_check_constants = first.device_check_constants


def device_balances(state, p):
    """balances() with jax.numpy: the same calcium terms in the same order."""
    from cells.models.surface_pump_checks import tissue_balances

    total = (
        state.membrane_transferred
        - p.stoichiometry * state.pump_cycles
        - p.calcium_stoichiometry * state.calcium_pump_cycles
    )
    result = tissue_balances(state, total, p)
    result["energy"] += (
        jnp.sum(state.pump_dissipated_energy_pJ)
        + jnp.sum(state.calcium_pump_dissipated_energy_pJ)
        - jnp.sum(state.metabolic_work_pJ)
        - jnp.sum(state.calcium_metabolic_work_pJ)
    )
    result["metabolic_work"] = jnp.concatenate(
        (
            state.metabolic_work_pJ + 1e-3 * p.pump_drive * state.pump_cycles,
            state.calcium_metabolic_work_pJ
            + 1e-3 * p.calcium_pump_drive * state.calcium_pump_cycles,
        )
    )
    return result


def device_checks(previous, row, p, constants):
    """check_values' tests for one accepted row on the device: (failed, diagnostics)."""
    from cells.models.surface_pump_checks import row_checks

    return row_checks(
        previous,
        row,
        p,
        constants,
        domain_valid=domain_valid,
        balances=device_balances,
        limits=first.ledger_limits,
        dissipation=DISSIPATION_FIELDS,
    )


OBSERVATION_FIELDS = (
    *kinetic.OBSERVATION_FIELDS[:1],
    *STATE_TYPE._fields,
    *(k for k in kinetic.OBSERVATION_FIELDS if k not in ("times", *kinetic.STATE_TYPE._fields)),
    "calcium_pump_cycle_rate_fmol_s",
    "calcium_pump_affinity_J_mol",
    "calcium_metabolic_power_pJ_s",
    "calcium_pump_availability",
)
Observations = make_dataclass(
    "SurfacePumpCalciumObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    from cells.core.surface_pump_v2_spec import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved kinetic observations require accepted times")
    controls, records = control_values(spec, requested), []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state, control = (
            STATE_TYPE(*(v[i] for v in history)),
            Control(*(v[j] for v in controls)),
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
                np.zeros_like(state.channel_transferred),
                np.zeros_like(state.channel_gate),
                np.ones_like(state.channel_gate),
                w.derivative.pump_cycles,
                w.pump_affinity_J_mol,
                w.derivative.metabolic_work_pJ,
                control.channel,
                control.pump,
                w.derivative.calcium_pump_cycles,
                w.calcium_pump_affinity_J_mol,
                w.derivative.calcium_metabolic_work_pJ,
                control.calcium_pump,
            )
        )
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.surface_pump_v2_spec import control_values

    controls = control_values(spec, [time])
    control = Control(*(v[0] for v in controls))
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not v.converged:
        raise NumericalError("Resolved kinetic ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return tissue.summarize(history, diagnostics, spec) | {
        "model": MODEL_ID,
        "field_solver": spec.execution.field_solver,
        "time_integrator": spec.execution.solver,
        "state_fields": list(STATE_TYPE._fields),
        "junction_law": junction_gate.RELAXATION_LAW_ID,
        "pump_law": pump.LAW_ID,
        "calcium_pump_law": calcium_atpase.LAW_ID,
        "membrane_transfer_ledger": "baseline passive only; pump ledgers separate",
    }
