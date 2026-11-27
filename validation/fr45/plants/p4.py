"""P4 (C7): the free-site load taken per population, not summed over the set, in the compiled step and the host
report alike (CRITERIA:124). Seam: site_occupancy.stage_loads."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P4"
CHANGE = "stage_loads: L_R per population, not summed over its set"


def apply():
    honest = so.stage_loads

    def planted(n, member_free, c, vol, mb, p, *, xp):
        load_n, _, load_b = honest(n, member_free, c, vol, mb, p, xp=xp)
        return load_n, mb * p.site_on_rate * c, load_b

    so.stage_loads = planted
