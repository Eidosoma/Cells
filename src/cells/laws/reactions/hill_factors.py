"""Hill activation and inhibition factors in log space (a neutral helper).

The factor forms of the shared-inventory reactions design (D152,
docs/SHARED_INVENTORY_REACTIONS_DESIGN.md
§2.2) and of the inventory-coupling design (docs/INVENTORY_COUPLING_DESIGN.md §1.3):

    activation  f = x^n / (K^n + x^n) = 1 / (1 + e^(-z))
    inhibition  f = K^n / (K^n + x^n) = 1 / (1 + e^(z)),     z = n (ln x - ln K),

with x a concentration (mM), K > 0 the half-saturation (mM) and n > 0 the Hill coefficient
(Hill 1910; Weiss 1997; Keener & Sneyd 2009, ch. 1). In log space, ln f = -logaddexp(0, -z) or
-logaddexp(0, z), finite at a trace concentration and at large x.

`log_factor` agrees bit for bit with cells.operator.local_species_reactions@1's factors (operators/
species_reactions.py, route_rates; tests/unit/test_hill_factors.py checks it against that
operator's own rates). Since 23 November 2026 that operator evaluates one branch at its declared
factors only, -logaddexp(0, s z) with s = -1 on an activation and +1 on an inhibition: s z is -z
or z exactly, so each ln f is this function's two-branch value, and the padding's 0 is placed.
cells.operator.species_regulated_availability@1 uses this helper; D152's operator keeps its inline expression
until its next version adopts the helper under crossrev (the lead's ruling 7, 14 November 2026).
"""

ACTIVATION = 1
INHIBITION = 2
KINDS = {"hill_activation": ACTIVATION, "hill_inhibition": INHIBITION}


def log_factor(log_x, half_saturation_mM, coefficient, kind, *, xp):
    """ln f elementwise: kind ACTIVATION or INHIBITION, 0 (f = 1) for any other kind (padding).

    log_x: ln of the concentration in mM; half_saturation_mM and coefficient broadcast with it.
    """
    z = coefficient * (log_x - xp.log(half_saturation_mM))
    return xp.where(
        kind == ACTIVATION,
        -xp.logaddexp(0.0, -z),
        xp.where(kind == INHIBITION, -xp.logaddexp(0.0, z), 0.0),
    )


def factor(log_x, half_saturation_mM, coefficient, kind, *, xp):
    """f = exp(ln f) elementwise (1 exactly for padding: exp(0) = 1)."""
    return xp.exp(log_factor(log_x, half_saturation_mM, coefficient, kind, xp=xp))
