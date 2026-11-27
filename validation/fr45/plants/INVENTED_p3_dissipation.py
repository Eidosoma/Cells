"""INVENTED, development only (the format sample's INVENTED-W1p-P3~check): P3's mechanism, and each step's site heat
booked negative, with the site free energy the energy ledger reads moved by twice the booked heat, so that ledger
stays closed and the dissipation check is the one that refuses. No registered run takes it."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import p3
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P3"
CHANGE = "INVENTED: P3's mechanism, and each step's site heat booked negative (the energy ledger kept closed)"


def apply():
    p3.apply()
    booking, energy = so.node_booking, so.site_energy

    def planted_booking(*args, xp, **kwargs):
        heat_cell, heat_outside, heated_cell, heated_outside = booking(*args, xp=xp, **kwargs)
        return -heat_cell, -heat_outside, heated_cell, heated_outside

    def planted_energy(row, p, *, xp):
        g, terms = energy(row, p, xp=xp)
        heat = xp.sum(row.site_dissipated_energy_pJ) + xp.sum(row.site_outside_dissipated_energy_pJ)
        return g - 2.0 * heat, terms + 2.0 * xp.abs(heat)

    so.node_booking = planted_booking
    so.site_energy = planted_energy
