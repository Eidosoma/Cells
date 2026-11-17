"""Closed passive spatial electrodiffusion on independently owned array axes.

One capacitor per intracellular cell; zero bulk capacitance. All inventories
evolve explicitly. Outside potentials are same-stage current constraints, not
independent voltage state, maintained baths or hidden electrical grounds.
"""

import math
from dataclasses import dataclass

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import SpatialExtracellularLayout, SpatialExtracellularState
from cells.numerics import extracellular_field as field
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    MOL_PER_FMOL,
    F,
    R,
    electrochemical_potential,
    ghk_leak,
)

STATE_TYPE = SpatialExtracellularState
LAYOUT_TYPE = SpatialExtracellularLayout
OBSERVER_ID = "passive_spatial_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_cubic_hermite@1"
STAGE_DOMAIN_ID = "positive_spatial_inventory_capacitive_components_current_continuity@1"
MAX_STEP = 0.000125
MAX_ABS_X = 50.0
CHARGE_TOLERANCE_C = 1e-20
BATCH_CAPACITIES = ("extracellular_capacity", "face_capacity", "field_solver")
STATE_AXES = {
    "amount_increment": ["species", "cell_slot"],
    "extracellular_amount_increment": ["species", "extracellular_slot"],
    "membrane_transferred": ["species", "membrane_slot"],
    "face_transferred": ["species", "face_slot"],
    "membrane_dissipated_energy_pJ": ["membrane_slot"],
    "face_dissipated_energy_pJ": ["face_slot"],
}


def batch_signature(model):
    return (len(model.species_ids),)


def parameters(spec, layout):
    return layout


def working_size(spec):
    """Conservative float64 array slots, including batched observer solve scratch."""
    x, s = spec.execution, len(spec.model.species_ids)
    return (
        (40 * s + 80) * (x.capacity + x.extracellular_capacity)
        + (48 * s + 96) * (x.membrane_capacity + x.face_capacity)
        + 16 * x.extracellular_capacity**2
    )


def check_definition(model):
    """Validate derived physical numbers using active owners, before padding allocation."""

    def finite(value, *, positive=False):
        if not math.isfinite(value) or (positive and value <= 0):
            raise ConfigError("Derived spatial coefficient exceeds positive finite float64")
        return value

    rt = finite(R * model.temperature_K, positive=True)
    finite(F * F / rt, positive=True)
    anchor = {c.id: [] for c in (*model.cells, *model.extracellular)}
    rates = {c.id: [] for c in (*model.cells, *model.extracellular)}
    for p in model.membranes:
        finite(CHARGE_PER_FMOL / p.capacitance_F, positive=True)
        charge = finite(p.capacitance_F * p.initial_voltage_V)
        anchor[p.inside].append(charge)
        anchor[p.outside].append(-charge)
        for z in model.valence:
            if abs(finite(z * F * p.initial_voltage_V / rt)) > MAX_ABS_X:
                raise ConfigError("Initial membrane voltage exceeds all-valence domain")
        for permeability in p.permeability_m_per_s:
            k = finite(p.area_m2 * permeability / MOL_PER_FMOL, positive=permeability > 0)
            rates[p.inside].append(k)
            rates[p.outside].append(k)
    for p in model.faces:
        conductors = []
        for z, d in zip(model.valence, p.diffusivity_m2_per_s, strict=True):
            k = finite(d * p.area_m2 / p.length_m, positive=d > 0)
            finite(k / MOL_PER_FMOL, positive=d > 0)
            conductors.append(finite(F * F / rt * z * z * k, positive=d > 0))
            rates[p.sender].append(k / MOL_PER_FMOL)
            rates[p.receiver].append(k / MOL_PER_FMOL)
        finite(math.fsum(conductors), positive=True)
    for c in (*model.cells, *model.extracellular):
        finite(1 / c.volume_pL, positive=True)
        for n in c.initial_amount_fmol:
            finite(n / c.volume_pL, positive=True)
        q = finite(
            CHARGE_PER_FMOL
            * math.fsum(
                (
                    c.fixed_charge_equivalent_fmol,
                    *(z * n for z, n in zip(model.valence, c.initial_amount_fmol, strict=True)),
                )
            )
        )
        if abs(q - finite(math.fsum(anchor[c.id]))) > CHARGE_TOLERANCE_C:
            raise ConfigError("Initial inventory, fixed background and capacitor anchor disagree")
        finite(math.fsum(rates[c.id]))


def initial_values(spec):
    m, x = spec.model, spec.execution
    s, nc, no, nm, ne = (
        len(m.species_ids),
        x.capacity,
        x.extracellular_capacity,
        x.membrane_capacity,
        x.face_capacity,
    )
    values = {}
    for active, ids, capacity, count in (
        ("active", "ids", nc, len(m.cells)),
        ("extracellular_active", "extracellular_ids", no, len(m.extracellular)),
        ("membrane_active", "membrane_ids", nm, len(m.membranes)),
        ("face_active", "face_ids", ne, len(m.faces)),
    ):
        values[active] = np.arange(capacity) < count
        values[ids] = np.where(values[active], np.arange(capacity) + 1, -1).astype(np.int64)
    values.update(
        species_codes=np.arange(1, s + 1, dtype=np.int64),
        valence=np.asarray(m.valence, dtype=np.int64)[:, None],
        temperature=np.asarray(m.temperature_K, dtype=np.float64),
        amount_reference=np.zeros((s, nc)),
        extracellular_amount_reference=np.zeros((s, no)),
        permeability=np.zeros((s, nm)),
        face_diffusivity=np.zeros((s, ne)),
        face_factor=np.zeros((s, ne)),
        gauge_mask=np.zeros(no, dtype=bool),
    )
    for key, size in (
        ("owners", nm),
        ("outside_owners", nm),
        ("cell_membranes", nc),
        ("senders", ne),
        ("receivers", ne),
    ):
        values[key] = np.zeros(size, dtype=np.int64)
    for key, size, fill in (
        ("volume", nc, 1),
        ("extracellular_volume", no, 1),
        ("area", nm, 1),
        ("capacitance", nm, 1),
        ("face_area", ne, 1),
        ("face_length", ne, 1),
        ("fixed_charge_equivalent", nc, 0),
        ("extracellular_fixed_charge_equivalent", no, 0),
        ("voltage_reference", nc, 0),
        ("initial_inside_charge_C", nc, 0),
        ("initial_outside_charge_C", no, 0),
    ):
        values[key] = np.full(size, fill, dtype=np.float64)
    for prefix, compartments in (("", m.cells), ("extracellular_", m.extracellular)):
        for i, c in enumerate(compartments):
            values[prefix + "volume"][i] = c.volume_pL
            values[prefix + "amount_reference"][:, i] = c.initial_amount_fmol
            values[prefix + "fixed_charge_equivalent"][i] = c.fixed_charge_equivalent_fmol
    outside = [c.id for c in m.extracellular]
    values["gauge_mask"][outside.index(m.gauge_reference)] = True
    for i, p in enumerate(m.membranes):
        owner = outside.index(p.outside)
        for key, value in (
            ("owners", i),
            ("cell_membranes", i),
            ("outside_owners", owner),
            ("area", p.area_m2),
            ("capacitance", p.capacitance_F),
            ("voltage_reference", p.initial_voltage_V),
        ):
            values[key][i] = value
        values["permeability"][:, i] = p.permeability_m_per_s
        values["initial_inside_charge_C"][i] = p.capacitance_F * p.initial_voltage_V
    # Stable explicit anchors for every capacitor component, never from a rounded
    # subtraction of two large mobile-ion totals.
    for i, c in enumerate(m.extracellular):
        values["initial_outside_charge_C"][i] = -math.fsum(
            p.capacitance_F * p.initial_voltage_V for p in m.membranes if p.outside == c.id
        )
    for i, p in enumerate(m.faces):
        values["senders"][i], values["receivers"][i] = (
            outside.index(p.sender),
            outside.index(p.receiver),
        )
        values["face_area"][i], values["face_length"][i] = p.area_m2, p.length_m
        values["face_diffusivity"][:, i] = p.diffusivity_m2_per_s
        values["face_factor"][:, i] = np.asarray(p.diffusivity_m2_per_s) * p.area_m2 / p.length_m
    return STATE_TYPE(
        np.zeros((s, nc)),
        np.zeros((s, no)),
        np.zeros((s, nm)),
        np.zeros((s, ne)),
        np.zeros(nm),
        np.zeros(ne),
    ), LAYOUT_TYPE(**values)


def physical_amounts(state, layout):
    return (
        layout.amount_reference + state.amount_increment,
        layout.extracellular_amount_reference + state.extracellular_amount_increment,
    )


def cell_voltage(increment, layout, *, xp=jnp, derivative=False):
    delta = (
        CHARGE_PER_FMOL
        / layout.capacitance[layout.cell_membranes]
        * xp.sum(layout.valence * increment, axis=-2)
    )
    return xp.where(layout.active, delta if derivative else layout.voltage_reference + delta, 0.0)


def component_charge(state, layout, *, xp=jnp, derivative=False):
    inside = CHARGE_PER_FMOL * xp.sum(layout.valence * state.amount_increment, axis=-2)
    outside = CHARGE_PER_FMOL * xp.sum(
        layout.valence * state.extracellular_amount_increment, axis=-2
    )
    if not derivative:
        inside, outside = (
            inside + layout.initial_inside_charge_C,
            outside + layout.initial_outside_charge_C,
        )
    return outside + field.scatter(
        xp.where(layout.membrane_active, inside[..., layout.owners], 0.0),
        outside,
        (layout.outside_owners,),
        xp=xp,
    )


def field_values(state, layout, *, xp=jnp):
    _, outside = physical_amounts(state, layout)
    concentration = xp.where(
        layout.extracellular_active, outside / layout.extracellular_volume, 1.0
    )
    return field.solve(concentration, layout, xp=xp)


def capacitor_residuals(state, layout, *, xp=jnp):
    """Check the actual floating capacitor equation as well as compatibility."""
    voltage = cell_voltage(state.amount_increment, layout, xp=xp)
    capacitor = layout.capacitance[layout.cell_membranes] * voltage
    inside = layout.initial_inside_charge_C + CHARGE_PER_FMOL * xp.sum(
        layout.valence * state.amount_increment, axis=-2
    )
    outside = layout.initial_outside_charge_C + CHARGE_PER_FMOL * xp.sum(
        layout.valence * state.extracellular_amount_increment, axis=-2
    )
    return (
        capacitor - inside,
        outside
        + field.scatter(
            xp.where(layout.membrane_active, capacitor[..., layout.owners], 0.0),
            outside,
            (layout.outside_owners,),
            xp=xp,
        ),
    )


def membrane_values(state, control, layout, *, xp=jnp):
    amount, outside = physical_amounts(state, layout)
    active, src, dst = layout.membrane_active, layout.owners, layout.outside_owners
    ci = xp.where(active, amount[..., :, src], 1.0) / xp.where(active, layout.volume[src], 1.0)
    co = xp.where(active, outside[..., :, dst], 1.0) / xp.where(
        active, layout.extracellular_volume[dst], 1.0
    )
    voltage = xp.where(active, cell_voltage(state.amount_increment, layout, xp=xp)[..., src], 0.0)
    # Shared GHK kernel is inward; this model's owned transfer convention is outward.
    flux = -ghk_leak(
        ci,
        co,
        voltage[..., None, :],
        layout.valence,
        layout.temperature,
        layout.area,
        layout.permeability,
        control[..., None, :],
        xp=xp,
    )
    mu = electrochemical_potential(
        ci, co, voltage[..., None, :], layout.valence, layout.temperature, xp=xp
    )
    flux, mu = xp.where(active, flux, 0.0), xp.where(active, mu, 0.0)
    return voltage, flux, mu, 1e-3 * xp.sum(flux * mu, axis=-2)


def rhs(state, control, layout, active, *, xp=jnp):
    _, membrane, _, md = membrane_values(state, control, layout, xp=xp)
    bulk = field_values(state, layout, xp=xp)
    inside = field.scatter(-membrane, state.amount_increment, (layout.owners,), xp=xp)
    outside = (
        field.scatter(
            membrane, state.extracellular_amount_increment, (layout.outside_owners,), xp=xp
        )
        + field.scatter(
            -bulk.flux_fmol_per_s, state.extracellular_amount_increment, (layout.senders,), xp=xp
        )
        + field.scatter(
            bulk.flux_fmol_per_s, state.extracellular_amount_increment, (layout.receivers,), xp=xp
        )
    )
    return STATE_TYPE(
        xp.where(active, inside, 0.0),
        outside,
        membrane,
        bulk.flux_fmol_per_s,
        md,
        bulk.dissipation_rate_pJ_per_s,
    )


def domain_valid(state, layout, active, *, xp=jnp):
    valid = xp.asarray(True)
    masks = (
        active,
        layout.extracellular_active,
        layout.membrane_active,
        layout.face_active,
        layout.membrane_active,
        layout.face_active,
    )
    for value, mask in zip(state, masks, strict=True):
        valid = valid & xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    for amount, mask, volume in zip(
        physical_amounts(state, layout),
        (active, layout.extracellular_active),
        (layout.volume, layout.extracellular_volume),
        strict=True,
    ):
        c = amount / volume
        valid = (
            valid
            & xp.all(xp.isfinite(c))
            & xp.all(xp.where(mask, (amount > 0) & (c > 0), amount == 0))
        )
    for possible, history in (
        (layout.permeability > 0, state.membrane_transferred),
        (layout.face_factor > 0, state.face_transferred),
        (xp.any(layout.permeability > 0, axis=-2), state.membrane_dissipated_energy_pJ),
        (xp.any(layout.face_factor > 0, axis=-2), state.face_dissipated_energy_pJ),
    ):
        valid = valid & xp.all(xp.where(possible, True, history == 0))
    x = (
        layout.valence
        * F
        * cell_voltage(state.amount_increment, layout, xp=xp)[..., None, :]
        / (R * layout.temperature)
    )
    charge = component_charge(state, layout, xp=xp)
    valid = (
        valid
        & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))
        & xp.all(xp.isfinite(charge) & (xp.abs(charge) <= CHARGE_TOLERANCE_C))
    )
    for residual in capacitor_residuals(state, layout, xp=xp):
        valid = valid & xp.all(xp.isfinite(residual) & (xp.abs(residual) <= CHARGE_TOLERANCE_C))

    def check_field():
        result = field_values(state, layout, xp=xp)
        ok = xp.all(result.current_normalized <= 1.0)
        for v in result:
            ok = ok & xp.all(xp.isfinite(v))
        return ok & xp.all(
            xp.where(layout.face_active, result.conductance_S > 0, result.conductance_S == 0)
        )

    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return check_field()
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(valid, check_field, lambda: jnp.asarray(False))


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Spatial model requires actual RK4 steps <= 0.000125 s; "
            "new meshes/regimes need qualification"
        )
    state, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise ConfigError("Initial spatial state or conducting field violates physical domains")
        for control in control_values(spec, [c.time for c in spec.experiment.changes]):
            if not all(
                np.isfinite(v).all() for v in rhs(state, control, layout, layout.active, xp=np)
            ):
                raise ConfigError("Initial spatial rates exceed finite float64")


def balances(state, layout):
    di, do = state.amount_increment, state.extracellular_amount_increment
    hm, hf = state.membrane_transferred, state.face_transferred
    inside = di + field.scatter(hm, di, (layout.owners,), xp=np)
    outside = (
        do
        - field.scatter(hm, do, (layout.outside_owners,), xp=np)
        + field.scatter(hf, do, (layout.senders,), xp=np)
        - field.scatter(hf, do, (layout.receivers,), xp=np)
    )
    total = np.sum(di, axis=-1) + np.sum(do, axis=-1)
    chemical = 0.0
    for delta, reference, volume, mask in (
        (di, layout.amount_reference, layout.volume, layout.active),
        (
            do,
            layout.extracellular_amount_reference,
            layout.extracellular_volume,
            layout.extracellular_active,
        ),
    ):
        n0 = np.where(mask, reference, 1.0)
        chemical = chemical + 1e-3 * R * layout.temperature * np.sum(
            delta * (np.log(n0 / volume) - 1) + (n0 + delta) * np.log1p(delta / n0), axis=(-2, -1)
        )
    dv = cell_voltage(di, layout, xp=np, derivative=True)
    cap = layout.capacitance[layout.cell_membranes]
    electric = 0.5e12 * np.sum(cap * dv * (2 * layout.voltage_reference + dv), axis=-1)
    energy = (
        chemical
        + electric
        + np.sum(state.membrane_dissipated_energy_pJ, axis=-1)
        + np.sum(state.face_dissipated_energy_pJ, axis=-1)
    )
    return inside, outside, total, component_charge(state, layout, xp=np), energy


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError("Invalid spatial inventory, charge, voltage or field; no repair")
        local, outside, total, charge, energy = balances(state, layout)
        tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
        if (
            np.any(np.abs(local) > tolerance[:, None])
            or np.any(np.abs(outside) > tolerance[:, None])
            or np.any(np.abs(total) > tolerance)
            or np.any(np.abs(energy) > 1e-6)
            or not all(np.isfinite(v).all() for v in (local, outside, total, charge, energy))
        ):
            raise NumericalError(
                "Spatial owner/global material or resolved-energy accounting failed"
            )
        for d in (state.membrane_dissipated_energy_pJ, state.face_dissipated_energy_pJ):
            if np.min(d, initial=0) < -1e-10 or (
                d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -1e-10
            ):
                raise NumericalError("Diagnostic spatial dissipation must not decrease")
        bulk = field_values(state, layout, xp=np)
    return dict(
        zip(
            (
                "max_balance_error_fmol",
                "max_extracellular_balance_error_fmol",
                "max_global_balance_error_fmol",
                "max_component_charge_C",
                "max_energy_balance_error_pJ",
                "max_current_residual_A",
                "max_current_normalized",
            ),
            (
                float(np.max(np.abs(v), initial=0))
                for v in (
                    local,
                    outside,
                    total,
                    charge,
                    energy,
                    bulk.current_residual_A,
                    bulk.current_normalized,
                )
            ),
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    if len(times) < 2:
        return
    for key, anchor, mask in (
        ("amount_increment", layout.amount_reference, layout.active),
        (
            "extracellular_amount_increment",
            layout.extracellular_amount_reference,
            layout.extracellular_active,
        ),
    ):
        lo, hi = hermite_bounds(times, getattr(history, key), getattr(f0, key), getattr(f1, key))
        if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
            (lo + anchor)[..., mask] <= 0
        ):
            raise NumericalError("Cubic interior violates positive spatial inventory")
    voltage = cell_voltage(history.amount_increment, layout, xp=np)
    slopes = [cell_voltage(f.amount_increment, layout, xp=np, derivative=True) for f in (f0, f1)]
    bound = MAX_ABS_X * R * layout.temperature / (F * np.max(np.abs(layout.valence)))
    lo, hi = hermite_bounds(times, voltage, *slopes)
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > bound
    ):
        raise NumericalError("Cubic interior exceeds all-valence membrane voltage domain")
    lo, hi = hermite_bounds(
        times,
        component_charge(history, layout, xp=np),
        *(component_charge(f, layout, xp=np, derivative=True) for f in (f0, f1)),
    )
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > CHARGE_TOLERANCE_C
    ):
        raise NumericalError("Cubic interior violates capacitive-component charge")


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount_increment: np.ndarray
    extracellular_amount_increment: np.ndarray
    membrane_transferred: np.ndarray
    face_transferred: np.ndarray
    membrane_dissipated_energy_pJ: np.ndarray
    face_dissipated_energy_pJ: np.ndarray
    amount: np.ndarray
    extracellular_amount: np.ndarray
    concentration_mM: np.ndarray
    extracellular_concentration_mM: np.ndarray
    cell_potential_V: np.ndarray
    extracellular_potential_V: np.ndarray
    membrane_voltage_V: np.ndarray
    membrane_availability: np.ndarray
    membrane_flux_fmol_per_s: np.ndarray
    membrane_current_A: np.ndarray
    membrane_delta_mu_J_per_mol: np.ndarray
    membrane_dissipation_rate_pJ_per_s: np.ndarray
    face_flux_fmol_per_s: np.ndarray
    face_delta_mu_J_per_mol: np.ndarray
    face_conductance_S: np.ndarray
    face_diffusion_current_A: np.ndarray
    face_drift_current_A: np.ndarray
    face_current_A: np.ndarray
    current_residual_A: np.ndarray
    current_normalized: np.ndarray
    face_dissipation_rate_pJ_per_s: np.ndarray
    species_balance_fmol: np.ndarray
    extracellular_species_balance_fmol: np.ndarray
    global_species_balance_fmol: np.ndarray
    component_charge_C: np.ndarray
    energy_balance_pJ: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    incoming = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(STATE_TYPE(*(v[part] for v in history)), incoming, layout, layout.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = STATE_TYPE(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, flux, mu, dissipation = membrane_values(sampled, control, layout, xp=np)
    bulk = field_values(sampled, layout, xp=np)
    amount, outside = physical_amounts(sampled, layout)
    cell_phi = np.where(
        layout.active,
        cell_voltage(sampled.amount_increment, layout, xp=np)
        + bulk.potential_V[..., layout.outside_owners[layout.cell_membranes]],
        0.0,
    )
    result = Observations(
        requested,
        *sampled,
        amount,
        outside,
        amount / layout.volume,
        outside / layout.extracellular_volume,
        cell_phi,
        bulk.potential_V,
        voltage,
        control,
        flux,
        CHARGE_PER_FMOL * np.sum(layout.valence * flux, axis=-2),
        mu,
        dissipation,
        *bulk[1:],
        *balances(sampled, layout),
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite spatial physical observation")
    return result


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    m, x = spec.model, spec.execution
    return {
        "model": "spatial_extracellular@1",
        "species_ids": list(m.species_ids),
        "cell_ids": [c.id for c in m.cells],
        "extracellular_ids": [c.id for c in m.extracellular],
        "membrane_ids": [p.id for p in m.membranes],
        "face_ids": [p.id for p in m.faces],
        "capacities": {
            k: getattr(x, k)
            for k in ("capacity", "extracellular_capacity", "membrane_capacity", "face_capacity")
        },
        "field_solver": x.field_solver,
        "gauge_reference": m.gauge_reference,
        "boundary": "closed finite inventories; connected conducting outside; one common gauge",
        "energy_scope": (
            "all finite ideal chemical inventories and each membrane capacitor once; "
            "no bulk capacitance or external chemical work"
        ),
        "external_support": ["temperature", "fixed volumes/geometries"],
        "final_amounts_fmol": (layout.amount_reference + history.amount_increment[-1])[
            :, : len(m.cells)
        ].tolist(),
        "final_extracellular_amounts_fmol": (
            layout.extracellular_amount_reference + history.extracellular_amount_increment[-1]
        )[:, : len(m.extracellular)].tolist(),
        **diagnostics,
    }
