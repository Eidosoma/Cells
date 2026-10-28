"""Compliant volumes with shared channels, kinetic junctions and Na/K ATPases.

Every transport law sees current concentrations at the same integration stage.
Maintained ATP inputs remain external chemical support, not owned osmotic solute.
The model preserves fixed interfaces/capacitances and the prior gate-law scope.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_water_kinetic_spec import (
    MODEL_ID,  # noqa: F401
    SurfaceWaterMorrisLecarModel,
    model_id,
    prior_spec,
    water_spec,
)
from cells.models import surface_kinetic as prior
from cells.models import surface_tissue as passive
from cells.models import surface_water as water_model
from cells.numerics import osmotic_water as water
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_active_compliant_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_ions_intrinsic_gates_atp_and_bounded_compliant_volumes@1"
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
VOLUME_ATOL_PL = water_model.VOLUME_ATOL_PL
EXTRA_AXES = water_model.EXTRA_AXES
STATE_AXES = (
    prior.STATE_AXES
    | {
        "channel_transferred": ["species", "channel_slot"],
        "channel_dissipated_energy_pJ": ["species", "channel_slot"],
    }
    | EXTRA_AXES
)
STATE_TYPE = NamedTuple("SurfaceWaterKineticState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceWaterKineticLayout",
    [
        (k, object)
        for k in (*prior.CAV_LAYOUT_TYPE._fields, *("water_" + k for k in water.Parameters._fields))
    ],
)
MORRIS_LECAR_LAYOUT_TYPE = NamedTuple(
    "SurfaceWaterMorrisLecarLayout",
    [
        (k, object)
        for k in (
            *prior.MORRIS_LECAR_LAYOUT_TYPE._fields,
            *("water_" + k for k in water.Parameters._fields),
        )
    ],
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *water_model.READOUTS)
Observations = make_dataclass(
    "SurfaceWaterKineticObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters
physical_amounts = prior.physical_amounts
volumes = water_model.volumes
water_values = water_model.water_values
water_parameters = water_model.water_parameters


class Values(NamedTuple):
    field: object
    derivative: object
    kinetics: object
    water: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    kind = (
        prior.MORRIS_LECAR_LAYOUT_TYPE
        if isinstance(p, MORRIS_LECAR_LAYOUT_TYPE)
        else prior.CAV_LAYOUT_TYPE
    )
    return kind(*(getattr(p, k) for k in kind._fields))


def water_state(state):
    return water_model.STATE_TYPE(*(getattr(state, k) for k in water_model.STATE_TYPE._fields))


def water_layout(p):
    return water_model.LAYOUT_TYPE(*(getattr(p, k) for k in water_model.LAYOUT_TYPE._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple(v.compartment_id for v in model.water_compartments),
        tuple(v.membrane_id for v in model.water_membranes),
    )


def working_size(spec):
    x = spec.execution
    return (
        prior.working_size(spec)
        + (3 * len(spec.model.species_ids) + 1) * x.channel_capacity
        + 192 * (x.capacity + x.extracellular_capacity + x.membrane_capacity)
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    ws, wp = water_model.initial_values(water_spec(spec))
    kind = (
        MORRIS_LECAR_LAYOUT_TYPE
        if isinstance(spec.model, SurfaceWaterMorrisLecarModel)
        else LAYOUT_TYPE
    )
    return (
        STATE_TYPE(*state, *(getattr(ws, k) for k in EXTRA_AXES)),
        kind(*p, *water_parameters(wp)),
    )


def effective_layout(state, p):
    return prior_layout(p)._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
    )


def domain_valid(state, p, active, *, xp=jnp):
    return prior.domain_valid(
        prior_state(state), prior_layout(p), active, xp=xp
    ) & water_model.domain_valid(water_state(state), water_layout(p), active, xp=xp)


def readouts(state, control, p, *, xp=jnp):
    kinetic = prior.readouts(prior_state(state), control, effective_layout(state, p), xp=xp)
    w = water_values(state, control, p, xp=xp)
    n = p.active.size
    result = STATE_TYPE(
        *kinetic.derivative,
        w.volume_rate_pL_s[:n],
        w.volume_rate_pL_s[n:],
        w.edge_flow_pL_s,
        w.edge_dissipation_pJ_s,
    )
    valid = kinetic.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= xp.all(xp.isfinite(control.water) & (control.water >= 0) & (control.water <= 1))
    valid &= xp.all(xp.where(p.membrane_active, True, control.water == 0))
    for value in (*result, *w):
        valid &= xp.all(xp.isfinite(value))
    return Values(kinetic.field._replace(converged=valid), result, kinetic, w, valid)


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


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
        ),
    )
    from cells.core.schedule import control_values

    state, p = initial_values(compact)
    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            control = type(controls)(*(v[i] for v in controls))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError("Initial shared-channel/pump/water domain invalid")


def check_steps(spec, steps, controls):
    # Retain the union of water, channel, pump and junction clocks.
    # Keep water-only off-grid boundaries while projecting the channel catalog.
    ionic = replace(prior_spec(spec), experiment=spec.experiment)
    prior.check_steps(ionic, steps, controls)
    state, p = initial_values(spec)
    maximum = np.sum(water_model.amounts(state, p)) + p.water_impermeant_amount_fmol
    rate = water.relaxation_rate_bound(maximum, water_parameters(p))
    if not np.isfinite(rate) or np.max(
        steps, initial=0
    ) * rate > water_model.MAX_WATER_RELAXATION_PER_STEP * (1 + 16 * np.finfo(float).eps):
        raise ConfigError("Active water relaxation requires a smaller RK4 step")


def balances(state, p):
    b = prior.balances(prior_state(state), prior_layout(p))
    di, do, moved = (
        state.volume_increment_pL,
        state.extracellular_volume_increment_pL,
        state.water_transferred_pL,
    )
    delta = np.r_[di, do]
    initial_volume = np.r_[p.volume, p.extracellular_volume]
    osmolytes = water_model.amounts(state, p).sum(axis=0) + p.water_impermeant_amount_fmol
    dilution = -1e-3 * R * p.temperature * np.sum(osmolytes * np.log1p(delta / initial_volume))
    stiffness = p.water_bulk_modulus_Pa / p.water_reference_volume_pL
    pressure = (
        stiffness * (initial_volume - p.water_reference_volume_pL) + p.water_pressure_offset_Pa
    )
    elastic = 1e-3 * np.sum(pressure * delta + 0.5 * stiffness * delta**2)
    # Prior accounting already includes active ionic heat minus maintained ATP
    # work. Correct its mixing energy at current solute amounts exactly once.
    b["energy"] += dilution + elastic + np.sum(state.water_dissipated_energy_pJ)
    return b | dict(
        water_local=di + scatter(moved, di, (p.membrane_cell,), xp=np),
        water_outside=do - scatter(moved, do, (p.membrane_outside,), xp=np),
        water_total=np.sum(delta),
    )


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
            "cell_water_balance_error_pL",
            "outside_water_balance_error_pL",
            "global_water_balance_error_pL",
        )
    }
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid active water state, gates, volume bounds or padding")
            b = balances(row, p)
            tol = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(row, p, xp=np)
            limits = (
                tol[:, None],
                tol[:, None],
                tol,
                field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                3e-25,
                passive.ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
                3e-12,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
            )
            for (name, value), key, limit in zip(b.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > limit):
                    raise NumericalError("Active water accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Active water dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Active water observations require accepted integration boundaries")
    controls, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        observed = prior.observe_history(
            np.array([time]),
            prior.STATE_TYPE(*(v[None] for v in prior_state(state))),
            effective_layout(state, p),
            np.array([time]),
            prior_spec(spec),
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        w = water_values(state, control, p, xp=np)
        volume = volumes(state, p)
        n = p.active.size
        ci, co = physical_amounts(state, p)
        row.update({k: getattr(state, k) for k in EXTRA_AXES})
        row.update(
            cell_volume_pL=volume[:n],
            extracellular_volume_pL=volume[n:],
            cell_concentration_mM=ci / volume[:n],
            extracellular_concentration_mM=co / volume[n:],
            water_flow_pL_s=w.edge_flow_pL_s,
            osmotic_pressure_Pa=w.osmotic_pressure_Pa,
            hydrostatic_pressure_Pa=w.hydrostatic_pressure_Pa,
            water_potential_Pa=w.water_potential_Pa,
            water_availability=control.water,
            water_dissipation_pJ_s=w.edge_dissipation_pJ_s,
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=row["energy_balance_pJ_s"] + w.energy_balance_pJ_s,
        )
        records.append(row)
    if records:
        return Observations(*(np.stack([row[k] for row in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    controls = control_values(spec, [time])
    control = type(controls)(*(v[0] for v in controls))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    p = type(layout)(*(np.asarray(v) for v in layout))
    if not domain_valid(state, p, p.active, xp=np):
        raise NumericalError("Active water ensemble state outside domain")
    w = readouts(state, control, p, xp=np)
    if not w.valid:
        raise NumericalError("Active water ensemble field/control invalid")
    return w.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(history, diagnostics, prior_spec(spec)) | dict(
        model=model_id(spec.model),
        state_fields=list(STATE_TYPE._fields),
        water_law=water.LAW_ID,
        volume_owner_ids=[v.id for v in (*spec.model.cells, *spec.model.extracellular)],
        water_interface_ids=[v.id for v in spec.model.membranes],
        geometry_scope="fixed interfaces/capacitances; compliant volumes; no shape mechanics",
        metabolic_scope="maintained chemical support, not finite volume-owned ATP/ADP/Pi",
    )
