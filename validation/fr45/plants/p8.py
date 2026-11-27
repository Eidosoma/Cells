"""P8 (C10, by its own ledger): the moiety held per population, R_s + B_b = S_s, not per set (CRITERIA:128). Seam:
site_occupancy.moiety_residuals; its own ledger, the moiety ledger, is expected to refuse (TABLE §8.2)."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P8"
CHANGE = "moiety_residuals: R_s + B_b - S_s per population, summed onto its set"


def apply():
    def planted(row, p, *, xp):
        per_population = row.site_free_increment_fmol[p.site_set_of] + row.site_bound_increment_fmol
        return so._scatter(per_population, p.site_set_of, p.site_set_capacity_fmol.shape[0], xp=xp)

    so.moiety_residuals = planted
