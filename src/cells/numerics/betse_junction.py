"""Dynamic junctions in the pinned spatial pump/channel compatibility model.

BETSE 1.5.0 advances the stored junction opening once per moving ion, using
the outer timestep each time, and applies blocking to that stored value.
This explicit compatibility component preserves those semantics. The separate
physical-time junction process keeps its existing clock and availability law.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.numerics import betse_active as active
from cells.numerics import betse_spatial as passive
from cells.processes import junction_gate

MODEL_ID = "betse_spatial_nak_kv1p5_dynamic_gj@1"


class Layout(NamedTuple):
    active: active.Layout
    junction: junction_gate.Parameters
    junction_block: object
    moving_order: object


class State(NamedTuple):
    active: active.State
    junction_open: object


class Control(NamedTuple):
    pump: object
    channel: object
    junction: object


class Rates(NamedTuple):
    active: active.Rates
    junction_after_ion: object


def validate_layout(layout):
    p = Layout(
        active.validate_layout(layout.active),
        junction_gate.Parameters(*(np.asarray(v) for v in layout.junction)),
        np.asarray(layout.junction_block),
        np.asarray(layout.moving_order),
    )
    t = p.active.tissue
    moving = np.flatnonzero(t.moving)
    if (
        p.moving_order.shape != moving.shape
        or p.moving_order.dtype.kind not in "iu"
        or not np.array_equal(np.sort(p.moving_order), moving)
    ):
        raise ValueError("Moving order must contain each moving species exactly once")
    for name, value, upper in (
        ("threshold", p.junction.threshold_voltage_V, junction_gate.MAX_ABS_VOLTAGE_V),
        ("minimum", p.junction.minimum_open_fraction, 1),
        ("block", p.junction_block, 1),
    ):
        if (
            value.shape != t.membrane_area.shape
            or not np.isfinite(value).all()
            or np.any((value < 0) | (value > upper))
            or not np.array_equal(value, value[t.partner])
        ):
            raise ValueError("Invalid reciprocal junction " + name)
    if not np.isin(t.junction_open, (0, 1)).all():
        raise ValueError("Dynamic junction layout requires a binary transport mask")
    return p


def initial_state(state, layout, opening):
    opening = np.asarray(opening, dtype=np.float64)
    if opening.shape != layout.junction_block.shape or not np.array_equal(
        opening, opening[layout.active.tissue.partner]
    ):
        raise ValueError("Initial junction state must match reciprocal patches")
    value = State(state, opening.copy())
    if not domain_valid(value, xp=np):
        raise ValueError("Invalid initial dynamic junction state")
    return value


def domain_valid(state, *, xp=jnp):
    gate = state.junction_open
    # Stored-state blocking permits values below the intrinsic minimum.
    return active.domain_valid(state.active, xp=xp) & xp.all(
        xp.isfinite(gate) & (gate >= 0) & (gate <= 1)
    )


def gate_step(gate, voltage, block, dt, parameters, *, xp=jnp):
    rates = junction_gate.kinetics(voltage, parameters, xp=xp)
    opening = (
        gate + dt * (rates.alpha_per_s + rates.beta_per_s * parameters.minimum_open_fraction)
    ) / (1 + rates.alpha_per_s * dt + rates.beta_per_s * dt)
    return opening * block


def step(state, p, dt, control, *, xp=jnp):
    tissue = p.active.tissue
    field = passive.field(state.active.tissue, tissue, xp=xp)
    vm = field.membrane_voltage_V
    voltage = vm[tissue.partner] - vm
    block = p.junction_block * control.junction
    opening, calls = state.junction_open, []
    weights = xp.zeros_like(tissue.junction_permeability)
    species = xp.arange(tissue.valence.size)[:, None]
    for index in range(p.moving_order.size):
        opening = gate_step(opening, voltage, block, dt, p.junction, xp=xp)
        calls.append(opening)
        weights = weights + (species == p.moving_order[index]) * opening
    effective = p.active._replace(
        tissue=tissue._replace(junction_permeability=tissue.junction_permeability * weights),
        pump_available=p.active.pump_available * control.pump,
        channel_permeability=p.active.channel_permeability * control.channel,
    )
    trial, rates, valid = active.step(state.active, effective, dt, xp=xp)
    candidate = State(trial, opening)
    valid &= domain_valid(state, xp=xp) & domain_valid(candidate, xp=xp)
    valid &= xp.all(xp.isfinite(voltage) & (xp.abs(voltage) <= junction_gate.MAX_ABS_VOLTAGE_V))
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v) & (v >= 0) & (v <= 1)) for v in control]))
    valid &= xp.all(control.junction == control.junction[tissue.partner])
    valid &= xp.all(state.junction_open == state.junction_open[tissue.partner])
    return (
        jax.tree.map(lambda new, old: xp.where(valid, new, old), candidate, state),
        Rates(rates, xp.stack(calls)),
        valid,
    )


def trajectory(state, p, dt, controls):
    def one(carry, control):
        old, accepted = carry
        trial, rates, valid = step(old, p, dt, control)
        accepted &= valid
        new = jax.tree.map(lambda a, b: jnp.where(accepted, a, b), trial, old)
        return (new, accepted), (new, rates, accepted)

    (final, valid), history = jax.lax.scan(one, (state, jnp.asarray(True)), controls)
    return final, history, valid


def trajectories(states, layouts, dt, controls):
    return jax.lax.map(
        lambda args: trajectory(args[0], args[1], dt, args[2]), (states, layouts, controls)
    )
