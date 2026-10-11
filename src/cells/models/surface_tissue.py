"""Evolving resolved surfaces with explicit material, electrode and work ledgers.

The qualified algebraic field is recomputed with actual controls at every RK4
stage. Reservoir concentrations/voltages are held; observations use accepted
boundaries. No hidden field cache or charge projection enters a checkpoint.
"""

import math
from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_tissue_spec import MODEL_ID
from cells.numerics import surface_field as field
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

OBSERVER_ID = "resolved_tissue_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = "read_only_accepted_grid_control_dependent_field@1"
STAGE_DOMAIN_ID = "positive_resolved_inventory_actual_control_charge_current@1"
MAX_STEP = 0.0001
ENERGY_ATOL_PJ = 2e-8
BATCH_CAPACITIES = ("extracellular_capacity", "face_capacity", "field_solver")
STATE_AXES = {
    "amount_increment": ["species", "cell_slot"],
    "extracellular_amount_increment": ["species", "extracellular_slot"],
    "membrane_transferred": ["species", "membrane_slot"],
    "junction_transferred": ["species", "edge_slot"],
    "face_transferred": ["species", "face_slot"],
    "reservoir_supplied": ["species", "extracellular_slot"],
    "membrane_dissipated_energy_pJ": ["membrane_slot"],
    "junction_dissipated_energy_pJ": ["edge_slot"],
    "face_dissipated_energy_pJ": ["face_slot"],
    "electrode_charge_transferred_C": ["extracellular_slot"],
    "reservoir_work_pJ": ["extracellular_slot"],
    "electrode_work_pJ": ["extracellular_slot"],
}
STATE_TYPE = NamedTuple("SurfaceTissueState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceTissueLayout",
    [
        (k, object)
        for k in (
            *surface.Layout._fields,
            *("field_" + k for k in field.Layout._fields if k != "surface"),
            "active",
            "ids",
            "volume",
            "extracellular_volume",
            "amount_reference",
            "extracellular_amount_reference",
            "initial_cell_charge_C",
            "initial_outside_charge_C",
            "boundary_V",
            "initial_membrane_voltage_V",
        )
    ],
)


def batch_signature(model):
    # Reduced floating-component axes depend on capacitor topology, not merely
    # padded counts. Require the same identified topology within each batch.
    return (
        len(model.species_ids),
        tuple(p.id for p in model.cells),
        tuple((p.id, p.reservoir) for p in model.extracellular),
        tuple((p.inside, p.outside) for p in model.membranes),
        model.gauge_reference,
    )


def parameters(spec, layout):
    return layout


def working_size(spec):
    x, s = spec.execution, len(spec.model.species_ids)
    return (
        (48 * s + 96) * (x.capacity + x.extracellular_capacity)
        + (48 * s + 96) * (x.membrane_capacity + x.edge_capacity + x.face_capacity)
        + 96 * (x.capacity + x.extracellular_capacity) ** 2
    )


def field_layout(p):
    return field.Layout(
        surface.Layout(*(getattr(p, k) for k in surface.Layout._fields)),
        *(getattr(p, "field_" + k) for k in field.Layout._fields if k != "surface"),
    )


def initial_values(spec):
    m, x = spec.model, spec.execution
    s, n, o, nm, ne, nf = (
        len(m.species_ids),
        x.capacity,
        x.extracellular_capacity,
        x.membrane_capacity,
        x.edge_capacity,
        x.face_capacity,
    )
    counts = {
        "cell": (n, len(m.cells)),
        "outside": (o, len(m.extracellular)),
        "membrane": (nm, len(m.membranes)),
        "junction": (ne, len(m.junctions)),
        "face": (nf, len(m.faces)),
    }
    v = {k + "_active": np.arange(capacity) < count for k, (capacity, count) in counts.items()}
    v.update(
        temperature=np.asarray(m.temperature_K),
        valence=np.asarray(m.valence, dtype=float)[:, None],
        reservoir=np.zeros(o, dtype=bool),
    )
    for name, size in (
        ("membrane_cell", nm),
        ("membrane_outside", nm),
        ("junction_sender", ne),
        ("junction_receiver", ne),
        ("face_sender", nf),
        ("face_receiver", nf),
    ):
        v[name] = np.zeros(size, dtype=np.int64)
    for name, size in (("membrane_area", nm), ("membrane_capacitance", nm), ("junction_area", ne)):
        v[name] = np.zeros(size)
    for name, size in (
        ("membrane_permeability", nm),
        ("junction_permeability", ne),
        ("face_factor", nf),
    ):
        v[name] = np.zeros((s, size))
    cids, oids = [p.id for p in m.cells], [p.id for p in m.extracellular]
    for i, p in enumerate(m.membranes):
        v["membrane_cell"][i], v["membrane_outside"][i] = (
            cids.index(p.inside),
            oids.index(p.outside),
        )
        v["membrane_area"][i], v["membrane_capacitance"][i] = p.area_m2, p.capacitance_F
        v["membrane_permeability"][:, i] = p.permeability_m_per_s
    for i, p in enumerate(m.junctions):
        v["junction_sender"][i], v["junction_receiver"][i] = (
            cids.index(p.sender),
            cids.index(p.receiver),
        )
        v["junction_area"][i], v["junction_permeability"][:, i] = p.area_m2, p.permeability_m_per_s
    for i, p in enumerate(m.faces):
        v["face_sender"][i], v["face_receiver"][i] = oids.index(p.sender), oids.index(p.receiver)
        v["face_factor"][:, i] = np.asarray(p.diffusivity_m2_per_s) * p.area_m2 / p.length_m
    v["reservoir"][: len(m.extracellular)] = [p.reservoir for p in m.extracellular]
    gauge = np.zeros(o, dtype=bool)
    if m.gauge_reference is not None:
        gauge[oids.index(m.gauge_reference)] = True
    bound = field.bind(surface.Layout(**v), gauge)
    v.update({"field_" + k: value for k, value in bound._asdict().items() if k != "surface"})
    v.update(
        active=v["cell_active"],
        ids=np.where(v["cell_active"], np.arange(n) + 1, -1).astype(np.int64),
        volume=np.ones(n),
        extracellular_volume=np.ones(o),
        amount_reference=np.zeros((s, n)),
        extracellular_amount_reference=np.zeros((s, o)),
        initial_cell_charge_C=np.zeros(n),
        initial_outside_charge_C=np.zeros(o),
        boundary_V=np.zeros(o),
    )
    for owners, volume, amount, charge in (
        (m.cells, "volume", "amount_reference", "initial_cell_charge_C"),
        (
            m.extracellular,
            "extracellular_volume",
            "extracellular_amount_reference",
            "initial_outside_charge_C",
        ),
    ):
        for i, p in enumerate(owners):
            v[volume][i], v[amount][:, i], v[charge][i] = (
                p.volume_pL,
                p.initial_amount_fmol,
                p.initial_charge_C,
            )
    v["boundary_V"][: len(m.extracellular)] = [p.boundary_potential_V for p in m.extracellular]
    base = field._capacitor_solve(
        np.r_[v["initial_cell_charge_C"], v["initial_outside_charge_C"]],
        np.r_[np.zeros(n), v["boundary_V"]],
        bound,
        xp=np,
    )
    v["initial_membrane_voltage_V"] = np.where(
        v["membrane_active"], base[v["membrane_cell"]] - base[n + v["membrane_outside"]], 0.0
    )
    state = STATE_TYPE(
        np.zeros((s, n)),
        np.zeros((s, o)),
        np.zeros((s, nm)),
        np.zeros((s, ne)),
        np.zeros((s, nf)),
        np.zeros((s, o)),
        np.zeros(nm),
        np.zeros(ne),
        np.zeros(nf),
        np.zeros(o),
        np.zeros(o),
        np.zeros(o),
    )
    return state, LAYOUT_TYPE(**v)


def physical_amounts(state, p):
    return (
        p.cytosol_amount
        if hasattr(p, "cytosol_amount")
        else p.amount_reference + state.amount_increment,
        p.extracellular_amount_reference + state.extracellular_amount_increment,
    )


def charge_increment(state, p, *, xp):
    return CHARGE_PER_FMOL * xp.concatenate(
        (
            xp.sum(p.valence * state.amount_increment, axis=0),
            xp.sum(p.valence * state.extracellular_amount_increment, axis=0),
        )
    )


def field_values(state, control, p, *, xp=jnp):
    ci, co = physical_amounts(state, p)
    q = charge_increment(state, p, xp=xp)
    n = p.active.size
    return field.solve(
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
        p.initial_cell_charge_C + q[:n],
        p.initial_outside_charge_C + q[n:],
        control.membrane,
        control.junction,
        p.boundary_V,
        field_layout(p),
        xp=xp,
    )


def rhs(state, control, p, active, *, xp=jnp):
    values = field_values(state, control, p, xp=xp)
    r = values.rates
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    result = STATE_TYPE(
        r.cell_rate_fmol_s,
        r.outside_rate_fmol_s,
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        r.face_flux_fmol_s,
        r.reservoir_supply_fmol_s,
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        r.face_dissipation_pJ_s,
        values.electrode_current_A,
        1e-3 * xp.sum(mu * r.reservoir_supply_fmol_s, axis=0),
        1e12 * p.boundary_V * values.electrode_current_A,
    )
    return STATE_TYPE(*(xp.where(values.converged, v, xp.nan) for v in result))


def capacitor_change(state, p, *, xp):
    """Charge-only increment; patch voltages do not depend on floating offsets."""
    q = charge_increment(state, p, xp=xp)
    dp = field._capacitor_solve(q, xp.zeros_like(q), field_layout(p), xp=xp)
    dv = xp.where(
        p.membrane_active, dp[p.membrane_cell] - dp[p.active.size + p.membrane_outside], 0.0
    )
    return q, p.field_capacitor_matrix @ dp, dv


def domain_valid(state, p, active, *, xp=jnp):
    valid = xp.asarray(True)
    masks = (
        p.active,
        p.outside_active & ~p.reservoir,
        p.membrane_active,
        p.junction_active,
        p.face_active,
        p.reservoir,
        p.membrane_active,
        p.junction_active,
        p.face_active,
        p.reservoir,
        p.reservoir,
        p.reservoir,
    )
    for v, mask in zip(state, masks, strict=True):
        valid &= xp.all(xp.isfinite(v)) & xp.all(xp.where(mask, True, v == 0))
    for amount, mask in zip(physical_amounts(state, p), (p.active, p.outside_active), strict=True):
        valid &= xp.all(xp.where(mask, xp.isfinite(amount) & (amount > 0), amount == 0))
    for name, coefficient in (
        ("membrane_transferred", p.membrane_permeability),
        ("junction_transferred", p.junction_permeability),
        ("face_transferred", p.face_factor),
    ):
        valid &= xp.all(xp.where(coefficient > 0, True, getattr(state, name) == 0))
    return valid


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
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
    for c in (*spec.model.cells, *spec.model.extracellular):
        q = CHARGE_PER_FMOL * math.fsum(
            (
                c.fixed_charge_equivalent_fmol,
                *(z * a for z, a in zip(spec.model.valence, c.initial_amount_fmol, strict=True)),
            )
        )
        if not math.isfinite(q) or abs(q - c.initial_charge_C) > 1e-20:
            raise ConfigError(
                "Initial inventory, fixed background and explicit charge anchor disagree"
            )
        if any(
            not math.isfinite(a / c.volume_pL) or a / c.volume_pL <= 0
            for a in c.initial_amount_fmol
        ):
            raise ConfigError("Initial concentration exceeds positive finite float64")
    # Validate active geometry before allocating caller-requested route padding.
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
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            control = type(controls)(*(v[i] for v in controls))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError(
                    "Initial resolved charge/current field or transport domain invalid"
                )


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError("Resolved tissue RK4 steps must be <= 0.0001 s")
    from cells.core.grid import EventGrid

    grid = EventGrid(spec)
    for t in spec.experiment.observation_times:
        try:
            grid.exact_index(t)
        except ConfigError as error:
            raise ConfigError(
                "Resolved tissue observations require accepted integration boundaries"
            ) from error


def balances(state, p, *, intracellular_energy_change_pJ=None):
    """One complete physical state; stable changes avoid subtracting bulk energies."""
    di, do = state.amount_increment, state.extracellular_amount_increment
    hm, hj, hf = state.membrane_transferred, state.junction_transferred, state.face_transferred
    local = (
        di
        + scatter(hm, di, (p.membrane_cell,), xp=np)
        + scatter(hj, di, (p.junction_sender,), xp=np)
        - scatter(hj, di, (p.junction_receiver,), xp=np)
    )
    outside = (
        do
        - scatter(hm, do, (p.membrane_outside,), xp=np)
        + scatter(hf, do, (p.face_sender,), xp=np)
        - scatter(hf, do, (p.face_receiver,), xp=np)
        - state.reservoir_supplied
    )
    total = di.sum(axis=1) + do.sum(axis=1) - state.reservoir_supplied.sum(axis=1)
    q, cap, dv = capacitor_change(state, p, xp=np)
    n = p.active.size
    initial_q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C]
    base = field._capacitor_solve(
        initial_q, np.r_[np.zeros(n), p.boundary_V], field_layout(p), xp=np
    )
    required = p.field_active & ~np.r_[np.zeros(n, dtype=bool), p.reservoir]
    charge = np.where(required, p.field_capacitor_matrix @ base - initial_q + cap - q, 0.0)
    electrode = state.electrode_charge_transferred_C - np.where(p.reservoir, cap[n:], 0.0)
    supply_charge = CHARGE_PER_FMOL * np.sum(p.valence * state.reservoir_supplied)
    global_charge = np.sum(state.electrode_charge_transferred_C) + supply_charge
    # A coupled store owns intracellular free/bound material. Its independent
    # exchange ledger still charges the plasma capacitors, but is not a free
    # cytosol inventory and must not be used in the chemical logarithms.
    chemical = 0.0 if intracellular_energy_change_pJ is None else intracellular_energy_change_pJ
    inventories = [(do, p.extracellular_amount_reference, p.extracellular_volume, p.outside_active)]
    if intracellular_energy_change_pJ is None:
        inventories.insert(0, (di, p.amount_reference, p.volume, p.active))
    for delta, anchor, volume, mask in inventories:
        a = np.where(mask, anchor, 1.0)
        chemical += (
            1e-3
            * R
            * p.temperature
            * np.sum(delta * (np.log(a / volume) - 1) + (a + delta) * np.log1p(delta / a))
        )
    electric = 0.5e12 * np.sum(
        p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + dv)
    )
    dissipated = sum(
        np.sum(getattr(state, k + "_dissipated_energy_pJ"))
        for k in ("membrane", "junction", "face")
    )
    energy = (
        chemical
        + electric
        + dissipated
        - np.sum(state.reservoir_work_pJ)
        - np.sum(state.electrode_work_pJ)
    )
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * np.log(co) + p.valence * F * p.boundary_V
    reservoir_work = state.reservoir_work_pJ - 1e-3 * np.sum(mu * state.reservoir_supplied, axis=0)
    electrode_work = (
        state.electrode_work_pJ - 1e12 * p.boundary_V * state.electrode_charge_transferred_C
    )
    return dict(
        local=local,
        outside=outside,
        total=total,
        charge=charge,
        electrode=electrode,
        global_charge=global_charge,
        energy=energy,
        reservoir_work=reservoir_work,
        electrode_work=electrode_work,
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
        )
    }
    with np.errstate(all="ignore"):
        for row in rows:
            if not domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid resolved inventory, ledger or padding; no repair")
            b = balances(row, p)
            tol = np.asarray(spec.execution.material_balance_atol_fmol)
            q = np.r_[p.initial_cell_charge_C, p.initial_outside_charge_C] + charge_increment(
                row, p, xp=np
            )
            charge_tol = field.CHARGE_ATOL_C + field.CHARGE_RTOL * np.abs(q)
            limits = (
                tol[:, None],
                tol[:, None],
                tol,
                charge_tol,
                field.CHARGE_ATOL_C
                + field.CHARGE_RTOL * np.abs(row.electrode_charge_transferred_C),
                3e-25,
                ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
            )
            for (name, value), key, bound in zip(b.items(), diagnostics, limits, strict=True):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError("Resolved tissue accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
    for name in (
        "membrane_dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
        "face_dissipated_energy_pJ",
    ):
        v = getattr(state, name)
        if np.min(v, initial=0) < -1e-12 or (
            v.ndim == 2 and np.min(np.diff(v, axis=0), initial=0) < -1e-12
        ):
            raise NumericalError("Resolved dissipation cannot be negative or decrease")
    return diagnostics


OBSERVATION_FIELDS = (
    "times",
    *STATE_TYPE._fields,
    "amount",
    "extracellular_amount",
    "cell_potential_V",
    "extracellular_potential_V",
    "membrane_voltage_V",
    "junction_voltage_V",
    "membrane_flux_fmol_s",
    "junction_flux_fmol_s",
    "face_flux_fmol_s",
    "reservoir_supply_fmol_s",
    "electrode_charge_C",
    "electrode_current_A",
    "reservoir_power_pJ_s",
    "electrode_power_pJ_s",
    "charge_residual_C",
    "component_current_residual_A",
    "energy_balance_pJ_s",
    "membrane_availability",
    "junction_availability",
)
Observations = make_dataclass(
    "SurfaceTissueObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved tissue observations require accepted times")
    controls = control_values(spec, requested)
    records = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        control = type(controls)(*(v[j] for v in controls))
        v = field_values(state, control, p, xp=np)
        if not v.converged:
            raise NumericalError("Resolved observation field failed its charge/current domain")
        r, n = v.rates, p.active.size
        records.append(
            (
                np.asarray(t),
                *state,
                *physical_amounts(state, p),
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
            )
        )
    if records:
        return Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    # Use a real accepted state to define empty observation shapes, including a
    # terminal continuation and windows without requested observations.
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    controls = control_values(spec, [time])
    control = type(controls)(*(v[0] for v in controls))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    values = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not values.converged:
        raise NumericalError("Ensemble endpoint field invalid")
    return values.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return {
        "model": MODEL_ID,
        "closure_law": field.LAW_ID,
        "boundary": "held chemical/electrical reservoirs"
        if any(p.reservoir for p in spec.model.extracellular)
        else "closed finite tissue",
        "species_ids": list(spec.model.species_ids),
        "state_fields": list(STATE_TYPE._fields),
        "observation_scope": "accepted integration boundaries only",
        **diagnostics,
    }
