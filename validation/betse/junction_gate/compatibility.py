"""Explicit pinned-native adapter; never selected as the physical-time law."""

import numpy as np

from cells.processes import junction_gate as physical


def class_initialization(voltage, block, parameters, *, xp=np):
    rates = physical.kinetics(voltage, parameters, xp=xp)
    # Native writes this to the gate object, not sim.gjopen; can exceed one.
    return block * (rates.alpha_per_s / rates.relaxation_per_s + parameters.minimum_open_fraction)


def step(gate, voltage, block, dt_s, parameters, *, xp=np):
    rates = physical.kinetics(voltage, parameters, xp=xp)
    # Each actual call consumes a full outer dt and blocking overwrites the
    # stored conductance. A fractional block has no ordinary fixed continuous
    # time limit as dt tends to zero; do not call this physical availability.
    return (
        block
        * (gate + dt_s * (rates.alpha_per_s + rates.beta_per_s * parameters.minimum_open_fraction))
        / (1 + dt_s * rates.relaxation_per_s)
    )
