"""P7 (C5, C1): a set's free-site change taken from its first population only (CRITERIA:127). Seam:
site_occupancy.set_free_change."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P7"
CHANGE = "set_free_change: dR from each set's first population only"


def first_members(p, xp):
    """[population] whether a population is the first of its set."""
    of = p.site_set_of
    idx = xp.arange(of.shape[0])
    earlier = (of[None, :] == of[:, None]) & (idx[None, :] < idx[:, None])
    return ~xp.any(earlier, axis=1)


def apply():
    def planted(dbound, p, *, xp):
        first = first_members(p, xp)
        return -so._scatter(xp.where(first, dbound, 0.0), p.site_set_of, p.site_set_capacity_fmol.shape[0], xp=xp)

    so.set_free_change = planted
