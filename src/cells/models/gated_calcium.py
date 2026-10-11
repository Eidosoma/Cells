"""Cav1.2 gates with finite calcium flux, charge and separate transfer/energy ledgers."""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.gated_calcium_spec import MODEL_ID, base_spec
from cells.core.schedule import PlasmaControl, control_values
from cells.core.specs import ConfigError
from cells.models import plasma_calcium as base
from cells.models import spatial_calcium as spatial
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes import calcium_gates as gates
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    F,
    R,
    electrochemical_potential,
    ghk_leak,
)

EXTRA_FIELDS = (
    "calcium_gate",
    "calcium_channel_transferred",
    "calcium_channel_dissipated_energy_pJ",
)
State = NamedTuple("State", [(k, object) for k in (*base.State._fields, *EXTRA_FIELDS)])
Layout = NamedTuple(
    "Layout", [(k, object) for k in (*base.Layout._fields, "cav_permeability", "cav_abundance")]
)
STATE_TYPE, LAYOUT_TYPE = State, Layout
STATE_AXES = base.STATE_AXES | {
    "calcium_gate": ["gate", "membrane_slot"],
    "calcium_channel_transferred": ["membrane_slot"],
    "calcium_channel_dissipated_energy_pJ": ["membrane_slot"],
}
OBSERVER_ID = "spatial_calcium_cav1p2_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_hermite_gated_calcium_enclosed@1"
STAGE_DOMAIN_ID = "positive_spatial_calcium_cav_unit_gates@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
parameters, cell_voltage = base.parameters, base.cell_voltage
cytosol_amount, store_state, store_layout, er = (
    base.cytosol_amount,
    base.store_state,
    base.store_layout,
    base.er,
)


def batch_signature(model):
    return base.batch_signature(model), len(model.calcium_channels), gates.LAW_ID


def working_size(spec):
    return base.working_size(base_spec(spec)) + 64 * 16 * spec.execution.membrane_capacity


def initial_values(spec):
    state, p = base.initial_values(base_spec(spec))
    nm = spec.execution.membrane_capacity
    gate, permeability, abundance = np.zeros((2, nm)), np.zeros(nm), np.zeros(nm)
    for i, c in enumerate(spec.model.calcium_channels):
        gate[:, i] = c.initial_gate
        permeability[i], abundance[i] = c.max_permeability_m_per_s, c.abundance
    return State(*state, gate, np.zeros(nm), np.zeros(nm)), Layout(*p, permeability, abundance)


def readouts(state, p, availability=1.0, *, xp=jnp):
    ci, co, v, t = spatial.finite.membrane_inputs(
        state, spatial.ionic_layout(state, p, xp=xp), xp=xp
    )
    targets, tau = gates.kinetics(v, xp=xp)
    opened = gates.open_probability(state.calcium_gate)
    permeability = p.cav_permeability * p.cav_abundance * availability * opened
    flux = ghk_leak(
        ci[..., p.plasma_ca, :], co[..., p.plasma_ca, :], v, 2, t, p.area, permeability, 1.0, xp=xp
    )
    mu = electrochemical_potential(ci[..., p.plasma_ca, :], co[..., p.plasma_ca, :], v, 2, t, xp=xp)
    return tuple(
        xp.where(p.membrane_active, value, 0.0)
        for value in ((targets - state.calcium_gate) / tau, flux, -1e-3 * flux * mu)
    )


def membrane_exchange(transferred, p):
    return transferred[..., None, :] * p.plasma_ca_selector


def rhs(state, control, p, active, *, xp=jnp, ionic=spatial.spatial):
    rates = base.rhs(state, PlasmaControl(*control[:9]), p, active, xp=xp, ionic=ionic)
    gate, transferred, dissipated = readouts(state, p, control.calcium_channel, xp=xp)
    flux = membrane_exchange(transferred, p)
    scatter = spatial.finite.gated.scatter
    inside = scatter(flux, rates.amount_increment, (p.owners,), xp=xp)
    outside = scatter(-flux, rates.extracellular_amount_increment, (p.outside_owners,), xp=xp)
    chemical = xp.stack(
        [
            xp.einsum("si,...i->...s", p.free_ion_selector, inside[..., :, i])[..., :, None]
            * p.cytosol_selector[i]
            for i in range(p.er_initial_amount.shape[0])
        ],
        axis=-3,
    )
    rates = rates._replace(
        amount_increment=rates.amount_increment + inside,
        extracellular_amount_increment=rates.extracellular_amount_increment + outside,
        chemical_amount_increment=rates.chemical_amount_increment + chemical,
    )
    return State(*rates, gate, transferred, dissipated)


def domain_valid(state, p, active, *, xp=jnp, ionic=spatial.spatial):
    valid = base.domain_valid(state, p, active, xp=xp, ionic=ionic)
    v = spatial.finite.membrane_voltage(state.amount_increment, p, xp=xp)
    valid &= xp.all(
        xp.where(
            p.membrane_active,
            (v >= gates.VOLTAGE_DOMAIN_V[0]) & (v <= gates.VOLTAGE_DOMAIN_V[1]),
            True,
        )
    )
    valid &= xp.all((state.calcium_gate >= 0) & (state.calcium_gate <= 1))
    for name, enabled in (
        ("calcium_gate", p.membrane_active),
        ("calcium_channel_transferred", (p.cav_permeability * p.cav_abundance) > 0),
        ("calcium_channel_dissipated_energy_pJ", (p.cav_permeability * p.cav_abundance) > 0),
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(enabled, True, value == 0))
    return valid & xp.all(state.calcium_channel_dissipated_energy_pJ >= 0)


def channel_loss_bound(spec):
    _, p = initial_values(spec)
    # B(+-x) <= 1 + |x| bounds both directions, gates and availability <= 1.
    x = 2 * F * max(map(abs, gates.VOLTAGE_DOMAIN_V)) / (R * p.temperature[p.outside_owners])
    coefficient = p.area * p.cav_permeability * p.cav_abundance / 1e-15 * (1 + x)
    inside = np.zeros_like(p.volume)
    outside = np.zeros_like(p.extracellular_volume)
    np.add.at(inside, p.owners, coefficient / p.volume[p.owners])
    np.add.at(outside, p.outside_owners, coefficient / p.extracellular_volume[p.outside_owners])
    return max(float(np.max(inside)), float(np.max(outside)))


def check_definition(spec):
    state, p = initial_values(spec)
    if not domain_valid(state, p, p.active, xp=np, ionic=spatial.ionic_model(spec)):
        raise ConfigError("Initial gated calcium state outside voltage/gate/inventory domain")


def check_steps(spec, steps, controls):
    original = base_spec(spec)
    base.check_steps(original, steps, control_values(original, [0.0]))
    h = np.max(steps, initial=0)
    loss = (
        spatial.loss_bound(base.base_spec(original))
        + base.plasma_loss_bound(original)
        + channel_loss_bound(spec)
    )
    if h * loss > 0.25 or h / gates.MIN_TAU_S > 0.25:
        raise ConfigError("Step times calcium transport/gate loss bound exceeds 0.25")


def energy_balance(state, p):
    return base.energy_balance(state, p) + np.sum(
        state.calcium_channel_dissipated_energy_pJ, axis=-1
    )


def check_values(state, spec):
    _, p = initial_values(spec)
    if not domain_valid(state, p, p.active, xp=np, ionic=spatial.ionic_model(spec)):
        raise NumericalError("Gated calcium state, voltage, gates or ledgers outside domain")
    d = state.calcium_channel_dissipated_energy_pJ
    if d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -spatial.chemistry.ROUND_ATOL:
        raise NumericalError("Calcium channel dissipation decreased")
    return base.check_values(
        state,
        base_spec(spec),
        additional_exchange=membrane_exchange(state.calcium_channel_transferred, p),
        additional_energy=np.sum(d, axis=-1),
    )


def check_interpolants(times, history, left, right, p):
    base.check_interpolants(times, history, left, right, p)
    if len(times) < 2:
        return
    lo, hi = hermite_bounds(
        times,
        spatial.finite.membrane_voltage(history.amount_increment, p, xp=np),
        *(
            CHARGE_PER_FMOL
            / p.capacitance
            * np.sum(p.valence * slope.amount_increment[..., :, p.owners], axis=-2)
            for slope in (left, right)
        ),
    )
    if np.any(lo[..., p.membrane_active] < gates.VOLTAGE_DOMAIN_V[0]) or np.any(
        hi[..., p.membrane_active] > gates.VOLTAGE_DOMAIN_V[1]
    ):
        raise NumericalError("Calcium channel cubic voltage outside domain")
    lo, hi = hermite_bounds(times, history.calcium_gate, left.calcium_gate, right.calcium_gate)
    if np.any(lo < 0) or np.any(hi > 1):
        raise NumericalError("Calcium channel cubic gate outside [0,1]")
    d = history.calcium_channel_dissipated_energy_pJ
    lo, hi = hermite_bounds(
        times,
        d,
        left.calcium_channel_dissipated_energy_pJ,
        right.calcium_channel_dissipated_energy_pJ,
    )
    if np.any(lo < d[:-1] - spatial.chemistry.ROUND_ATOL) or np.any(
        hi > d[1:] + spatial.chemistry.ROUND_ATOL
    ):
        raise NumericalError("Calcium channel cubic dissipation left its ledger interval")


Observations = make_dataclass(
    "Observations",
    [(k, np.ndarray) for k in ("times", *State._fields, *spatial.DERIVED_FIELDS)],
    frozen=True,
)


def observe_history(times, history, layout, requested, spec):
    p = Layout(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=np.float64)
    controls = control_values(spec, times[:-1])
    left, right = (
        rhs(State(*(v[part] for v in history)), controls, p, p.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, left, right, p)
    sampled = State(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, left, right, strict=True)
        )
    )
    check_values(sampled, spec)
    return Observations(
        requested,
        *sampled,
        cytosol_amount(sampled, p, xp=np),
        p.extracellular_amount_reference + sampled.extracellular_amount_increment,
        cell_voltage(sampled.amount_increment, p, xp=np),
        np.stack(
            [
                er.voltage(store_state(sampled, i), store_layout(p, i), xp=np)
                for i in range(p.er_initial_amount.shape[0])
            ],
            axis=-1,
        ),
        spatial.spatial.field_values(sampled, p, xp=np).potential_V,
    )


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, base_spec(spec)) | {
        "model": MODEL_ID,
        "state_axes": STATE_AXES,
        "calcium_channel_law": gates.LAW_ID,
        "calcium_channel_ids": [c.id for c in spec.model.calcium_channels],
        "final_calcium_channel_transferred_fmol": history.calcium_channel_transferred[-1].tolist(),
        "claim_scope": (
            "Pinned Cav1.2 gate equations with synthetic finite calcium transport; "
            "no native full trajectory or biological calibration"
        ),
    }
