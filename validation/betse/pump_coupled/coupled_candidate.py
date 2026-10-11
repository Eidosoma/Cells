"""Validation-only conservative composition using existing pure Cells primitives.

Not a registry/model change. No replacement of the accepted synthetic pump.
This small harness qualifies the coupling/timestep before production integration.
"""

import sys
from pathlib import Path

from coupled_plan import F, R

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pump_contact"))
from pump_array import densities  # noqa: E402
from pump_reference import FIELDS  # noqa: E402


def parameters(case, xp):
    p = {
        key: xp.asarray(case[key], dtype=xp.float64)
        for key in (
            "volume_pL",
            "initial_inside_mM",
            "initial_outside_mM",
            "initial_voltage_V",
            "area_m2",
            "specific_capacitance_F_m2",
            "permeability_m_s",
            "alpha_mol_m2_s",
            "atp_mM",
            "adp_mM",
            "pi_mM",
            "km_na_mM",
            "km_k_mM",
            "km_atp_mM",
            "delta_g0_J_mol",
            "valence",
            "pump_stoichiometry",
            "temperature_K",
            "outside_volume_pL",
        )
    }
    p["capacitance_F"] = p["area_m2"] * p["specific_capacitance_F_m2"]
    p["sodium_index"], p["potassium_index"] = case["sodium_index"], case["potassium_index"]
    p["initial_amount"] = p["initial_inside_mM"] * p["volume_pL"][:, None]
    p["outside_amount"] = p["initial_outside_mM"] * p["outside_volume_pL"]
    p["chemical_drive"] = p["delta_g0_J_mol"] + R * p["temperature_K"] * (
        xp.log(p["adp_mM"]) + xp.log(p["pi_mM"]) - xp.log(p["atp_mM"]) - xp.log(1000.0)
    )
    return p


def chemistry(state, p, xp):
    n = p["volume_pL"].shape[0]
    inside = (p["initial_amount"] + state[: 3 * n].reshape(n, 3)) / p["volume_pL"][:, None]
    outside = (p["outside_amount"] + state[3 * n : 3 * n + 3]) / p["outside_volume_pL"]
    voltage = p["initial_voltage_V"] + F * 1e-15 / p["capacitance_F"] * xp.sum(
        state[: 3 * n].reshape(n, 3) * p["valence"], axis=-1
    )
    return inside, outside, voltage


def valid(state, p, _active=None, *, xp):
    ci, co, v = chemistry(state, p, xp)
    physical = xp.all(xp.isfinite(state)) & xp.all(ci > 0) & xp.all(co > 0)
    # Neutral arguments only make the rejection predicate itself safe to trace;
    # these values never replace physical state or enter an accepted RHS.
    ci_safe = xp.where((ci > 0) & xp.isfinite(ci), ci, 1.0)
    co_safe = xp.where((co > 0) & xp.isfinite(co), co, 1.0)
    voltage_limit = 50 * R * p["temperature_K"] / (F * xp.max(xp.abs(p["valence"])))
    voltage_ok = xp.isfinite(v) & (xp.abs(v) <= voltage_limit)
    safe_voltage = xp.where(voltage_ok, v, 0.0)
    mu = (
        R * p["temperature_K"] * (xp.log(ci_safe) - xp.log(co_safe))
        + F * safe_voltage[:, None] * p["valence"]
    )
    affinity = p["chemical_drive"] + xp.sum(p["pump_stoichiometry"] * mu, axis=-1)
    return physical & xp.all(voltage_ok) & xp.all(xp.abs(affinity / (R * p["temperature_K"])) <= 80)


def rhs(state, control, p, _active=None, *, xp):
    from cells.processes.electrochemistry import ghk_leak

    ci, co, voltage = chemistry(state, p, xp)
    mu = R * p["temperature_K"] * (xp.log(ci) - xp.log(co)) + F * voltage[:, None] * p["valence"]
    a, b = p["sodium_index"], p["potassium_index"]
    values = {
        **p,
        "na_in_mM": ci[:, a],
        "na_out_mM": xp.broadcast_to(co[a], voltage.shape),
        "k_in_mM": ci[:, b],
        "k_out_mM": xp.broadcast_to(co[b], voltage.shape),
        "availability": xp.full_like(voltage, control[0]),
        "voltage_V": voltage,
        "temperature_K": xp.full_like(voltage, p["temperature_K"]),
    }
    density = densities(xp.stack([values[name] for name in FIELDS], axis=1), {"F": F, "R": R}, xp)
    cycles = -density[:, 0] / 3 * p["area_m2"] * 1e15
    leak = ghk_leak(
        ci,
        co,
        voltage[:, None],
        p["valence"],
        p["temperature_K"],
        p["area_m2"][:, None],
        p["permeability_m_s"],
        control[1],
        xp=xp,
    )
    flux = leak + cycles[:, None] * p["pump_stoichiometry"]
    affinity = p["chemical_drive"] + xp.sum(p["pump_stoichiometry"] * mu, axis=-1)
    dissipated = -0.001 * (xp.sum(leak * mu, axis=-1) + cycles * affinity)
    return xp.concatenate(
        (flux.reshape(-1), -xp.sum(flux, axis=0), leak.reshape(-1), cycles, dissipated)
    )


def numpy_rollout(case, dt, inputs, initial=None):
    import numpy as np

    p, n = parameters(case, np), len(case["volume_pL"])
    state = np.zeros(8 * n + 3) if initial is None else np.asarray(initial).copy()
    states = [state.copy()]
    for control in np.asarray(inputs):

        def slope(y, control=control):
            if not bool(valid(y, p, xp=np)):
                raise ValueError("Invalid NumPy RK4 trial; no state repair")
            value = rhs(y, control, p, xp=np)
            if not np.isfinite(value).all():
                raise ValueError("Nonfinite candidate rate")
            return value

        a = slope(state)
        b = slope(state + dt / 2 * a)
        c = slope(state + dt / 2 * b)
        d = slope(state + dt * c)
        state = state + dt / 6 * (a + 2 * b + 2 * c + d)
        if not bool(valid(state, p, xp=np)):
            raise ValueError("Invalid NumPy endpoint")
        states.append(state.copy())
    return np.asarray(states)


def jax_rollout(case, dt, inputs, initial=None):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.numerics.fixed_step import rk4_checked_step

    if not jax.config.x64_enabled or jax.default_backend() != "cpu" or jax.config.jax_disable_jit:
        raise ValueError("Coupled candidate requires enabled JIT / CPU float64")
    p, n = parameters(case, jnp), len(case["volume_pL"])
    state = jnp.zeros(8 * n + 3) if initial is None else jnp.asarray(initial)

    def rate(y, u, p, active):
        return rhs(y, u, p, active, xp=jnp)

    def domain(y, p, active):
        return valid(y, p, active, xp=jnp)

    @jax.jit
    def evolve(y, controls):
        def step(carry, control):
            old, previous_ok = carry
            new, ok = rk4_checked_step(rate, domain, old, dt, control, p, None)
            return (new, previous_ok & ok), new

        return jax.lax.scan(step, (y, jnp.asarray(True)), controls)

    (_, ok), states = evolve(state, jnp.asarray(inputs))
    if not bool(ok):
        raise ValueError("Compiled RK4 trial rejected; no state repair")
    return np.asarray(jnp.concatenate((state[None, :], states), axis=0))
