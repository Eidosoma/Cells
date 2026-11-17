"""One well-mixed Na/K/Cl cell, lumped membrane, and explicit maintained bath.

Amounts own ionic charge. Voltage is affine-derived from immutable initial
anchors; leak and pump ledgers account for external exchange, not extra matter.
The bounded electrical closure is NOT a multi-membrane or multi-cell solver.
"""

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import BioelectricLayout, BioelectricState, identity_arrays
from cells.observers import sample_hermite_history
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    M3_PER_PL,
    MOL_PER_FMOL,
    F,
    R,
    electrochemical_potential,
    ghk_leak,
    reversible_pump,
)

STATE_TYPE = BioelectricState
LAYOUT_TYPE = BioelectricLayout
OBSERVER_ID = "bioelectric_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite@1"
STAGE_DOMAIN_ID = "positive_ions_finite_state_abs_zFV_over_RT_le_50@1"
TRACE_COLUMNS = 40
TRACE_EDGE_COLUMNS = 0
TRACE_MEMBRANE_COLUMNS = 80
OBSERVATION_COLUMNS = 40
OBSERVATION_EDGE_COLUMNS = 0
OBSERVATION_MEMBRANE_COLUMNS = 80
Z = np.array([1.0, 1.0, -1.0])[:, None]
NU = np.array([-3.0, 2.0, 0.0])[:, None]
MAX_STEP = 0.005
MAX_ABS_X = 50.0
STATE_AXES = {
    "amount": ["species", "cell_slot"],
    "leak_transferred": ["species", "membrane_slot"],
    "pump_cycles": ["membrane_slot"],
}


def check_definition(model):
    m, b = model.membrane, model.bath
    n, co = np.asarray(model.initial_amount), np.asarray(b.concentration_mM)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        capacitance = np.float64(m.area_m2) * m.specific_capacitance_F_per_m2
        rt = R * np.float64(b.temperature_K)
        charge_scale = CHARGE_PER_FMOL / capacitance
        x = F * model.initial_voltage_V / rt
        fixed = capacitance * model.initial_voltage_V - CHARGE_PER_FMOL * np.sum(Z[:, 0] * n)
        ci = n / model.volume_pL
        mu = electrochemical_potential(
            ci, co, model.initial_voltage_V, Z[:, 0], b.temperature_K, xp=np
        )
        coefficients = m.area_m2 * np.asarray(m.permeability_m_per_s) / MOL_PER_FMOL
        bath_charge = Z[:, 0] @ co
        bounds = np.r_[
            capacitance,
            rt,
            charge_scale,
            F / rt,
            fixed,
            ci,
            mu,
            coefficients,
            bath_charge,
            b.atp_free_energy_J_per_mol + NU[:, 0] @ mu,
            8 * np.float64(m.pump_capacity_fmol_per_s),
        ]
    if (
        not np.isfinite(bounds).all()
        or capacitance <= 0
        or rt <= 0
        or charge_scale <= 0
        or np.any(ci <= 0)
    ):
        raise ConfigError(
            "Derived physical coefficients must fit the finite positive float64 domain"
        )
    if fixed > 0:
        raise ConfigError("Initial anchors require a nonnegative fixed anion equivalent")
    if abs(float(bath_charge)) > 1e-12:
        raise ConfigError("The clamped Na/K/Cl bath must be electroneutral")
    if not np.isfinite(x) or abs(x) > MAX_ABS_X:
        raise ConfigError("Initial voltage exceeds abs(zFV/RT) <= 50")


def initial_values(spec):
    m, size, membranes = spec.model, spec.execution.capacity, spec.execution.membrane_capacity
    active, ids = identity_arrays(spec)
    amount = np.zeros((3, size))
    amount[:, 0] = m.initial_amount
    volume, vref, fixed = np.ones(size), np.zeros(size), np.zeros(size)
    volume[0], vref[0] = m.volume_pL, m.initial_voltage_V
    area, cs, cap = np.ones(membranes), np.ones(membranes), np.ones(membranes)
    area[0], cs[0] = m.membrane.area_m2, m.membrane.specific_capacitance_F_per_m2
    cap[0] = area[0] * cs[0]
    fixed[0] = cap[0] * vref[0] - CHARGE_PER_FMOL * np.sum(Z[:, 0] * amount[:, 0])
    permeability, pump = np.zeros((3, membranes)), np.zeros(membranes)
    permeability[:, 0], pump[0] = (
        m.membrane.permeability_m_per_s,
        m.membrane.pump_capacity_fmol_per_s,
    )
    membrane_ids = np.full(membranes, -1, dtype=np.int64)
    membrane_ids[0] = m.membrane.membrane_id
    layout = BioelectricLayout(
        volume,
        active,
        ids,
        amount.copy(),
        vref,
        fixed,
        membrane_ids,
        np.arange(membranes) == 0,
        np.zeros(membranes, dtype=np.int64),
        np.zeros(membranes, dtype=np.int64),
        area,
        cs,
        cap,
        permeability,
        pump,
        np.array([m.bath.bath_id], dtype=np.int64),
        np.array(m.bath.concentration_mM)[:, None],
        np.array([m.bath.potential_V]),
        np.array([m.bath.temperature_K]),
        np.array([m.bath.atp_free_energy_J_per_mol]),
    )
    return BioelectricState(amount, np.zeros_like(permeability), np.zeros(membranes)), layout


def parameters(spec, layout):
    return layout


def membrane_voltage(amount, layout, *, xp=jnp):
    delta = amount[..., :, layout.owners] - layout.amount_reference[:, layout.owners]
    voltage = layout.voltage_reference[
        layout.owners
    ] + CHARGE_PER_FMOL / layout.capacitance * xp.sum(Z * delta, axis=-2)
    return xp.where(layout.membrane_active, voltage, 0.0)


def readouts(state, control, layout, *, xp=jnp):
    active = layout.membrane_active
    voltage = membrane_voltage(state.amount, layout, xp=xp)
    # Neutral finite padding BEFORE every division and logarithm. No real ion is floored.
    ci = (MOL_PER_FMOL / M3_PER_PL) * (
        xp.where(active, state.amount[..., :, layout.owners], 1.0)
        / xp.where(active, layout.volume[layout.owners], 1.0)
    )
    co = xp.where(active, layout.bath_concentration[:, layout.membrane_baths], 1.0)
    temperature = layout.temperature[layout.membrane_baths]
    mu = electrochemical_potential(ci, co, voltage[..., None, :], Z, temperature, xp=xp)
    leak = ghk_leak(
        ci,
        co,
        voltage[..., None, :],
        Z,
        temperature,
        layout.area,
        layout.permeability,
        control[..., :3, :],
        xp=xp,
    )
    cycles, energy = reversible_pump(
        mu,
        NU,
        layout.atp_free_energy[layout.membrane_baths],
        temperature,
        layout.pump_capacity,
        control[..., 3, :],
        xp=xp,
    )
    return (
        voltage,
        xp.where(active, leak, 0.0),
        xp.where(active, cycles, 0.0),
        xp.where(active, mu, 0.0),
        xp.where(active, energy, 0.0),
    )


def rhs(state, control, layout, active, *, xp=jnp):
    _, leak, cycles, _, _ = readouts(state, control, layout, xp=xp)
    flux = leak + NU * cycles[..., None, :]
    amount = xp.zeros_like(state.amount)
    if xp is np:
        np.add.at(amount, (..., layout.owners), flux)
    else:
        amount = amount.at[..., layout.owners].add(flux)
    return BioelectricState(xp.where(active, amount, 0.0), leak, cycles)


def domain_valid(state, layout, active, *, xp=jnp):
    finite = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state]))
    positive = xp.all(xp.where(active, state.amount > 0, state.amount == 0))
    padding = xp.all(xp.where(layout.membrane_active, True, state.leak_transferred == 0)) & xp.all(
        xp.where(layout.membrane_active, True, state.pump_cycles == 0)
    )
    ci = xp.where(active, state.amount, 1.0) / layout.volume
    x = (
        F
        * membrane_voltage(state.amount, layout, xp=xp)
        / (R * layout.temperature[layout.membrane_baths])
    )
    return (
        finite
        & positive
        & padding
        & xp.all(xp.isfinite(ci) & (ci > 0))
        & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))
    )


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0.0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Bioelectric RK4 requires largest actual step <= 0.005 s; new regimes need refinement"
        )
    state, layout = initial_values(spec)
    # Include the final-time control declaration, even when it has no subsequent step.
    all_controls = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for control in all_controls:
            values = readouts(state, control, layout, xp=np)
            slopes = rhs(state, control, layout, layout.active, xp=np)
            if not all(np.isfinite(v).all() for v in (*values, *slopes)):
                raise ConfigError(
                    "Initial membrane rates or derived readouts exceed finite float64"
                )


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError(
                "Invalid bioelectric state: positive ions, finite storage and "
                "abs(zFV/RT) <= 50 required; no clipping"
            )
        exchanged = state.leak_transferred[..., :, 0] + NU[:, 0] * state.pump_cycles[..., 0, None]
        delta = state.amount[..., :, 0] - layout.amount_reference[:, 0]
        residual = delta - exchanged
        charge_error = CHARGE_PER_FMOL / layout.capacitance[0] * np.sum(Z[:, 0] * residual, axis=-1)
        amount_error = float(np.max(np.abs(residual), initial=0))
        voltage_error = float(np.max(np.abs(charge_error), initial=0))
    if (
        not np.isfinite([amount_error, voltage_error]).all()
        or amount_error > 1e-10
        or voltage_error > 1e-8
    ):
        raise NumericalError("Bioelectric species/charge exchange accounting failed")
    return {"max_balance_error_fmol": amount_error, "max_charge_balance_error_V": voltage_error}


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount: np.ndarray
    concentration_mM: np.ndarray
    leak_transferred: np.ndarray
    pump_cycles: np.ndarray
    voltage_V: np.ndarray
    leak_multiplier: np.ndarray
    pump_multiplier: np.ndarray
    leak_flux_fmol_per_s: np.ndarray
    pump_rate_fmol_per_s: np.ndarray
    pump_flux_fmol_per_s: np.ndarray
    delta_mu_J_per_mol: np.ndarray
    cycle_energy_J_per_mol: np.ndarray
    inward_current_A: np.ndarray
    chemical_power_W: np.ndarray
    chemical_work_J: np.ndarray
    species_balance_fmol: np.ndarray
    charge_balance_V: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = BioelectricLayout(*(np.asarray(v) for v in layout))
    # Vectorized host evaluation is read-only. Both endpoint slopes hold the LEFT
    # interval's control, including at discontinuities; new controls affect readouts.
    interval_control = control_values(spec, times[:-1])
    left = BioelectricState(*(v[:-1] for v in history))
    right = BioelectricState(*(v[1:] for v in history))
    f0 = rhs(left, interval_control, layout, layout.active, xp=np)
    f1 = rhs(right, interval_control, layout, layout.active, xp=np)
    sampled = BioelectricState(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, leak, cycles, mu, energy = readouts(sampled, control, layout, xp=np)
    pump_flux = NU * cycles[:, None, :]
    current = CHARGE_PER_FMOL * np.sum(Z * (leak + pump_flux), axis=-2)
    drive = layout.atp_free_energy[layout.membrane_baths]
    power, work = -MOL_PER_FMOL * drive * cycles, -MOL_PER_FMOL * drive * sampled.pump_cycles
    residual = (
        sampled.amount[:, :, 0]
        - layout.amount_reference[:, 0]
        - sampled.leak_transferred[:, :, 0]
        - NU[:, 0] * sampled.pump_cycles[:, 0, None]
    )
    charge = CHARGE_PER_FMOL / layout.capacitance[0] * np.sum(Z[:, 0] * residual, axis=-1)
    result = Observations(
        requested,
        sampled.amount,
        sampled.amount / layout.volume,
        sampled.leak_transferred,
        sampled.pump_cycles,
        voltage,
        control[:, :3],
        control[:, 3],
        leak,
        cycles,
        pump_flux,
        mu,
        energy,
        current,
        power,
        work,
        residual,
        charge,
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Non-finite bioelectric observation; refused without clipping")
    return result


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return {
        "claim_scope": (
            "synthetic dimensional bioelectric engineering; "
            "not calibrated biology or BITSEY/BETSE parity"
        ),
        "species": ["Na", "K", "Cl"],
        "state_axes": STATE_AXES,
        "physical_membranes": 1,
        "membrane_capacity": spec.execution.membrane_capacity,
        "membrane_ids": [spec.model.membrane.membrane_id],
        "clamped_bath_id": spec.model.bath.bath_id,
        "external_support": [
            "bath chemistry and countercharge",
            "zero bath potential",
            "temperature",
            "fixed volume",
            "effective ATP chemical drive",
        ],
        "final_amounts_fmol": history.amount[-1, :, 0].tolist(),
        "final_voltage_V": float(membrane_voltage(history.amount[-1], layout, xp=np)[0]),
        "final_leak_transferred_fmol": history.leak_transferred[-1, :, 0].tolist(),
        "final_pump_cycles_fmol": float(history.pump_cycles[-1, 0]),
        "fixed_anion_equivalent_fmol": float(-layout.fixed_charge[0] / CHARGE_PER_FMOL),
        **diagnostics,
    }
