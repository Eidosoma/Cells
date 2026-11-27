"""P6 (C3b, or the energy ledger): a set's free-site term counted once per ligand pool, not once per set, in the
step's booking (CRITERIA:126). Seam: site_occupancy.node_booking."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P6"
CHANGE = "node_booking: each set's dG_R counted once per ligand pool"


def apply():
    honest = so.node_booking

    def planted(pool_dg, dg_b, dg_r, pool_on, on, set_on, p, cells, outsides, *, xp):
        per_pool = xp.where(on, dg_r[p.site_set_of], 0.0)
        return honest(pool_dg, dg_b + per_pool, xp.zeros_like(dg_r), pool_on, on, set_on, p, cells, outsides, xp=xp)

    so.node_booking = planted
