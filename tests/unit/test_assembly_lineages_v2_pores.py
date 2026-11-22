"""cells.pore_nucleation@1's law and the six-point fit (docs/VESICLE_PORES_LAWS.md §2, §4, §8).

New file for a new feature (FR-31, Phase A). It compiles no world and runs in well under a second:
the law's closed form at a point, its temperature slope against a finite difference, and the fit
recovering known parameters from rows made by the law.
"""

import math

import pytest

from cells.models.assembly_lineages_v2 import pore_nucleation as law
from validation.vesicle_pores import fit_rows

E_A = 27e3


def test_the_rate_is_the_sheets_closed_form():
    sigma, t, log_nu, gamma = 7.5e-3, 300.0, 21.0, 11e-12
    expected = (log_nu + 0.5 * math.log(sigma) - 1.5 * math.log(t) - E_A / (law.R * t)
                - math.pi * gamma**2 / (sigma * law.K_B * t))  # fmt: skip
    assert law.log_rate_per_area(sigma, t, log_nu, gamma, E_A) == pytest.approx(
        expected, abs=0, rel=1e-15
    )
    assert law.log_rate(2e-9, sigma, t, log_nu, gamma, E_A) == pytest.approx(
        expected + math.log(2e-9), abs=0, rel=1e-15
    )


@pytest.mark.parametrize("sigma", [3.3e-3, 7.0e-3, 8.0e-3])
def test_the_temperature_slope_matches_a_finite_difference(sigma):
    t, h, gamma = 300.0, 1e-3, 11e-12
    numeric = (law.log_rate_per_area(sigma, t + h, 0.0, gamma, E_A)
               - law.log_rate_per_area(sigma, t - h, 0.0, gamma, E_A)) / (2 * h)  # fmt: skip
    assert law.dlog_rate_dt(sigma, t, gamma, E_A) == pytest.approx(numeric, rel=1e-7)


def test_the_fit_recovers_the_laws_parameters():
    ln_c, gamma = 20.5, 11.3e-12
    ses = [0.03, 0.044, 0.028, 0.038, 0.025, 0.0365]
    conditions = [(t, s) for t in (1e6 / 3356, 1e6 / 3279) for s in (7.0e-3, 7.5e-3, 8.0e-3)]
    points = [
        (t, s, law.log_rate_per_area(s, t, ln_c, gamma, E_A), se)
        for (t, s), se in zip(conditions, ses, strict=True)
    ]
    out = fit_rows.fit(points, E_A)
    assert out["estimates"]["ln_C"] == pytest.approx(ln_c, rel=1e-10)
    assert out["estimates"]["gamma_N"] == pytest.approx(gamma, rel=1e-10)
    assert out["chi2"] < 1e-12 and out["dof"] == 4
