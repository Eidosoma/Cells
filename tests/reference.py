"""Closed-form oracle of two cells exchanging through one contact; outside simulator code and JAX.

Without reactions each species only moves through the contact, at P s(t) (a1/V1 - a2/V2) with P its
permeability and s the piecewise-constant open fraction. The total N = a1 + a2 is constant, so the
first cell's amount relaxes to its share N V1 / (V1 + V2) at the rate P s (1/V1 + 1/V2): its
distance from the share has shrunk by exp(-P (1/V1 + 1/V2) S(t)), S the integral of s.
"""

import numpy as np


def opened(spec, time):
    """S(time), the integral of the contact's open fraction from 0."""
    changes = spec.experiment.contact
    ends = [*(c.time for c in changes[1:]), time]
    return sum(
        c.open_fractions[0] * (min(end, time) - c.time)
        for c, end in zip(changes, ends, strict=True)
        if c.time < time
    )


def exact_exchange(spec, requested):
    """(amount [time, species, cell], transferred [time, species]) at the requested times; the
    contact runs from the first cell to the second, and transferred is positive that way."""
    model, (contact,) = spec.model, spec.model.contacts
    assert (contact.from_cell_id, contact.to_cell_id) == model.cell_ids
    assert not any(model.forward_rate) and not any(model.reverse_rate)
    first, second = np.asarray(model.initial_amounts, dtype=float).T
    v1, v2 = model.volumes
    share = (first + second) * v1 / (v1 + v2)
    rate = np.asarray(contact.permeability) * (1 / v1 + 1 / v2)
    moved = np.array(
        [(first - share) * -np.expm1(-rate * opened(spec, float(t))) for t in requested]
    )
    return np.stack([first - moved, second + moved], axis=-1), moved
