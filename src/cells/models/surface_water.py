"""Resolved passive ions and conservative water in compliant finite compartments.

Volume changes enter every ionic stage through concentration = amount / volume.
Interfaces, capacitances and topology stay fixed. This is not shape mechanics,
solvent drag, an extracellular fluid field or a native BETSE volume trajectory.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_water_spec import MODEL_ID, prior_spec
from cells.models import surface_tissue as prior
from cells.numerics import osmotic_water as water
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_compliant_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_closed_ions_and_bounded_compliant_volumes@1"
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
VOLUME_ATOL_PL = 2e-12
MAX_WATER_RELAXATION_PER_STEP = 0.05
EXTRA_AXES = {
    "volume_increment_pL": ["cell_slot"],
    "extracellular_volume_increment_pL": ["extracellular_slot"],
    "water_transferred_pL": ["membrane_slot"],
    "water_dissipated_energy_pJ": ["membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceWaterState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceWaterLayout",
    [
        (k, object)
        for k in (*prior.LAYOUT_TYPE._fields, *("water_" + k for k in water.Parameters._fields))
    ],
)
READOUTS = (
    "cell_volume_pL",
    "extracellular_volume_pL",
    "cell_concentration_mM",
    "extracellular_concentration_mM",
    "water_flow_pL_s",
    "osmotic_pressure_Pa",
    "hydrostatic_pressure_Pa",
    "water_potential_Pa",
    "water_availability",
    "water_dissipation_pJ_s",
    "energy_balance_pJ",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceWaterObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def water_parameters(p):
    return water.Parameters(*(getattr(p, "water_" + k) for k in water.Parameters._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple(v.compartment_id for v in model.water_compartments),
        tuple(v.membrane_id for v in model.water_membranes),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(spec) + 192 * (
        x.capacity + x.extracellular_capacity + x.membrane_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    m, x = spec.model, spec.execution
    n, o, e = x.capacity, x.extracellular_capacity, x.membrane_capacity
    names = {v.id: i for i, v in enumerate(m.cells)} | {
        v.id: n + i for i, v in enumerate(m.extracellular)
    }
    values = dict(
        temperature_K=p.temperature,
        active=np.r_[p.active, p.outside_active],
        reference_volume_pL=np.ones(n + o),
        minimum_volume_pL=np.full(n + o, 0.5),
        maximum_volume_pL=np.full(n + o, 1.5),
        impermeant_amount_fmol=np.zeros(n + o),
        bulk_modulus_Pa=np.zeros(n + o),
        pressure_offset_Pa=np.zeros(n + o),
        edge_active=p.membrane_active,
        sender=p.membrane_cell,
        receiver=n + p.membrane_outside,
        conductance_pL_per_Pa_s=np.zeros(e),
    )
    for row in m.water_compartments:
        for key in (
            "reference_volume_pL",
            "minimum_volume_pL",
            "maximum_volume_pL",
            "impermeant_amount_fmol",
            "bulk_modulus_Pa",
            "pressure_offset_Pa",
        ):
            values[key][names[row.compartment_id]] = getattr(row, key)
    for i, membrane in enumerate(m.water_membranes):
        values["conductance_pL_per_Pa_s"][i] = (
            1e15 * m.membranes[i].area_m2 * membrane.hydraulic_permeability_m_per_Pa_s
        )
    q = water.validate_parameters(water.Parameters(**values))
    return (
        STATE_TYPE(*state, np.zeros(n), np.zeros(o), np.zeros(e), np.zeros(e)),
        LAYOUT_TYPE(*p, *q),
    )


def volumes(state, p, *, xp=np):
    return xp.concatenate(
        (
            p.volume + state.volume_increment_pL,
            p.extracellular_volume + state.extracellular_volume_increment_pL,
        )
    )


def amounts(state, p, *, xp=np):
    return xp.concatenate(prior.physical_amounts(state, p), axis=-1)


def effective_layout(state, p):
    return prior_layout(p)._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
    )


def field_values(state, control, p, *, xp=jnp):
    return prior.field_values(prior_state(state), control, effective_layout(state, p), xp=xp)


def water_values(state, control, p, *, xp=jnp):
    return water.evaluate(
        volumes(state, p, xp=xp),
        amounts(state, p, xp=xp),
        control.water,
        water_parameters(p),
        xp=xp,
    )


def rhs(state, control, p, active, *, xp=jnp):
    current = effective_layout(state, p)
    electrical = prior.field_values(prior_state(state), control, current, xp=xp)
    ionic = prior.derivative_from_field(electrical, current, xp=xp)
    w = water_values(state, control, p, xp=xp)
    n = p.active.size
    return STATE_TYPE(
        *ionic,
        w.volume_rate_pL_s[:n],
        w.volume_rate_pL_s[n:],
        w.edge_flow_pL_s,
        w.edge_dissipation_pJ_s,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= water.domain_valid(
        volumes(state, p, xp=xp), amounts(state, p, xp=xp), water_parameters(p), xp=xp
    )
    support = p.membrane_active & (p.water_conductance_pL_per_Pa_s > 0)
    for name, mask in (
        ("volume_increment_pL", p.active),
        ("extracellular_volume_increment_pL", p.outside_active),
        ("water_transferred_pL", support),
        ("water_dissipated_energy_pJ", support),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    return valid


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    valid &= xp.all(xp.isfinite(control.water)) & xp.all(
        (control.water >= 0) & (control.water <= 1)
    )
    valid &= xp.all(xp.where(p.membrane_active, True, control.water == 0))
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return field_values(state, control, p, xp=np).converged
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: field_values(state, control, p).converged, lambda: jnp.asarray(False)
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
        ),
    )
    from cells.core.schedule import control_values

    try:
        state, p = initial_values(compact)
        table = control_values(compact, [c.time for c in compact.experiment.changes])
        for i in range(len(compact.experiment.changes)):
            control = type(table)(*(v[i] for v in table))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ValueError("Initial water/ionic state outside the actual-control domain")
    except (ValueError, FloatingPointError) as error:
        raise ConfigError("Invalid compliant water definition: " + str(error)) from error


def check_steps(spec, steps, controls):
    # Use the full union of water and ionic event clocks for accepted observations.
    prior.check_steps(spec, steps, controls)
    state, p = initial_values(spec)
    maximum = np.sum(amounts(state, p)) + p.water_impermeant_amount_fmol
    rate = water.relaxation_rate_bound(maximum, water_parameters(p))
    if not np.isfinite(rate) or np.max(steps, initial=0) * rate > MAX_WATER_RELAXATION_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Water relaxation requires a smaller RK4 step (bound exceeds 0.05)")


def balances(state, p):
    b = prior.balances(prior_state(state), prior_layout(p))
    di, do, moved = (
        state.volume_increment_pL,
        state.extracellular_volume_increment_pL,
        state.water_transferred_pL,
    )
    local = di + scatter(moved, di, (p.membrane_cell,), xp=np)
    outside = do - scatter(moved, do, (p.membrane_outside,), xp=np)
    delta = np.r_[di, do]
    initial_volume = np.r_[p.volume, p.extracellular_volume]
    osmolytes = amounts(state, p).sum(axis=0) + p.water_impermeant_amount_fmol
    # Correct the existing fixed-volume ionic free-energy change. This stable
    # log1p form includes *current* ion amounts, so simultaneous ion/water motion
    # does not drop its cross term or count chemical energy twice.
    dilution = -1e-3 * R * p.temperature * np.sum(osmolytes * np.log1p(delta / initial_volume))
    stiffness = p.water_bulk_modulus_Pa / p.water_reference_volume_pL
    initial_pressure = (
        stiffness * (initial_volume - p.water_reference_volume_pL) + p.water_pressure_offset_Pa
    )
    elastic = 1e-3 * np.sum(initial_pressure * delta + 0.5 * stiffness * delta**2)
    b["energy"] += dilution + elastic + np.sum(state.water_dissipated_energy_pJ)
    return b | dict(water_local=local, water_outside=outside, water_total=np.sum(delta))


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
        "cell_water_balance_error_pL",
        "outside_water_balance_error_pL",
        "global_water_balance_error_pL",
    )
    diagnostics = {"max_" + k: 0.0 for k in names}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid water/ionic state, volume bounds, ledger or padding")
            b = balances(row, p)
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + prior.charge_increment(row, p, xp=np)
            limits = (
                tolerance[:, None],
                tolerance[:, None],
                tolerance,
                field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                3e-25,
                prior.ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
                VOLUME_ATOL_PL,
            )
            for (name, value), key, limit in zip(b.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > limit):
                    raise NumericalError("Water/ionic accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in ("membrane", "junction", "face", "water"):
        value = getattr(state, name + "_dissipated_energy_pJ")
        if np.min(value, initial=0) < -1e-12 or (
            value.ndim == 2 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Water/ionic dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Water observations require accepted integration boundaries")
    controls, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        ionic_history = prior.STATE_TYPE(
            *(getattr(state, k)[None] for k in prior.STATE_TYPE._fields)
        )
        observed = prior.observe_history(
            np.array([time]),
            ionic_history,
            effective_layout(state, p),
            np.array([time]),
            prior_spec(spec),
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        w = water_values(state, control, p, xp=np)
        volume = volumes(state, p)
        n = p.active.size
        ci, co = prior.physical_amounts(state, p)
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

    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    state = STATE_TYPE(*(np.asarray(v) for v in state))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    result = field_values(state, control, p, xp=np)
    if not result.converged:
        raise NumericalError("Water ensemble endpoint field invalid")
    return result.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return prior.summarize(history, diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        water_law=water.LAW_ID,
        state_fields=list(STATE_TYPE._fields),
        volume_owner_ids=[v.id for v in (*spec.model.cells, *spec.model.extracellular)],
        water_interface_ids=[v.id for v in spec.model.membranes],
        geometry_scope="fixed interfaces/capacitances; compliant volumes; no shape mechanics",
        water_solute_transfer="none; ionic routes retain their own material ledgers",
    )
