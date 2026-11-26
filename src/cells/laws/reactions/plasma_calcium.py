"""The calcium pump's kernel at a plasma membrane, on positive concentrations.

laws/pumps/ca_atp_mass_action_positive.py evaluates it. The one-calcium form with its numeric-mM ATP
quotient is BETSE v1.5.0's pumpCaATP (betse/science/sim_toolbox.py; docs/PLASMA_CALCIUM.md).
Positive cycles move Ca out. The exchange that was here is a cycle law of its own
(laws/cycles/sodium_calcium_exchange_symmetric_barrier.py).
"""

import jax.numpy as jnp

from cells.laws.reactions import er_calcium

MAX_VOLTAGE = 0.15


def pump_rates(ci, co, voltage, temperature, p, availability, *, xp=jnp):
    # ER voltage is destination minus source. Plasma Vm is inside minus outside.
    return er_calcium.pump_rates(ci, co, -voltage, temperature, p, availability, xp=xp)
