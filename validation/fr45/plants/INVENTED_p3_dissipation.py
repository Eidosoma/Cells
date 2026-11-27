"""INVENTED, development only (the format sample's INVENTED-W1p-P3~check): P3's mechanism, and each step's site heat
booked negative, which the dissipation check refuses. No registered run takes it."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import p3
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P3"
CHANGE = "INVENTED: P3's mechanism, and each step's site heat booked negative"


def apply():
    p3.apply()
    honest = so.node_booking

    def planted(*args, xp, **kwargs):
        heat_cell, heat_outside, heated_cell, heated_outside = honest(*args, xp=xp, **kwargs)
        return -xp.abs(heat_cell) - 1.0, -xp.abs(heat_outside) - 1.0, heated_cell, heated_outside

    so.node_booking = planted
