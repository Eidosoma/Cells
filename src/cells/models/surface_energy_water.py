"""Finite cellular energy and conservative water with once-owned mixing energy.

ATP/ADP/Pi contribute explicitly declared neutral ideal osmotic particles.
Their volume work is an internal signed transfer, never an external source.
Interfaces and capacitances stay fixed; pH/Mg/solvent remain transformed buffers.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_energy_water_spec import MODEL_ID, energy_spec, water_spec
from cells.models import surface_energy as prior
from cells.models import surface_tissue as passive
from cells.models import surface_water as water_model
from cells.numerics import osmotic_water as water
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_finite_energy_compliant_water_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_finite_energy_ions_and_bounded_water_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
VOLUME_ATOL_PL = water_model.VOLUME_ATOL_PL
EXTRA_AXES = water_model.EXTRA_AXES | {"pool_volume_work_pJ": ["cell_slot"]}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceEnergyWaterState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceEnergyWaterLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            *("water_" + k for k in water.Parameters._fields),
        )
    ],
)
READOUTS = (*water_model.READOUTS, "pool_osmolyte_amount_fmol", "pool_volume_power_pJ_s")
OBSERVATION_FIELDS = tuple(dict.fromkeys((*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)))
Observations = make_dataclass(
    "SurfaceEnergyWaterObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = prior.parameters
physical_amounts = prior.physical_amounts
volumes = water_model.volumes
water_parameters = water_model.water_parameters


class Values(NamedTuple):
    field: object
    derivative: object
    energy: object
    water: object
    valid: object


def energy_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def energy_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def water_state(state):
    return water_model.STATE_TYPE(*(getattr(state, k) for k in water_model.STATE_TYPE._fields))


def water_layout(p):
    return water_model.LAYOUT_TYPE(*(getattr(p, k) for k in water_model.LAYOUT_TYPE._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        model.energy_osmotic_coupling,
        tuple(v.compartment_id for v in model.water_compartments),
        tuple(v.membrane_id for v in model.water_membranes),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(spec) + 224 * (
        x.capacity + x.extracellular_capacity + x.membrane_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(energy_spec(spec))
    ws, wp = water_model.initial_values(water_spec(spec))
    return (
        STATE_TYPE(
            *state,
            *(getattr(ws, k) for k in water_model.EXTRA_AXES),
            np.zeros(spec.execution.capacity),
        ),
        LAYOUT_TYPE(*p, *water_parameters(wp)),
    )


def effective_layout(state, p):
    return energy_layout(p)._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
    )


def osmotic_amounts(state, p, *, xp=np):
    """Live ionic and three pool rows; no duplicate background or pool energy."""
    ionic = water_model.amounts(state, p, xp=xp)
    pools = xp.concatenate(
        (prior.energy_amounts(state, p), xp.zeros((3, p.outside_active.size))),
        axis=-1,
    )
    return xp.concatenate((ionic, pools), axis=-2)


def water_values(state, control, p, *, xp=jnp):
    return water.evaluate(
        volumes(state, p, xp=xp),
        osmotic_amounts(state, p, xp=xp),
        control.water,
        water_parameters(p),
        xp=xp,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(energy_state(state), effective_layout(state, p), active, xp=xp)
    valid &= water_model.domain_valid(water_state(state), water_layout(p), active, xp=xp)
    support = p.membrane_active & (p.water_conductance_pL_per_Pa_s > 0)
    incident = (
        ordered_scatter(support.astype(float), xp.zeros_like(p.volume), (p.membrane_cell,), xp=xp)
        > 0
    )
    valid &= xp.all(xp.isfinite(state.pool_volume_work_pJ))
    valid &= xp.all(xp.where(p.active & incident, True, state.pool_volume_work_pJ == 0))
    return valid


def readouts(state, control, p, *, xp=jnp):
    current = effective_layout(state, p)
    energetic = prior.readouts(energy_state(state), control, current, xp=xp)
    w = water_values(state, control, p, xp=xp)
    n = p.active.size
    volume_work = energetic.energy.volume_derivative_pJ_per_pL * w.volume_rate_pL_s[:n]
    derivative = STATE_TYPE(
        *energetic.derivative,
        w.volume_rate_pL_s[:n],
        w.volume_rate_pL_s[n:],
        w.edge_flow_pL_s,
        w.edge_dissipation_pJ_s,
        volume_work,
    )
    valid = energetic.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= xp.all(xp.isfinite(control.water) & (control.water >= 0) & (control.water <= 1))
    valid &= xp.all(xp.where(p.membrane_active, True, control.water == 0))
    for value in (*derivative, *w):
        valid &= xp.all(xp.isfinite(value))
    # The water partial-volume balance includes the pool gradient already.
    # Wvol is retained as an internal diagnostic, not added a second time here.
    v = energetic.field._replace(
        dissipation_pJ_s=energetic.field.dissipation_pJ_s + w.dissipation_pJ_s,
        energy_balance_pJ_s=energetic.field.energy_balance_pJ_s + w.energy_balance_pJ_s,
        converged=valid,
        rates=energetic.field.rates._replace(valid=valid),
    )
    return Values(v, derivative, energetic, w, valid)


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


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
    from cells.core.schedule import control_values

    state, p = initial_values(compact)
    table = control_values(compact, [v.time for v in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(compact.experiment.changes)):
            control = type(table)(*(v[i] for v in table))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError("Initial finite-energy/water state or actual control invalid")


def maximum_osmolyte_amount_fmol(state, p):
    # Pool N=P-A-ATP < P-A; initial N is not a bound during hydrolysis.
    a = p.energy_initial_amount_fmol
    pool_bound = 2 * a[0] + a[1] + a[2]
    return (
        np.sum(water_model.amounts(state, p))
        + p.water_impermeant_amount_fmol
        + np.r_[pool_bound, np.zeros(p.outside_active.size)]
    )


def check_steps(spec, steps, controls):
    prior.check_steps(spec, steps, controls)
    state, p = initial_values(spec)
    rate = water.relaxation_rate_bound(maximum_osmolyte_amount_fmol(state, p), water_parameters(p))
    if not np.isfinite(rate) or np.max(steps, initial=0) * rate > (
        water_model.MAX_WATER_RELAXATION_PER_STEP * (1 + 16 * np.finfo(float).eps)
    ):
        raise ConfigError("Finite-energy water relaxation requires a smaller RK4 step")


def pool_dilution_pJ(state, p):
    return (
        -1e-3
        * R
        * p.temperature
        * np.sum(prior.energy_amounts(state, p), axis=0)
        * np.log1p(state.volume_increment_pL / p.volume)
    )


def pool_free_energy_change_pJ(state, p):
    return prior.pool_free_energy_change_pJ(
        energy_state(state), energy_layout(p)
    ) + pool_dilution_pJ(state, p)


def balances(state, p):
    b = prior.balances(energy_state(state), energy_layout(p))
    di, do, moved = (
        state.volume_increment_pL,
        state.extracellular_volume_increment_pL,
        state.water_transferred_pL,
    )
    delta = np.r_[di, do]
    initial_volume = np.r_[p.volume, p.extracellular_volume]
    particles = osmotic_amounts(state, p).sum(axis=0) + p.water_impermeant_amount_fmol
    dilution = -1e-3 * R * p.temperature * np.sum(particles * np.log1p(delta / initial_volume))
    stiffness = p.water_bulk_modulus_Pa / p.water_reference_volume_pL
    pressure = (
        stiffness * (initial_volume - p.water_reference_volume_pL) + p.water_pressure_offset_Pa
    )
    elastic = 1e-3 * np.sum(pressure * delta + 0.5 * stiffness * delta**2)
    b["energy"] += dilution + elastic + np.sum(state.water_dissipated_energy_pJ)
    b["pool_energy"] += pool_dilution_pJ(state, p) - state.pool_volume_work_pJ
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
        "cell_water_balance_error_pL",
        "outside_water_balance_error_pL",
        "global_water_balance_error_pL",
    )
    diagnostics = {"max_" + k: 0.0 for k in names}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid finite-energy/water state, bounds or padding")
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
                prior.POOL_MATERIAL_ATOL_FMOL,
                prior.POOL_MATERIAL_ATOL_FMOL,
                prior.POOL_MATERIAL_ATOL_FMOL,
                passive.ENERGY_ATOL_PJ,
                3e-12,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
            )
            for (name, value), key, limit in zip(b.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > limit):
                    raise NumericalError("Finite-energy/water accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, name)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Finite-energy/water dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Finite-energy/water observations require accepted boundaries")
    controls, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        value = readouts(state, control, p, xp=np)
        if not value.valid:
            raise NumericalError("Invalid finite-energy/water observation state/control")
        observed = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(v[None] for v in energy_state(state))),
            effective_layout(state, p),
            np.asarray([time]),
            energy_spec(spec),
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        w, volume, n = value.water, volumes(state, p), p.active.size
        ci, co = physical_amounts(state, p)
        b = balances(state, p)
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
            energy_balance_pJ=np.atleast_1d(b["energy"]),
            energy_balance_pJ_s=np.atleast_1d(value.field.energy_balance_pJ_s),
            energy_free_energy_change_pJ=pool_free_energy_change_pJ(state, p),
            pool_internal_transfer_balance_pJ=b["pool_energy"],
            pool_osmolyte_amount_fmol=value.energy.energy.osmolyte_amount_fmol,
            pool_volume_power_pJ_s=value.derivative.pool_volume_work_pJ,
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

    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    if not domain_valid(state, p, p.active, xp=np):
        raise NumericalError("Finite-energy/water ensemble state outside domain")
    value = readouts(state, control, p, xp=np)
    if not value.valid:
        raise NumericalError("Finite-energy/water ensemble field/control invalid")
    return value.field.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(history, diagnostics, energy_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        water_law=water.LAW_ID,
        energy_osmotic_coupling=spec.model.energy_osmotic_coupling,
        pool_volume_work_role="Internal signed pool/volume transfer, not external supply",
        scope="Fixed interfaces/capacitance; compliant volumes; neutral transformed pool osmolytes",
    )
