"""Prescribed patch injury coupled to the existing finite ion/ER owners.

The added Na/K route uses the same outward-positive GHK transport as channel
populations. Damage, opening/closure integrals, transfer and heat are explicit
checkpoint arrays. Geometry and capacitance are fixed. Structural repair energy
is outside this phenomenological law; ion/chemical/electrical accounting is not.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_repair_spec import MODEL_ID, accounting_spec, base_spec
from cells.coupling.selective import selective_flux
from cells.models import surface_calcium as base
from cells.models import surface_calcium_cav as prior
from cells.models import surface_tissue as surface
from cells.numerics.extracellular_field import scatter
from cells.processes import membrane_injury as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = {
    "damage": ["membrane_slot"],
    "damage_opened": ["membrane_slot"],
    "damage_closed": ["membrane_slot"],
    "injury_transferred": ["species", "membrane_slot"],
    "injury_dissipated_energy_pJ": ["species", "membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceRepairState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceRepairLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "initial_damage",
            "injury_rate",
            "resealing_rate",
            "injury_permeability",
        )
    ],
)
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
OBSERVER_ID = "resolved_injury_resealing_accepted_grid@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "resolved_owned_calcium_patch_damage_actual_controls@1"
OBSERVATION_FIELDS = (*base.OBSERVATION_FIELDS, *EXTRA_AXES, "injury_control", "resealing_control")
Observations = make_dataclass(
    "SurfaceRepairObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters
batch_signature = prior.batch_signature


def base_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def base_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def base_control(control):
    from cells.core.schedule import SurfaceCalciumControl

    return SurfaceCalciumControl(*(getattr(control, k) for k in SurfaceCalciumControl._fields))


def accounting_state(state, *, xp=np):
    return base_state(state)._replace(
        membrane_transferred=state.membrane_transferred + state.injury_transferred,
        membrane_dissipated_energy_pJ=state.membrane_dissipated_energy_pJ
        + xp.sum(state.injury_dissipated_energy_pJ, axis=-2),
    )


def working_size(spec):
    return (
        prior.working_size(base_spec(spec))
        + (64 + 32 * len(spec.model.species_ids)) * spec.execution.membrane_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(base_spec(spec))
    nm = spec.execution.membrane_capacity
    damage, injury, reseal = (np.zeros(nm) for _ in range(3))
    permeability = np.zeros((len(spec.model.species_ids), nm))
    for i, row in enumerate(spec.model.injury_patches):
        damage[i], injury[i], reseal[i] = (
            row.initial_damage,
            row.injury_rate_per_s,
            row.resealing_rate_per_s,
        )
        permeability[:, i] = row.permeability_m_per_s
    return STATE_TYPE(
        *state,
        damage,
        np.zeros(nm),
        np.zeros(nm),
        np.zeros_like(permeability),
        np.zeros_like(permeability),
    ), LAYOUT_TYPE(*p, damage.copy(), injury, reseal, permeability)


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(base_state(state), base_layout(p), active, xp=xp)
    for k in EXTRA_AXES:
        value = getattr(state, k)
        mask = p.injury_permeability > 0 if k.startswith("injury_") else p.membrane_active
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all((state.damage >= 0) & (state.damage <= 1))
    for k in ("damage_opened", "damage_closed", "injury_dissipated_energy_pJ"):
        valid &= xp.all(getattr(state, k) >= -base.chemistry.ROUND_ATOL)
    valid &= xp.all(
        xp.abs(state.damage - p.initial_damage - state.damage_opened + state.damage_closed)
        <= base.chemistry.ROUND_ATOL
    )
    return valid


def readouts(state, control, p, *, xp=jnp):
    q = base_layout(p)
    w = prior.readouts(base_state(state), base_control(control), q, xp=xp)
    v, r, dr = w.field, w.field.rates, w.derivative
    ci = xp.where(p.active, base.cytosol_amount(state, q, xp=xp) / p.volume, 1.0)
    co = xp.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    a, b = p.membrane_cell, p.membrane_outside
    flux = selective_flux(
        ci[:, a],
        co[:, b],
        r.membrane_voltage_V,
        p.valence,
        p.temperature,
        p.membrane_area,
        p.injury_permeability,
        0.0,
        state.damage,
        1.0,
        xp=xp,
    )
    flux = xp.where(p.membrane_active, flux, 0.0)
    heat = 1e-3 * flux * r.membrane_delta_mu_J_mol
    cell = -scatter(flux, dr.amount_increment, (a,), xp=xp)
    outside = scatter(flux, dr.extracellular_amount_increment, (b,), xp=xp)
    chemical = xp.stack(
        [
            (p.free_ion_selector @ cell[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = base.field._capacitor_solve(qdot, xp.zeros_like(qdot), surface.field_layout(q), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[p.active.size + b], 0.0)
    chemical_power = (
        1e-3 * R * p.temperature * (xp.sum(xp.log(ci) * cell) + xp.sum(xp.log(co) * outside))
    )
    electric_power = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    damage_rate, opened, closed = process.rates(
        state.damage, p.injury_rate, p.resealing_rate, control.injury, control.resealing, xp=xp
    )
    derivative = STATE_TYPE(
        *dr._replace(
            amount_increment=dr.amount_increment + cell,
            extracellular_amount_increment=dr.extracellular_amount_increment + outside,
            chemical_amount_increment=dr.chemical_amount_increment + chemical,
        ),
        *(xp.where(p.membrane_active, z, 0.0) for z in (damage_rate, opened, closed)),
        flux,
        heat,
    )
    valid = w.valid & domain_valid(state, p, active=p.active, xp=xp)
    for value in (control.injury, control.resealing):
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
        valid &= xp.all(xp.where(p.membrane_active, True, value == 0))
    for value in (*derivative, chemical_power, electric_power, dvm):
        valid &= xp.all(xp.isfinite(value))
    r = r._replace(
        cell_rate_fmol_s=r.cell_rate_fmol_s + cell,
        outside_rate_fmol_s=r.outside_rate_fmol_s + outside,
        membrane_flux_fmol_s=r.membrane_flux_fmol_s + flux,
        membrane_current_A=r.membrane_current_A
        + CHARGE_PER_FMOL * xp.sum(p.valence * flux, axis=0),
        membrane_dissipation_pJ_s=r.membrane_dissipation_pJ_s + xp.sum(heat, axis=0),
        valid=valid,
    )
    v = v._replace(
        rates=r,
        membrane_voltage_rate_V_s=v.membrane_voltage_rate_V_s + dvm,
        chemical_energy_rate_pJ_s=v.chemical_energy_rate_pJ_s + chemical_power,
        capacitor_energy_rate_pJ_s=v.capacitor_energy_rate_pJ_s + electric_power,
        dissipation_pJ_s=v.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=v.energy_balance_pJ_s + chemical_power + electric_power + xp.sum(heat),
        converged=valid,
    )
    return w._replace(field=v, derivative=derivative, valid=valid)


def rhs(state, control, p, active, *, xp=jnp):
    w = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(w.valid, v, xp.nan) for v in w.derivative))


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


def injury_loss_bound(spec):
    _, p = initial_values(spec)
    coefficient = (
        p.membrane_area
        * p.injury_permeability
        / 1e-15
        * (1 + np.abs(p.valence) * F * 0.12 / (R * p.temperature))
    )
    inside = scatter(coefficient, p.amount_reference, (p.membrane_cell,), xp=np) / p.volume
    outside = (
        scatter(coefficient, p.extracellular_amount_reference, (p.membrane_outside,), xp=np)
        / p.extracellular_volume
    )
    return max(float(np.max(inside)), float(np.max(outside)))


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(controls.injury)):
        if not control_domain_valid(
            state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
        ):
            raise ConfigError("Initial injury state/control is outside the coupled domain")


def check_steps(spec, steps, controls):
    # Preserve injury-only event boundaries in the observation grid.
    prior.check_steps(spec, steps, controls)
    h = np.max(steps, initial=0)
    rate = max(
        (p.injury_rate_per_s + p.resealing_rate_per_s for p in spec.model.injury_patches),
        default=0.0,
    )
    if (
        h > 0.625e-6 + 1e-16
        or h * rate > 0.015 + 1e-14
        or h * (base.loss_bound(spec) + injury_loss_bound(spec)) > 0.25
    ):
        raise ConfigError(
            "Injury requires steps <=0.625 us, step * damage rate <=0.015 "
            "and step * combined transport loss <=0.25"
        )


def balances(state, p):
    result = prior.balances(accounting_state(state), base_layout(p))
    result["damage_ledger"] = (
        state.damage - p.initial_damage - state.damage_opened + state.damage_closed
    )
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.damage.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.damage))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid injury damage, ledger, transport or padding")
    diagnostics = prior.check_values(accounting_state(state), accounting_spec(spec))
    diagnostics["max_damage_ledger_error"] = float(
        np.max(
            np.abs(state.damage - p.initial_damage - state.damage_opened + state.damage_closed),
            initial=0,
        )
    )
    if state.damage.ndim > 1:
        for k in ("damage_opened", "damage_closed", "injury_dissipated_energy_pJ"):
            if np.min(np.diff(getattr(state, k), axis=0), initial=0) < -base.chemistry.ROUND_ATOL:
                raise NumericalError("Injury integral decreased: " + k)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Injury observations require accepted times")
    controls = control_values(spec, requested)
    records = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Injury observation domain invalid")
        v, r, n = w.field, w.field.rates, p.active.size
        records.append(
            (
                np.asarray(t),
                *base_state(state),
                *base.physical_amounts(base_state(state), base_layout(p)),
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
                w.er_voltage_V,
                w.ip3_cytosol_mM,
                w.ip3_release_fraction,
                w.calcium_targets,
                w.calcium_tau_s,
                w.plasma_affinity_J_mol,
                control.channel,
                control.pump,
                control.calcium_channel,
                control.plasma_pump,
                control.plasma_exchange,
                *(getattr(state, k) for k in EXTRA_AXES),
                control.injury,
                control.resealing,
            )
        )
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    return prior.ensemble_voltage(base_state(state), base_layout(layout), base_spec(spec), time)


def summarize(history, diagnostics, spec):
    return prior.summarize(accounting_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        injury_law=process.LAW_ID,
        injury_patch_ids=[p.membrane_id for p in spec.model.injury_patches],
        final_damage=history.damage[-1, : len(spec.model.membranes)].tolist(),
        injury_transfer_direction="outward positive",
        structural_repair_energy="not modelled",
        claim_scope=(
            "Synthetic fixed-geometry injury and prescribed resealing; "
            "no measured repair or regeneration claim"
        ),
    )
