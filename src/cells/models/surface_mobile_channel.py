"""Neutral mobile Kv1.5 populations carrying their complete joint gate state.

Open channels set same-stage potassium permeability. Conserved conformation
amounts, lateral transfer, gate transitions and ideal-mixture/rate-bias ledgers
remain distinct from ionic, ATP and electrode work. Gate bias is a declared
phenomenological source, not resolved gating charge or measured metabolic work.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_mobile_channel_spec import MODEL_ID, prior_spec
from cells.core.surface_mobile_pump_spec import Control as PumpControl
from cells.models import surface_mobile_pump as prior
from cells.models import surface_redistribution as surface
from cells.models import surface_tissue as ionic
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import mobile_channel_gates as gates

OBSERVER_ID = "resolved_mobile_joint_gate_readouts@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_joint_gate_populations_actual_control_resolved_field@1"
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "channel_population_capacity")
EXTRA_AXES = {
    "channel_state_amount_increment": [
        "channel_population_slot",
        "joint_gate_state",
        "membrane_slot",
    ],
    "channel_state_transferred": [
        "channel_population_slot",
        "joint_gate_state",
        "surface_edge_slot",
    ],
    "channel_state_dissipated_energy_pJ": [
        "channel_population_slot",
        "joint_gate_state",
        "surface_edge_slot",
    ],
    "channel_gate_transferred": ["channel_population_slot", "gate_transition", "membrane_slot"],
    "channel_gate_dissipated_energy_pJ": [
        "channel_population_slot",
        "gate_transition",
        "membrane_slot",
    ],
    "channel_gate_bias_work_pJ": ["channel_population_slot", "gate_transition", "membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceMobileChannelState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceMobileChannelLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "channel_active",
            "channel_state_reference",
            "channel_reference_density",
            "channel_diffusivity",
            "channel_permeability",
            "channel_dynamic",
        )
    ],
)
OBSERVATION_FIELDS = (
    *prior.OBSERVATION_FIELDS,
    *EXTRA_AXES,
    "channel_state_amount_fmol",
    "channel_state_density_fmol_um2",
    "channel_state_flux_fmol_s",
    "channel_gate_transition_rate_fmol_s",
    "channel_gate_target",
    "channel_gate_tau_s",
    "channel_gate_marginals",
    "channel_open_fraction",
    "channel_joint_correlation",
    "channel_availability",
    "channel_mixing_balance_pJ",
)
Observations = make_dataclass(
    "SurfaceMobileChannelObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters


class Values(NamedTuple):
    pump: object
    derivative: object
    surface: object
    gating: object
    permeability: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def amounts(state, p):
    return p.channel_state_reference + state.channel_state_amount_increment


def surface_state(state):
    populations = state.channel_state_amount_increment.shape[0] * 4
    return surface.STATE_TYPE(
        *surface.base_state(state),
        *(
            getattr(state, k).reshape((populations, getattr(state, k).shape[-1]))
            for k in tuple(EXTRA_AXES)[:3]
        ),
    )


def surface_layout(p, *, xp=np):
    k, _, m = p.channel_state_reference.shape
    return surface.LAYOUT_TYPE(*(getattr(p, k) for k in surface.LAYOUT_TYPE._fields))._replace(
        surface_amount_reference=p.channel_state_reference.reshape((k * 4, m)),
        reference_density=xp.repeat(p.channel_reference_density, 4),
        reference_permeability=xp.zeros((p.valence.shape[0], k * 4)),
        mobile_effective_charge_e=xp.zeros(k * 4),
        mobile_edge_diffusivity_um2_s=xp.repeat(p.channel_diffusivity, 4, axis=0),
    )


def accounting_layout(p, *, xp=np):
    present = xp.sum(p.channel_state_reference, axis=1) > 0
    return prior_layout(p)._replace(
        membrane_permeability=p.membrane_permeability
        + p.channel_permeability @ xp.asarray(present, dtype=float)
    )


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple((p.id, p.kinetic_law, p.species_id) for p in model.mobile_channels),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(spec) + 768 * x.channel_population_capacity * (
        x.membrane_capacity + x.surface_edge_capacity + len(spec.model.species_ids)
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    m, x = spec.model, spec.execution
    k, n, e = x.channel_population_capacity, x.membrane_capacity, x.surface_edge_capacity
    reference = np.zeros((k, 4, n))
    density = np.ones(k)
    diff = np.zeros((k, e))
    permeability = np.zeros((len(m.species_ids), k))
    dynamic = np.zeros(k, dtype=bool)
    for i, pop in enumerate(m.mobile_channels):
        reference[i, :, : len(m.membranes)] = pop.initial_state_amount_fmol
        density[i] = pop.reference_density_fmol_per_um2
        diff[i, : len(m.surface_edges)] = pop.diffusivity_um2_per_s
        permeability[m.species_ids.index(pop.species_id), i] = (
            pop.permeability_at_reference_density_m_per_s
        )
        dynamic[i] = pop.gate_mode == "dynamic"
    layout = LAYOUT_TYPE(
        *p, np.arange(k) < len(m.mobile_channels), reference, density, diff, permeability, dynamic
    )
    return STATE_TYPE(
        *state,
        np.zeros((k, 4, n)),
        np.zeros((k, 4, e)),
        np.zeros((k, 4, e)),
        np.zeros((k, 4, n)),
        np.zeros((k, 4, n)),
        np.zeros((k, 4, n)),
    ), layout


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), accounting_layout(p, xp=xp), active, xp=xp)
    valid &= surface.surface_domain_valid(surface_state(state), surface_layout(p, xp=xp), xp=xp)
    support = (p.channel_state_reference[:, 0] > 0)[:, None] & p.channel_dynamic[:, None, None]
    for value in (
        state.channel_gate_transferred,
        state.channel_gate_dissipated_energy_pJ,
        state.channel_gate_bias_work_pJ,
    ):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(support, True, value == 0))
    return valid


def readouts(state, control, p, *, xp=jnp):
    amount = amounts(state, p)
    area = xp.where(p.membrane_active, p.mobile_patch_area_um2, 1.0)
    conductive = amount[:, 3] / area / p.channel_reference_density[:, None] * control.channel
    passive = surface.effective_layout(
        surface.STATE_TYPE(*(getattr(state, k) for k in surface.STATE_TYPE._fields)), p, xp=xp
    )
    permeability = (
        passive.membrane_permeability * control.membrane + p.channel_permeability @ conductive
    )
    pc = PumpControl(xp.asarray(p.membrane_active, dtype=float), control.junction, control.pump)
    w = prior.readouts(
        prior_state(state),
        pc,
        accounting_layout(p, xp=xp),
        xp=xp,
        membrane_permeability=permeability,
    )
    present = p.channel_state_reference[:, 0] > 0
    g = gates.rates(
        amount,
        w.field.rates.membrane_voltage_V[None, :],
        present,
        p.channel_dynamic,
        p.temperature,
        xp=xp,
    )
    motion, heat = surface.surface_readouts(surface_state(state), surface_layout(p, xp=xp), xp=xp)
    k, _, n = amount.shape
    result = STATE_TYPE(
        *w.derivative,
        motion.amount_rate_fmol_s.reshape((k, 4, n)) + g.amount_rate,
        motion.flux_fmol_s.reshape((k, 4, -1)),
        heat.reshape((k, 4, -1)),
        g.transfer,
        g.dissipation,
        g.bias_work,
    )
    support = p.channel_active[:, None] & p.membrane_active
    valid = w.valid & g.valid & motion.valid & domain_valid(state, p, p.active, xp=xp)
    for value, mask in ((control.channel, support), (control.membrane, p.membrane_active)):
        valid &= (
            xp.all(xp.isfinite(value))
            & xp.all((value >= 0) & (value <= 1))
            & xp.all(xp.where(mask, True, value == 0))
        )
    for value in result:
        valid &= xp.all(xp.isfinite(value))
    return Values(w, result, motion, g, permeability, valid)


def rhs(state, control, p, active, *, xp=jnp):
    v = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(v.valid, x, xp.nan) for x in v.derivative))


def field_values(state, control, p, *, xp=jnp):
    v = readouts(state, control, p, xp=xp)
    return v.pump.field._replace(
        converged=v.valid, rates=v.pump.field.rates._replace(valid=v.valid)
    )


def control_domain_valid(state, control, p, active, *, xp=jnp):
    ok = domain_valid(state, p, active, xp=xp)
    if xp is np:
        if not ok:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(ok, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False))


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
            channel_population_capacity=len(m.mobile_channels),
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    c = control_values(compact, [v.time for v in compact.experiment.changes])
    for i in range(len(compact.experiment.changes)):
        control = type(c)(*(v[i] for v in c))
        if not control_domain_valid(state, control, p, p.active, xp=np):
            raise ConfigError("Initial mobile-channel domain or actual-control field invalid")


def check_steps(spec, steps, controls):
    ionic.check_steps(spec, steps, controls)
    m = spec.model
    channel_loss = surface.surface_loss_bound(m, m.mobile_channels)
    if any(p.gate_mode == "dynamic" for p in m.mobile_channels):
        channel_loss += gates.MAX_GATE_EXIT_PER_S
    bound = max(
        surface.surface_loss_bound(m, m.mobile_populations),
        surface.surface_loss_bound(m, m.mobile_pumps),
        channel_loss,
    )
    if np.max(steps, initial=0) * bound > surface.MAX_SURFACE_LOSS_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Joint gate-state diffusion/transition requires a smaller RK4 step")


def channel_balances(state, p):
    b = surface.surface_balances(surface_state(state), surface_layout(p))
    k, _, n = state.channel_state_amount_increment.shape
    local = b["local"].reshape((k, 4, n)) - gates.incidence(state.channel_gate_transferred, xp=np)
    cell = ordered_scatter(
        state.channel_state_amount_increment.sum(axis=1),
        np.zeros((k, p.active.size)),
        (p.membrane_cell,),
        xp=np,
    )
    energy = b["energy"].reshape((k, 4)).sum(axis=1) + (
        state.channel_gate_dissipated_energy_pJ - state.channel_gate_bias_work_pJ
    ).sum(axis=(1, 2))
    return dict(local=local, cell=cell, energy=energy)


def check_values(state, spec):
    _, p = initial_values(spec)
    result = prior.check_values(prior_state(state), prior_spec(spec), layout=accounting_layout(p))
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    names = (
        "max_channel_state_balance_error_fmol",
        "max_channel_cell_balance_error_fmol",
        "max_channel_mixing_balance_error_pJ",
    )
    result.update(dict.fromkeys(names, 0.0))
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid joint channel state, history or padding; no repair")
        for name, value, bound in zip(
            names,
            channel_balances(row, p).values(),
            (
                surface.SURFACE_MATERIAL_ATOL_FMOL,
                surface.SURFACE_MATERIAL_ATOL_FMOL,
                surface.SURFACE_ENERGY_ATOL_PJ,
            ),
            strict=True,
        ):
            error = float(np.max(np.abs(value), initial=0))
            if not np.isfinite(value).all() or error > bound:
                raise NumericalError("Mobile channel accounting failed: " + name)
            result[name] = max(result[name], error)
    for name in ("channel_state_dissipated_energy_pJ", "channel_gate_dissipated_energy_pJ"):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Channel mixture dissipation cannot be negative or decrease")
    return result


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    times, requested = np.asarray(times), np.asarray(requested)
    if any(t not in times for t in requested):
        raise ConfigError("Mobile channel observations require accepted boundaries")
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    controls = control_values(spec, requested)
    records = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Mobile channel observation domain invalid")
        f = w.pump.field
        r = f.rates
        n = p.active.size
        leak = surface.STATE_TYPE(*(getattr(state, k) for k in surface.STATE_TYPE._fields))
        lp = surface.LAYOUT_TYPE(*(getattr(p, k) for k in surface.LAYOUT_TYPE._fields))
        lr = surface.surface_rates(leak, lp, xp=np)
        ps = prior.pump_surface_state(state)
        pp = prior.pump_surface_layout(p)
        pr = surface.surface_rates(ps, pp, xp=np)
        amount = amounts(state, p)
        total = amount.sum(axis=1)
        safe = np.where(total > 0, total, 1)
        marginal = np.stack(
            ((amount[:, 2] + amount[:, 3]) / safe, (amount[:, 1] + amount[:, 3]) / safe), axis=1
        )
        opened = amount[:, 3] / safe
        row = state._asdict() | dict(
            times=np.asarray(t),
            amount=ionic.physical_amounts(state, p)[0],
            extracellular_amount=ionic.physical_amounts(state, p)[1],
            cell_potential_V=f.potential_V[:n],
            extracellular_potential_V=f.potential_V[n:],
            membrane_voltage_V=r.membrane_voltage_V,
            junction_voltage_V=r.junction_voltage_V,
            membrane_flux_fmol_s=r.membrane_flux_fmol_s,
            junction_flux_fmol_s=r.junction_flux_fmol_s,
            face_flux_fmol_s=r.face_flux_fmol_s,
            reservoir_supply_fmol_s=r.reservoir_supply_fmol_s,
            electrode_charge_C=f.electrode_charge_C,
            electrode_current_A=f.electrode_current_A,
            reservoir_power_pJ_s=np.atleast_1d(f.reservoir_power_pJ_s),
            electrode_power_pJ_s=np.atleast_1d(f.electrode_power_pJ_s),
            charge_residual_C=f.charge_residual_C,
            component_current_residual_A=f.component_current_residual_A,
            energy_balance_pJ_s=np.atleast_1d(f.energy_balance_pJ_s),
            membrane_availability=control.membrane,
            junction_availability=control.junction,
            surface_amount_fmol=surface.surface_amount(leak, lp),
            surface_density_fmol_um2=lr.density_fmol_um2,
            surface_flux_fmol_s=lr.flux_fmol_s,
            effective_membrane_permeability_m_per_s=w.permeability,
            surface_energy_balance_pJ=surface.surface_balances(leak, lp)["energy"],
            pump_amount_fmol=p.pump_amount_reference + state.pump_surface_amount_increment,
            pump_density_fmol_um2=pr.density_fmol_um2,
            pump_surface_flux_fmol_s=pr.flux_fmol_s,
            pump_surface_energy_balance_pJ=surface.surface_balances(ps, pp)["energy"],
            pump_cycle_rate_fmol_s=w.derivative.pump_cycles,
            pump_capacity_fmol_s=w.pump.capacity,
            pump_affinity_J_mol=w.pump.affinity,
            metabolic_power_pJ_s=w.derivative.metabolic_work_pJ,
            pump_availability=control.pump,
            channel_state_amount_fmol=amount,
            channel_state_density_fmol_um2=w.surface.density_fmol_um2.reshape(amount.shape),
            channel_state_flux_fmol_s=w.surface.flux_fmol_s.reshape(
                state.channel_state_transferred.shape
            ),
            channel_gate_transition_rate_fmol_s=w.gating.transfer,
            channel_gate_target=w.gating.targets,
            channel_gate_tau_s=w.gating.tau_s,
            channel_gate_marginals=marginal,
            channel_open_fraction=opened,
            channel_joint_correlation=opened - marginal[:, 0] * marginal[:, 1],
            channel_availability=control.channel,
            channel_mixing_balance_pJ=channel_balances(state, p)["energy"],
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

    c = control_values(spec, [time])
    control = type(c)(*(v[0] for v in c))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    f = field_values(state, control, p, xp=np)
    if not f.converged:
        raise NumericalError("Mobile channel ensemble field invalid")
    return f.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(prior_state(history), diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        mobile_channels=[p.id for p in spec.model.mobile_channels],
        joint_gate_states=list(gates.STATE_IDS),
        gating_energy_scope=(
            "phenomenological ideal-mixture/rate-bias accounting; no resolved gating charge"
        ),
    )
