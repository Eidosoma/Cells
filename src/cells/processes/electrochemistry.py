"""Pure dimensioned membrane laws, independent of layouts, schedules, and solvers.

Na/K/Cl selection and owner accumulation belong to the composing model. Callers
must supply valid positive concentrations and finite neutral padding BEFORE these
laws. The engine refuses invalid trials; these functions never floor or clip them.
"""

import jax.numpy as jnp

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
MOL_PER_FMOL = 1e-15
M3_PER_PL = 1e-15
CHARGE_PER_FMOL = F * MOL_PER_FMOL


def bernoulli(x, *, xp=jnp):
    """x/expm1(x), including a differentiable, mask-safe removable singularity."""
    small = xp.abs(x) < 1e-4
    # Both alternatives are evaluated by array backends: no masked 0/0.
    regular_x = xp.where(small, 1.0, x)
    series_x = xp.where(small, x, 0.0)
    series = 1 - series_x / 2 + series_x**2 / 12 - series_x**4 / 720
    return xp.where(small, series, regular_x / xp.expm1(regular_x))


def electrochemical_potential(ci, co, voltage, valence, temperature, *, xp=jnp):
    # Difference of logarithms avoids overflow/underflow of a concentration ratio.
    return R * temperature * (xp.log(ci) - xp.log(co)) + valence * F * voltage


def ghk_leak(ci, co, voltage, valence, temperature, area, permeability, multiplier, *, xp=jnp):
    x = valence * F * voltage / (R * temperature)
    return (
        area
        * permeability
        * multiplier
        / MOL_PER_FMOL
        * (co * bernoulli(x, xp=xp) - ci * bernoulli(-x, xp=xp))
    )


def reversible_pump(delta_mu, stoichiometry, drive, temperature, capacity, multiplier, *, xp=jnp):
    """Phenomenological reference law, not a calibrated ATPase kinetic model.

    Species occupy the penultimate axis; remaining axes are independent routes.
    Returns signed cycles/s and J/mol cycles, not an amount or energy state.
    """
    cycle_energy = drive + xp.sum(stoichiometry * delta_mu, axis=-2)
    cycles = capacity * multiplier * xp.tanh(-cycle_energy / (2 * R * temperature))
    return cycles, cycle_energy
