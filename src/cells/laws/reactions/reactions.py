"""First-order reversible conversion between two explicitly supplied amount fields."""

import jax.numpy as jnp


def reversible_rate(first_amount, second_amount, forward_rate, reverse_rate, active):
    """Signed net amount/time; no knowledge of species labels, topology, or assays."""
    return jnp.where(active, forward_rate * first_amount - reverse_rate * second_amount, 0.0)
