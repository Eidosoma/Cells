"""One maintained-bath membrane with data-defined charged species and pump roles.

Composes the existing pure dimensioned laws; no reference/test imports, mutable
objects, string dispatch or case-name branches occur in the numerical kernel.
"""

import math
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.core.state import MultispeciesLayout, MultispeciesState
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    MOL_PER_FMOL,
    F,
    R,
    electrochemical_potential,
    ghk_leak,
    reversible_pump,
)

STATE_TYPE = MultispeciesState
LAYOUT_TYPE = MultispeciesLayout
OBSERVER_ID = "multispecies_membrane_physical_readouts@1"
OBSERVATION_SAMPLING = "read_only_interval_control_cubic_hermite_extrema_checked@1"
STAGE_DOMAIN_ID = "positive_species_finite_state_all_valences_abs_zFV_over_RT_le_50@1"
MAX_STEP = 0.01
MAX_ABS_X = 50.0
STATE_AXES = {
    "amount": ["species", "cell_slot"],
    "leak_transferred": ["species", "membrane_slot"],
    "pump_cycles": ["membrane_slot"],
    "dissipated_energy_pJ": ["membrane_slot"],
}


def working_columns(spec):
    """Conservative float64-equivalent buffers, including host cubic analysis.

    Accounts for dynamic species extent, layouts, trial states, native history,
    controls, observations, endpoint slopes and polynomial extrema temporaries.
    Like other model estimates, this excludes compiler/runtime/OS overhead.
    """
    species = len(spec.model.species_ids)
    return 16 * species + 24, 0, 40 * species + 80


def batch_signature(model):
    return (len(model.species_ids),)


def definition_residuals(m):
    try:
        bath = math.fsum(
            [m.bath_background_charge_mM]
            + [z * c for z, c in zip(m.valence, m.bath_mM, strict=True)]
        )
        charge = math.fsum(
            [m.fixed_charge_equivalent_fmol]
            + [z * n for z, n in zip(m.valence, m.initial_amount_fmol, strict=True)]
        )
        voltage = CHARGE_PER_FMOL / (m.area_m2 * m.specific_capacitance_F_per_m2) * charge
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise ConfigError("Derived charge closure exceeds finite float64") from error
    return bath, voltage - m.initial_voltage_V


def check_definition(m):
    bath, anchor = definition_residuals(m)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        cap = np.float64(m.area_m2) * m.specific_capacitance_F_per_m2
        rt = R * np.float64(m.temperature_K)
        scale = CHARGE_PER_FMOL / cap
        ci = np.asarray(m.initial_amount_fmol) / m.volume_pL
        x = np.asarray(m.valence) * F * m.initial_voltage_V / rt
        mu = electrochemical_potential(
            ci,
            np.asarray(m.bath_mM),
            m.initial_voltage_V,
            np.asarray(m.valence),
            m.temperature_K,
            xp=np,
        )
        coefficients = m.area_m2 * np.asarray(m.permeability_m_per_s) / MOL_PER_FMOL
        derived = np.r_[
            cap,
            rt,
            scale,
            F / rt,
            ci,
            x,
            mu,
            coefficients,
            bath,
            anchor,
            CHARGE_PER_FMOL * m.fixed_charge_equivalent_fmol,
            m.drive_J_per_mol + np.asarray(m.stoichiometry) @ mu,
            8 * np.float64(m.capacity_fmol_per_s),
        ]
    if not np.isfinite(derived).all() or min(cap, rt, scale) <= 0 or np.any(ci <= 0):
        raise ConfigError("Derived physical coefficients must fit finite positive float64")
    if abs(bath) > 1e-12:
        raise ConfigError("Maintained bath plus explicit background charge must balance")
    if abs(anchor) > 1e-10:
        raise ConfigError("Fixed charge, initial amounts and voltage anchor are inconsistent")
    if np.any(np.abs(x) > MAX_ABS_X):
        raise ConfigError("Initial voltage exceeds a declared species' abs(zFV/RT) <= 50")


def initial_values(spec):
    m, x = spec.model, spec.execution
    species, cells, membranes = len(m.species_ids), x.capacity, x.membrane_capacity
    active, membrane_active = np.arange(cells) == 0, np.arange(membranes) == 0
    amount = np.zeros((species, cells))
    amount[:, 0] = m.initial_amount_fmol
    volume, vref, fixed = np.ones(cells), np.zeros(cells), np.zeros(cells)
    volume[0], vref[0], fixed[0] = m.volume_pL, m.initial_voltage_V, m.fixed_charge_equivalent_fmol
    area, cs, cap = np.ones(membranes), np.ones(membranes), np.ones(membranes)
    area[0], cs[0] = m.area_m2, m.specific_capacitance_F_per_m2
    cap[0] = area[0] * cs[0]
    permeability, capacity, drive = (
        np.zeros((species, membranes)),
        np.zeros(membranes),
        np.zeros(membranes),
    )
    permeability[:, 0], capacity[0], drive[0] = (
        m.permeability_m_per_s,
        m.capacity_fmol_per_s,
        m.drive_J_per_mol,
    )
    # Local label codes are separate from storage slots. Their canonical string
    # dictionary is retained in every resolved definition/checkpoint, never hashed
    # into a collision-prone integer or carried as an object array onto a device.
    layout = MultispeciesLayout(
        volume,
        active,
        np.where(active, 1, -1).astype(np.int64),
        np.arange(1, species + 1, dtype=np.int64),
        np.array(m.valence, dtype=np.int64)[:, None],
        np.array(m.stoichiometry, dtype=np.int64)[:, None],
        amount.copy(),
        vref,
        fixed,
        np.where(membrane_active, 1, -1).astype(np.int64),
        membrane_active,
        np.zeros(membranes, dtype=np.int64),
        np.zeros(membranes, dtype=np.int64),
        area,
        cs,
        cap,
        permeability,
        capacity,
        drive,
        np.array([1], dtype=np.int64),
        np.asarray(m.bath_mM)[:, None],
        np.array([m.bath_background_charge_mM]),
        np.array([m.temperature_K]),
    )
    return MultispeciesState(
        amount, np.zeros_like(permeability), np.zeros(membranes), np.zeros(membranes)
    ), layout


def parameters(spec, layout):
    return layout


def membrane_voltage(amount, layout, *, xp=jnp):
    delta = amount[..., :, layout.owners] - layout.amount_reference[:, layout.owners]
    voltage = layout.voltage_reference[
        layout.owners
    ] + CHARGE_PER_FMOL / layout.capacitance * xp.sum(layout.valence * delta, axis=-2)
    return xp.where(layout.membrane_active, voltage, 0.0)


def readouts(state, control, layout, *, xp=jnp):
    active = layout.membrane_active
    voltage = membrane_voltage(state.amount, layout, xp=xp)
    # Sanitize only inactive padding BEFORE nonlinear laws. Real species remain
    # strictly positive even when their permeability or control is zero.
    ci = xp.where(active, state.amount[..., :, layout.owners], 1.0) / xp.where(
        active, layout.volume[layout.owners], 1.0
    )
    co = xp.where(active, layout.bath_concentration[:, layout.membrane_baths], 1.0)
    temperature = layout.temperature[layout.membrane_baths]
    mu = electrochemical_potential(
        ci, co, voltage[..., None, :], layout.valence, temperature, xp=xp
    )
    leak = ghk_leak(
        ci,
        co,
        voltage[..., None, :],
        layout.valence,
        temperature,
        layout.area,
        layout.permeability,
        control[..., :-1, :],
        xp=xp,
    )
    cycles, energy = reversible_pump(
        mu,
        layout.stoichiometry,
        layout.pump_drive,
        temperature,
        layout.pump_capacity,
        control[..., -1, :],
        xp=xp,
    )
    return tuple(xp.where(active, v, 0.0) for v in (voltage, leak, cycles, mu, energy))


def dissipation_rate(leak, cycles, mu, energy, *, xp=jnp):
    return -1e-3 * (xp.sum(leak * mu, axis=-2) + cycles * energy)


def rhs(state, control, layout, active, *, xp=jnp):
    _, leak, cycles, mu, energy = readouts(state, control, layout, xp=xp)
    flux = leak + layout.stoichiometry * cycles[..., None, :]
    amount = xp.zeros_like(state.amount)
    if xp is np:
        np.add.at(amount, (..., layout.owners), flux)
    else:
        amount = amount.at[..., layout.owners].add(flux)
    return MultispeciesState(
        xp.where(active, amount, 0.0),
        leak,
        cycles,
        dissipation_rate(leak, cycles, mu, energy, xp=xp),
    )


def domain_valid(state, layout, active, *, xp=jnp):
    finite = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state]))
    positive = xp.all(xp.where(active, state.amount > 0, state.amount == 0))
    padding = xp.all(
        xp.stack([xp.all(xp.where(layout.membrane_active, True, v == 0)) for v in state[1:]])
    )
    absent = xp.all(xp.where(layout.permeability == 0, state.leak_transferred == 0, True)) & xp.all(
        xp.where(layout.pump_capacity == 0, state.pump_cycles == 0, True)
    )
    ci = xp.where(active, state.amount, 1.0) / layout.volume
    x = (
        layout.valence
        * F
        * membrane_voltage(state.amount, layout, xp=xp)[..., None, :]
        / (R * layout.temperature[layout.membrane_baths])
    )
    return (
        finite
        & positive
        & padding
        & absent
        & xp.all(xp.isfinite(ci) & (ci > 0))
        & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))
    )


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Multispecies RK4 requires largest actual step <= 0.01 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for control in held:
            slopes = rhs(state, control, layout, layout.active, xp=np)
            values = readouts(state, control, layout, xp=np)
            if not all(np.isfinite(v).all() for v in (*slopes, *values)):
                raise ConfigError("Initial multispecies rates/readouts exceed finite float64")


def balances(state, layout):
    n0, n = layout.amount_reference[:, 0], state.amount[..., :, 0]
    delta = n - n0
    exchange = (
        state.leak_transferred[..., :, 0]
        + layout.stoichiometry[:, 0] * state.pump_cycles[..., 0, None]
    )
    residual = delta - exchange
    scale = CHARGE_PER_FMOL / layout.capacitance[0]
    charge = scale * np.sum(layout.valence[:, 0] * residual, axis=-1)
    chemical = (
        1e-3
        * R
        * layout.temperature[0]
        * np.sum(
            delta * (np.log(n0 / layout.volume[0]) - np.log(layout.bath_concentration[:, 0]) - 1)
            + n * np.log1p(delta / n0),
            axis=-1,
        )
    )
    dv = scale * np.sum(layout.valence[:, 0] * delta, axis=-1)
    capacitor = 0.5e12 * layout.capacitance[0] * dv * (2 * layout.voltage_reference[0] + dv)
    supplied = -1e-3 * layout.pump_drive[0] * state.pump_cycles[..., 0]
    energy = chemical + capacitor + state.dissipated_energy_pJ[..., 0] - supplied
    return residual, charge, energy


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not domain_valid(state, layout, layout.active, xp=np):
            raise NumericalError(
                "Invalid multispecies state: positive species, finite storage and "
                "all-valence voltage domain required; no clipping"
            )
        residual, charge, energy = balances(state, layout)
        maxima = [float(np.max(np.abs(v), initial=0)) for v in (residual, charge, energy)]
        outside = np.any(np.abs(residual) > np.asarray(spec.execution.material_balance_atol_fmol))
    if not np.isfinite(maxima).all() or outside or maxima[1] > 1e-8 or maxima[2] > 1e-6:
        raise NumericalError("Multispecies material/charge/resolved-energy accounting failed")
    d = state.dissipated_energy_pJ
    if np.min(d, initial=0) < -1e-10 or (
        d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -1e-10
    ):
        raise NumericalError("Diagnostic dissipation must not decrease")
    return dict(
        zip(
            ("max_balance_error_fmol", "max_charge_balance_error_V", "max_energy_balance_error_pJ"),
            maxima,
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    if len(times) < 2:
        return
    if not all(np.isfinite(v).all() for v in (*f0, *f1)):
        raise NumericalError("Nonfinite cubic endpoint slope")
    lo, hi = hermite_bounds(times, history.amount, f0.amount, f1.amount)
    if np.any(lo[..., layout.active] <= 0) or not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all():
        raise NumericalError("Cubic interior violates positive-species domain; no clipping")
    voltage = membrane_voltage(history.amount, layout, xp=np)
    slopes = [
        np.where(
            layout.membrane_active,
            CHARGE_PER_FMOL
            / layout.capacitance
            * np.sum(layout.valence * f.amount[..., :, layout.owners], axis=-2),
            0.0,
        )
        for f in (f0, f1)
    ]
    lo, hi = hermite_bounds(times, voltage, *slopes)
    bound = (
        np.max(np.abs(layout.valence))
        * F
        * np.maximum(np.abs(lo), np.abs(hi))
        / (R * layout.temperature[layout.membrane_baths])
    )
    if not np.isfinite(bound).all() or np.any(bound > MAX_ABS_X):
        raise NumericalError("Cubic interior exceeds a declared species' voltage domain")


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount: np.ndarray
    leak_transferred: np.ndarray
    pump_cycles: np.ndarray
    dissipated_energy_pJ: np.ndarray
    concentration_mM: np.ndarray
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
    dissipation_rate_pJ_per_s: np.ndarray
    bath_exchange_fmol: np.ndarray
    species_balance_fmol: np.ndarray
    charge_balance_V: np.ndarray
    resolved_energy_balance_pJ: np.ndarray


def observe_history(times, history, layout, requested, spec):
    requested = np.asarray(requested, dtype=np.float64)
    layout = MultispeciesLayout(*(np.asarray(v) for v in layout))
    control = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(MultispeciesState(*(v[part] for v in history)), control, layout, layout.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = MultispeciesState(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, leak, cycles, mu, energy = readouts(sampled, control, layout, xp=np)
    pump_flux = layout.stoichiometry * cycles[..., None, :]
    result = Observations(
        requested,
        *sampled,
        sampled.amount / layout.volume,
        voltage,
        control[:, :-1],
        control[:, -1],
        leak,
        cycles,
        pump_flux,
        mu,
        energy,
        CHARGE_PER_FMOL * np.sum(layout.valence * (leak + pump_flux), axis=-2),
        -MOL_PER_FMOL * layout.pump_drive * cycles,
        -MOL_PER_FMOL * layout.pump_drive * sampled.pump_cycles,
        dissipation_rate(leak, cycles, mu, energy, xp=np),
        -(sampled.leak_transferred + layout.stoichiometry * sampled.pump_cycles[..., None, :]),
        *balances(sampled, layout),
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite multispecies observation; refused without clipping")
    return result


def summarize(history, diagnostics, spec):
    m = spec.model
    _, layout = initial_values(spec)
    bath, anchor = definition_residuals(m)
    return {
        "claim_scope": (
            "synthetic multispecies membrane engineering; not calibrated biology, "
            "BETSE parity, calcium signaling, organs or GPU execution"
        ),
        "numerical_scope": (
            "NUM-006 qualifies only its two assemblies and fourteen schedules; "
            "dt bound and runtime guards are not a parameter-box error guarantee"
        ),
        "species": list(m.species_ids),
        "valences": list(m.valence),
        "state_axes": STATE_AXES,
        "identity_labels": {
            "cell": {"1": m.cell_id},
            "membrane": {"1": m.membrane_id},
            "bath": {"1": m.bath_id},
            "species": {str(i + 1): s for i, s in enumerate(m.species_ids)},
        },
        "pump_id": m.pump_id,
        "pump_roles": m.pump_roles,
        "physical_membranes": 1,
        "membrane_capacity": spec.execution.membrane_capacity,
        "boundary": "maintained bath at zero potential; exchange ledger is not an inventory",
        "external_support": [
            "bath chemistry and background countercharge",
            "temperature",
            "fixed volume and membrane geometry",
            "pump chemical drive",
        ],
        "fixed_charge_equivalent_fmol": m.fixed_charge_equivalent_fmol,
        "bath_background_charge_mM": m.bath_background_charge_mM,
        "initial_anchor_residual_V": anchor,
        "bath_charge_residual_mM": bath,
        "final_amounts_fmol": history.amount[-1, :, 0].tolist(),
        "final_voltage_V": float(membrane_voltage(history.amount[-1], layout, xp=np)[0]),
        "final_leak_transferred_fmol": history.leak_transferred[-1, :, 0].tolist(),
        "final_pump_cycles_fmol": float(history.pump_cycles[-1, 0]),
        "final_dissipated_energy_pJ": float(history.dissipated_energy_pJ[-1, 0]),
        **diagnostics,
    }
