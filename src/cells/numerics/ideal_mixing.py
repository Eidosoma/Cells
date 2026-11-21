"""The ideal-mixing function phi(r) = r ln r - r + 1 >= 0, in a form that stays finite where r is
within rounding of 0 (FR-27; the cleft fix's form).

The heat of mixing two ideal liquids of one species, at concentrations c and c_b into c', is
RT c' [V phi(c / c') + dV phi(c_b / c')] (restricted_lumen.fill_energy) or, for a wash,
RT V c' [(1 - f) phi(c / c') + f phi(c_b / c')] (operators/wash_schedule.py). Each argument
r = 1 + e is formed twice by its caller without cancellation: e, as a scaled difference of
concentrations, and r itself, as a quotient of positive concentrations.

phi takes the series e^2 (1/2 - e/6 + e^2/12 - e^3/20) for |e| < SERIES_BELOW, the e-form
(1 + e) log1p(e) - e elsewhere, and the ratio form r ln r - r + 1 (with r ln r = 0 at r = 0) where
r < RATIO_BELOW. There e lies within about 4000 ulps of -1 and can round to -1 or below, where
log1p reads -1 and (1 + e) log1p(e) is 0 x (-inf), NaN: the independent Lean project found it in
the cleft's fill at 1 mM against 2^-60 mM (lean/PROGRESS.md "cleft mixing heat", 20 November 2026).
Its accuracy: a few ulps from the series and from the ratio; the e-form keeps about eps |ln r| of
phi far from 1, and about 2 eps / |e| of it just above the series' threshold. The choice reads the
ratio only, and each branch not taken reads 1.

This is the form of restricted_lumen.mixing as fixed at 28c4e7ff (D148, in place), which is not on
main when this module is written: phi(e, ratio) equals that mixing(e, ratio) bit for bit, in NumPy
and compiled (checked on 4,601 ratios from 0 to 1e6, 20 November 2026). restricted_lumen keeps its
own copy, and one shared function is the cleft's owner's later choice.
"""

SERIES_BELOW = 1e-4  # phi(1 + e) by its series for |e| below this (it never rounds negative).
RATIO_BELOW = 2.0**-40  # phi(r) from the ratio itself below this.


def phi(e, ratio, *, xp):
    """phi(r) at r = 1 + e = ratio: e and ratio formed by the caller without cancellation."""
    small = xp.abs(e) < SERIES_BELOW
    series = e * e * (0.5 - e * (1.0 / 6.0 - e * (1.0 / 12.0 - e / 20.0)))
    tiny = ratio < RATIO_BELOW
    safe = xp.where(small | tiny, 1.0, e)
    direct = (1.0 + safe) * xp.log1p(safe) - safe
    r = xp.where(tiny, ratio, 1.0)
    from_ratio = r * xp.log(xp.where(r > 0, r, 1.0)) - r + 1.0
    return xp.where(small, series, xp.where(tiny, from_ratio, direct))
