"""Pinned driver recurrence with lagged face concentrations; validation only."""

import importlib.util
from pathlib import Path

import numpy as np

from cells.processes.junction_gate import Parameters

_spec = importlib.util.spec_from_file_location(
    "native_gate_compatibility", Path(__file__).parents[1] / "junction_gate/compatibility.py"
)
gate_adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_adapter)


def replay(c, protocol, dt, backend):
    """Evolve from initial data only; no native trajectory samples enter this solve."""
    import jax
    import jax.numpy as xp

    device = jax.devices(backend)[0]
    arrays = {k: jax.device_put(v, device) for k, v in c.items() if isinstance(v, np.ndarray)}
    concentration0, volume, cap = (
        arrays[k] for k in ("initial_concentration_mM", "volume_pL", "capacitance_F")
    )
    sender, receiver, incidence = (arrays[k] for k in ("senders", "receivers", "incidence"))
    z = arrays["valence"][:, None]
    params = Parameters(protocol["threshold_voltage_V"], protocol["minimum_open_fraction"])
    coefficient = arrays["edge_area_m2"] * arrays["permeability_m_s"] * 1e15
    blocks = arrays["opening"] * c["block"]
    e = len(c["opening"])
    n = round(protocol["duration_s"] / dt)

    def step(state, unused):
        current, concentration, gate, transferred, dissipated = state
        delta = (current - concentration0) * volume
        voltage = arrays["initial_voltage_V"] + c["F"] * 1e-15 / cap * xp.sum(z * delta, axis=0)
        dv = voltage[sender] - voltage[receiver]
        ca, cb = concentration[:, sender], concentration[:, receiver]
        x = z * c["F"] * dv / (c["R"] * c["temperature_K"])
        small = xp.abs(x) < 1e-5
        safe = xp.where(small, 1.0, x)
        bernoulli = xp.where(small, 1 - x / 2 + x**2 / 12 - x**4 / 720, safe / xp.expm1(safe))
        ungated = coefficient * ((bernoulli + x) * ca - bernoulli * cb)
        fluxes = []
        for i in range(len(c["species"])):
            gate = gate_adapter.step(gate, dv, blocks, dt, params, xp=xp)
            fluxes.append(ungated[i] * gate)
        flux = xp.stack(fluxes)
        mu = c["R"] * c["temperature_K"] * xp.log(cb / ca) - z * c["F"] * dv
        # BETSE adds a rounded concentration increment to the full stored
        # concentration on every update. Accumulating tiny amount deltas avoids
        # that rounding and changes the subsequent voltage/gate trajectory.
        # Keep the addition separate from multiplication on CPU and GPU.
        change = jax.lax.optimization_barrier(dt * ((flux @ incidence.T) / volume))
        answer = (
            current + change,
            current,
            gate,
            transferred + dt * flux,
            dissipated - dt * 1e-3 * xp.sum(flux * mu, axis=0),
        )
        return answer, answer

    with jax.default_device(device):
        initial = (
            concentration0,
            concentration0,
            xp.full(e, protocol["initial_gate"]),
            xp.zeros_like(arrays["permeability_m_s"]),
            xp.zeros(e),
        )
        _, history = jax.jit(lambda s: jax.lax.scan(step, s, None, length=n))(initial)
    combined = [
        np.concatenate((np.asarray(a)[None], np.asarray(b)))
        for a, b in zip(initial, history, strict=True)
    ]
    concentration, lagged_concentration, gate, transferred, dissipated = combined
    initial_host, volume_host = c["initial_concentration_mM"], c["volume_pL"]
    delta = (concentration - initial_host) * volume_host
    lagged = (lagged_concentration - initial_host) * volume_host
    values = np.concatenate(
        (delta.reshape(n + 1, -1), transferred.reshape(n + 1, -1), dissipated, gate), axis=-1
    )
    return (
        values,
        lagged,
        {"device": str(device), "platform": device.platform, "dtype": str(history[0].dtype)},
    )
