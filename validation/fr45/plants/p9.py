"""P9 (C9): a population's occupied fraction B_b / (B_b + R_s) (CRITERIA:129). Seam: site_occupancy.occupied_fraction."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P9"
CHANGE = "occupied_fraction: B_b / (B_b + R_s)"


def apply():
    def planted(B, R, p, *, xp):
        total = B + R[p.site_set_of]
        return B / xp.where(total > 0, total, 1.0)

    so.occupied_fraction = planted
