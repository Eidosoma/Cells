"""P1 (C1): each population binds as if alone on its set: its free sites S_s - B_b, whatever R_s does
(CRITERIA:119; the lead's ruling 7, from the references' own words). Seam: site_occupancy.member_free_sites."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P1"
CHANGE = "member_free_sites: each population's free sites S_s - B_b, as if alone on its set"


def apply():
    def planted(R, B, p, *, xp):
        return p.site_capacity_fmol - B

    so.member_free_sites = planted
