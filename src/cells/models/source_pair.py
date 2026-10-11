"""Nominal source-compatible regulation/membrane/contact composition.

No additional gate or cache memory, no physical RNA charge mapping, and no
legacy integrator timing. The shared checked engine owns all time advancement.
"""

from dataclasses import dataclass
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import EMTState, SourcePairLayout, SourcePairState
from cells.coupling.passive import scatter_exchange
from cells.models import emt_mirna
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes import source_electrochemistry as laws

STATE_TYPE, LAYOUT_TYPE = SourcePairState, SourcePairLayout
OBSERVER_ID = "bitsey_nominal_pair_pure_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite_extrema_checked@1"
STAGE_DOMAIN_ID = (
    "source_ions_1e-6_to_1000_regulation_0_to_1000_abs_voltage_le_0.2_finite_padding@1"
)
TRACE_COLUMNS = OBSERVATION_COLUMNS = 180
TRACE_MEMBRANE_COLUMNS = OBSERVATION_MEMBRANE_COLUMNS = 100
TRACE_EDGE_COLUMNS = OBSERVATION_EDGE_COLUMNS = 100
MAX_STEP = 0.01
AREA = 4 * np.pi * laws.RADIUS**2
VOLUME = 4 * np.pi * laws.RADIUS**3 / 3
VOLTAGE_FACTOR = laws.F * VOLUME / (AREA * laws.CM)
SURFACE_FACTOR = AREA / VOLUME
NU = np.array([-3.0, 2.0, 0.0])[:, None]
STATE_AXES = {
    "ions": ["ion:Na,K,Cl", "cell_slot"],
    "regulation": ["coordinate:u,m,z", "cell_slot"],
    "leak_history": ["ion:Na,K,Cl", "membrane_slot"],
    "pump_history": ["membrane_slot"],
    "ion_transferred": ["ion:Na,K,Cl", "edge_slot"],
    "local_regulation": ["coordinate:u,m,z", "cell_slot"],
    "mirna_transferred": ["edge_slot"],
}


def check_definition(model):
    ions, context = np.asarray(model.initial_ions), np.asarray(model.context)
    voltage = VOLTAGE_FACTOR * (ions[0] + ions[1] - ions[2] - context[0])
    if np.max(abs(voltage)) > 0.2 or abs(voltage[0] - voltage[1]) > 0.2:
        raise ConfigError("Initial source membrane/junction voltage must lie within 0.2 V")
    diffusion = np.asarray([m.diffusion for m in model.membranes]).T
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        leak, cycle = laws.membrane_flux(
            ions,
            voltage,
            np.asarray(model.bath_ions)[:, None],
            diffusion,
            np.ones((3, 2)),
            np.ones(2),
            xp=np,
        )
        coefficients = (
            np.r_[diffusion.ravel(), model.contact.ion_diffusion, model.contact.mirna_diffusion]
            / laws.CONTACT_LENGTH
            * SURFACE_FACTOR
        )
        finite = np.isfinite(
            np.r_[leak.ravel() * SURFACE_FACTOR, cycle * SURFACE_FACTOR, coefficients]
        ).all()
    if not finite:
        raise ConfigError("Source coefficients/rates exceed finite float64")


def initial_values(spec):
    m, x = spec.model, spec.execution
    cells, membranes, edges = x.capacity, x.membrane_capacity, x.edge_capacity
    ions, regulation, context = (np.zeros((3, cells)) for _ in range(3))
    ions[:, :2], regulation[:, :2], context[:, :2] = m.initial_ions, m.initial_regulation, m.context
    ids, membrane_ids, contact_ids = (
        np.full(n, -1, dtype=np.int64) for n in (cells, membranes, edges)
    )
    ids[:2], membrane_ids[:2], contact_ids[0] = (
        m.cell_ids,
        [a.membrane_id for a in m.membranes],
        m.contact.contact_id,
    )
    owners = np.zeros(membranes, dtype=np.int64)
    owners[:2] = [m.cell_ids.index(a.owner_cell_id) for a in m.membranes]
    diffusion = np.zeros((3, membranes))
    diffusion[:, :2] = np.asarray([a.diffusion for a in m.membranes]).T
    volume, area = np.ones(cells), np.zeros(membranes)
    volume[:2], area[:2] = VOLUME, AREA
    senders, receivers = (np.zeros(edges, dtype=np.int64) for _ in range(2))
    senders[0], receivers[0] = (
        m.cell_ids.index(getattr(m.contact, name)) for name in ("from_cell_id", "to_cell_id")
    )
    ion_diffusion, mirna_diffusion = np.zeros((3, edges)), np.zeros(edges)
    ion_diffusion[:, 0], mirna_diffusion[0] = m.contact.ion_diffusion, m.contact.mirna_diffusion
    gate_parameters, enabled = np.zeros((6, edges)), np.zeros(edges, dtype=bool)
    if m.contact.gate_profile is not None:
        gate_parameters[:, 0] = laws.GATES[m.contact.gate_profile]
        if m.contact.swap_hemichannels:
            gate_parameters[:4, 0] = gate_parameters[[2, 3, 0, 1], 0]
        enabled[0] = True
    state = SourcePairState(
        ions,
        regulation,
        np.zeros((3, membranes)),
        np.zeros(membranes),
        np.zeros((3, edges)),
        np.zeros((3, cells)),
        np.zeros(edges),
    )
    layout = SourcePairLayout(
        np.arange(cells) < 2,
        ids,
        ions.copy(),
        regulation.copy(),
        context,
        volume,
        membrane_ids,
        np.arange(membranes) < 2,
        owners,
        np.zeros(membranes, dtype=np.int64),
        area,
        diffusion,
        np.array([m.bath_id], dtype=np.int64),
        np.asarray(m.bath_ions)[:, None],
        contact_ids,
        np.arange(edges) == 0,
        senders,
        receivers,
        ion_diffusion,
        mirna_diffusion,
        enabled,
        gate_parameters,
    )
    return state, layout


def parameters(spec, layout):
    return layout


def cell_voltage(ions, layout, *, xp=jnp):
    value = VOLTAGE_FACTOR * (
        ions[..., 0, :] + ions[..., 1, :] - ions[..., 2, :] - layout.context[0]
    )
    return xp.where(layout.active, value, 0.0)


class Rates(NamedTuple):
    voltage: object
    junction_voltage: object
    leak: object
    cycles: object
    junction: object
    scales: object
    local: object


def rates(state, control, layout, *, xp=jnp):
    voltage = cell_voltage(state.ions, layout, xp=xp)
    ions = xp.where(layout.membrane_active, state.ions[..., :, layout.owners], 1.0)
    leak, cycles = laws.membrane_flux(
        ions,
        voltage[..., layout.owners],
        layout.bath_ions[:, layout.membrane_baths],
        layout.membrane_diffusion,
        control.membrane[..., :3, :],
        control.membrane[..., 3, :],
        xp=xp,
    )
    leak, cycles = (xp.where(layout.membrane_active, value, 0.0) for value in (leak, cycles))
    carriers = xp.concatenate((state.ions, state.regulation[..., :1, :]), axis=-2)
    src, dst, edge_active = layout.senders, layout.receivers, layout.contact_active
    delta = xp.where(edge_active, voltage[..., src] - voltage[..., dst], 0.0)
    diffusion = xp.concatenate((layout.ion_diffusion, layout.mirna_diffusion[None, :]), axis=0)
    flux, scales = laws.junction_flux(
        (
            xp.where(edge_active, carriers[..., src], 0.0),
            xp.where(edge_active, carriers[..., dst], 0.0),
        ),
        delta,
        diffusion,
        layout.gate_parameters,
        layout.gate_enabled,
        control.contact,
        xp=xp,
    )
    flux, scales = (xp.where(edge_active, value, 0.0) for value in (flux, scales))
    local = xp.stack(
        emt_mirna.rhs(
            EMTState(*(state.regulation[..., i, :] for i in range(3))),
            None,
            layout.context[1],
            layout.active,
            xp=xp,
        ),
        axis=-2,
    )
    return Rates(voltage, delta, leak, cycles, flux, scales, local)


def scatter(flux, layout, like, *, xp=jnp):
    if xp is not np:
        return scatter_exchange(flux, layout.senders, layout.receivers, like)
    result = np.zeros_like(like)
    np.add.at(result, (..., layout.senders), -flux)
    np.add.at(result, (..., layout.receivers), flux)
    return result


def rhs(state, control, layout, active, *, xp=jnp):
    r = rates(state, control, layout, xp=xp)
    # The named source profile fixes equal spheres and whole-cell surface scaling.
    # These concentration-equivalent ledgers are not a general unequal-volume law.
    leak, pump = r.leak * SURFACE_FACTOR, r.cycles * SURFACE_FACTOR
    ion_transfer, mirna_transfer = (
        r.junction[..., :3, :] * SURFACE_FACTOR,
        r.junction[..., 3, :] * SURFACE_FACTOR,
    )
    ionic = scatter(ion_transfer, layout, state.ions, xp=xp)
    inward = leak + xp.asarray(NU) * pump[..., None, :]
    if xp is np:
        np.add.at(ionic, (..., layout.owners), inward)
    else:
        ionic = ionic.at[..., layout.owners].add(inward)
    mirna = scatter(mirna_transfer, layout, state.regulation[..., 0, :], xp=xp)
    regulation = r.local + xp.stack((mirna, xp.zeros_like(mirna), xp.zeros_like(mirna)), axis=-2)
    return SourcePairState(
        xp.where(active, ionic, 0.0),
        xp.where(active, regulation, 0.0),
        leak,
        pump,
        ion_transfer,
        r.local,
        mirna_transfer,
    )


def domain_valid(state, layout, active, *, xp=jnp):
    ok = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state]))
    for values, mask in zip(
        state,
        (
            active,
            active,
            layout.membrane_active,
            layout.membrane_active,
            layout.contact_active,
            active,
            layout.contact_active,
        ),
        strict=True,
    ):
        ok &= xp.all(xp.where(mask, True, values == 0))
    ok &= xp.all(xp.where(active, (state.ions >= 1e-6) & (state.ions <= 1000), True))
    ok &= xp.all(xp.where(active, (state.regulation >= 0) & (state.regulation <= 1000), True))
    voltage = cell_voltage(state.ions, layout, xp=xp)
    return (
        ok
        & xp.all(xp.abs(voltage) <= 0.2)
        & xp.all(xp.abs(voltage[..., layout.senders] - voltage[..., layout.receivers]) <= 0.2)
    )


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Source pair RK4 requires largest actual step <= 0.01 nominal units; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for index in range(len(held.contact)):
            control = type(held)(*(v[index] for v in held))
            if not all(
                np.isfinite(v).all() for v in rhs(state, control, layout, layout.active, xp=np)
            ):
                raise ConfigError("Source initial rates exceed finite float64")


def balances(state, layout):
    ionic = scatter(state.ion_transferred, layout, state.ions, xp=np)
    np.add.at(
        ionic, (..., layout.owners), state.leak_history + NU * state.pump_history[..., None, :]
    )
    regulatory = state.local_regulation.copy()
    regulatory[..., 0, :] += scatter(
        state.mirna_transferred, layout, state.regulation[..., 0, :], xp=np
    )
    return (
        state.ions - layout.ion_reference - ionic,
        state.regulation - layout.regulatory_reference - regulatory,
    )


def check_values(state, spec):
    _, layout = initial_values(spec)
    if not domain_valid(state, layout, layout.active, xp=np):
        raise NumericalError("Invalid source-coordinate state, voltage or padding; no clipping")
    residuals = balances(state, layout)
    maxima = [float(np.max(abs(v), initial=0)) for v in residuals]
    if not np.isfinite(maxima).all() or max(maxima) > 2e-9:
        raise NumericalError("Source typed ionic/regulatory history accounting failed")
    return dict(
        zip(("max_ionic_balance_error", "max_regulatory_balance_error"), maxima, strict=True)
    )


def check_interpolants(times, history, f0, f1, layout):
    if len(times) < 2:
        return
    for name, value, left, right in zip(STATE_TYPE._fields, history, f0, f1, strict=True):
        lo, hi = hermite_bounds(times, value, left, right)
        if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all():
            raise NumericalError("Nonfinite source cubic coefficients/bounds")
        if name in ("ions", "regulation"):
            minimum = 1e-6 if name == "ions" else 0
            if np.any(lo[..., layout.active] < minimum) or np.any(hi[..., layout.active] > 1000):
                raise NumericalError("Source cubic interior violates primary domain; no clipping")
    voltage = cell_voltage(history.ions, layout, xp=np)
    slopes = [
        VOLTAGE_FACTOR * (s.ions[..., 0, :] + s.ions[..., 1, :] - s.ions[..., 2, :])
        for s in (f0, f1)
    ]
    for values, left, right in (
        (voltage, *slopes),
        tuple(v[..., layout.senders] - v[..., layout.receivers] for v in (voltage, *slopes)),
    ):
        lo, hi = hermite_bounds(times, values, left, right)
        if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
            np.maximum(abs(lo), abs(hi)) > 0.2
        ):
            raise NumericalError("Source cubic interior violates electrical domain")


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    ions: np.ndarray
    regulation: np.ndarray
    leak_history: np.ndarray
    pump_history: np.ndarray
    ion_transferred: np.ndarray
    local_regulation: np.ndarray
    mirna_transferred: np.ndarray
    voltage_V: np.ndarray
    junction_voltage_V: np.ndarray
    gate_scales: np.ndarray
    membrane_multipliers: np.ndarray
    route_multipliers: np.ndarray
    leak_flux: np.ndarray
    pump_cycle_flux: np.ndarray
    ionic_junction_flux: np.ndarray
    mirna_junction_flux: np.ndarray
    local_regulatory_rate: np.ndarray
    free_mirna_proxy: np.ndarray
    bound_complexes: np.ndarray
    ionic_balance: np.ndarray
    regulatory_balance: np.ndarray
    label: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    held = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(STATE_TYPE(*(v[s] for v in history)), held, layout, layout.active, xp=np)
        for s in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = STATE_TYPE(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    held = control_values(spec, requested)
    r = rates(sampled, held, layout, xp=np)
    u, m = sampled.regulation[..., 0, :], sampled.regulation[..., 1, :]
    result = Observations(
        requested,
        *sampled,
        r.voltage,
        r.junction_voltage,
        r.scales,
        held.membrane,
        held.contact,
        r.leak,
        r.cycles,
        r.junction[..., :3, :],
        r.junction[..., 3, :],
        r.local,
        u.copy(),
        np.moveaxis(emt_mirna.complexes(u, m, xp=np), -1, -2),
        *balances(sampled, layout),
        emt_mirna.labels(u, m, layout.active),
    )
    if not all(np.isfinite(v).all() for k, v in vars(result).items() if k != "label"):
        raise NumericalError("Nonfinite source-compatible observation; no clipping")
    return result


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return {
        "claim_scope": (
            "bounded source-compatible nominal equations; not physical EMT calibration "
            "or full Levin-assay parity"
        ),
        "upstream_revision": emt_mirna.UPSTREAM_REVISION,
        "clock": "bitsey_time_unit",
        "state_axes": STATE_AXES,
        "external_support": [
            "maintained bath",
            "fixed geometry",
            "fixed Snail/P/ST context",
            "maintained ATP/ADP/Pi",
        ],
        "binding_approximation": "total_mirna_in_mass_action; free_proxy_equals_total",
        "mirna_voltage_charge": 0,
        "mirna_transport_valence": -1,
        "gate_memory": "none: algebraic readout",
        "energy_inequality_claimed": False,
        "final_ions": history.ions[-1, :, :2].tolist(),
        "final_regulation": history.regulation[-1, :, :2].tolist(),
        "final_voltage_V": cell_voltage(history.ions[-1], layout, xp=np)[:2].tolist(),
        "final_label": emt_mirna.labels(
            history.regulation[-1, 0, :2], history.regulation[-1, 1, :2], True
        ).tolist(),
        **diagnostics,
    }
