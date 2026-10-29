"""Exactly the full56 joint repair @2 owner with native background-D pulses.

Physical chemistry, stage fuel and every parent equation stay owner-specific.
Only the closed background transfer diagnostic receives the qualified
readout-only view; all actual full histories drive accounting and output.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import joint_water_profile_interventions_binding as binding
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_water_repair_profile_interventions_spec import (
    MODEL_ID,
    artifact,
    owner_spec,
)
from cells.models import surface_calcium_energy_water_hcn_extra as water_owner
from cells.models import surface_calcium_energy_water_repair_hcn_extra as base
from cells.models import surface_profile_interventions as scheduled

STATE_AXES = base.STATE_AXES | {"phase_clock_s": ["phase_clock"]}
STATE_TYPE = NamedTuple(
    "SurfaceCalciumEnergyWaterRepairProfileState", [(k, object) for k in STATE_AXES]
)
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyWaterRepairProfileLayout",
    [(k, object) for k in (*base.LAYOUT_TYPE._fields, *scheduled.EXTRA_LAYOUT)],
)
OBSERVER_ID = "resolved_surface_calcium_energy_water_repair_profile_interventions_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_clock_background_D_actual_repair_owner@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "intervention_capacity", "intervention_target_capacity")
OBSERVATION_FIELDS = (
    *base.OBSERVATION_FIELDS,
    "phase_clock_s",
    "membrane_permeability_m_per_s",
    "scheduled_native_Dm_m2_s",
    "native_pulse",
)
Observations = make_dataclass(
    "SurfaceCalciumEnergyWaterRepairProfileObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = base.parameters
signal_values = scheduled.signal_values


def parent_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def parent_layout(layout):
    # Exact parent type is part of channel-catalog dispatch, including its
    # zero/one/two-state and calcium-dependent instantaneous channel contracts.
    return base.LAYOUT_TYPE(*(getattr(layout, k) for k in base.LAYOUT_TYPE._fields))


def water_projection(spec):
    return base.base_spec(owner_spec(spec))


def water_layout(layout):
    return base.base_layout(parent_layout(layout))


def initial_values(spec):
    state, p = base.initial_values(owner_spec(spec))
    layout = LAYOUT_TYPE(**(p._asdict() | binding.native_parameters(spec)))
    return STATE_TYPE(*state, np.zeros(1)), layout


def accounting_layout(p, *, xp=jnp):
    union = scheduled.accounting_layout(p, xp=xp).membrane_permeability
    return parent_layout(p)._replace(membrane_permeability=union)


def accounting_spec(spec):
    _, p = initial_values(spec)
    original = owner_spec(spec)
    union = accounting_layout(p, xp=np).membrane_permeability
    membranes = tuple(
        replace(row, permeability_m_per_s=tuple(union[:, j]))
        for j, row in enumerate(original.model.membranes)
    )
    return replace(original, model=replace(original.model, membranes=membranes))


def readout_state(state, permeability, *, xp):
    # These diagnostic integrals never enter gates, fluxes, pump kinetics,
    # inventories, charge or fields. Only the fixed-parent route validity reads
    # them here. Actual histories remain in state and are checked separately.
    value = parent_state(state)
    return value._replace(
        membrane_transferred=xp.where(permeability > 0, value.membrane_transferred, 0.0)
    )


def domain_valid(state, p, active, *, xp=jnp):
    clock = state.phase_clock_s
    if clock.shape != (1,):
        return xp.asarray(False)
    return base.domain_valid(
        parent_state(state), accounting_layout(p, xp=xp), active, xp=xp
    ) & xp.all(xp.isfinite(clock) & (clock >= 0) & (clock <= p.phase_end_s + p.phase_clock_atol_s))


class Values(NamedTuple):
    field: object
    derivative: object
    signal: object
    parent: object
    valid: object


def readouts(state, control, p, *, xp=jnp):
    signal = signal_values(state, p, xp=xp)
    current = parent_layout(p)._replace(membrane_permeability=signal.permeability)
    value = base.readouts(readout_state(state, signal.permeability, xp=xp), control, current, xp=xp)
    valid = value.valid & signal.valid & domain_valid(state, p, p.active, xp=xp)
    field = value.field._replace(converged=valid, rates=value.field.rates._replace(valid=valid))
    value = value._replace(field=field, valid=valid)
    return Values(
        field,
        STATE_TYPE(*value.derivative, xp.ones_like(state.phase_clock_s)),
        signal,
        value,
        valid,
    )


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp) & signal_values(state, p, xp=xp).valid
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
    clocks = sorted(
        {
            0.0,
            spec.experiment.end_time,
            *(c.time for c in spec.experiment.changes),
            *(
                t
                for e in spec.model.interventions
                for t in (e.on_s, (e.on_s + e.off_s) / 2, e.off_s)
            ),
        }
    )
    controls = control_values(owner_spec(spec), clocks)
    for i, time in enumerate(clocks):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        u = type(controls)(*(v[i] for v in controls))
        if not control_domain_valid(trial, u, p, p.active, xp=np):
            raise ConfigError(
                "Joint water profile pulse/control stage violates the full physical domain"
            )


def check_steps(spec, steps, controls):
    from cells.models import surface_calcium as calcium
    from cells.models import surface_calcium_energy as fuel
    from cells.processes import calcium_gates

    complete = accounting_spec(spec)
    # Preserve all water, live-pool, chemical and prescribed-damage bounds.
    base.check_steps(complete, steps, controls)
    _, p = initial_values(spec)
    minimum = p.water_minimum_volume_pL
    upper = accounting_layout(p, xp=np)._replace(
        volume=minimum[: p.active.size], extracellular_volume=minimum[p.active.size :]
    )
    chemical = fuel.bounded_prior_spec(water_owner.minimum_energy_spec(water_projection(complete)))
    bound = (
        binding.background_loss_bound(upper, max(map(abs, calcium_gates.VOLTAGE_DOMAIN_V)))
        + calcium.loss_bound(chemical)
        + base.injury_loss_bound(complete)
    )
    if not np.isfinite(bound) or np.max(steps, initial=0) * bound > 0.25:
        raise ConfigError("Scheduled joint water minimum-volume complete loss exceeds 0.25")
    scheduled.check_steps(spec, steps, controls)


def check_values(state, spec):
    clock = np.asarray(state.phase_clock_s)
    if clock.ndim not in (1, 2) or clock.shape[-1:] != (1,):
        raise NumericalError("Joint water scheduled phase clock has incompatible shape")
    diagnostics = base.check_values(parent_state(state), accounting_spec(spec))
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.phase_clock_s.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.phase_clock_s))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np) or not signal_values(row, p, xp=np).valid:
            raise NumericalError(
                "Invalid joint water profile physical state/history/clock/permeability; no repair"
            )
    if (
        state.phase_clock_s.ndim == 2
        and np.min(np.diff(np.asarray(state.phase_clock_s)[:, 0]), initial=0)
        < -p.phase_clock_atol_s
    ):
        raise NumericalError("Joint water scheduled phase clock cannot decrease")
    diagnostics["phase_clock_final_s"] = float(np.asarray(rows[-1].phase_clock_s)[0])
    return diagnostics


def check_checkpoint(spec, checkpoint):
    return binding.check_checkpoint(spec, checkpoint)


def batch_signature(model):
    return (
        base.batch_signature(model),
        tuple((c.id, c.membrane_id, c.kinetic_law) for c in model.channels),
        tuple(
            (e.name, e.kind, e.profiles, None if e.spatial is None else e.spatial["axis"])
            for e in model.interventions
        ),
    )


def working_size(spec):
    x = spec.execution
    return (
        base.working_size(owner_spec(spec))
        + 256 * x.intervention_capacity * max(1, x.intervention_target_capacity)
        + 256 * x.membrane_capacity
    )


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values
    from cells.core.surface_calcium_energy_spec import initial_prior_spec
    from cells.models import surface_calcium_energy as fuel
    from cells.models import surface_calcium_water as chemical_water

    # Every material/work check sees the actual full physical history.
    # Only the fixed-parent background-route validity marker uses a view.
    check_values(history, spec)
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    records = []
    for time in requested:
        matches = np.flatnonzero(times == time)
        if len(matches) != 1:
            raise ConfigError("Joint water profile observations need accepted boundaries")
        i = int(matches[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        signal = signal_values(state, p, xp=np)
        if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
            raise ConfigError("Observed joint water phase clock differs from accepted time")
        current = parent_layout(p)._replace(membrane_permeability=signal.permeability)
        actual = parent_state(state)
        view = readout_state(state, signal.permeability, xp=np)
        table = control_values(owner_spec(spec), [time])
        control = type(table)(*(v[0] for v in table))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid actual joint water profile observation")
        stage = water_owner.effective_layout(actual, water_layout(current))
        physical = fuel.prior.observe_history(
            np.asarray([time]),
            fuel.prior.STATE_TYPE(
                *(v[None] for v in fuel.prior_state(water_owner.prior_state(view)))
            ),
            fuel.stage_layout(water_owner.prior_state(actual), stage, xp=np),
            [time],
            initial_prior_spec(water_owner.energy_spec(water_projection(spec))),
        )
        row = {key: v[0] for key, v in vars(physical).items()}
        row.update({key: getattr(actual, key) for key in base.STATE_TYPE._fields})
        amount = fuel.energy_amounts(actual, current)
        conserved = fuel.energy.invariants(amount, xp=np)
        # Actual original history, original volume anchors and separate lesion
        # transfer/heat ledgers supply every conservation observable.
        balance = base.balances(actual, accounting_layout(p, xp=np))
        coupled = value.parent
        full = coupled.calcium
        w = coupled.water
        volume = water_owner.volumes(actual, current)
        n = p.active.size
        inside, outside = water_owner.physical_amounts(actual, current)
        particles = water_owner.osmolyte_amounts(actual, current)
        v, r = value.field, value.field.rates
        row.update(
            cell_potential_V=v.potential_V[:n],
            extracellular_potential_V=v.potential_V[n:],
            membrane_voltage_V=r.membrane_voltage_V,
            membrane_flux_fmol_s=r.membrane_flux_fmol_s,
            energy_amount_fmol=amount,
            energy_concentration_mM=full.energy.concentration_mM,
            energy_chemical_potential_J_mol=full.energy.chemical_potential_J_mol,
            energy_hydrolysis_free_energy_J_mol=full.energy.hydrolysis_free_energy_J_mol,
            energy_free_energy_change_pJ=water_owner.pool_free_energy_change_pJ(actual, current),
            adenylate_fmol=conserved.adenylate_fmol,
            phosphorus_fmol=conserved.phosphorus_fmol,
            regeneration_cycle_rate_fmol_s=full.regeneration.synthesis_fmol_s,
            regeneration_affinity_J_mol=full.regeneration.reaction_free_energy_J_mol,
            regeneration_power_pJ_s=full.regeneration.supplied_power_pJ_s,
            regeneration_dissipation_pJ_s=full.regeneration.dissipated_power_pJ_s,
            regeneration_availability=control.regeneration,
            energy_balance_pJ=np.atleast_1d(balance["energy"]),
            pool_internal_transfer_balance_pJ=balance["pool_energy"],
            energy_balance_pJ_s=np.atleast_1d(v.energy_balance_pJ_s),
            cell_volume_pL=volume[:n],
            extracellular_volume_pL=volume[n:],
            cell_concentration_mM=inside / volume[:n],
            extracellular_concentration_mM=outside / volume[n:],
            water_flow_pL_s=w.edge_flow_pL_s,
            osmotic_pressure_Pa=w.osmotic_pressure_Pa,
            hydrostatic_pressure_Pa=w.hydrostatic_pressure_Pa,
            water_potential_Pa=w.water_potential_Pa,
            water_availability=control.water,
            water_dissipation_pJ_s=w.edge_dissipation_pJ_s,
            cytosol_osmolytes_fmol=np.sum(particles[:, :n], axis=0),
            cytosol_chemical_concentration_mM=chemical_water.osmolyte_amounts(actual, current)[
                :, :n
            ]
            / volume[:n],
            pool_osmolyte_amount_fmol=np.sum(amount, axis=0),
            pool_volume_power_pJ_s=coupled.derivative.pool_volume_work_pJ,
            er_volume_pL=p.er_volume[np.arange(p.er_volume.shape[0]), p.er_er],
        )
        row.update(injury_control=control.injury, resealing_control=control.resealing)
        records.append(
            (
                *(row[key] for key in base.OBSERVATION_FIELDS),
                state.phase_clock_s,
                signal.permeability,
                signal.scheduled,
                signal.pulse,
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

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    y = STATE_TYPE(*(np.asarray(v) for v in state))
    if abs(y.phase_clock_s[0] - time) > p.phase_clock_atol_s:
        raise ConfigError("Joint water endpoint phase clock differs from accepted time")
    table = control_values(owner_spec(spec), [time])
    u = type(table)(*(v[0] for v in table))
    value = readouts(y, u, p, xp=np)
    if not value.valid:
        raise NumericalError("Joint water scheduled endpoint field/domain invalid")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(parent_state(history), diagnostics, owner_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        phase=spec.model.phase,
        timing_policy=spec.model.timing_policy,
        reset_policy=spec.model.reset_policy,
        intervention_identity=artifact(spec)["interventions"]["identity"],
        intervention_scope=(
            "background membrane D; actual chemical/water/fuel/repair owners retained"
        ),
        native_solver_loop_parity=False,
    )
