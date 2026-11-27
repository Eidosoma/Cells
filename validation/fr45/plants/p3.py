"""P3 (C3b, or the dissipation check): each member's free sites taken as S_s - B_b in G_site, in the step's booking and
in the energy ledger alike, so the ledger stays closed (CRITERIA:121; TABLE §8.2). Seam: site_lattice_terms."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P3"
CHANGE = "site_lattice_terms: each member's free sites S_s - B_b in G_site, in the booking and the ledger"


def own_free_terms(B, dB, p, xp):
    """(dG, terms) of each member's own free sites S_s - B_b, summed onto its set."""
    rt = so.site_rt(p.temperature)
    own = p.site_capacity_fmol - B
    dg, terms = so.site_free_energy(own, -dB, 0.0, p.site_capacity_fmol, rt, xp=xp)
    size = p.site_set_capacity_fmol.shape[0]
    return so._scatter(dg, p.site_set_of, size, xp=xp), so._scatter(terms, p.site_set_of, size, xp=xp)


def apply():
    honest = so.site_lattice_terms

    def planted(B, dB, R, dR, p, *, xp):
        dg_b, terms_b, _, _ = honest(B, dB, R, dR, p, xp=xp)
        dg_r, terms_r = own_free_terms(B, dB, p, xp)
        return dg_b, terms_b, dg_r, terms_r

    so.site_lattice_terms = planted
