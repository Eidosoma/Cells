"""Owned chemical cytosol plus compliant water, with a fixed-volume ER.

All chemical species count once as osmotic particles. Solute mixing belongs to
the chemical free energy; only its exact volume correction, additional inert
mixing, compliance and water heat augment the parent reference-volume balance.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_water_spec import MODEL_ID as MODEL_ID
from cells.core.surface_calcium_water_spec import minimum_volume_spec, prior_spec, water_spec
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_morris_lecar as prior
from cells.models import surface_tissue as passive
from cells.models import surface_water as water_model
from cells.numerics import osmotic_water as water
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import R

STATE_AXES = prior.STATE_AXES | water_model.EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumWaterState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumWaterLayout",
    [
        (k, object)
        for k in (*prior.LAYOUT_TYPE._fields, *("water_" + k for k in water.Parameters._fields))
    ],
)
EXTRA_AXES = water_model.EXTRA_AXES
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
OBSERVER_ID = "resolved_owned_calcium_compliant_water_accepted_grid@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "owned_chemical_particles_free_cytosol_fixed_er_bounded_water@1"
VOLUME_ATOL_PL = water_model.VOLUME_ATOL_PL
READOUTS = (
    *water_model.READOUTS,
    "cytosol_osmolytes_fmol",
    "cytosol_chemical_concentration_mM",
    "er_volume_pL",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumWaterObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
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
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def base_control(control):
    from cells.core.schedule import SurfaceCalciumControl

    return SurfaceCalciumControl(*(getattr(control, k) for k in SurfaceCalciumControl._fields))


def batch_signature(model):
    return (
        prior.batch_signature(model),
        model.chemical_osmotic_coupling,
        tuple(v.compartment_id for v in model.water_compartments),
        tuple(v.membrane_id for v in model.water_membranes),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(prior_spec(spec)) + 192 * (
        x.capacity + x.extracellular_capacity + x.membrane_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    ws, wp = water_model.initial_values(water_spec(spec))
    return (
        STATE_TYPE(*state, *(getattr(ws, k) for k in EXTRA_AXES)),
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
    """Chemical particles in cytosol, mapped free ions outside; no ionic duplicate."""
    particles = xp.sum(
        (p.er_initial_amount + state.chemical_amount_increment) * p.cytosol_selector[:, None, :],
        axis=-1,
    )
    particles = xp.swapaxes(particles, -1, -2)
    n = p.er_initial_amount.shape[0]
    inside = xp.concatenate(
        (particles, xp.zeros((*particles.shape[:-1], p.active.size - n))), axis=-1
    )
    outside = xp.einsum(
        "cs,...so->...co",
        p.free_ion_selector,
        p.extracellular_amount_reference + state.extracellular_amount_increment,
    )
    return xp.concatenate((inside, outside), axis=-1)


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
    concentration, _ = prior.ip3_readouts(prior_state(state), prior_layout(p), xp=xp)
    count = p.er_initial_amount.shape[0]
    concentration = (
        concentration
        * p.volume[:count]
        / (p.volume[:count] + state.volume_increment_pL[..., :count])
    )
    activation = (concentration / p.ip3_activation) ** p.ip3_power
    return concentration, activation / (1 + activation)


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
    return valid


def readouts(state, control, p, *, xp=jnp):
    c = prior.readouts(prior_state(state), base_control(control), effective_layout(state, p), xp=xp)
    w = water_values(state, control, p, xp=xp)
    n = p.active.size
    derivative = STATE_TYPE(
        *c.derivative,
        w.volume_rate_pL_s[:n],
        w.volume_rate_pL_s[n:],
        w.edge_flow_pL_s,
        w.edge_dissipation_pJ_s,
    )
    valid = c.valid & domain_valid(state, p, p.active, xp=xp)
    valid &= xp.all(xp.isfinite(control.water) & (control.water >= 0) & (control.water <= 1))
    valid &= xp.all(xp.where(p.membrane_active, True, control.water == 0))
    for value in (*derivative, *w):
        valid &= xp.all(xp.isfinite(value))
    v = c.field._replace(
        chemical_energy_rate_pJ_s=c.field.chemical_energy_rate_pJ_s + w.mixing_energy_rate_pJ_s,
        dissipation_pJ_s=c.field.dissipation_pJ_s + w.dissipation_pJ_s,
        energy_balance_pJ_s=c.field.energy_balance_pJ_s + w.energy_balance_pJ_s,
        converged=valid,
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
                raise ConfigError("Initial owned calcium/water state or controls outside domain")


def maximum_osmolytes(p):
    """Closed integer moieties bound every particle, including IP3 conversions."""
    initial = np.sum(p.er_initial_amount * p.er_active[:, None, :], axis=(0, 2))
    initial += p.free_ion_selector @ np.sum(p.extracellular_amount_reference, axis=1)
    # Each declared species has at least one conserved integer moiety. Binding
    # can change particle count, so the initial particle count is not a bound.
    return float(np.sum(p.er_moieties[0] @ initial)) + p.water_impermeant_amount_fmol


def check_steps(spec, steps, controls):
    # Preserve water-only off-grid boundaries in the observation contract.
    prior.check_steps(spec, steps, controls)
    h = np.max(steps, initial=0)
    if h * calcium.loss_bound(minimum_volume_spec(spec)) > 0.25:
        raise ConfigError("Calcium water minimum-volume chemical/transport loss exceeds 0.25")
    _, p = initial_values(spec)
    rate = water.relaxation_rate_bound(maximum_osmolytes(p), water_parameters(p))
    if not np.isfinite(rate) or h * rate > water_model.MAX_WATER_RELAXATION_PER_STEP * (
        1 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("Calcium water relaxation requires a smaller RK4 step")


def volume_energy_change(state, p):
    delta = np.r_[state.volume_increment_pL, state.extracellular_volume_increment_pL]
    initial = np.r_[p.volume, p.extracellular_volume]
    particles = np.sum(osmolyte_amounts(state, p), axis=0) + p.water_impermeant_amount_fmol
    dilution = -1e-3 * R * p.temperature * np.sum(particles * np.log1p(delta / initial))
    stiffness = p.water_bulk_modulus_Pa / p.water_reference_volume_pL
    pressure = stiffness * (initial - p.water_reference_volume_pL) + p.water_pressure_offset_Pa
    elastic = 1e-3 * np.sum(pressure * delta + 0.5 * stiffness * delta**2)
    return dilution + elastic


def balances(state, p):
    result = prior.balances(prior_state(state), prior_layout(p))
    result["energy"] += volume_energy_change(state, p) + np.sum(state.water_dissipated_energy_pJ)
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
        "metabolic_work_pJ",
        "plasma_metabolic_work_pJ",
        "er_metabolic_work_pJ",
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
            raise NumericalError("Invalid owned calcium/water state, volume or padding")
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
            metabolic_work=3e-12,
            plasma_metabolic_work=3e-12,
            er_metabolic_work=3e-12,
            chemical_ledger=calcium.chemistry.ROUND_ATOL,
            ownership=calcium.chemistry.ROUND_ATOL,
            water_local=VOLUME_ATOL_PL,
            water_outside=VOLUME_ATOL_PL,
            water_total=VOLUME_ATOL_PL,
        )
        for key, value in b.items():
            if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                raise NumericalError("Owned calcium/water accounting failed: " + key)
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
                raise NumericalError("Calcium/water dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Calcium water observations require accepted integration boundaries")
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
            cytosol_chemical_concentration_mM=particles[:, :n] / volume[:n],
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
        prior_state(state), effective_layout(state, layout), prior_spec(spec), time
    )


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    concentration, fraction = ip3_readouts(history, p, xp=np)
    return prior.summarize(prior_state(history), diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        chemical_osmotic_coupling=spec.model.chemical_osmotic_coupling,
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
            "exterior free ions; additional inert solute"
        ),
        claim_scope=(
            "Synthetic compliant chemical cytosol with fixed interfaces/ER "
            "and maintained ATP; no biological calibration"
        ),
    )
