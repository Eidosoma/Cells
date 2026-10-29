"""Finite internal mitochondria with one conserved whole-cell ion inventory.

The physical model uses continuous passive transport and charge-consistent
voltage. Native Euler/cache/copy-initialization correspondence is kept in the
separate betse_mitochondria component, never substituted into this RK4 RHS.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_calcium_energy_mitochondria_spec import MODEL_ID, base_spec
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_calcium_energy_transport as prior
from cells.models import surface_tissue as surface
from cells.processes import mitochondrial_passive as process
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = {
    "mitochondrial_amount_increment_fmol": ["species", "cell_slot"],
    "mitochondrial_transferred_fmol": ["species", "cell_slot"],
    "mitochondrial_dissipated_energy_pJ": ["species", "cell_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceCalciumEnergyMitochondriaState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyMitochondriaLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            "mitochondrial_initial_amount_fmol",
            "mitochondrial_volume_pL",
            "mitochondrial_area_m2",
            "mitochondrial_capacitance_F",
            "mitochondrial_thickness_m",
            "mitochondrial_initial_voltage_V",
            "mitochondrial_diffusivity_m2_s",
            "mitochondrial_fixed_charge_C",
            "mitochondrial_initial_countercharge_C",
        )
    ],
)
BATCH_CAPACITIES = prior.BATCH_CAPACITIES
OBSERVER_ID = "resolved_calcium_energy_mitochondria_accepted_grid@1"
STAGE_DOMAIN_ID = "owned_cytosol_er_mitochondria_fuel_actual_controls@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
READOUTS = (
    "mitochondrial_amount_fmol",
    "mitochondrial_concentration_mM",
    "mitochondrial_voltage_V",
    "mitochondrial_charge_C",
    "mitochondrial_countercharge_C",
    "mitochondrial_flux_fmol_s",
    "mitochondrial_transfer_energy_J_mol",
    "mitochondrial_dissipation_pJ_s",
    "mitochondrial_availability",
    "mitochondrial_stored_energy_change_pJ",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyMitochondriaObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = prior.parameters
ENERGY_ATOL_PJ = prior.ENERGY_ATOL_PJ
cytosol_amount = prior.cytosol_amount
store_state, store_layout, er = prior.store_state, prior.store_layout, prior.er
ip3_readouts = prior.ip3_readouts


class Values(NamedTuple):
    field: object
    derivative: object
    parent: object
    mitochondria: object
    mitochondrial_voltage_V: object
    valid: object


def base_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def base_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def base_control(control):
    from cells.core.surface_calcium_energy_transport_spec import Control

    return Control(*(getattr(control, k) for k in Control._fields))


def parent_view(state, p, *, xp):
    """Temporary old-owner coordinates; saved whole-cell charges never change.

    The parent represents cytosol+ER but not mitochondria. Subtract the internal
    mitochondrial increment from its inventory coordinate, and add its charge
    to the temporary field offset. Their sum is the authoritative whole-cell
    charge. Actual free chemical amounts, rates and fuel are untouched. Never
    use this view as a checkpoint, initial condition or endpoint energy anchor.
    """
    delta = state.mitochondrial_amount_increment_fmol
    projected = base_state(state)._replace(amount_increment=state.amount_increment - delta)
    p42 = base_layout(p)._replace(
        initial_cell_charge_C=p.initial_cell_charge_C
        + CHARGE_PER_FMOL * xp.sum(p.valence * delta, axis=-2)
    )
    return projected, p42


def batch_signature(model):
    return prior.batch_signature(model), tuple((m.id, m.cell_id) for m in model.mitochondria)


def working_size(spec):
    return prior.working_size(base_spec(spec)) + 8 * spec.execution.capacity * (
        256 + 64 * len(spec.model.species_ids)
    )


def initial_values(spec):
    state, p = prior.initial_values(base_spec(spec))
    n, ns = spec.execution.capacity, len(spec.model.species_ids)
    amount, diffusion = np.zeros((ns, n)), np.zeros((ns, n))
    volume, cap, thickness = (np.ones(n) for _ in range(3))
    area, voltage = np.zeros(n), np.zeros(n)
    for i, m in enumerate(spec.model.mitochondria):
        amount[:, i], diffusion[:, i] = m.initial_amount_fmol, m.diffusivity_m2_per_s
        volume[i], area[i], cap[i], thickness[i], voltage[i] = (
            m.volume_pL,
            m.area_m2,
            m.area_m2 * m.specific_capacitance_F_per_m2,
            m.membrane_thickness_m,
            m.initial_voltage_V,
        )
    charge = cap * voltage
    fixed = charge - CHARGE_PER_FMOL * np.sum(p.valence * amount, axis=0)
    return STATE_TYPE(
        *state, np.zeros_like(amount), np.zeros_like(amount), np.zeros_like(amount)
    ), LAYOUT_TYPE(*p, amount, volume, area, cap, thickness, voltage, diffusion, fixed, -charge)


def mitochondrial_amount(state, p):
    return p.mitochondrial_initial_amount_fmol + state.mitochondrial_amount_increment_fmol


def mitochondrial_voltage(state, p, *, xp=np):
    return xp.where(
        p.active,
        p.mitochondrial_initial_voltage_V
        + CHARGE_PER_FMOL
        * xp.sum(p.valence * state.mitochondrial_amount_increment_fmol, axis=-2)
        / p.mitochondrial_capacitance_F,
        0.0,
    )


def physical_amounts(state, p, *, xp=np):
    return cytosol_amount(
        state, p, xp=xp
    ), p.extracellular_amount_reference + state.extracellular_amount_increment


def chemical_exchange(flux, p, *, xp):
    return xp.stack(
        [
            -(p.free_ion_selector @ flux[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )


def domain_valid(state, p, active, *, xp=jnp):
    projected, q = parent_view(state, p, xp=xp)
    valid = prior.domain_valid(projected, q, active, xp=xp)
    supported = p.active & (p.mitochondrial_diffusivity_m2_s > 0)
    for key in EXTRA_AXES:
        value = getattr(state, key)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(supported, True, value == 0))
    amount = mitochondrial_amount(state, p)
    valid &= xp.all(xp.where(p.active, xp.isfinite(amount) & (amount > 0), amount == 0))
    voltage = mitochondrial_voltage(state, p, xp=xp)
    valid &= xp.all(xp.isfinite(voltage) & (xp.abs(voltage) <= process.MAX_VOLTAGE_V))
    valid &= xp.all(state.mitochondrial_dissipated_energy_pJ >= -calcium.chemistry.ROUND_ATOL)
    valid &= xp.all(
        xp.abs(state.mitochondrial_amount_increment_fmol - state.mitochondrial_transferred_fmol)
        <= calcium.chemistry.ROUND_ATOL
    )
    return valid


def readouts(state, control, p, *, xp=jnp):
    projected, q = parent_view(state, p, xp=xp)
    w = prior.readouts(projected, base_control(control), q, xp=xp)
    ci = xp.where(p.active, cytosol_amount(state, p, xp=xp) / p.volume, 1.0)
    cm = xp.where(p.active, mitochondrial_amount(state, p) / p.mitochondrial_volume_pL, 1.0)
    voltage = mitochondrial_voltage(state, p, xp=xp)
    mito = process.rates(
        ci,
        cm,
        voltage,
        p.valence,
        p.temperature,
        p.mitochondrial_area_m2,
        p.mitochondrial_diffusivity_m2_s,
        p.mitochondrial_thickness_m,
        control.mitochondria,
        xp=xp,
    )
    flux, heat = mito.transferred_fmol_s, mito.dissipated_power_pJ_s
    derivative = STATE_TYPE(
        *w.derivative._replace(
            chemical_amount_increment=w.derivative.chemical_amount_increment
            + chemical_exchange(flux, p, xp=xp),
        ),
        flux,
        flux,
        heat,
    )
    chemical = 1e-3 * R * p.temperature * xp.sum((xp.log(cm) - xp.log(ci)) * flux)
    electric = 1e12 * CHARGE_PER_FMOL * xp.sum(voltage * p.valence * flux)
    valid = w.valid & domain_valid(state, p, p.active, xp=xp)
    opening = control.mitochondria
    valid &= xp.all(xp.isfinite(opening) & (opening >= 0) & (opening <= 1))
    valid &= xp.all(xp.where(p.active, True, opening == 0))
    valid &= xp.all(heat >= -1e-12)
    for value in (*derivative, *mito, chemical, electric):
        valid &= xp.all(xp.isfinite(value))
    v = w.field._replace(
        rates=w.field.rates._replace(valid=valid),
        chemical_energy_rate_pJ_s=w.field.chemical_energy_rate_pJ_s + chemical,
        capacitor_energy_rate_pJ_s=w.field.capacitor_energy_rate_pJ_s + electric,
        dissipation_pJ_s=w.field.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=w.field.energy_balance_pJ_s + chemical + electric + xp.sum(heat),
        converged=valid,
    )
    return Values(v, derivative, w, mito, voltage, valid)


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


def check_definition(spec):
    from cells.core.schedule import control_values

    state, p = initial_values(spec)
    controls = control_values(spec, [c.time for c in spec.experiment.changes])
    for i in range(len(controls.mitochondria)):
        if not control_domain_valid(
            state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
        ):
            raise ConfigError("Initial mitochondrial ownership/state/control is outside domain")
    for value in p[len(prior.LAYOUT_TYPE._fields) :]:
        if not np.isfinite(value).all():
            raise ConfigError("Mitochondrial geometry or charge is not representable")


def loss_bound(spec):
    """Include all initial mitochondrial ions in conserved chemical upper bounds."""
    projected = fuel.bounded_prior_spec(prior.base_spec(base_spec(spec)))
    _, p = calcium.initial_values(projected)
    global_ions = np.sum(p.extracellular_amount_reference, axis=-1)
    global_ions += np.sum([m.initial_amount_fmol for m in spec.model.mitochondria], axis=0)
    for i in range(len(projected.model.stores)):
        c = calcium.store_layout(p, i)
        global_ions += p.ion_content @ np.sum(c.initial_amount * c.active, axis=-1)
    chemical = []
    for i, m in enumerate(projected.model.stores):
        c = calcium.store_layout(p, i)
        totals = c.moieties @ np.sum(c.initial_amount * c.active, axis=-1)
        for ion, value in zip(projected.model.species_ids, global_ions, strict=True):
            totals[m.moieties.index(ion)] = value
        chemical.append(er.loss_bound(calcium.store_spec(projected, i), conserved_totals=totals))
    plasma = calcium.loss_bound(projected) - calcium.chemical_loss_bound(projected)
    _, q = initial_values(spec)
    coefficient = (
        q.mitochondrial_area_m2
        * q.mitochondrial_diffusivity_m2_s
        / (1e-15 * q.mitochondrial_thickness_m)
    )
    coefficient *= 1 + np.abs(q.valence) * F * process.MAX_VOLTAGE_V / (R * q.temperature)
    internal = np.max(
        coefficient * np.maximum(1 / q.volume, 1 / q.mitochondrial_volume_pL), initial=0
    )
    return max(chemical) + plasma + internal


def check_steps(spec, steps, controls):
    prior.check_steps(replace(base_spec(spec), experiment=spec.experiment), steps, controls)
    bound = loss_bound(spec)
    if not np.isfinite(bound) or np.max(steps, initial=0) * bound > 0.25:
        raise ConfigError(
            "Mitochondrial-inclusive conserved-pool transport/chemical bound requires smaller steps"
        )


def stored_energy_change(state, p):
    delta = state.mitochondrial_amount_increment_fmol
    anchor = np.where(p.active, p.mitochondrial_initial_amount_fmol, 1.0)
    chemical = (
        1e-3
        * R
        * p.temperature
        * np.sum(
            delta * (np.log(anchor / p.mitochondrial_volume_pL) - 1)
            + (anchor + delta) * np.log1p(delta / anchor),
            axis=-2,
        )
    )
    dv = CHARGE_PER_FMOL * np.sum(p.valence * delta, axis=-2) / p.mitochondrial_capacitance_F
    return chemical + 0.5e12 * p.mitochondrial_capacitance_F * dv * (
        2 * p.mitochondrial_initial_voltage_V + dv
    )


def balances(state, p):
    result = prior.balances(base_state(state), base_layout(p))
    count = p.er_initial_amount.shape[0]
    # Parent energy already uses actual depleted cytosolic chemical amounts.
    # Add only the newly owned mitochondrial chemical/capacitor store and heat.
    result["energy"] += np.sum(stored_energy_change(state, p)) + np.sum(
        state.mitochondrial_dissipated_energy_pJ
    )
    result["ownership"] += state.mitochondrial_amount_increment_fmol[:, :count]
    result["chemical_ledger"] -= chemical_exchange(
        state.mitochondrial_transferred_fmol, p, xp=np
    ) / np.maximum(1, p.er_initial_amount)
    result["mitochondrial_material"] = (
        state.mitochondrial_amount_increment_fmol - state.mitochondrial_transferred_fmol
    )
    v = mitochondrial_voltage(state, p)
    result["mitochondrial_charge"] = p.mitochondrial_capacitance_F * (
        v - p.mitochondrial_initial_voltage_V
    ) - CHARGE_PER_FMOL * np.sum(p.valence * state.mitochondrial_amount_increment_fmol, axis=0)
    return result


def check_values(state, spec):
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    diagnostics = {}
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Invalid mitochondrial inventory, ownership, voltage or ledger"
                )
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + surface.charge_increment(row, p, xp=np)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=fuel.field.CHARGE_ATOL_C + fuel.field.CHARGE_RTOL * np.abs(charge),
                electrode=fuel.field.CHARGE_ATOL_C,
                global_charge=3e-25,
                energy=ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                chemical_ledger=calcium.chemistry.ROUND_ATOL,
                ownership=calcium.chemistry.ROUND_ATOL,
                pool_material=fuel.POOL_MATERIAL_ATOL_FMOL,
                adenylate=fuel.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=fuel.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                network_material=tolerance[:, None],
                network_work=3e-12,
                mitochondrial_material=tolerance[:, None],
                mitochondrial_charge=fuel.field.CHARGE_ATOL_C,
            )
            for key, value in balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Mitochondrial accounting failed: " + key)
                name = "max_" + key + "_error"
                diagnostics[name] = max(
                    diagnostics.get(name, 0.0), float(np.max(np.abs(value), initial=0))
                )
    for key in (k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ")):
        value = getattr(state, key)
        if np.min(value, initial=0) < -1e-12 or (
            state.amount_increment.ndim == 3 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Dissipated energy cannot be negative or decrease: " + key)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Mitochondrial observations require accepted times")
    controls, records = control_values(spec, requested), []
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        projected, q = parent_view(state, p, xp=np)
        observed = prior.observe_history(
            np.asarray([time]),
            prior.STATE_TYPE(*(v[None, ...] for v in projected)),
            q,
            np.asarray([time]),
            base_spec(spec),
        )
        row = {key: value[0] for key, value in vars(observed).items()}
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Mitochondrial observation domain invalid")
        row.update(state._asdict())  # Restore authoritative whole-cell coordinates.
        charge = p.mitochondrial_capacitance_F * w.mitochondrial_voltage_V
        row.update(
            energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(w.field.energy_balance_pJ_s),
            mitochondrial_amount_fmol=mitochondrial_amount(state, p),
            mitochondrial_concentration_mM=mitochondrial_amount(state, p)
            / p.mitochondrial_volume_pL,
            mitochondrial_voltage_V=w.mitochondrial_voltage_V,
            mitochondrial_charge_C=charge,
            mitochondrial_countercharge_C=-charge,
            mitochondrial_flux_fmol_s=w.mitochondria.transferred_fmol_s,
            mitochondrial_transfer_energy_J_mol=w.mitochondria.transfer_energy_J_mol,
            mitochondrial_dissipation_pJ_s=w.mitochondria.dissipated_power_pJ_s,
            mitochondrial_availability=control.mitochondria,
            mitochondrial_stored_energy_change_pJ=stored_energy_change(state, p),
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
    w = readouts(state, type(table)(*(v[0] for v in table)), layout, xp=np)
    if not w.valid:
        raise NumericalError("Invalid mitochondrial ensemble readout")
    return w.field.rates.membrane_voltage_V[: len(spec.model.membranes)]


def summarize(history, diagnostics, spec):
    return prior.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        mitochondrial_law=process.LAW_ID,
        mitochondrial_source_law=process.SOURCE_LAW,
        mitochondrial_ids=[m.id for m in spec.model.mitochondria],
        mitochondrial_cell_ids=[m.cell_id for m in spec.model.mitochondria],
        mitochondrial_initialization=(
            "Explicit disjoint inventories, fixed internal capacitor and paired countercharge"
        ),
        mitochondrial_energy=(
            "Passive chemical/capacitor exchange and heat; no ATP production or respiration"
        ),
        claim_scope=(
            "Continuous physical composition; "
            "not literal native Euler/cache/copy-initialization trajectory parity"
        ),
    )
