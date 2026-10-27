"""Conservative mobile Kv1.5 coupled to owned calcium/ER and fixed-geometry injury.

Channel proteins and their joint gates move on the surface. Conducted K enters
the existing free-cytosol owner and charges the same capacitors. Separate ion
ledgers prevent conflating lateral protein transport with transmembrane flow.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_mobile_repair_spec import MODEL_ID, accounting_spec, prior_spec
from cells.coupling.selective import selective_flux
from cells.models import surface_calcium as calcium
from cells.models import surface_mobile_channel as mobile
from cells.models import surface_redistribution as surface
from cells.models import surface_repair as prior
from cells.models import surface_tissue as ionic
from cells.numerics import membrane_redistribution as movement
from cells.numerics.extracellular_field import ordered_scatter, scatter
from cells.processes import mobile_channel_gates as gates
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EXTRA_AXES = mobile.EXTRA_AXES | {
    "mobile_channel_transferred": ["channel_population_slot", "membrane_slot"],
    "mobile_channel_dissipated_energy_pJ": ["channel_population_slot", "membrane_slot"],
}
STATE_AXES = prior.STATE_AXES | EXTRA_AXES
STATE_TYPE = NamedTuple("SurfaceMobileRepairState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple(
    "SurfaceMobileRepairLayout",
    [
        (k, object)
        for k in (
            *prior.LAYOUT_TYPE._fields,
            *("mobile_" + k for k in movement.Layout._fields),
            "channel_state_reference",
            "channel_reference_density",
            "mobile_channel_permeability",
            "mobile_channel_dynamic",
            "mobile_channel_active",
            "mobile_potassium",
            "mobile_k_selector",
        )
    ],
)
OBSERVER_ID = "resolved_mobile_channels_owned_calcium_repair_readouts@1"
OBSERVATION_SAMPLING = prior.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_mobile_joint_states_owned_free_cytosol_repair@1"
BATCH_CAPACITIES = (*prior.BATCH_CAPACITIES, "channel_population_capacity", "surface_edge_capacity")
READOUTS = (
    "mobile_channel_amount_fmol",
    "mobile_channel_density_fmol_um2",
    "mobile_channel_flux_fmol_s",
    "mobile_channel_gate_rate_fmol_s",
    "mobile_channel_gate_target",
    "mobile_channel_gate_tau_s",
    "mobile_channel_open_fraction",
    "mobile_channel_joint_correlation",
    "mobile_channel_availability",
    "mobile_channel_ion_flux_fmol_s",
    "mobile_channel_permeability_m_per_s",
    "mobile_channel_mixing_balance_pJ",
)
OBSERVATION_FIELDS = (*prior.OBSERVATION_FIELDS, *EXTRA_AXES, *READOUTS)
Observations = make_dataclass(
    "SurfaceMobileRepairObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)
parameters = prior.parameters
cytosol_amount = prior.cytosol_amount
store_state, store_layout, er = prior.store_state, prior.store_layout, prior.er
ip3_readouts = prior.ip3_readouts


class Values(NamedTuple):
    prior: object
    field: object
    derivative: object
    motion: object
    gating: object
    permeability: object
    valid: object


def prior_state(state):
    return prior.STATE_TYPE(*(getattr(state, k) for k in prior.STATE_TYPE._fields))


def prior_layout(p):
    return prior.LAYOUT_TYPE(*(getattr(p, k) for k in prior.LAYOUT_TYPE._fields))


def prior_control(control):
    from cells.core.schedule import SurfaceRepairControl

    return SurfaceRepairControl(*(getattr(control, k) for k in SurfaceRepairControl._fields))


def batch_signature(model):
    return (
        *prior.batch_signature(model),
        tuple((p.id, p.kinetic_law, p.species_id) for p in model.mobile_channels),
    )


def working_size(spec):
    x = spec.execution
    return prior.working_size(prior_spec(spec)) + 1024 * x.channel_population_capacity * (
        x.membrane_capacity + x.surface_edge_capacity
    )


def initial_values(spec):
    state, p = prior.initial_values(prior_spec(spec))
    m, x = spec.model, spec.execution
    k, n, e = x.channel_population_capacity, x.membrane_capacity, x.surface_edge_capacity
    reference, density, diff = np.zeros((k, 4, n)), np.ones(k), np.zeros((k, e))
    permeability, dynamic = np.zeros(k), np.zeros(k, dtype=bool)
    for i, pop in enumerate(m.mobile_channels):
        reference[i, :, : len(m.membranes)] = pop.initial_state_amount_fmol
        density[i] = pop.reference_density_fmol_per_um2
        diff[i, : len(m.surface_edges)] = pop.diffusivity_um2_per_s
        permeability[i], dynamic[i] = (
            pop.permeability_at_reference_density_m_per_s,
            pop.gate_mode == "dynamic",
        )
    sender, receiver = np.zeros(e, dtype=np.int64), np.zeros(e, dtype=np.int64)
    width, distance = np.zeros(e), np.zeros(e)
    ids = [v.id for v in m.membranes]
    for i, edge in enumerate(m.surface_edges):
        sender[i], receiver[i] = ids.index(edge.sender), ids.index(edge.receiver)
        width[i], distance[i] = edge.width_um, edge.distance_um
    motion = movement.validate_layout(
        movement.Layout(
            p.temperature,
            np.zeros(k * 4),
            p.active,
            p.membrane_active,
            p.membrane_cell,
            p.membrane_area * 1e12,
            np.arange(e) < len(m.surface_edges),
            sender,
            receiver,
            np.repeat(diff, 4, axis=0),
            width,
            distance,
        )
    )
    potassium = m.species_ids.index("K")
    layout = LAYOUT_TYPE(
        *p,
        *motion,
        reference,
        density,
        permeability,
        dynamic,
        np.arange(k) < len(m.mobile_channels),
        np.int32(potassium),
        np.eye(len(m.species_ids))[potassium, :, None],
    )
    return STATE_TYPE(
        *state,
        np.zeros((k, 4, n)),
        np.zeros((k, 4, e)),
        np.zeros((k, 4, e)),
        np.zeros((k, 4, n)),
        np.zeros((k, 4, n)),
        np.zeros((k, 4, n)),
        np.zeros((k, n)),
        np.zeros((k, n)),
    ), layout


def surface_layout(p, *, xp=np):
    k, _, n = p.channel_state_reference.shape
    return surface.LAYOUT_TYPE(
        *(getattr(p, name) for name in ionic.LAYOUT_TYPE._fields),
        *(getattr(p, "mobile_" + name) for name in movement.Layout._fields),
        p.channel_state_reference.reshape((k * 4, n)),
        xp.repeat(p.channel_reference_density, 4),
        xp.zeros((p.valence.shape[0], k * 4)),
    )


def accounting_state(state, p, *, xp=np):
    flow = p.mobile_k_selector * xp.sum(state.mobile_channel_transferred, axis=-2)[..., None, :]
    return prior_state(state)._replace(
        membrane_transferred=state.membrane_transferred + flow,
        membrane_dissipated_energy_pJ=state.membrane_dissipated_energy_pJ
        + xp.sum(state.mobile_channel_dissipated_energy_pJ, axis=-2),
    )


def domain_valid(state, p, active, *, xp=jnp):
    valid = prior.domain_valid(prior_state(state), prior_layout(p), active, xp=xp)
    valid &= surface.surface_domain_valid(
        mobile.surface_state(state), surface_layout(p, xp=xp), xp=xp
    )
    present = p.channel_state_reference[:, 0] > 0
    gate_support = present[:, None] & p.mobile_channel_dynamic[:, None, None]
    ion_support = present & (p.mobile_channel_permeability[:, None] > 0)
    for name, support in (
        ("channel_gate_transferred", gate_support),
        ("channel_gate_dissipated_energy_pJ", gate_support),
        ("channel_gate_bias_work_pJ", gate_support),
        ("mobile_channel_transferred", ion_support),
        ("mobile_channel_dissipated_energy_pJ", ion_support),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(support, True, value == 0))
    return valid


def readouts(state, control, p, *, xp=jnp):
    q = prior_layout(p)
    w = prior.readouts(prior_state(state), prior_control(control), q, xp=xp)
    v, r, dr = w.field, w.field.rates, w.derivative
    amount = p.channel_state_reference + state.channel_state_amount_increment
    present = p.channel_state_reference[:, 0] > 0
    area = xp.where(p.membrane_active, p.mobile_patch_area_um2, 1.0)
    permeability = (
        p.mobile_channel_permeability[:, None]
        * amount[:, 3]
        / area
        / p.channel_reference_density[:, None]
        * control.mobile_channel
    )
    ci = xp.where(p.active, calcium.cytosol_amount(state, q, xp=xp) / p.volume, 1.0)
    co = xp.where(
        p.outside_active,
        (p.extracellular_amount_reference + state.extracellular_amount_increment)
        / p.extracellular_volume,
        1.0,
    )
    a, b, potassium = p.membrane_cell, p.membrane_outside, p.mobile_potassium
    flux = selective_flux(
        ci[potassium, a],
        co[potassium, b],
        r.membrane_voltage_V,
        1.0,
        p.temperature,
        p.membrane_area,
        permeability,
        0.0,
        1.0,
        1.0,
        xp=xp,
    )
    flux = xp.where(p.membrane_active, flux, 0.0)
    heat = 1e-3 * flux * r.membrane_delta_mu_J_mol[potassium]
    transport = p.mobile_k_selector * xp.sum(flux, axis=0)
    cell = -scatter(transport, dr.amount_increment, (a,), xp=xp)
    outside = scatter(transport, dr.extracellular_amount_increment, (b,), xp=xp)
    chemical = xp.stack(
        [
            (p.free_ion_selector @ cell[:, i])[:, None] * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ]
    )
    qdot = CHARGE_PER_FMOL * xp.sum(p.valence * xp.concatenate((cell, outside), axis=1), axis=0)
    dphi = calcium.field._capacitor_solve(qdot, xp.zeros_like(qdot), ionic.field_layout(q), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[a] - dphi[p.active.size + b], 0.0)
    chemical_power = (
        1e-3 * R * p.temperature * (xp.sum(xp.log(ci) * cell) + xp.sum(xp.log(co) * outside))
    )
    electric_power = 1e12 * xp.sum(p.membrane_capacitance * r.membrane_voltage_V * dvm)
    g = gates.rates(
        amount, r.membrane_voltage_V[None], present, p.mobile_channel_dynamic, p.temperature, xp=xp
    )
    motion, mixing_heat = surface.surface_readouts(
        mobile.surface_state(state), surface_layout(p, xp=xp), xp=xp
    )
    k, _, n = amount.shape
    derivative = STATE_TYPE(
        *dr._replace(
            amount_increment=dr.amount_increment + cell,
            extracellular_amount_increment=dr.extracellular_amount_increment + outside,
            chemical_amount_increment=dr.chemical_amount_increment + chemical,
        ),
        motion.amount_rate_fmol_s.reshape((k, 4, n)) + g.amount_rate,
        motion.flux_fmol_s.reshape((k, 4, -1)),
        mixing_heat.reshape((k, 4, -1)),
        g.transfer,
        g.dissipation,
        g.bias_work,
        flux,
        heat,
    )
    valid = w.valid & g.valid & motion.valid & domain_valid(state, p, p.active, xp=xp)
    support = p.mobile_channel_active[:, None] & p.membrane_active
    level = control.mobile_channel
    valid &= xp.all(xp.isfinite(level) & (level >= 0) & (level <= 1)) & xp.all(
        xp.where(support, True, level == 0)
    )
    for value in (*derivative, chemical_power, electric_power, dvm):
        valid &= xp.all(xp.isfinite(value))
    rates = r._replace(
        cell_rate_fmol_s=r.cell_rate_fmol_s + cell,
        outside_rate_fmol_s=r.outside_rate_fmol_s + outside,
        membrane_flux_fmol_s=r.membrane_flux_fmol_s + transport,
        membrane_current_A=r.membrane_current_A
        + CHARGE_PER_FMOL * xp.sum(p.valence * transport, axis=0),
        membrane_dissipation_pJ_s=r.membrane_dissipation_pJ_s + xp.sum(heat, axis=0),
        valid=valid,
    )
    field = v._replace(
        rates=rates,
        membrane_voltage_rate_V_s=v.membrane_voltage_rate_V_s + dvm,
        chemical_energy_rate_pJ_s=v.chemical_energy_rate_pJ_s + chemical_power,
        capacitor_energy_rate_pJ_s=v.capacitor_energy_rate_pJ_s + electric_power,
        dissipation_pJ_s=v.dissipation_pJ_s + xp.sum(heat),
        energy_balance_pJ_s=v.energy_balance_pJ_s + chemical_power + electric_power + xp.sum(heat),
        converged=valid,
    )
    return Values(w, field, derivative, motion, g, permeability, valid)


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
    for i in range(len(controls.mobile_channel)):
        if not control_domain_valid(
            state, type(controls)(*(v[i] for v in controls)), p, p.active, xp=np
        ):
            raise ConfigError("Mobile repair initial state or actual controls outside domain")


def ion_loss_bound(spec):
    _, p = initial_values(spec)
    # A conserved population could accumulate entirely on any patch of its cell.
    totals = ordered_scatter(
        p.channel_state_reference.sum(axis=1),
        np.zeros((spec.execution.channel_population_capacity, p.active.size)),
        (p.membrane_cell,),
        xp=np,
    )
    max_p = np.sum(
        p.mobile_channel_permeability[:, None]
        * totals[:, p.membrane_cell]
        / np.where(p.membrane_active, p.mobile_patch_area_um2, 1.0)
        / p.channel_reference_density[:, None],
        axis=0,
    )
    coefficient = (
        p.mobile_k_selector * p.membrane_area * max_p / 1e-15 * (1 + F * 0.12 / (R * p.temperature))
    )
    inside = scatter(coefficient, p.amount_reference, (p.membrane_cell,), xp=np) / p.volume
    outside = (
        scatter(coefficient, p.extracellular_amount_reference, (p.membrane_outside,), xp=np)
        / p.extracellular_volume
    )
    return max(float(np.max(inside)), float(np.max(outside)))


def check_steps(spec, steps, controls):
    prior.check_steps(spec, steps, controls)
    h = np.max(steps, initial=0)
    bound = surface.surface_loss_bound(spec.model, spec.model.mobile_channels)
    if any(c.gate_mode == "dynamic" for c in spec.model.mobile_channels):
        bound += gates.MAX_GATE_EXIT_PER_S
    if h * bound > surface.MAX_SURFACE_LOSS_PER_STEP * (1 + 16 * np.finfo(float).eps):
        raise ConfigError("Mobile joint-gate diffusion/transitions require a smaller RK4 step")
    if h * (calcium.loss_bound(spec) + prior.injury_loss_bound(spec) + ion_loss_bound(spec)) > 0.25:
        raise ConfigError("Combined calcium/injury/mobile-channel loss requires a smaller step")


def channel_balances(state, p):
    b = surface.surface_balances(mobile.surface_state(state), surface_layout(p))
    k, _, n = state.channel_state_amount_increment.shape
    local = b["local"].reshape((k, 4, n)) - gates.incidence(state.channel_gate_transferred, xp=np)
    cell = ordered_scatter(
        state.channel_state_amount_increment.sum(axis=1),
        np.zeros((k, p.active.size)),
        (p.membrane_cell,),
        xp=np,
    )
    energy = b["energy"].reshape((k, 4)).sum(axis=1) + (
        state.channel_gate_dissipated_energy_pJ - state.channel_gate_bias_work_pJ
    ).sum(axis=(1, 2))
    return dict(local=local, cell=cell, energy=energy)


def check_values(state, spec, *, additional_transport=None):
    _, p = initial_values(spec)
    diagnostics = prior.check_values(
        accounting_state(state, p), accounting_spec(spec), additional_transport=additional_transport
    )
    rows = (
        [state]
        if state.damage.ndim == 1
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.damage))]
    )
    for row in rows:
        if not domain_valid(row, p, p.active, xp=np):
            raise NumericalError("Invalid mobile channel amount, history or padding")
        for name, value in channel_balances(row, p).items():
            error = float(np.max(np.abs(value), initial=0))
            limit = (
                surface.SURFACE_ENERGY_ATOL_PJ
                if name == "energy"
                else surface.SURFACE_MATERIAL_ATOL_FMOL
            )
            if not np.isfinite(value).all() or error > limit:
                raise NumericalError("Mobile channel balance failed: " + name)
            key = "max_mobile_channel_" + name + "_error"
            diagnostics[key] = max(diagnostics.get(key, 0.0), error)
    for name in EXTRA_AXES:
        if name.endswith("_dissipated_energy_pJ"):
            value = getattr(state, name)
            if np.min(value, initial=0) < -1e-12 or (
                state.damage.ndim > 1 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
            ):
                raise NumericalError("Mobile channel dissipation is negative or decreased: " + name)
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    from cells.core.schedule import control_values

    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    original = prior.observe_history(
        times, prior_state(history), prior_layout(p), requested, prior_spec(spec)
    )
    requested = np.asarray(requested)
    controls = control_values(spec, requested)
    rows = []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = type(controls)(*(v[j] for v in controls))
        w = readouts(state, control, p, xp=np)
        if not w.valid:
            raise NumericalError("Mobile repair observation outside domain")
        row = {k: v[j] for k, v in vars(original).items()}
        row.update({k: getattr(state, k) for k in EXTRA_AXES})
        for name in ("membrane_flux_fmol_s", "membrane_current_A"):
            if name in row:
                row[name] = getattr(w.field.rates, name)
        row["energy_balance_pJ_s"] = np.atleast_1d(w.field.energy_balance_pJ_s)
        amount = p.channel_state_reference + state.channel_state_amount_increment
        total = amount.sum(axis=1)
        safe = np.where(total > 0, total, 1.0)
        opened = amount[:, 3] / safe
        correlation = (
            opened - (amount[:, 2] + amount[:, 3]) * (amount[:, 1] + amount[:, 3]) / safe**2
        )
        values = (
            amount,
            w.motion.density_fmol_um2.reshape(amount.shape),
            w.motion.flux_fmol_s.reshape(state.channel_state_transferred.shape),
            w.gating.transfer,
            w.gating.targets,
            w.gating.tau_s,
            opened,
            correlation,
            control.mobile_channel,
            w.derivative.mobile_channel_transferred,
            w.permeability,
            channel_balances(state, p)["energy"],
        )
        row.update(zip(READOUTS, values, strict=True))
        rows.append(tuple(row[k] for k in OBSERVATION_FIELDS))
    if rows:
        return Observations(*(np.stack(v) for v in zip(*rows, strict=True)))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    from cells.core.schedule import control_values

    c = control_values(spec, [time])
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    f = field_values(
        STATE_TYPE(*(np.asarray(v) for v in state)), type(c)(*(v[0] for v in c)), p, xp=np
    )
    if not f.converged:
        raise NumericalError("Mobile repair ensemble field invalid")
    return f.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    return prior.summarize(accounting_state(history, p), diagnostics, prior_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_AXES),
        mobile_channels=[c.id for c in spec.model.mobile_channels],
        gating_energy_scope=(
            "phenomenological ideal-mixture/rate-bias accounting; no resolved gating charge"
        ),
    )
