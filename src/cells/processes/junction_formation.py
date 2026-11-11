"""delayed_first_order_junction_formation@1: junction abundance after a cell replacement.

A newcomer arrives without gap junction channels to its neighbours: the departing
cell's plaques leave whole (annular junctions, Jordan et al. 2001 J Cell Sci
114:763; Piehl et al. 2007 Mol Biol Cell 18:337) and new channels form from
connexons docking at plaque margins (Lauf et al. 2002 PNAS 99:10446). Coupling
appears after minutes and grows over tens of minutes (Rook et al. 1990 J Membr
Biol 118:179; Johnson et al. 1974 PNAS 71:4536); connexin half-lives of 1.3-5 h
bound de novo formation (Beardslee et al. 1998 Circ Res 83:629; Fallon and
Goodenough 1981 J Cell Biol 90:521). Sources and ranges:
/mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md.

The law is a declared delay followed by first-order growth of the relative
abundance A of a junction's channels towards 1 (the junction's declared
conductance):

    A(age) = 1 - (1 - A0) exp(-max(0, age - lag) / tau)

with A0 the abundance at arrival. The state is (lag remaining, deficit 1 - A),
both zero for a formed junction, so a world without replacements holds exact
zeros. advance() is the exact solution over an interval; nothing is integrated
numerically. The shape is a modelling choice loosely consistent with the cited
time courses, not a fit.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

LAW_ID = "delayed_first_order_junction_formation@1"


class Parameters(NamedTuple):
    """Scalars (or arrays broadcast over edges)."""

    initial_abundance: Any  # A0 in [0, 1]
    lag_s: Any  # >= 0
    time_constant_s: Any  # > 0


def arrival(parameters, *, xp=jnp):
    """(lag remaining, deficit) of a junction at a replacement."""
    return xp.asarray(parameters.lag_s), 1.0 - xp.asarray(parameters.initial_abundance)


def advance(lag, deficit, interval_s, parameters, *, xp=jnp):
    """Exact (lag, deficit) after interval_s: the lag elapses first, then the deficit decays.

    A formed junction (lag 0, deficit 0) stays exactly formed.
    """
    remaining = xp.maximum(lag - interval_s, 0.0)
    growing = xp.maximum(interval_s - lag, 0.0)
    return remaining, deficit * xp.exp(-growing / parameters.time_constant_s)


def abundance(deficit):
    return 1.0 - deficit


def closed_form(age_s, parameters, *, xp=jnp):
    """A at a time age_s after arrival (the reference form of advance)."""
    a0, lag, tau = parameters
    return 1.0 - (1.0 - a0) * xp.exp(-xp.maximum(age_s - lag, 0.0) / tau)


def domain_valid(lag, deficit, *, xp=jnp):
    return (
        xp.all(xp.isfinite(lag))
        & xp.all(lag >= 0)
        & xp.all(xp.isfinite(deficit))
        & xp.all((deficit >= 0) & (deficit <= 1))
    )
