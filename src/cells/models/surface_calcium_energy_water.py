"""Owned calcium/ER, finite ATP and compliant water with once-owned free energy.

All three pump families use one live owner pool at the current cytosol volume.
Chemical species and ATP/ADP/Pi each count once as osmotic particles. ER volume,
interfaces and capacitances stay fixed; pH/Mg/solvent are transformed buffers.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_water_spec import MODEL_ID as MODEL_ID
from cells.core.surface_calcium_energy_water_spec import (
    energy_spec,
    minimum_energy_spec,
    water_spec,
)
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as prior
from cells.models import surface_calcium_water as chemical_water
from cells.models import surface_tissue as passive
from cells.models import surface_water as water_model
from cells.numerics import osmotic_water as water
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes import finite_energy as energy
from cells.processes.electrochemistry import R

EXTRA_AXES = water_model.EXTRA_AXES | {"pool_volume_work_pJ": ["cell_slot"]}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumEnergyWaterState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyWaterLayout",
    [
        (k, object)
        for k in (
            *prior.MORRIS_LECAR_LAYOUT_TYPE._fields,
            *("water_" + k for k in water.Parameters._fields),
        )
    ],
)
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
OBSERVER_ID = "resolved_owned_calcium_finite_energy_water_accepted_grid@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "owned_chemical_and_fuel_particles_fixed_er_bounded_water@1"
VOLUME_ATOL_PL = water_model.VOLUME_ATOL_PL
READOUTS = (
    *water_model.READOUTS,
    "cytosol_osmolytes_fmol",
    "cytosol_chemical_concentration_mM",
    "er_volume_pL",
    "pool_osmolyte_amount_fmol",
    "pool_volume_power_pJ_s",
)
OBSERVATION_FIELDS = tuple(dict.fromkeys((*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)))
Observations = make_dataclass(
    "SurfaceCalciumEnergyWaterObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = prior.parameters
cytosol_amount, store_state, store_layout, er = (
    prior.cytosol_amount,
    prior.store_state,
    prior.store_layout,
    prior.er,
)
physical_amounts = calcium.physical_amounts
water_parameters = water_model.water_parameters


class Values(NamedTuple):
    field: object
    derivative: object
    calcium: object
    water: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.MORRIS_LECAR_LAYOUT_TYPE(
        *(getattr(p, k) for k in prior.MORRIS_LECAR_LAYOUT_TYPE._fields)
    )


def base_control(control):
    from cells.core.surface_calcium_energy_spec import Control

    return Control(*(getattr(control, k) for k in Control._fields))


def batch_signature(model):
    return (
        prior.batch_signature(model),
        model.chemical_osmotic_coupling,
        model.energy_osmotic_coupling,
        tuple(v.compartment_id for v in model.water_compartments),
        tuple(v.membrane_id for v in model.water_membranes),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(energy_spec(spec)) + 224 * (
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


def volumes(state, p, *, xp=np):
    return xp.concatenate(
        (
            p.volume + state.volume_increment_pL,
            p.extracellular_volume + state.extracellular_volume_increment_pL,
        ),
        axis=-1,
    )


def osmolyte_amounts(state, p, *, xp=np):
    """Chemical species once, exterior free ions, then three neutral fuel rows."""
    chemicals = chemical_water.osmolyte_amounts(state, p, xp=xp)
    fuel = prior.energy_amounts(state, p)
    outside = xp.zeros((*fuel.shape[:-1], p.outside_active.size))
    return xp.concatenate((chemicals, xp.concatenate((fuel, outside), axis=-1)), axis=-2)


def effective_layout(state, p):
    inside = p.volume + state.volume_increment_pL
    count = p.er_initial_amount.shape[0]
    cy = p.cytosol_selector
    return prior_layout(p)._replace(
        volume=inside,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
        er_volume=p.er_volume * (1 - cy) + inside[:count, None] * cy,
        ip3_weights=p.ip3_weights * (p.volume[:count] / inside[:count])[:, None, None],
    )


def ip3_readouts(state, p, *, xp=np):
    return chemical_water.ip3_readouts(state, p, xp=xp)


def water_values(state, control, p, *, xp=jnp):
    return water.evaluate(
        volumes(state, p, xp=xp),
        osmolyte_amounts(state, p, xp=xp),
        control.water,
        water_parameters(p),
        xp=xp,
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), effective_layout(state, p), active, xp=xp)
    valid &= water.domain_valid(
        volumes(state, p, xp=xp), osmolyte_amounts(state, p, xp=xp), water_parameters(p), xp=xp
    )
    support = p.membrane_active & (p.water_conductance_pL_per_Pa_s > 0)
    for key, mask in (
        ("volume_increment_pL", p.active),
        ("extracellular_volume_increment_pL", p.outside_active),
        ("water_transferred_pL", support),
        ("water_dissipated_energy_pJ", support),
    ):
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all(state.water_dissipated_energy_pJ >= -calcium.chemistry.ROUND_ATOL)
    valid &= xp.all(state.regeneration_dissipated_energy_pJ >= -calcium.chemistry.ROUND_ATOL)
    incident = (
        ordered_scatter(support.astype(float), xp.zeros_like(p.volume), (p.membrane_cell,), xp=xp)
        > 0
    )
    valid &= xp.all(xp.isfinite(state.pool_volume_work_pJ))
    valid &= xp.all(xp.where(p.active & incident, True, state.pool_volume_work_pJ == 0))
    return valid


def readouts(state, control, p, *, xp=jnp):
    c = prior.readouts(prior_state(state), base_control(control), effective_layout(state, p), xp=xp)
    w = water_values(state, control, p, xp=xp)
    n = p.active.size
    volume_work = c.energy.volume_derivative_pJ_per_pL * w.volume_rate_pL_s[:n]
    derivative = STATE_TYPE(
        *c.derivative,
        w.volume_rate_pL_s[:n],
        w.volume_rate_pL_s[n:],
        w.edge_flow_pL_s,
        w.edge_dissipation_pJ_s,
        volume_work,
    )
    valid = c.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= xp.all(xp.isfinite(control.water) & (control.water >= 0) & (control.water <= 1))
    valid &= xp.all(xp.where(p.membrane_active, True, control.water == 0))
    for value in (*derivative, *w):
        valid &= xp.all(xp.isfinite(value))
    # Pool mu*dN is part of the joint chemical power; the water partial-volume
    # gradient already includes the pool particles. Wvol is diagnostic only.
    chemical_power = xp.sum(energy.chemical_power_pJ_s(c.exchange.amount_fmol_s, c.energy, xp=xp))
    v = c.field._replace(
        chemical_energy_rate_pJ_s=c.field.chemical_energy_rate_pJ_s
        + chemical_power
        + w.mixing_energy_rate_pJ_s,
        dissipation_pJ_s=c.field.dissipation_pJ_s + w.dissipation_pJ_s,
        energy_balance_pJ_s=c.field.energy_balance_pJ_s + w.energy_balance_pJ_s,
        converged=valid,
        rates=c.field.rates._replace(valid=valid),
    )
    return Values(v, derivative, c, w, valid)


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


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
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    table = control_values(spec, [c.time for c in spec.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(table.water)):
            if not control_domain_valid(
                state, type(table)(*(v[i] for v in table)), p, p.active, xp=np
            ):
                raise ConfigError(
                    "Initial owned calcium/fuel/water state or controls outside domain"
                )


def maximum_osmolytes(p):
    """Closed chemical moieties plus each pool's phosphorus-minus-adenylate bound."""
    a = p.energy_initial_amount_fmol
    pool_bound = 2 * a[0] + a[1] + a[2]
    return chemical_water.maximum_osmolytes(p) + np.r_[pool_bound, np.zeros(p.outside_active.size)]


def check_steps(spec, steps, controls):
    # Keep ALL accepted boundaries, including water-only and supply-only clocks.
    prior.check_steps(replace(energy_spec(spec), experiment=spec.experiment), steps, controls)
    h = np.max(steps, initial=0)
    bounded = prior.bounded_prior_spec(minimum_energy_spec(spec))
    if h * calcium.loss_bound(bounded) > 0.25:
        raise ConfigError("Calcium energy water minimum-volume loss exceeds 0.25")
    _, p = initial_values(spec)
    rate = water.relaxation_rate_bound(maximum_osmolytes(p), water_parameters(p))
    if not np.isfinite(rate) or h * rate > water_model.MAX_WATER_RELAXATION_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Calcium energy water relaxation requires a smaller RK4 step")


def volume_energy_change(state, p):
    delta = np.r_[state.volume_increment_pL, state.extracellular_volume_increment_pL]
    initial = np.r_[p.volume, p.extracellular_volume]
    particles = np.sum(osmolyte_amounts(state, p), axis=0) + p.water_impermeant_amount_fmol
    dilution = -1e-3 * R * p.temperature * np.sum(particles * np.log1p(delta / initial))
    stiffness = p.water_bulk_modulus_Pa / p.water_reference_volume_pL
    pressure = stiffness * (initial - p.water_reference_volume_pL) + p.water_pressure_offset_Pa
    elastic = 1e-3 * np.sum(pressure * delta + 0.5 * stiffness * delta**2)
    return dilution + elastic


def pool_dilution_pJ(state, p):
    return (
        -1e-3
        * R
        * p.temperature
        * np.sum(prior.energy_amounts(state, p), axis=0)
        * np.log1p(state.volume_increment_pL / p.volume)
    )


def pool_free_energy_change_pJ(state, p):
    return prior.pool_free_energy_change_pJ(prior_state(state), prior_layout(p)) + pool_dilution_pJ(
        state, p
    )


def balances(state, p):
    result = prior.balances(prior_state(state), prior_layout(p))
    result["energy"] += volume_energy_change(state, p) + np.sum(state.water_dissipated_energy_pJ)
    result["pool_energy"] += pool_dilution_pJ(state, p) - state.pool_volume_work_pJ
    di, do, moved = (
        state.volume_increment_pL,
        state.extracellular_volume_increment_pL,
        state.water_transferred_pL,
    )
    return result | dict(
        water_local=di + scatter(moved, di, (p.membrane_cell,), xp=np),
        water_outside=do - scatter(moved, do, (p.membrane_outside,), xp=np),
        water_total=np.sum(di) + np.sum(do),
    )


def free_energy_change(state, p):
    """Endpoint physical free energy, excluding dissipated heat and external work."""
    value = balances(state, p)["energy"]
    for key in STATE_AXES:
        if key.endswith("_dissipated_energy_pJ"):
            value -= np.sum(getattr(state, key))
    for key in (
        "regeneration_supplied_work_pJ",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    ):
        value += np.sum(getattr(state, key))
    return value


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {}
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid owned calcium/fuel/water state, volume or padding")
        b = balances(row, p)
        tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
        charge = np.r_[
            p.initial_cell_charge_C, p.initial_outside_charge_C
        ] + passive.charge_increment(row, p, xp=np)
        limits = dict(
            local=tolerance[:, None],
            outside=tolerance[:, None],
            total=tolerance,
            charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(charge),
            electrode=field.CHARGE_ATOL_C,
            global_charge=3e-25,
            energy=calcium.ENERGY_ATOL_PJ,
            reservoir_work=3e-12,
            electrode_work=3e-12,
            pool_material=prior.POOL_MATERIAL_ATOL_FMOL,
            adenylate=prior.POOL_MATERIAL_ATOL_FMOL,
            phosphorus=prior.POOL_MATERIAL_ATOL_FMOL,
            pool_energy=prior.ENERGY_ATOL_PJ,
            regeneration_work=3e-12,
            chemical_ledger=calcium.chemistry.ROUND_ATOL,
            ownership=calcium.chemistry.ROUND_ATOL,
            water_local=VOLUME_ATOL_PL,
            water_outside=VOLUME_ATOL_PL,
            water_total=VOLUME_ATOL_PL,
        )
        for key, value in b.items():
            if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                raise NumericalError("Owned calcium/fuel/water accounting failed: " + key)
            label = "max_" + key + "_error"
            diagnostics[label] = max(
                diagnostics.get(label, 0), float(np.max(np.abs(value), initial=0))
            )
    for key, axes in STATE_AXES.items():
        if key.endswith("_dissipated_energy_pJ"):
            value = getattr(state, key)
            if np.min(value, initial=0) < -calcium.chemistry.ROUND_ATOL or (
                value.ndim > len(axes)
                and np.min(np.diff(value, axis=0), initial=0) < -calcium.chemistry.ROUND_ATOL
            ):
                raise NumericalError(
                    "Calcium/fuel/water dissipation cannot be negative or decrease"
                )
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError(
            "Calcium energy water observations require accepted integration boundaries"
        )
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
            energy_spec(spec),
        )
        row = {key: value[0] for key, value in vars(observed).items()}
        w = water_values(state, control, p, xp=np)
        volume = volumes(state, p)
        n = p.active.size
        inside, outside = physical_amounts(state, p)
        particles = osmolyte_amounts(state, p)
        row.update({key: getattr(state, key) for key in EXTRA_AXES})
        row.update(
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
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(
                readouts(state, control, p, xp=np).field.energy_balance_pJ_s
            ),
            cytosol_osmolytes_fmol=np.sum(particles[:, :n], axis=0),
            cytosol_chemical_concentration_mM=chemical_water.osmolyte_amounts(state, p)[:, :n]
            / volume[:n],
            energy_free_energy_change_pJ=pool_free_energy_change_pJ(state, p),
            pool_internal_transfer_balance_pJ=balances(state, p)["pool_energy"],
            pool_osmolyte_amount_fmol=np.sum(prior.energy_amounts(state, p), axis=0),
            pool_volume_power_pJ_s=readouts(
                state, control, p, xp=np
            ).derivative.pool_volume_work_pJ,
            er_volume_pL=p.er_volume[np.arange(p.er_volume.shape[0]), p.er_er],
        )
        records.append(row)
    if records:
        return Observations(*(np.stack([row[k] for row in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    return prior.ensemble_voltage(
        prior_state(state), effective_layout(state, layout), energy_spec(spec), time
    )


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    concentration, fraction = ip3_readouts(history, p, xp=np)
    return prior.summarize(prior_state(history), diagnostics, energy_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        chemical_osmotic_coupling=spec.model.chemical_osmotic_coupling,
        energy_osmotic_coupling=spec.model.energy_osmotic_coupling,
        water_law=water.LAW_ID,
        water_transfer_direction="outward positive",
        final_cell_volume_pL=(p.volume + history.volume_increment_pL[-1]).tolist(),
        final_extracellular_volume_pL=(
            p.extracellular_volume + history.extracellular_volume_increment_pL[-1]
        ).tolist(),
        final_ip3_cytosol_mM=concentration[-1].tolist(),
        final_ip3_release_fraction=fraction[-1].tolist(),
        er_water_coupling="fixed ER volume; no ER water port",
        osmotic_particle_scope=(
            "Each distinct cytosolic chemical species once; "
            "exterior free ions; three neutral fuel species; additional inert solute"
        ),
        pool_volume_work_role="Internal signed pool/volume transfer, not external supply",
        scope=(
            "Fixed interfaces/capacitance and ER; compliant cytosol/outside; "
            "transformed finite fuel"
        ),
        claim_scope=(
            "Synthetic compliant chemical cytosol with fixed interfaces/ER "
            "and one finite cellular fuel owner; no biological calibration"
        ),
    )
