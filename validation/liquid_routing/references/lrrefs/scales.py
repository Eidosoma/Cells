"""LAWS section 9's counts and READOUTS section 2's scales: the expected tolerances of the plants, and the bounds of
check 11. Nothing here reads a run.
"""

from . import propagator as pr
from .arith import ONE, U, ZERO, exact


def m_flow(world):
    """m_n (and m_V): 2 (H + 18)."""
    return 2 * (world.holder_count + 18)


M_FACE = 40            # m_f, a face step
M_DEFAULT = M_FACE + 50    # m_4, the default heat
M_T3 = M_FACE + 24         # T3 and arm 2's exact heat against its own rows


def m_label(world):
    """m_q: 6H + 106."""
    return 6 * world.holder_count + 106


def m_heat(world):
    """m_h: 24 + 2H (N + 1)."""
    return 24 + 2 * world.holder_count * (world.species_count + 1)


def total_amount(world, species, time):
    """N_x: the species' total amount in the world to that time, start plus supplied (portions too)."""
    total = world.start_total(species) + pr.supplied(world, species, time)
    for event in world.events:
        if event["kind"] == "delivery" and exact(event["time_s"]) < time:
            level = world.inlet_level(event["inlet"], species, exact(event["time_s"]))
            total += exact(event["volume_pL"]) * level
    return total


def heat_scale(world, time):
    """s_F = RT (Lambda + 1) sum_x N_x."""
    return world.rt * (world.largest_log() + ONE) * sum((total_amount(world, x, time) for x in world.species), ZERO)


def rounding(count, steps, scale):
    """e_round = m (S + 1) u s."""
    return count * (steps + 1) * U * scale
