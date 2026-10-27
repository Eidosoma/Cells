"""Resolved ionic tissue coupled to conserved neutral mobile leak populations.

Local permeability is background + reference permeability * local density /
reference density. The current RK4 stage owns both inventories. Neutral surface
diffusion has its own transfer and ideal-mixing heat ledgers; it is not ionic
charge, transmembrane protein transport, gating or an ATP-driven pump.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_redistribution_spec import MODEL_ID, base_spec
from cells.models import surface_tissue as base
from cells.numerics import membrane_redistribution as movement
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import R

OBSERVER_ID = "resolved_neutral_mobile_surface_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_mobile_surface_and_resolved_charge_current@1"
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "population_capacity", "surface_edge_capacity")
SURFACE_MATERIAL_ATOL_FMOL = 2e-12
SURFACE_ENERGY_ATOL_PJ = 2e-10
MAX_SURFACE_LOSS_PER_STEP = 0.05
EXTRA_AXES = {
    "surface_amount_increment": ["population_slot", "membrane_slot"],
    "surface_transferred": ["population_slot", "surface_edge_slot"],
    "surface_dissipated_energy_pJ": ["population_slot", "surface_edge_slot"],
}
STATE_AXES = base.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceRedistributionState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceRedistributionLayout",
    [
        (k, object)
        for k in (
            *base.LAYOUT_TYPE._fields,
            *("mobile_" + k for k in movement.Layout._fields),
            "surface_amount_reference",
            "reference_density",
            "reference_permeability",
        )
    ],
)
OBSERVATION_FIELDS = (
    *base.OBSERVATION_FIELDS,
    *EXTRA_AXES,
    "surface_amount_fmol",
    "surface_density_fmol_um2",
    "surface_flux_fmol_s",
    "effective_membrane_permeability_m_per_s",
    "surface_energy_balance_pJ",
)
Observations = make_dataclass(
    "SurfaceRedistributionObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = base.parameters


def base_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def base_layout(p):
    return base.LAYOUT_TYPE(*(getattr(p, k) for k in base.LAYOUT_TYPE._fields))


def mobile_layout(p):
    return movement.Layout(*(getattr(p, "mobile_" + k) for k in movement.Layout._fields))


def batch_signature(model):
    return (
        *base.batch_signature(model),
        model.species_ids,
        tuple(p.id for p in model.membranes),
        tuple(p.id for p in model.mobile_populations),
        tuple((p.id, p.sender, p.receiver) for p in model.surface_edges),
    )


def working_size(spec):
    x = spec.execution
    return base.working_size(spec) + 96 * x.population_capacity * (
        x.membrane_capacity + x.surface_edge_capacity + len(spec.model.species_ids)
    )


def initial_values(spec):
    state, p = base.initial_values(base_spec(spec))
    m, x = spec.model, spec.execution
    k, e, nm = x.population_capacity, x.surface_edge_capacity, x.membrane_capacity
    reference = np.zeros((k, nm))
    density = np.ones(k)
    permeability = np.zeros((len(m.species_ids), k))
    d = np.zeros((k, e))
    for i, population in enumerate(m.mobile_populations):
        reference[i, : len(m.membranes)] = population.initial_amount_fmol
        density[i] = population.reference_density_fmol_per_um2
        permeability[:, i] = population.permeability_at_reference_density_m_per_s
        d[i, : len(m.surface_edges)] = population.diffusivity_um2_per_s
    sender, receiver = np.zeros(e, dtype=np.int64), np.zeros(e, dtype=np.int64)
    width, distance = np.zeros(e), np.zeros(e)
    ids = [v.id for v in m.membranes]
    for i, edge in enumerate(m.surface_edges):
        sender[i], receiver[i] = ids.index(edge.sender), ids.index(edge.receiver)
        width[i], distance[i] = edge.width_um, edge.distance_um
    mobile = movement.validate_layout(
        movement.Layout(
            p.temperature,
            np.zeros(k),
            p.active,
            p.membrane_active,
            p.membrane_cell,
            p.membrane_area * 1e12,
            np.arange(e) < len(m.surface_edges),
            sender,
            receiver,
            d,
            width,
            distance,
        )
    )
    layout = LAYOUT_TYPE(*p, *mobile, reference, density, permeability)
    return STATE_TYPE(*state, np.zeros_like(reference), np.zeros((k, e)), np.zeros((k, e))), layout


def surface_amount(state, p):
    return p.surface_amount_reference + state.surface_amount_increment


def effective_layout(state, p, *, xp=jnp):
    area = xp.where(p.membrane_active, p.mobile_patch_area_um2, 1.0)
    relative_density = surface_amount(state, p) / area / p.reference_density[:, None]
    permeability = p.membrane_permeability + p.reference_permeability @ relative_density
    return base_layout(p)._replace(membrane_permeability=permeability)


def accounting_layout(p, *, xp):
    # Union of possible ionic routes, only for ledger support/domain checks.
    union = p.membrane_permeability + p.reference_permeability @ xp.asarray(
        p.surface_amount_reference > 0, dtype=float
    )
    return base_layout(p)._replace(membrane_permeability=union)


def accounting_spec(spec):
    original = base_spec(spec)
    membranes = tuple(
        replace(
            p,
            permeability_m_per_s=tuple(
                value
                + sum(
                    pop.permeability_at_reference_density_m_per_s[s]
                    for pop in spec.model.mobile_populations
                    if pop.initial_amount_fmol[j] > 0
                )
                for s, value in enumerate(p.permeability_m_per_s)
            ),
        )
        for j, p in enumerate(original.model.membranes)
    )
    return replace(original, model=replace(original.model, membranes=membranes))


def surface_rates(state, p, *, xp=jnp):
    return movement.rates(
        surface_amount(state, p), xp.zeros_like(p.membrane_area), mobile_layout(p), xp=xp
    )


def field_values(state, control, p, *, xp=jnp):
    return base.field_values(base_state(state), control, effective_layout(state, p, xp=xp), xp=xp)


def rhs(state, control, p, active, *, xp=jnp):
    layout = effective_layout(state, p, xp=xp)
    values = base.field_values(base_state(state), control, layout, xp=xp)
    ionic = base.derivative_from_field(values, layout, xp=xp)
    r, heat = surface_readouts(state, p, xp=xp)
    result = STATE_TYPE(*ionic, r.amount_rate_fmol_s, r.flux_fmol_s, heat)
    valid = r.valid & xp.all(
        xp.where(
            p.surface_amount_reference > 0,
            surface_amount(state, p) > 0,
            surface_amount(state, p) == 0,
        )
    )
    return STATE_TYPE(*(xp.where(valid, v, xp.nan) for v in result))


def surface_readouts(state, p, *, xp=jnp):
    """Neutral surface rates/heat shared by separately owned protein pools."""
    r = surface_rates(state, p, xp=xp)
    present = p.surface_amount_reference > 0
    density = xp.where(present, r.density_fmol_um2 / p.reference_density[:, None], 1.0)
    log_density = xp.log(density)
    heat = (
        1e-3
        * R
        * p.temperature
        * r.flux_fmol_s
        * (log_density[:, p.mobile_edge_sender] - log_density[:, p.mobile_edge_receiver])
    )
    return r, heat


def domain_valid(state, p, active, *, xp=jnp):
    valid = base.domain_valid(base_state(state), accounting_layout(p, xp=xp), active, xp=xp)
    return valid & surface_domain_valid(state, p, xp=xp)


def surface_domain_valid(state, p, *, xp=jnp):
    """Check only owned surface amounts and their transfer/heat histories."""
    valid = xp.asarray(True)
    present = p.surface_amount_reference > 0
    amount = surface_amount(state, p)
    valid &= xp.all(xp.isfinite(amount)) & xp.all(xp.where(present, amount > 0, amount == 0))
    support = (
        p.mobile_edge_active
        & (p.mobile_edge_diffusivity_um2_s > 0)
        & present[:, p.mobile_edge_sender]
        & present[:, p.mobile_edge_receiver]
    )
    for value, mask in (
        (state.surface_amount_increment, present),
        (state.surface_transferred, support),
        (state.surface_dissipated_energy_pJ, support),
    ):
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
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
    # Validate compact physical axes before allocating user-specified capacities.
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
            population_capacity=max(1, len(m.mobile_populations)),
            surface_edge_capacity=len(m.surface_edges),
        ),
    )
    state, p = initial_values(compact)
    from cells.core.schedule import control_values

    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    for i in range(len(compact.experiment.changes)):
        control = type(controls)(*(v[i] for v in controls))
        if not control_domain_valid(state, control, p, p.active, xp=np):
            raise ConfigError("Initial mobile surfaces fail the actual-control field domain")


def check_steps(spec, steps, controls):
    base.check_steps(base_spec(spec), steps, controls)
    loss = surface_loss_bound(spec.model, spec.model.mobile_populations)
    if np.max(steps, initial=0) * loss > MAX_SURFACE_LOSS_PER_STEP * (1 + 16 * np.finfo(float).eps):
        raise ConfigError(
            "Mobile surface diffusion requires a smaller RK4 step (total outgoing loss > 0.05)"
        )


def surface_loss_bound(m, populations):
    # Geometry-only outgoing coefficients; compact allocation independent of
    # padding. Use all neighbours, not separate per-edge stability estimates.
    areas = np.asarray([p.area_m2 * 1e12 for p in m.membranes])
    loss = np.zeros((len(populations), len(m.membranes)))
    ids = [p.id for p in m.membranes]
    for e in m.surface_edges:
        for side in (e.sender, e.receiver):
            j = ids.index(side)
            loss[:, j] += (
                np.asarray([p.diffusivity_um2_per_s for p in populations])
                * e.width_um
                / e.distance_um
                / areas[j]
            )
    return np.max(loss, initial=0)


def surface_balances(state, p):
    delta, h = state.surface_amount_increment, state.surface_transferred
    local = (
        delta
        + ordered_scatter(h, np.zeros_like(delta), (p.mobile_edge_sender,), xp=np)
        - ordered_scatter(h, np.zeros_like(delta), (p.mobile_edge_receiver,), xp=np)
    )
    cell = ordered_scatter(
        delta, np.zeros((delta.shape[0], p.active.size)), (p.membrane_cell,), xp=np
    )
    present = p.surface_amount_reference > 0
    anchor = np.where(present, p.surface_amount_reference, 1.0)
    area = np.where(p.membrane_active, p.mobile_patch_area_um2, 1.0)
    change = (
        1e-3
        * R
        * p.temperature
        * np.sum(
            delta * (np.log(anchor / area / p.reference_density[:, None]) - 1)
            + (anchor + delta) * np.log1p(delta / anchor),
            axis=1,
        )
    )
    return dict(
        local=local, cell=cell, energy=change + state.surface_dissipated_energy_pJ.sum(axis=1)
    )


def check_values(state, spec):
    diagnostics = base.check_values(base_state(state), accounting_spec(spec))
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.surface_amount_increment.ndim == 2
        else [
            STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.surface_amount_increment))
        ]
    )
    keys = (
        "max_surface_balance_error_fmol",
        "max_surface_cell_balance_error_fmol",
        "max_surface_energy_balance_error_pJ",
    )
    diagnostics.update(dict.fromkeys(keys, 0.0))
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid mobile surface inventory, ledger or padding; no repair")
        for key, value, tolerance in zip(
            keys,
            surface_balances(row, p).values(),
            (SURFACE_MATERIAL_ATOL_FMOL, SURFACE_MATERIAL_ATOL_FMOL, SURFACE_ENERGY_ATOL_PJ),
            strict=True,
        ):
            error = float(np.max(np.abs(value), initial=0))
            if not np.isfinite(value).all() or error > tolerance:
                raise NumericalError("Mobile surface accounting failed: " + key)
            diagnostics[key] = max(diagnostics[key], error)
    heat = state.surface_dissipated_energy_pJ
    if np.min(heat, initial=0) < -1e-12 or (
        heat.ndim == 3 and np.min(np.diff(heat, axis=0), initial=0) < -1e-12
    ):
        raise NumericalError("Mobile surface dissipation cannot be negative or decrease")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    times, requested = np.asarray(times), np.asarray(requested)
    if any(t not in times for t in requested):
        raise ConfigError("Mobile surface observations require accepted times")
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    records = []
    for time in requested:
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        effective = effective_layout(state, p, xp=np)
        observed = base.observe_history(
            np.asarray([time]),
            base.STATE_TYPE(*(v[None] for v in base_state(state))),
            effective,
            [time],
            base_spec(spec),
        )
        r = surface_rates(state, p, xp=np)
        records.append(
            (
                *[v[0] for v in vars(observed).values()],
                *(getattr(state, k) for k in EXTRA_AXES),
                surface_amount(state, p),
                r.density_fmol_um2,
                r.flux_fmol_s,
                effective.membrane_permeability,
                surface_balances(state, p)["energy"],
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

    controls = control_values(spec, [time])
    control = type(controls)(*(v[0] for v in controls))
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    y = STATE_TYPE(*(np.asarray(v) for v in state))
    values = field_values(y, control, p, xp=np)
    if not values.converged:
        raise NumericalError("Mobile surface ensemble endpoint field invalid")
    return values.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(base_state(history), diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        mobile_populations=[p.id for p in spec.model.mobile_populations],
        surface_law=movement.LAW_ID,
        population_law="neutral_mobile_leak@1",
    )
