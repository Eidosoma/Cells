"""Two physical cells composed with one selective, dynamically gated contact.

Diagonal capacitance, one bath-facing effective membrane per fixed-volume cell.
Shared one-cell membrane laws and single edge scatter use the SAME RK stage.
No second ionic/voltage inventory; energy quadratures are diagnostic history.
"""

from dataclasses import dataclass, replace

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, ExperimentSpec, SimulationSpec
from cells.core.state import BioelectricPairLayout, BioelectricPairState
from cells.coupling.passive import scatter_exchange
from cells.coupling.selective import gate_target, selective_flux
from cells.models import bioelectric_cell as membrane
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R

STATE_TYPE = BioelectricPairState
LAYOUT_TYPE = BioelectricPairLayout
OBSERVER_ID = "bioelectric_pair_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite_extrema_checked@1"
STAGE_DOMAIN_ID = "positive_ions_unit_gates_finite_state_membrane_junction_abs_zFV_over_RT_le_50@1"
TRACE_COLUMNS = 80
TRACE_MEMBRANE_COLUMNS = 120
TRACE_EDGE_COLUMNS = 120
OBSERVATION_COLUMNS = 80
OBSERVATION_MEMBRANE_COLUMNS = 120
OBSERVATION_EDGE_COLUMNS = 120
MAX_STEP = 0.001
MAX_ABS_X = 50.0
Z, NU = membrane.Z, membrane.NU
STATE_AXES = {
    **membrane.STATE_AXES,
    "transferred": ["species", "edge_slot"],
    "gate": ["edge_slot"],
    "dissipated_energy_pJ": ["diagnostic_process:leak,pump,junction"],
}


def check_definition(model):
    for cell in model.cells:
        membrane.check_definition(cell)
    c, a, b = model.contact, *model.cells
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        rt = R * np.float64(a.bath.temperature_K)
        x = F * (np.float64(a.initial_voltage_V) - b.initial_voltage_V) / rt
        coefficients = np.float64(c.area_m2) * np.asarray(c.permeability_m_per_s) / MOL_PER_FMOL
        inverse_tau = 1 / np.float64(c.tau_s)
        # All gate logits throughout the declared voltage domain must remain finite.
        logit_bound = np.float64(c.sensitivity_per_V) * (50 * rt / F + c.half_voltage_V)
    if not np.isfinite(np.r_[x, coefficients, inverse_tau, logit_bound]).all() or inverse_tau <= 0:
        raise ConfigError("Derived contact/gate coefficients exceed finite float64")
    if abs(x) > MAX_ABS_X:
        raise ConfigError("Initial junction voltage exceeds abs(zF deltaV/RT) <= 50")


def initial_values(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    first = SimulationSpec(
        m.cells[0],
        ExperimentSpec(
            e.end_time, (), e.observation_times, leak=e.membranes[0].leak, pump=e.membranes[0].pump
        ),
        replace(x, edge_capacity=0),
    )
    base_state, base_layout = membrane.initial_values(first)
    values = base_layout._asdict()
    for slot, cell in enumerate(m.cells):
        a = cell.membrane
        values["active"][slot], values["ids"][slot] = True, cell.cell_id
        values["volume"][slot], values["voltage_reference"][slot] = (
            cell.volume_pL,
            cell.initial_voltage_V,
        )
        base_state.amount[:, slot] = cell.initial_amount
        values["amount_reference"][:, slot] = cell.initial_amount
        values["membrane_ids"][slot], values["membrane_active"][slot] = a.membrane_id, True
        values["owners"][slot] = slot
        values["area"][slot], values["specific_capacitance"][slot] = (
            a.area_m2,
            a.specific_capacitance_F_per_m2,
        )
        values["capacitance"][slot] = a.area_m2 * a.specific_capacitance_F_per_m2
        values["permeability"][:, slot] = a.permeability_m_per_s
        values["pump_capacity"][slot] = a.pump_capacity_fmol_per_s
        values["fixed_charge"][slot] = values["capacitance"][
            slot
        ] * cell.initial_voltage_V - CHARGE_PER_FMOL * np.sum(Z[:, 0] * base_state.amount[:, slot])
    cell_membranes = np.zeros(x.capacity, dtype=np.int64)
    cell_membranes[:2] = (0, 1)
    edges, c = x.edge_capacity, m.contact
    contact_ids = np.full(edges, -1, dtype=np.int64)
    contact_ids[0] = c.contact_id
    senders, receivers = np.zeros(edges, dtype=np.int64), np.zeros(edges, dtype=np.int64)
    ids = [cell.cell_id for cell in m.cells]
    senders[0], receivers[0] = ids.index(c.from_cell_id), ids.index(c.to_cell_id)
    area, tau, sensitivity = np.ones(edges), np.ones(edges), np.ones(edges)
    half, gate = np.zeros(edges), np.zeros(edges)
    permeability, residual = np.zeros((3, edges)), np.zeros((3, edges))
    area[0], tau[0], sensitivity[0], half[0], gate[0] = (
        c.area_m2,
        c.tau_s,
        c.sensitivity_per_V,
        c.half_voltage_V,
        c.initial_gate,
    )
    permeability[:, 0], residual[:, 0] = c.permeability_m_per_s, c.residual
    layout = BioelectricPairLayout(
        *values.values(),
        cell_membranes,
        contact_ids,
        np.arange(edges) == 0,
        senders,
        receivers,
        area,
        permeability,
        residual,
        sensitivity,
        half,
        tau,
    )
    return BioelectricPairState(*base_state, np.zeros((3, edges)), gate, np.zeros(3)), layout


def parameters(spec, layout):
    return layout


def cell_voltage(amount, layout, *, xp=jnp):
    voltage = membrane.membrane_voltage(amount, layout, xp=xp)[..., layout.cell_membranes]
    return xp.where(layout.active, voltage, 0.0)


def junction_readouts(state, control, layout, *, xp=jnp):
    active, src, dst = layout.contact_active, layout.senders, layout.receivers
    v = cell_voltage(state.amount, layout, xp=xp)
    delta_v = xp.where(active, v[..., src] - v[..., dst], 0.0)
    # Sanitize absent routes BEFORE division/logarithms, not after nonlinear laws.
    ca = xp.where(active, state.amount[..., :, src], 1.0) / xp.where(
        active, layout.volume[src], 1.0
    )
    cb = xp.where(active, state.amount[..., :, dst], 1.0) / xp.where(
        active, layout.volume[dst], 1.0
    )
    target = gate_target(delta_v, layout.gate_sensitivity, layout.gate_half_voltage, xp=xp)
    rate = (target - state.gate) / layout.gate_tau
    flux = selective_flux(
        ca,
        cb,
        delta_v[..., None, :],
        Z,
        layout.temperature[0],
        layout.contact_area,
        layout.contact_permeability,
        layout.residual,
        state.gate[..., None, :],
        control.contact[..., None, :],
        xp=xp,
    )
    mu = R * layout.temperature[0] * (xp.log(cb) - xp.log(ca)) - Z * F * delta_v[..., None, :]
    return tuple(xp.where(active, v, 0.0) for v in (delta_v, target, rate, flux, mu))


def rates(state, control, layout, *, xp=jnp):
    mem = membrane.readouts(state, control.membrane, layout, xp=xp)
    edge = junction_readouts(state, control, layout, xp=xp)
    _, leak, cycles, mu, energy = mem
    *_, flux, edge_mu = edge
    dissipation = -1e-3 * xp.stack(
        (
            xp.sum(leak * mu, axis=(-2, -1)),
            xp.sum(cycles * energy, axis=-1),
            xp.sum(flux * edge_mu, axis=(-2, -1)),
        ),
        axis=-1,
    )
    return mem, edge, dissipation


def scatter(flux, layout, like_amount, *, xp=jnp):
    if xp is not np:
        return scatter_exchange(flux, layout.senders, layout.receivers, like_amount)
    result = np.zeros_like(like_amount)
    np.add.at(result, (..., layout.senders), -flux)
    np.add.at(result, (..., layout.receivers), flux)
    return result


def rhs(state, control, layout, active, *, xp=jnp):
    mem, edge, dissipated = rates(state, control, layout, xp=xp)
    _, leak, cycles, _, _ = mem
    _, _, gate_rate, flux, _ = edge
    inward = leak + NU * cycles[..., None, :]
    amount = scatter(flux, layout, state.amount, xp=xp)
    if xp is np:
        np.add.at(amount, (..., layout.owners), inward)
    else:
        amount = amount.at[..., layout.owners].add(inward)
    return BioelectricPairState(
        xp.where(active, amount, 0.0), leak, cycles, flux, gate_rate, dissipated
    )


def domain_valid(state, layout, active, *, xp=jnp):
    # Reuse the one-cell membrane domain across all active owners; it also checks
    # finiteness of every pair-state leaf supplied here.
    base = membrane.domain_valid(state, layout, active, xp=xp)
    gates = xp.all(
        xp.where(layout.contact_active, (state.gate >= 0) & (state.gate <= 1), state.gate == 0)
    )
    padding = xp.all(xp.where(layout.contact_active, True, state.transferred == 0))
    voltage = cell_voltage(state.amount, layout, xp=xp)
    x = (
        F
        * (voltage[..., layout.senders] - voltage[..., layout.receivers])
        / (R * layout.temperature[0])
    )
    return base & gates & padding & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Physical pair RK4 requires largest actual step <= 0.001 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for i in range(len(held.contact)):
            control = type(held)(*(v[i] for v in held))
            slope = rhs(state, control, layout, layout.active, xp=np)
            mem, edge, d = rates(state, control, layout, xp=np)
            if not all(np.isfinite(v).all() for v in (*slope, *mem, *edge, d)):
                raise ConfigError("Initial pair rates/readouts exceed finite float64")


def balances(state, layout):
    exchange = scatter(state.transferred, layout, state.amount, xp=np)
    np.add.at(
        exchange,
        (..., layout.owners),
        state.leak_transferred + NU * state.pump_cycles[..., None, :],
    )
    delta = state.amount - layout.amount_reference
    residual = delta - exchange
    cap = layout.capacitance[layout.cell_membranes]
    charge = np.where(layout.active, CHARGE_PER_FMOL / cap * np.sum(Z * residual, axis=-2), 0.0)
    # Difference of grand potentials, using log1p to avoid cancellation at rest.
    n0 = np.where(layout.active, layout.amount_reference, 1.0)
    n = np.where(layout.active, state.amount, 1.0)
    bath = layout.bath_concentration[:, :1]
    chemical = (
        1e-3
        * R
        * layout.temperature[0]
        * np.sum(
            delta * (np.log(n0 / layout.volume) - np.log(bath) - 1) + n * np.log1p(delta / n0),
            axis=(-2, -1),
        )
    )
    dv = np.where(layout.active, CHARGE_PER_FMOL / cap * np.sum(Z * delta, axis=-2), 0.0)
    electric = 0.5e12 * np.sum(cap * dv * (2 * layout.voltage_reference + dv), axis=-1)
    work = -1e-3 * np.sum(
        layout.atp_free_energy[layout.membrane_baths] * state.pump_cycles, axis=-1
    )
    energy = chemical + electric + np.sum(state.dissipated_energy_pJ, axis=-1) - work
    return residual, charge, energy


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError(
                "Invalid physical pair state: positive ions, unit gates, finite storage "
                "and membrane/junction voltage domain required; no clipping"
            )
        residual, charge, energy = balances(state, layout)
        maxima = [float(np.max(np.abs(v), initial=0)) for v in (residual, charge, energy)]
    if not np.isfinite(maxima).all() or any(
        v > limit for v, limit in zip(maxima, (1e-8, 1e-8, 1e-6), strict=True)
    ):
        raise NumericalError("Physical pair material/charge/resolved-energy accounting failed")
    if np.min(state.dissipated_energy_pJ, initial=0) < -1e-10 or (
        state.dissipated_energy_pJ.ndim > 1
        and np.min(np.diff(state.dissipated_energy_pJ, axis=0), initial=0) < -1e-10
    ):
        raise NumericalError("Physical pair diagnostic dissipation must not decrease")
    return dict(
        zip(
            ("max_balance_error_fmol", "max_charge_balance_error_V", "max_energy_balance_error_pJ"),
            maxima,
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    """Floating polynomial-extrema domain check, even if no samples were requested.

    Affine voltage combinations are bounded as their own cubics, not by taking
    independent ion extrema. This is not an interval-arithmetic error proof.
    """
    if len(times) < 2:
        return
    if not all(np.isfinite(v).all() for v in (*f0, *f1)):
        raise NumericalError("Nonfinite cubic endpoint slope; observation domain cannot be checked")
    lo, hi = hermite_bounds(times, history.amount, f0.amount, f1.amount)
    gl, gh = hermite_bounds(times, history.gate, f0.gate, f1.gate)
    if (
        np.any(lo[..., layout.active] <= 0)
        or np.any(gl < 0)
        or np.any(gh > 1)
        or not np.isfinite(np.r_[lo.ravel(), hi.ravel(), gl.ravel(), gh.ravel()]).all()
    ):
        raise NumericalError("Cubic interior violates positive-ion/unit-gate domain; no clipping")
    voltage = cell_voltage(history.amount, layout, xp=np)
    scale = CHARGE_PER_FMOL / layout.capacitance[layout.cell_membranes]
    a, b = (
        np.where(layout.active, scale * np.sum(Z * slope.amount, axis=-2), 0.0)
        for slope in (f0, f1)
    )
    for v, left, right in (
        (voltage, a, b),
        (
            voltage[..., layout.senders] - voltage[..., layout.receivers],
            a[..., layout.senders] - a[..., layout.receivers],
            b[..., layout.senders] - b[..., layout.receivers],
        ),
    ):
        lo, hi = hermite_bounds(times, v, left, right)
        bound = np.maximum(np.abs(lo), np.abs(hi)) * F / (R * layout.temperature[0])
        if not np.isfinite(bound).all() or np.any(bound > MAX_ABS_X):
            raise NumericalError("Cubic interior exceeds membrane/junction voltage domain")


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount: np.ndarray
    leak_transferred: np.ndarray
    pump_cycles: np.ndarray
    transferred: np.ndarray
    gate: np.ndarray
    dissipated_energy_pJ: np.ndarray
    concentration_mM: np.ndarray
    voltage_V: np.ndarray
    junction_voltage_V: np.ndarray
    gate_target: np.ndarray
    gate_rate_per_s: np.ndarray
    leak_multiplier: np.ndarray
    pump_multiplier: np.ndarray
    contact_multiplier: np.ndarray
    leak_flux_fmol_per_s: np.ndarray
    pump_rate_fmol_per_s: np.ndarray
    junction_flux_fmol_per_s: np.ndarray
    membrane_delta_mu_J_per_mol: np.ndarray
    junction_delta_mu_J_per_mol: np.ndarray
    pump_cycle_energy_J_per_mol: np.ndarray
    membrane_inward_current_A: np.ndarray
    junction_current_A: np.ndarray
    chemical_power_W: np.ndarray
    chemical_work_J: np.ndarray
    dissipation_rate_pJ_per_s: np.ndarray
    species_balance_fmol: np.ndarray
    charge_balance_V: np.ndarray
    resolved_energy_balance_pJ: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = BioelectricPairLayout(*(np.asarray(v) for v in layout))
    control = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(
            BioelectricPairState(*(v[slice_] for v in history)),
            control,
            layout,
            layout.active,
            xp=np,
        )
        for slice_ in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = BioelectricPairState(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    mem, edge, dissipation = rates(sampled, control, layout, xp=np)
    _, leak, cycles, mu, energy = mem
    dv, target, gate_rate, flux, edge_mu = edge
    drive = layout.atp_free_energy[layout.membrane_baths]
    result = Observations(
        requested,
        *sampled,
        sampled.amount / layout.volume,
        cell_voltage(sampled.amount, layout, xp=np),
        dv,
        target,
        gate_rate,
        control.membrane[:, :3],
        control.membrane[:, 3],
        control.contact,
        leak,
        cycles,
        flux,
        mu,
        edge_mu,
        energy,
        CHARGE_PER_FMOL * np.sum(Z * (leak + NU * cycles[..., None, :]), axis=-2),
        CHARGE_PER_FMOL * np.sum(Z * flux, axis=-2),
        -MOL_PER_FMOL * drive * cycles,
        -MOL_PER_FMOL * drive * sampled.pump_cycles,
        dissipation,
        *balances(sampled, layout),
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite physical pair observation; refused without clipping")
    return result


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return {
        "claim_scope": (
            "synthetic dimensional gated pair; not calibrated biology, source parity, "
            "tissue or GPU execution"
        ),
        "species": ["Na", "K", "Cl"],
        "state_axes": STATE_AXES,
        "physical_membranes": 2,
        "physical_contacts": 1,
        "membrane_capacity": spec.execution.membrane_capacity,
        "edge_capacity": spec.execution.edge_capacity,
        "membrane_ids": [c.membrane.membrane_id for c in spec.model.cells],
        "contact_id": spec.model.contact.contact_id,
        "clamped_bath_id": spec.model.cells[0].bath.bath_id,
        "external_support": [
            "bath chemistry and countercharge",
            "zero bath potential",
            "temperature",
            "fixed volumes",
            "effective ATP chemical drive",
        ],
        "excluded_energetics": [
            "gate conformational energy",
            "gating current",
            "gate control cost",
        ],
        "final_amounts_fmol": history.amount[-1, :, :2].tolist(),
        "final_voltage_V": cell_voltage(history.amount[-1], layout, xp=np)[:2].tolist(),
        "final_gate": float(history.gate[-1, 0]),
        "final_transferred_fmol": history.transferred[-1, :, 0].tolist(),
        "final_leak_transferred_fmol": history.leak_transferred[-1, :, :2].tolist(),
        "final_pump_cycles_fmol": history.pump_cycles[-1, :2].tolist(),
        "final_dissipated_energy_pJ": history.dissipated_energy_pJ[-1].tolist(),
        **diagnostics,
    }
