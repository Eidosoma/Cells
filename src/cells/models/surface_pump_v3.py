"""resolved_pump_tissue@3: resolved_pump_tissue@2 with voltage-gated channel populations.

A channel population (core/surface_pump_v3_spec.py) is one more membrane process
at its patch: the constant-field flux of its law's ion with permeability
P * abundance * opening(gates) * availability, the shared-gate population
equations of resolved_tissue@5 and later (surface_kinetic.readouts). It moves
material from the cell to the patch's outside node, charging both capacitor
components, and has its own per-species transfer and dissipation ledgers. The
field law, factored solver, junction gate, both pumps and every @2 check are
those of models/surface_pump_v2.py; each rate below is @2's sequence of
operations with the channel terms appended, so with no channels this identity
reproduces resolved_pump_tissue@2. Accepted rows are checked on the host
(check_values) or, in vectorized worlds and projective bursts, on the device
(device_checks): the same tests with the same bounds.

Time integration. RK4 (reference runs) integrates the gate equations with every
other rate. The IMEX steps keep the split of @1 and @2: face electromigration
implicit, every other rate explicit at stage potentials, now including the
channel currents at stage gates. Gates are not advanced by the tableau: at each
stage they are the exponential update (numerics/exponential_gates.py) from the
step start to the stage time, from the start and stage membrane voltages. A
stage's voltage depends only on earlier stages' currents, so no iteration is
needed. Gates stay in [0, 1] at any step, and ARS(2,2,2) remains second order
(Euler first order); stiff NaV m gates relax to their quasi-steady values
instead of making the step unstable. The channel currents themselves stay
explicit, so their stiffness depends on how far the channels are open: an
IMEX step refuses itself (no repair) when dt times the membrane relaxation
rate at its actual openings (membrane_rate) exceeds the family's explicit
bound at any explicit stage. The step size the openings admit is therefore a
property of the run, not of the definition: window currents admit
millisecond steps, a fully open NaV1.2 population of 2.5e-7 m/s needs about
0.37 ms.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_pump_v3_spec import (
    GATED_CODES,
    LAW_CODES,
    MODEL_ID,
    NAV1P2_LAW_ID,
    TRAPEZOID_JUNCTION_HEAT,
    Control,
    projection,
)
from cells.coupling.selective import selective_flux
from cells.models import kinetic_finite_extracellular as pumps
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_tissue as tissue
from cells.numerics import exponential_gates as gates
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import calcium_atpase, junction_gate, sodium_channels, voltage_gates
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = kinetic.OBSERVER_ID
OBSERVATION_SAMPLING = kinetic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = kinetic.STAGE_DOMAIN_ID
BATCH_CAPACITIES = (*tissue.BATCH_CAPACITIES, "channel_capacity")
STATE_AXES = second.STATE_AXES | {
    "channel_transferred": ["species", "channel_slot"],
    "channel_dissipated_energy_pJ": ["species", "channel_slot"],
}
STATE_TYPE = NamedTuple("SurfacePumpChannelState", [(k, object) for k in STATE_AXES])
# junction_heat_trapezoid: one element with the trapezoid_nonnegative@1 junction-heat
# booking, none by default, so the step's branch is static (shape, not value). Every
# @3 layout carries it (empty by default); the state layout (STATE_TYPE) is unchanged,
# and @3 checkpoints from source before this field do not load (snapshots already
# refuse a source change).
CHANNEL_LAYOUT_FIELDS = (
    "channel_laws",
    "channel_relative_permeability",
    "channel_gate_active",
    "junction_heat_trapezoid",
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpChannelLayout",
    [
        (k, object)
        for k in (
            *(k for k in second.LAYOUT_TYPE._fields if k != "channel_species"),
            *CHANNEL_LAYOUT_FIELDS,
        )
    ],
)
FLOOR_LAYOUT_TYPE = NamedTuple(  # Declared field solver surface_field.FLOOR_SOLVER_ID.
    "SurfacePumpChannelFloorLayout",
    [
        (k, object)
        for k in (
            *(k for k in second.FLOOR_LAYOUT_TYPE._fields if k != "channel_species"),
            *CHANNEL_LAYOUT_FIELDS,
        )
    ],
)
ENERGY_RTOL = first.ENERGY_RTOL
EXPLICIT_STEP_BOUND = first.EXPLICIT_STEP_BOUND
GATE_INTEGRATOR_ID = gates.LAW_ID
VOLTAGE_DOMAIN_V = voltage_gates.VOLTAGE_DOMAIN_V
# RK4 reference steps keep the resolved channel family's qualified bounds
# (surface_kinetic.check_steps): 2.5 us with NaV1.2, 25 us with Kv1.5/Kir2.1.
RK4_SODIUM_STEP = 2.5e-6
RK4_POTASSIUM_STEP = 25e-6

parameters = first.parameters
batch_signature = first.batch_signature
physical_amounts = first.physical_amounts
global_charge_bound = first.global_charge_bound
node_charge = first.node_charge
rebind = first.rebind


class Values(NamedTuple):
    field: object
    derivative: object
    channel_flux_fmol_s: object
    channel_targets: object
    channel_tau_s: object
    pump_affinity_J_mol: object
    calcium_pump_affinity_J_mol: object
    valid: object


def working_size(spec):
    x, s = spec.execution, len(spec.model.species_ids)
    return second.working_size(projection(spec)) + 2 * (2 + 2 * s) * x.channel_capacity


def initial_values(spec):
    state, layout = second.initial_values(projection(spec))
    m, nc, s = spec.model, spec.execution.channel_capacity, len(spec.model.species_ids)
    v = layout._asdict()
    del v["channel_species"]
    v.update(
        channel_active=np.arange(nc) < len(m.channels),
        channel_membranes=np.zeros(nc, dtype=np.int64),
        channel_permeability=np.zeros(nc),
        channel_abundance=np.zeros(nc),
        channel_laws=np.zeros(nc, dtype=np.int64),
        channel_relative_permeability=np.zeros((s, nc)),
        channel_gate_active=np.zeros((2, nc), dtype=bool),
        junction_heat_trapezoid=np.zeros(int(m.junction_heat_booking == TRAPEZOID_JUNCTION_HEAT)),
    )
    gate, mids = np.zeros((2, nc)), [p.id for p in m.membranes]
    for i, c in enumerate(m.channels):
        v["channel_membranes"][i] = mids.index(c.membrane_id)
        v["channel_permeability"][i] = c.max_permeability_m_per_s
        v["channel_abundance"][i] = c.abundance
        v["channel_laws"][i] = LAW_CODES[c.kinetic_law]
        for ion in c.permeant_ions:
            row = m.species_ids.index(ion.species_id)
            v["channel_relative_permeability"][row, i] = ion.relative_permeability
        v["channel_gate_active"][: len(c.initial_gate), i] = True
        gate[: len(c.initial_gate), i] = c.initial_gate
    channel = dict(
        channel_gate=gate,
        channel_transferred=np.zeros((s, nc)),
        channel_dissipated_energy_pJ=np.zeros((s, nc)),
    )
    kind = FLOOR_LAYOUT_TYPE if "field_current_floor" in v else LAYOUT_TYPE
    return STATE_TYPE(**(state._asdict() | channel)), kind(**v)


def channel_kinetics(voltage, codes, *, xp=jnp):
    """Targets and time constants [..., 2, channel] in s; gate-free leaks get 0 and 1."""
    gated = codes < GATED_CODES
    target, tau = sodium_channels.kinetics(voltage, xp.where(gated, codes, 0), xp=xp)
    rows = xp.expand_dims(gated, -2)
    return xp.where(rows, target, 0.0), xp.where(rows, tau, 1.0)


def channel_opening(gate, codes, *, xp=jnp):
    gated = codes < GATED_CODES
    return xp.where(gated, sodium_channels.opening(gate, xp.where(gated, codes, 0), xp=xp), 1.0)


def channel_voltage(membrane_voltage, p, *, xp=jnp):
    return xp.where(p.channel_active, membrane_voltage[p.channel_membranes], 0.0)


def channel_domain_valid(voltage, target, tau, p, *, xp=jnp):
    """Active populations stay on their laws' -120..60 mV domain with finite kinetics."""
    inside = (voltage >= VOLTAGE_DOMAIN_V[0]) & (voltage <= VOLTAGE_DOMAIN_V[1])
    kinetics = xp.isfinite(target) & (target >= 0) & (target <= 1) & xp.isfinite(tau) & (tau > 0)
    return xp.all(xp.where(p.channel_active, inside & xp.all(kinetics, axis=-2), True))


def channel_rates(gate, ci, co, membrane_voltage, delta_mu, availability, p, *, xp=jnp):
    """Outward flux and heat [species, channel], kinetics and voltage of each population."""
    patch = p.channel_membranes
    voltage = channel_voltage(membrane_voltage, p, xp=xp)
    target, tau = channel_kinetics(voltage, p.channel_laws, xp=xp)
    flux = selective_flux(
        ci[:, p.membrane_cell[patch]],
        co[:, p.membrane_outside[patch]],
        voltage,
        p.valence,
        p.temperature,
        p.membrane_area[patch],
        p.channel_permeability * p.channel_relative_permeability,
        0.0,
        p.channel_abundance,
        channel_opening(gate, p.channel_laws, xp=xp) * availability,
        xp=xp,
    )
    flux = xp.where(p.channel_active, flux, 0.0)
    return flux, 1e-3 * flux * delta_mu[:, patch], target, tau, voltage


def channel_to_membrane(value, p, *, xp=jnp):
    """Sum [species, channel] values into their patches [species, membrane]."""
    return scatter(value, xp.zeros_like(p.membrane_permeability), (p.channel_membranes,), xp=xp)


def channel_heat(heat, p, *, xp=jnp):
    return scatter(
        xp.sum(heat, axis=0), xp.zeros_like(p.membrane_area), (p.channel_membranes,), xp=xp
    )


def readouts(state, control, p, *, xp=jnp):
    """surface_pump_v2.readouts with the channel populations' currents and gate rates."""
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
    channel, channel_d, target, tau, cv = channel_rates(
        state.channel_gate,
        ci,
        co,
        r.membrane_voltage_V,
        r.membrane_delta_mu_J_mol,
        control.channel,
        p,
        xp=xp,
    )
    gate_rate = xp.where(p.channel_gate_active, (target - state.channel_gate) / tau, 0.0)
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
    ca_cycles, ca_d, ca_metabolic, ca_affinity, ca_args = second.calcium_rates(
        ci[:, p.membrane_cell], co[:, p.membrane_outside], r.membrane_voltage_V, control, p, xp=xp
    )
    jgate_rate = xp.where(
        p.junction_active,
        junction_gate.rhs(
            state.junction_gate, r.junction_voltage_V, kinetic.junction_parameters(p), xp=xp
        ),
        0.0,
    )
    # Inward-positive pump stoichiometries, outward-positive channel flux.
    extra = (
        -p.stoichiometry * cycles
        - p.calcium_stoichiometry * ca_cycles
        + channel_to_membrane(channel, p, xp=xp)
    )
    cell = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    out_extra = scatter(extra, r.outside_rate_fmol_s, (p.membrane_outside,), xp=xp)
    outside = r.outside_rate_fmol_s + xp.where(p.reservoir, 0.0, out_extra)
    supplied = r.reservoir_supply_fmol_s - xp.where(p.reservoir, out_extra, 0.0)
    total_flux = r.membrane_flux_fmol_s + extra
    total_membrane_d = (
        r.membrane_dissipation_pJ_s + pump_d + ca_d + channel_heat(channel_d, p, xp=xp)
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
        gate_rate,
        channel,
        channel_d,
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
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
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
        channel,
        target,
        tau,
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
    valid = tissue.domain_valid(kinetic.passive_state(state), p, active, xp=xp)
    laws = p.channel_laws
    valid &= xp.all((laws >= 0) & (laws < len(LAW_CODES)))
    valid &= xp.all(xp.where(p.channel_active, True, laws == 0))
    masks = (
        p.channel_gate_active,
        p.channel_active,
        p.channel_active,
        p.junction_active,
        p.pump_present,
        p.pump_present,
        p.pump_present,
        p.calcium_pump_present,
        p.calcium_pump_present,
        p.calcium_pump_present,
    )
    for value, mask in zip(state[len(tissue.STATE_TYPE._fields) :], masks, strict=True):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all((state.channel_gate >= 0) & (state.channel_gate <= 1))
    valid &= xp.all((state.junction_gate >= p.junction_minimum) & (state.junction_gate <= 1))
    # Absent species routes never carry hidden transfers or heat.
    route = p.channel_relative_permeability * p.channel_permeability * p.channel_abundance
    valid &= xp.all(xp.where(route > 0, True, state.channel_transferred == 0))
    valid &= xp.all(xp.where(route > 0, True, state.channel_dissipated_energy_pJ == 0))
    valid &= xp.all(xp.where(p.pump_capacity > 0, True, state.pump_cycles == 0))
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
    """surface_pump_v2.explicit_rates with the channel currents at the same potentials.

    The gate rate is zero here: IMEX steps set gates by the exponential update.
    """
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
    channel, channel_d, target, tau, cv = channel_rates(
        state.channel_gate,
        ci,
        co,
        r.membrane_voltage_V,
        r.membrane_delta_mu_J_mol,
        control.channel,
        p,
        xp=xp,
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
    rate = pump.kinetics(*args, xp=xp)
    cycles = xp.where(p.pump_present, rate.cycles_fmol_s, 0.0)
    ca_cycles, ca_d, ca_metabolic, _, ca_args = second.calcium_rates(
        ci[:, p.membrane_cell], co[:, p.membrane_outside], r.membrane_voltage_V, control, p, xp=xp
    )
    extra = (
        -p.stoichiometry * cycles
        - p.calcium_stoichiometry * ca_cycles
        + channel_to_membrane(channel, p, xp=xp)
    )
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
        channel,
        channel_d,
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
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
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


def potential_kinetics(potential, p, *, xp=jnp):
    """Channel targets, time constants and voltage-domain status at node potentials."""
    n = p.active.size
    membrane = potential[p.membrane_cell] - potential[n + p.membrane_outside]
    voltage = channel_voltage(xp.where(p.membrane_active, membrane, 0.0), p, xp=xp)
    target, tau = channel_kinetics(voltage, p.channel_laws, xp=xp)
    return target, tau, channel_domain_valid(voltage, target, tau, p, xp=xp)


def stage_gates(gate, start, stage, fraction, dt, p, *, xp=jnp):
    """Exponential gate update from the step start to a stage at fraction * dt.

    start is (targets, time constants) at the step start; stage is (targets,
    time constants, voltage domain status) from potential_kinetics. Gate rows
    without a relaxation law (leaks, padding) keep their zero state.
    """
    advanced = gates.advance(gate, start[0], start[1], stage[0], stage[1], fraction * dt, xp=xp)
    return xp.where(p.channel_gate_active, advanced, gate), stage[2]


def imex_step(state, dt, control, p, *, xp=jnp):
    """surface_pump_v2.imex_step with channel currents and exponential stage gates."""
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
    # Channel currents are explicit: refuse the step where their actual
    # conductance at an explicit stage exceeds the family's stability bound.
    valid &= dt * membrane_rate(state, control, p, xp=xp) <= EXPLICIT_STEP_BOUND
    # The start kinetics are the law's own (readouts at the start potentials).
    start_kinetics = (first_values.channel_targets, first_values.channel_tau_s)
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
        gate, ok = stage_gates(
            state.channel_gate,
            start_kinetics,
            potential_kinetics(potential, p, xp=xp),
            xp.sum(explicit_matrix[i]),
            dt,
            p,
            xp=xp,
        )
        stage, valid = stage._replace(channel_gate=gate), valid & ok
        if i < stages - 1:
            rates, ok = explicit_rates(stage, potential, control, p, xp=xp)
            explicit.append(rates)
            valid &= ok & (dt * membrane_rate(stage, control, p, xp=xp) <= EXPLICIT_STEP_BOUND)
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
    if p.junction_heat_trapezoid.shape[0]:  # trapezoid_nonnegative@1 (a static choice).
        # The tableau's explicit weights (delta, 1 - delta), delta < 0, book a negative
        # junction heat increment where a junction's power falls by more than 59% in a
        # step (its voltage crossing zero). This booking instead averages the start
        # and end states' junction powers, both >= 0 (sum_s J_s dmu_s with J_s and dmu_s
        # of one sign); the end state's at its last-stage potentials, which satisfy
        # C phi = its charges. Only this ledger changes: the state is the default's.
        end_power = junction_heat_rate(stage, potential, control, p, xp=xp)
        stage = stage._replace(
            junction_dissipated_energy_pJ=state.junction_dissipated_energy_pJ
            + 0.5 * dt * (explicit[0].junction_dissipated_energy_pJ + end_power)
        )
    valid &= domain_valid(stage, p, p.active, xp=xp)
    for value in stage:
        valid &= xp.all(xp.isfinite(value))
    return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage), valid


def junction_heat_rate(state, potential, control, p, *, xp=jnp):
    """Each junction's dissipation (pJ/s) at the given node potentials.

    The junction part of numerics/surface_transport.transport: constant-field
    flux (coupling/selective.selective_flux) at the gated opening times the
    species' electrochemical potential difference, summed over species.
    """
    s = tissue.field_layout(p).surface
    ci, _ = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    active = s.junction_active
    left = xp.where(active, ci[:, s.junction_sender], 1.0)
    right = xp.where(active, ci[:, s.junction_receiver], 1.0)
    dv = xp.where(active, potential[s.junction_sender] - potential[s.junction_receiver], 0.0)
    mu = R * s.temperature * (xp.log(left) - xp.log(right)) + s.valence * F * dv
    flux = selective_flux(
        left,
        right,
        dv,
        s.valence,
        s.temperature,
        s.junction_area,
        s.junction_permeability,
        0.0,
        1.0,
        control.junction * state.junction_gate,
        xp=xp,
    )
    flux, mu = xp.where(active, flux, 0.0), xp.where(active, mu, 0.0)
    return 1e-3 * xp.sum(flux * mu, axis=0)


def checked_step(state, dt, control, p, active):
    """RK4 for an empty tableau (reference runs); otherwise the declared IMEX step."""
    if p.imex_explicit.shape[0] == 0:
        return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p)


def check_definition(spec):
    from cells.core.surface_pump_v3_spec import control_values

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
    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            if not control_domain_valid(
                state, Control(*(v[i] for v in controls)), p, p.active, xp=np
            ):
                raise ConfigError("Initial resolved channel/junction/pump domain invalid")


def membrane_rate(state, control, p, *, xp=jnp):
    """Gershgorin rate (1/s) of membrane charge relaxation at a stage's actual openings.

    @1's membrane term, max_i sum_m G_m / C_i, with each population's open
    constant-field slope conductance F^2/RT sum z^2 P r a o v A max(c) added to
    its patch (o its opening, v its availability). max(c) bounds the
    constant-field slope, so this bounds the explicit channel stiffness.
    Quasi-steady gating slopes are not included; the step studies measure them.
    """
    ci, co = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 0.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 0.0)
    slope, n, patch = F * F / (R * p.temperature), p.active.size, p.channel_membranes
    largest = xp.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside])
    passive = xp.sum(p.valence**2 * p.membrane_permeability * largest, axis=0) * control.membrane
    open_fraction = xp.where(
        p.channel_active,
        p.channel_abundance * channel_opening(state.channel_gate, p.channel_laws, xp=xp),
        0.0,
    )
    channel = xp.sum(
        p.valence**2 * p.channel_permeability * p.channel_relative_permeability * largest[:, patch],
        axis=0,
    ) * (open_fraction * control.channel)
    membrane = xp.where(p.membrane_active, passive * p.membrane_area, 0.0)
    membrane += scatter(channel * p.membrane_area[patch], membrane, (patch,), xp=xp)
    total = slope * scatter(membrane, xp.zeros(n), (p.membrane_cell,), xp=xp)
    capacitance = scatter(p.membrane_capacitance, xp.zeros(n), (p.membrane_cell,), xp=xp)
    return xp.max(xp.where(p.active, total / xp.where(p.active, capacitance, 1.0), 0.0))


def check_steps(spec, steps, controls):
    """@2's step checks on this definition's own event grid (channel events included).

    Observations must lie on accepted boundaries of the full grid; the junction,
    explicit-rate and calcium bounds depend only on the channel-free part. RK4
    also keeps the channel family's qualified step bounds. IMEX channel
    stiffness depends on the openings, so each IMEX step refuses itself when
    dt * membrane_rate exceeds the explicit bound at a stage.
    """
    from cells.core.grid import EventGrid

    step, base = np.max(steps, initial=0), projection(spec)
    if spec.execution.solver == "rk4":
        tissue.check_steps(spec, steps, controls)
        laws = {c.kinetic_law for c in spec.model.channels if c.initial_gate}
        if NAV1P2_LAW_ID in laws and step > RK4_SODIUM_STEP + 1e-16:
            raise ConfigError("Resolved NaV1.2 channels require RK4 steps <= 2.5 us")
        if laws and step > RK4_POTASSIUM_STEP + 1e-16:
            raise ConfigError("Resolved gated channels require RK4 steps <= 25 us")
    else:
        grid = EventGrid(spec)
        for t in spec.experiment.observation_times:
            try:
                grid.exact_index(t)
            except ConfigError as error:
                raise ConfigError(
                    "Resolved pump observations require accepted integration boundaries"
                ) from error
        if step * first.explicit_rate_bound(base) > EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit-rate stability bound")
        if step * second.calcium_rate_bound(base) > EXPLICIT_STEP_BOUND:
            raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")
    if step * first.junction_gate_rate_bound(spec) > first.GATE_STEP_BOUND:
        raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


def balances(state, p):
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=np)
    result = second.balances(state._replace(membrane_transferred=total), p)
    result["energy"] += np.sum(state.channel_dissipated_energy_pJ)
    return result


def channel_magnitudes(row, p, *, xp=np):
    """surface_pump.ledger_magnitudes with both pumps' and the channels' accumulators."""
    membrane = (
        xp.abs(row.membrane_transferred)
        + channel_to_membrane(xp.abs(row.channel_transferred), p, xp=xp)
        + xp.abs(p.stoichiometry * row.pump_cycles)
        + xp.abs(p.calcium_stoichiometry * row.calcium_pump_cycles)
    )
    metabolic = xp.concatenate(
        (
            xp.abs(row.metabolic_work_pJ) + 1e-3 * xp.abs(p.pump_drive * row.pump_cycles),
            xp.abs(row.calcium_metabolic_work_pJ)
            + 1e-3 * xp.abs(p.calcium_pump_drive * row.calcium_pump_cycles),
        )
    )
    return first.ledger_magnitudes(row, p, membrane, metabolic, xp=xp)


DISSIPATION_FIELDS = tuple(k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ"))


def check_values(state, spec, steps=None):
    """The family's host checks (surface_pump.checked_rows) with the channel ledgers."""
    _, p = initial_values(spec)
    return first.checked_rows(
        state,
        spec,
        p,
        domain=domain_valid,
        balances=balances,
        magnitudes=channel_magnitudes,
        dissipation=DISSIPATION_FIELDS,
        steps=steps,
    )


# Device checks (cells.core.vector_windows, core/projective.py): check_values'
# tests per accepted row, compiled. They are the host tests with the same
# functions and bounds: domain_valid (channel laws and padding, gates in [0, 1],
# no gate state on gate-free leaks or padding, no transfer or heat on an absent
# route), every ledger of balances() with the channel transfers in the membrane
# total and their heat in the energy ledger, bounds from surface_pump.ledger_limits
# with channel_magnitudes, and every dissipation field, channels' included.
DEVICE_CHECKS = first.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = first.DEVICE_DIAGNOSTICS
device_failure_message = first.device_failure_message
device_check_constants = first.device_check_constants


def device_balances(state, p):
    """balances() with jax.numpy: the same channel terms, then @2's, in the same order."""
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=jnp)
    result = second.device_balances(state._replace(membrane_transferred=total), p)
    result["energy"] += jnp.sum(state.channel_dissipated_energy_pJ)
    return result


def device_checks(previous, row, p, constants, steps):
    """check_values' tests for one accepted row on the device: (failed, diagnostics).

    steps is the row's accepted-step count, the host check's value for that row.
    """
    from cells.models.surface_pump_checks import row_checks

    return row_checks(
        previous,
        row,
        p,
        constants,
        steps,
        domain_valid=domain_valid,
        balances=device_balances,
        limits=first.ledger_limits,
        magnitudes=channel_magnitudes,
        dissipation=DISSIPATION_FIELDS,
    )


OBSERVATION_FIELDS = second.OBSERVATION_FIELDS
Observations = make_dataclass(
    "SurfacePumpChannelObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    from cells.core.surface_pump_v3_spec import control_values

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
                w.channel_flux_fmol_s,
                w.channel_targets,
                w.channel_tau_s,
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
    from cells.core.surface_pump_v3_spec import control_values

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
        "gate_integrator": "rk4" if spec.execution.solver == "rk4" else GATE_INTEGRATOR_ID,
        "state_fields": list(STATE_TYPE._fields),
        "junction_law": junction_gate.RELAXATION_LAW_ID,
        "pump_law": pump.LAW_ID,
        "calcium_pump_law": calcium_atpase.LAW_ID,
        "channel_laws": {c.id: c.kinetic_law for c in spec.model.channels},
        "membrane_transfer_ledger": "baseline passive only; channel and pump ledgers separate",
        "junction_heat_booking": spec.model.junction_heat_booking,
    }
