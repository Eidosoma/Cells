"""Finite ER/cytosol inventories, buffered chemistry and capacitive transport."""

from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import compartment_reactions as chemistry
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes import er_calcium as processes
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R, bernoulli, ghk_leak

OBSERVER_ID = "finite_er_chemistry_readouts@1"
OBSERVATION_SAMPLING = "read_only_control_local_hermite_er_domain_checked@1"
STAGE_DOMAIN_ID = "positive_finite_er_inventory_voltage_affinity@1"
BATCH_CAPACITIES = chemistry.BATCH_CAPACITIES
batch_signature = chemistry.batch_signature
ENERGY_ATOL_PJ = chemistry.ENERGY_ATOL_PJ
MAX_VOLTAGE = 0.15
MAX_STEP = 0.00005


class State(NamedTuple):
    amount_increment: object
    reaction_extent: object
    dissipated_energy_pJ: object
    passive_transferred: object
    pump_transferred: object
    release_transferred: object
    transport_dissipated_energy_pJ: object


# Flat numeric leaves retain the ordinary complete-checkpoint/batch codecs.
EXTRA_LAYOUT = (
    "cytosol",
    "er",
    "calcium",
    "incidence",
    "calcium_selector",
    "area",
    "capacitance",
    "initial_voltage",
    "permeability",
    "pump_present",
    "pump_capacity",
    "pump_km_ca",
    "pump_km_atp",
    "pump_atp",
    "pump_adp",
    "pump_pi",
    "pump_dg0",
    "release_permeability",
    "activation_mM",
    "activation_n",
    "inhibition_mM",
    "inhibition_n",
    "fixed_charge_C",
)
Layout = NamedTuple(
    "Layout", [(name, object) for name in (*chemistry.Layout._fields, *EXTRA_LAYOUT)]
)
STATE_TYPE, LAYOUT_TYPE = State, Layout
STATE_AXES = chemistry.STATE_AXES | {
    "passive_transferred": ["species"],
    "pump_transferred": ["membrane"],
    "release_transferred": ["membrane"],
    "transport_dissipated_energy_pJ": ["passive_pump_release"],
}


def working_size(spec):
    return chemistry.working_size(spec) + 64 * (4 * len(spec.model.species) + 32)


def initial_values(spec):
    state, layout = chemistry.initial_values(spec)
    m = spec.model.membrane
    ids = [c.id for c in spec.model.compartments]
    cy, er = ids.index(m.cytosol), ids.index(m.er)
    ca = [s.id for s in spec.model.species].index(m.calcium_species)
    incidence = np.zeros(spec.execution.capacity)
    incidence[cy], incidence[er] = -1, 1
    selector = np.zeros(len(spec.model.species))
    selector[ca] = 1
    pump = m.pump
    pump_values = (
        (0, 1, 1, 1, 1, 1, 0)
        if pump is None
        else (
            pump.capacity_fmol_per_s,
            pump.km_ca_mM,
            pump.km_atp_mM,
            pump.atp_mM,
            pump.adp_mM,
            pump.pi_mM,
            pump.delta_g0_J_per_mol,
        )
    )
    release = m.release
    release_values = (
        (0, 1, 1, 1, 1)
        if release is None
        else (
            release.permeability_m_per_s,
            release.activation_mM,
            release.activation_n,
            release.inhibition_mM,
            release.inhibition_n,
        )
    )
    cap = m.area_m2 * m.specific_capacitance_F_per_m2
    fixed_charge = cap * m.initial_voltage_V * incidence - CHARGE_PER_FMOL * (
        layout.valence @ (layout.initial_amount * layout.active)
    )
    return State(*state, np.zeros(len(selector)), np.zeros(1), np.zeros(1), np.zeros(3)), Layout(
        *layout,
        np.int64(cy),
        np.int64(er),
        np.int64(ca),
        incidence,
        selector,
        np.float64(m.area_m2),
        np.float64(cap),
        np.float64(m.initial_voltage_V),
        np.asarray(m.permeability_m_per_s),
        np.bool_(pump is not None),
        *(np.float64(v) for v in (*pump_values, *release_values)),
        fixed_charge,
    )


def parameters(spec, layout):
    return layout


def pump_parameters(p):
    return processes.PumpParameters(
        p.pump_capacity, p.pump_km_ca, p.pump_km_atp, p.pump_atp, p.pump_adp, p.pump_pi, p.pump_dg0
    )


def voltage(state, p, *, xp=jnp):
    return p.initial_voltage + CHARGE_PER_FMOL / p.capacitance * xp.sum(
        p.valence * state.amount_increment[..., :, p.er], axis=-1
    )


def readouts(state, control, p, *, xp=jnp):
    amount = p.initial_amount + state.amount_increment
    ci, co = amount[..., :, p.er] / p.volume[p.er], amount[..., :, p.cytosol] / p.volume[p.cytosol]
    v = voltage(state, p, xp=xp)
    mu = R * p.temperature * (xp.log(ci) - xp.log(co)) + p.valence * F * v[..., None]
    leak = ghk_leak(
        ci,
        co,
        v[..., None],
        p.valence,
        p.temperature,
        p.area,
        p.permeability,
        control.passive,
        xp=xp,
    )
    # No absent-pump route reads chemical affinity from real concentrations.
    pump, affinity, drive = processes.pump_rates(
        xp.where(p.pump_present, co[..., p.calcium], 1.0),
        xp.where(p.pump_present, ci[..., p.calcium], 1.0),
        xp.where(p.pump_present, v, 0.0),
        p.temperature,
        pump_parameters(p),
        control.pump,
        xp=xp,
    )
    opening = processes.release_open(
        co[..., p.calcium], p.activation_mM, p.activation_n, p.inhibition_mM, p.inhibition_n, xp=xp
    )
    release = ghk_leak(
        ci[..., p.calcium],
        co[..., p.calcium],
        v,
        2,
        p.temperature,
        p.area,
        p.release_permeability,
        control.release * opening,
        xp=xp,
    )
    return v, mu, leak, pump, affinity, drive, release, opening


def rhs(state, control, p, active, *, xp=jnp):
    local = chemistry.rhs(state, control.reactions, p, active, xp=xp)
    _, mu, leak, pump, affinity, _, release, _ = readouts(state, control, p, xp=xp)
    transfer = leak + (pump + release)[..., None] * p.calcium_selector
    return State(
        local.amount_increment + transfer[..., :, None] * p.incidence,
        local.reaction_extent,
        local.dissipated_energy_pJ,
        leak,
        pump[..., None],
        release[..., None],
        -1e-3
        * xp.stack(
            (xp.sum(leak * mu, axis=-1), pump * affinity, release * mu[..., p.calcium]), axis=-1
        ),
    )


def domain_valid(state, p, active, *, xp=jnp):
    amount = p.initial_amount + state.amount_increment
    finite = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state]))
    v = voltage(state, p, xp=xp)
    affinity = (
        processes.chemical_drive(pump_parameters(p), p.temperature, xp=xp)
        + R
        * p.temperature
        * (
            xp.log(amount[..., p.calcium, p.er] / p.volume[p.er])
            - xp.log(amount[..., p.calcium, p.cytosol] / p.volume[p.cytosol])
        )
        + 2 * F * v
    ) / (R * p.temperature)
    return (
        finite
        & xp.all(amount > 0)
        & xp.all(xp.abs(v) <= MAX_VOLTAGE)
        & xp.all(xp.where(p.pump_present, xp.abs(affinity) <= processes.MAX_AFFINITY_RT, True))
        & xp.all(xp.where(active, 0.0, state.amount_increment) == 0)
        & xp.all(xp.where(p.reaction_active, 0.0, state.reaction_extent) == 0)
        & xp.all(xp.where(p.reaction_active, 0.0, state.dissipated_energy_pJ) == 0)
        & xp.all(state.dissipated_energy_pJ >= 0)
        & xp.all(state.transport_dissipated_energy_pJ >= 0)
        & xp.all(xp.where(p.permeability > 0, 0.0, state.passive_transferred) == 0)
        & xp.all(xp.where(p.pump_capacity > 0, 0.0, state.pump_transferred) == 0)
        & xp.all(xp.where(p.release_permeability > 0, 0.0, state.release_transferred) == 0)
    )


def loss_bound(spec, *, conserved_totals=None):
    _, p = initial_values(spec)
    totals = (
        np.sum(p.moieties @ (p.initial_amount * p.active), axis=-1)
        if conserved_totals is None
        else np.asarray(conserved_totals)
    )
    upper = np.array(
        [
            np.min(totals[p.moieties[:, i] > 0] / p.moieties[p.moieties[:, i] > 0, i])
            for i in range(len(p.valence))
        ]
    )
    activity = upper[:, None] / (p.volume * p.standard_concentration)
    loss = np.zeros_like(p.initial_amount)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for j in range(len(spec.model.reactions)):
            owner = p.owners[j]
            for side, rate in (
                (p.reactants[:, j], p.forward_rate[j]),
                (p.products[:, j], p.forward_rate[j] * np.exp(p.delta_mu_RT[j])),
            ):
                for i in np.flatnonzero(side):
                    powers = side.copy()
                    powers[i] -= 1
                    loss[i, owner] += side[i] * rate * np.prod(activity[:, owner] ** powers)
        rates = p.area / 1e-15 * (p.permeability + p.calcium_selector * p.release_permeability)
        rates *= bernoulli(-np.abs(p.valence) * F * MAX_VOLTAGE / (R * p.temperature), xp=np)
        for owner in (p.cytosol, p.er):
            loss[:, owner] += rates / p.volume[owner]
        saturation = p.pump_atp / (p.pump_km_atp + p.pump_atp)
        loss[p.calcium, p.cytosol] += (
            p.pump_capacity * saturation / (p.pump_km_ca * p.volume[p.cytosol])
        )
        loss[p.calcium, p.er] += (
            p.pump_capacity
            * saturation
            * np.exp(
                (
                    processes.chemical_drive(pump_parameters(p), p.temperature, xp=np)
                    + 2 * F * MAX_VOLTAGE
                )
                / (R * p.temperature)
            )
            / (p.pump_km_ca * p.volume[p.er])
        )
    if not np.isfinite(loss).all():
        raise ConfigError("Nonfinite ER conserved-pool loss bound")
    return float(np.max(loss))


def check_definition(spec):
    state, p = initial_values(spec)
    if not domain_valid(state, p, p.active, xp=np):
        raise ConfigError("Initial ER physical domain is invalid")
    loss_bound(spec)


def check_steps(spec, steps, controls):
    largest = np.max(steps, initial=0)
    if (
        largest > MAX_STEP + 16 * np.finfo(float).eps
        or largest * loss_bound(spec) > 0.25 + 16 * np.finfo(float).eps
    ):
        raise ConfigError("ER requires steps <= 50 us and actual step * loss bound <= 0.25")


def energy_balance(state, p):
    v = voltage(state, p, xp=np)
    dv = v - p.initial_voltage
    chemical = np.sum(chemistry.free_energy_change(state, p), axis=-1)
    electrical = 0.5e12 * p.capacitance * dv * (2 * p.initial_voltage + dv)
    work = (
        -1e-3
        * processes.chemical_drive(pump_parameters(p), p.temperature, xp=np)
        * state.pump_transferred[..., 0]
    )
    return (
        chemical
        + electrical
        + np.sum(state.dissipated_energy_pJ, axis=-1)
        + np.sum(state.transport_dissipated_energy_pJ, axis=-1)
        - work
    )


def check_values(state, spec):
    _, p = initial_values(spec)
    with np.errstate(divide="ignore", invalid="ignore"):
        valid = domain_valid(state, p, p.active, xp=np)
    if not valid:
        raise NumericalError("Invalid ER positive-inventory, voltage, affinity or ledger domain")
    transport = (
        state.passive_transferred
        + (state.pump_transferred + state.release_transferred) * p.calcium_selector
    )
    residue = (
        state.amount_increment
        - chemistry.reaction_amount(state.reaction_extent, p)
        - transport[..., :, None] * p.incidence
    )
    local = state.amount_increment - transport[..., :, None] * p.incidence
    moiety = np.einsum("qs,...sc->...qc", p.moieties, local)
    charge = np.einsum("s,...sc->...c", p.valence, local)
    global_moiety = np.einsum("qs,...s->...q", p.moieties, np.sum(state.amount_increment, axis=-1))
    for name, value, inventory in (
        ("reaction/transport", residue, p.initial_amount),
        ("local moiety", moiety, p.moieties @ p.initial_amount),
        ("local charge", charge, np.abs(p.valence) @ p.initial_amount),
        (
            "global moiety",
            global_moiety,
            np.sum(p.moieties @ (p.initial_amount * p.active), axis=-1),
        ),
    ):
        if not np.isfinite(value).all() or np.any(
            np.abs(value) > chemistry.ROUND_ATOL * np.maximum(1, inventory)
        ):
            raise NumericalError("ER " + name + " balance failed")
    energy = energy_balance(state, p)
    if not np.isfinite(energy).all() or np.max(np.abs(energy), initial=0) > ENERGY_ATOL_PJ:
        raise NumericalError("ER chemical/capacitor/work/dissipation energy balance failed")
    for values in (state.dissipated_energy_pJ, state.transport_dissipated_energy_pJ):
        if values.ndim == 2 and np.any(np.diff(values, axis=0) < -chemistry.ROUND_ATOL):
            raise NumericalError("ER dissipation ledger decreased")
    return {
        "max_balance_error_fmol": float(np.max(np.abs(moiety), initial=0)),
        "max_process_accounting_error_fmol": float(np.max(np.abs(residue), initial=0)),
        "max_global_moiety_error_fmol": float(np.max(np.abs(global_moiety), initial=0)),
        "max_charge_balance_error_equivalent_fmol": float(np.max(np.abs(charge), initial=0)),
        "max_energy_balance_error_pJ": float(np.max(np.abs(energy), initial=0)),
    }


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount_increment: np.ndarray
    reaction_extent: np.ndarray
    dissipated_energy_pJ: np.ndarray
    passive_transferred: np.ndarray
    pump_transferred: np.ndarray
    release_transferred: np.ndarray
    transport_dissipated_energy_pJ: np.ndarray
    amount: np.ndarray
    concentration_mM: np.ndarray
    er_voltage_V: np.ndarray
    passive_rate_fmol_per_s: np.ndarray
    pump_rate_fmol_per_s: np.ndarray
    release_rate_fmol_per_s: np.ndarray
    release_open_fraction: np.ndarray
    pump_work_pJ: np.ndarray


def check_interpolants(times, history, left, right, p):
    if len(times) > 1:
        lo, hi = hermite_bounds(
            times, history.amount_increment, left.amount_increment, right.amount_increment
        )
        lo, hi = lo + p.initial_amount, hi + p.initial_amount
        if np.any(lo <= 0):
            raise NumericalError("ER observation cubic leaves positive amounts")

        def slope(s):
            return (
                CHARGE_PER_FMOL
                / p.capacitance
                * np.sum(p.valence * s.amount_increment[..., :, p.er], axis=-1)
            )

        vlo, vhi = hermite_bounds(times, voltage(history, p, xp=np), slope(left), slope(right))
        if np.any(vlo < -MAX_VOLTAGE) or np.any(vhi > MAX_VOLTAGE):
            raise NumericalError("ER observation cubic leaves voltage domain")
        if p.pump_present:
            drive = processes.chemical_drive(pump_parameters(p), p.temperature, xp=np) / (
                R * p.temperature
            )
            low = (
                drive
                + np.log(lo[..., p.calcium, p.er] / p.volume[p.er])
                - np.log(hi[..., p.calcium, p.cytosol] / p.volume[p.cytosol])
                + 2 * F * vlo / (R * p.temperature)
            )
            high = (
                drive
                + np.log(hi[..., p.calcium, p.er] / p.volume[p.er])
                - np.log(lo[..., p.calcium, p.cytosol] / p.volume[p.cytosol])
                + 2 * F * vhi / (R * p.temperature)
            )
            if np.any(low < -processes.MAX_AFFINITY_RT) or np.any(high > processes.MAX_AFFINITY_RT):
                raise NumericalError("ER observation cubic cannot certify pump affinity domain")
        for field in ("dissipated_energy_pJ", "transport_dissipated_energy_pJ"):
            values = getattr(history, field)
            low, high = hermite_bounds(times, values, getattr(left, field), getattr(right, field))
            if np.any(low < values[:-1] - chemistry.ROUND_ATOL) or np.any(
                high > values[1:] + chemistry.ROUND_ATOL
            ):
                raise NumericalError("ER observation dissipation leaves its interval ledger")


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
    v, _, leak, pump, _, drive, release, opening = readouts(
        sampled, control_values(spec, requested), p, xp=np
    )
    amount = np.where(p.active, p.initial_amount + sampled.amount_increment, 0.0)
    return Observations(
        requested,
        *sampled,
        amount,
        amount / p.volume,
        v,
        leak,
        pump,
        release,
        opening,
        -1e-3 * drive * sampled.pump_transferred[..., 0],
    )


def summarize(history, diagnostics, spec):
    _, p = initial_values(spec)
    result = chemistry.summarize(history, diagnostics, spec)
    result.update(
        claim_scope=(
            "Synthetic finite ER/cytosol with BETSE source-law pump and calcium-only release; "
            "maintained ATP/ADP/Pi; no plasma-membrane/assembly coupling or biological calibration"
        ),
        state_axes=STATE_AXES,
        er_voltage_V=float(voltage(history, p, xp=np)[-1]),
        pump_transferred_fmol=float(history.pump_transferred[-1, 0]),
        release_transferred_fmol=float(history.release_transferred[-1, 0]),
        pump_work_pJ=float(
            -1e-3
            * processes.chemical_drive(pump_parameters(p), p.temperature, xp=np)
            * history.pump_transferred[-1, 0]
        ),
        transport_dissipated_energy_pJ=history.transport_dissipated_energy_pJ[-1].tolist(),
        fixed_background_charge_C=p.fixed_charge_C.tolist(),
    )
    return result
