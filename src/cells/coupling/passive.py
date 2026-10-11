"""Passive amount exchange on a fixed, host-validated contact graph.

Permeability has units volume/time. Each oriented edge flux is calculated once;
scatter applies its negative to the sender and positive to the receiver. Edge
orientation is an accounting convention, not a one-way physical channel.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp


class ContactParameters(NamedTuple):
    volume: jax.Array
    senders: jax.Array
    receivers: jax.Array
    permeability: jax.Array
    contact_active: jax.Array


def edge_flux(amount, open_fraction, parameters, cell_active, *, xp=jnp):
    """Return signed amount/time, with optional leading observation/batch axes.

    Inputs must have finite neutral padding and resolved in-bounds indices.
    Biological control of open_fraction is NOT supplied by this passive law.
    """
    concentration = amount / parameters.volume
    connected = (
        parameters.contact_active
        & cell_active[parameters.senders]
        & cell_active[parameters.receivers]
    )
    conductance = xp.where(connected, parameters.permeability * open_fraction, 0.0)
    difference = concentration[..., parameters.senders] - concentration[..., parameters.receivers]
    return xp.where(conductance != 0, conductance * difference, 0.0)


def scatter_exchange(flux, senders, receivers, like_amount):
    """Accumulate all edges on the last (cell) axis, retaining any leading axes."""
    changes = jnp.zeros_like(like_amount)
    changes = changes.at[..., senders].add(-flux)
    return changes.at[..., receivers].add(flux)
