"""cells.transfer_factor.ph_conditioned_factor@1: the pH factor FR-5's routing door applies to a transfer's rate.

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §8–§9. A transfer across a compartment's bounding patch is
open when the compartment is acidic:

    f(pH) = 1 / (1 + 10^(m (pH - pH50))),     m > 0 (the Hill slope in pH units),

so f = 1/2 at pH50, f -> 1 below it and f -> 0 above it. The pH is the compartment's free proton
read through its closure (cells.kind.rapid_proton_buffer@1). The routing door combines factors by `multiply`
in declared order (d x f where both are declared); a factor outside [0, 1] refuses the step. The
factor books nothing; the route it scales (cells.route.passive_neutral_permeation@1 for a neutral cargo) books
material and heat.

Pure functions in the xp style of processes/.
"""

import jax.numpy as jnp

LAW_ID = "cells.transfer_factor.ph_conditioned_factor@1"
LN10 = 2.302585092994046


def factor(ph, ph50, slope, *, xp=jnp):
    """f(pH) in [0, 1], as 1/(1 + e^x) = (1 - tanh(x/2))/2 with x = ln 10 m (pH - pH50)."""
    x = slope * (ph - ph50) * LN10
    return 0.5 * (1.0 - xp.tanh(x / 2.0))


def factor_valid(ph, ph50, slope, *, xp=jnp):
    """A finite pH, a finite pH50 and a positive finite slope."""
    return xp.isfinite(ph) & xp.isfinite(ph50) & xp.isfinite(slope) & (slope > 0)


def combine(factors, *, xp=jnp):
    """The routing door's `multiply` in declared order, with its [0, 1] check: (value, valid)."""
    value = 1.0
    valid = True
    for f in factors:
        valid = valid & xp.isfinite(f) & (f >= 0) & (f <= 1)
        value = value * f
    return value, valid
