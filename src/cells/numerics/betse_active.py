"""Pinned spatial BETSE order with Na/K ATPase and one Kv1p5 population.

Separate compatibility component, not the resolved thermodynamic model. Pump
and ordinary membrane fluxes use lagged membrane concentrations. The dynamic
channel uses bulk cell and post-diffusion exterior concentrations, transfers
material first, then ordinary membrane/junction transfers complete the step.
Metabolic pools are maintained inputs, not a finite ATP or energy balance.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.numerics import betse_spatial as passive
from cells.processes import kinetic_pump, voltage_gates
from cells.processes.electrochemistry import electrochemical_potential, ghk_leak

MODEL_ID = "betse_spatial_nak_kv1p5@1"


class Layout(NamedTuple):
    tissue: passive.Layout
    pump: kinetic_pump.Parameters
    sodium_index: object
    potassium_index: object
    pump_available: object
    channel_permeability: object


class State(NamedTuple):
    tissue: passive.State
    m_gate: object
    h_gate: object
    pump_cycles_fmol: object
    channel_inward_fmol: object


class Rates(NamedTuple):
    ordinary: passive.Rates
    pump_cycles_fmol_s: object
    channel_inward_fmol_s: object


def validate_layout(layout):
    tissue = passive.validate_layout(layout.tissue)
    p = Layout(
        tissue,
        kinetic_pump.Parameters(*(np.asarray(x) for x in layout.pump)),
        *(np.asarray(x) for x in layout[2:]),
    )
    m, s = tissue.membrane_area.size, tissue.valence.size
    for name in ("sodium_index", "potassium_index"):
        index = getattr(p, name)
        if index.shape != () or index.dtype.kind not in "iu" or not 0 <= index < s:
            raise ValueError("Invalid active species index")
        if tissue.valence[index] != 1 or not tissue.moving[index]:
            raise ValueError("Active Na/K species must be moving monovalent cations")
    if p.sodium_index == p.potassium_index:
        raise ValueError("Na/K roles must be distinct")
    for name, value in list(p.pump._asdict().items()) + [
        ("pump_available", p.pump_available),
        ("channel_permeability", p.channel_permeability),
    ]:
        if value.shape != (m,) or not np.isfinite(value).all():
            raise ValueError("Invalid active patch parameter: " + name)
    if np.any(p.pump.capacity_fmol_s < 0) or np.any(p.channel_permeability < 0):
        raise ValueError("Active transport capacity must be nonnegative")
    if any(np.any(v <= 0) for v in p.pump[1:-1]):
        raise ValueError("Pump substrates and Km must be positive")
    if np.any((p.pump_available < 0) | (p.pump_available > 1)):
        raise ValueError("Pump availability must be in [0,1]")
    if tissue.temperature != voltage_gates.TEMPERATURE_K:
        raise ValueError("Compatibility Kv1p5 panel uses 298.15 K")
    return p


def initial_state(tissue, p, m_gate, h_gate):
    gates = [np.asarray(v, dtype=np.float64) for v in (m_gate, h_gate)]
    if any(v.shape != p.tissue.membrane_area.shape for v in gates):
        raise ValueError("Initial gate shape")
    state = State(tissue, *gates, np.zeros_like(gates[0]), np.zeros_like(gates[0]))
    if not domain_valid(state, xp=np):
        raise ValueError("Invalid active initial state")
    return state


def domain_valid(state, *, xp=jnp):
    return (
        passive.domain_valid(state.tissue, xp=xp)
        & xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in state[1:]]))
        & xp.all((state.m_gate >= 0) & (state.m_gate <= 1))
        & xp.all((state.h_gate >= 0) & (state.h_gate <= 1))
    )


def step(state, p, dt, *, xp=jnp):
    t, old = p.tissue, state.tissue
    cells, outside = passive.ownership(t, xp=xp)
    ordinary, reset, delta, field = passive.transport(old, t, dt, xp=xp)
    vm, na, k = field.membrane_voltage_V, p.sodium_index, p.potassium_index
    cin, cout = old.membrane_concentration, old.outside_concentration[:, t.outside_owner]
    mu_na = electrochemical_potential(cin[na], cout[na], vm, 1, t.temperature, xp=xp)
    mu_k = electrochemical_potential(cin[k], cout[k], vm, 1, t.temperature, xp=xp)
    cycles = (
        kinetic_pump.kinetics(
            cin[na], cout[k], mu_na, mu_k, t.temperature, p.pump, p.pump_available, xp=xp
        ).cycles_fmol_s
        * t.membrane_open
    )
    species = xp.arange(t.valence.size)[:, None]
    pump_flux = (-3 * (species == na) + 2 * (species == k)) * cycles
    membrane = ordinary.membrane_inward_fmol_s + pump_flux
    ordinary = ordinary._replace(membrane_inward_fmol_s=membrane)

    targets, tau = voltage_gates.kinetics(vm, xp=xp)
    gates = (tau * xp.stack((state.m_gate, state.h_gate)) + dt * targets) / (tau + dt)
    after_ecm = (reset + delta).reshape(old.outside_concentration.shape)
    channel = ghk_leak(
        old.cell_concentration[k, t.cell_owner],
        after_ecm[k, t.outside_owner],
        vm,
        1,
        t.temperature,
        t.membrane_area,
        p.channel_permeability,
        gates[0] * gates[1],
        xp=xp,
    )
    # Native network channels do not apply cluster_open's boundary membrane mask.
    # The channel population's permeability is its independently declared control.
    channel_flux = (species == k) * channel
    voxel_fmol = t.height * t.spacing**2 * 1e15
    after_channel = old.cell_concentration + dt * (channel_flux @ cells.T) / (t.cell_volume * 1e15)
    outside_channel = after_ecm - dt * (channel_flux @ outside.T) / voxel_fmol
    after_membrane = after_channel + dt * (membrane @ cells.T) / (t.cell_volume * 1e15)
    gap = ordinary.junction_outward_fmol_s
    tissue = passive.State(
        after_membrane - dt * (gap @ cells.T) / (t.cell_volume * 1e15),
        xp.where(t.moving[:, None], after_membrane[:, t.cell_owner], old.membrane_concentration),
        outside_channel - dt * (membrane @ outside.T) / voxel_fmol,
        old.membrane_inward_fmol + dt * membrane,
        old.junction_outward_fmol + dt * gap,
        old.reservoir_reset_fmol
        + ((reset - old.outside_concentration.reshape(reset.shape)) * voxel_fmol).reshape(
            old.outside_concentration.shape
        ),
        old.stencil_exchange_fmol + (delta * voxel_fmol).reshape(old.outside_concentration.shape),
        old.step_count + 1,
        old.elapsed_s + dt,
    )
    candidate = State(
        tissue,
        gates[0],
        gates[1],
        state.pump_cycles_fmol + dt * cycles,
        state.channel_inward_fmol + dt * channel,
    )
    rates = Rates(ordinary, cycles, channel)
    valid = domain_valid(state, xp=xp) & domain_valid(candidate, xp=xp) & xp.isfinite(dt) & (dt > 0)
    lo, hi = voltage_gates.VOLTAGE_DOMAIN_V
    valid &= xp.all((vm >= lo) & (vm <= hi))
    valid &= xp.all(after_channel > 0) & xp.all(outside_channel > 0) & xp.all(after_membrane > 0)
    valid &= xp.all(
        kinetic_pump.domain_valid(
            cin[na], cout[k], mu_na, mu_k, t.temperature, p.pump, p.pump_available, xp=xp
        )
    )
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in jax.tree.leaves((rates, field))]))
    return (
        jax.tree.map(lambda new, prior: xp.where(valid, new, prior), candidate, state),
        rates,
        valid,
    )


def trajectory(state, p, dt, steps):
    def one(carry, _):
        old, ok = carry
        trial, rates, valid = step(old, p, dt)
        ok &= valid
        new = jax.tree.map(lambda x, y: jnp.where(ok, x, y), trial, old)
        return (new, ok), (new, rates, ok)

    (final, valid), history = jax.lax.scan(one, (state, jnp.asarray(True)), None, length=steps)
    return final, history, valid


def trajectories(states, layouts, dt, steps):
    return jax.lax.map(lambda args: trajectory(args[0], args[1], dt, steps), (states, layouts))
