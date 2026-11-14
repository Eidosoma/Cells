"""Tier-1 checks of the held sphere's closed forms (D150 v1's R-continuum; NumPy only).

validation/tissue/secreted_species_closed_forms.py: the start meets both boundary conditions and is
positive; the exact shell integrals equal Gauss-Legendre quadrature; the amount, the two supplies
and the clearance close the mass balance to rounding; the solution relaxes to the steady state; and
the exact solution of the declared finite-volume system (secreted_species_radial, the exact
spherical-shell faces) converges to the closed form at second order in the shell width once the
steady flux dominates (2 s), on the coarse shells, for the amount and for the source's supply, and
every error falls with each halving early (0.25 s). The probes' planar faces leave a gap many
times larger (design §11.3).
"""

import math

import numpy as np
import pytest

from validation.tissue import secreted_species_closed_forms as cf
from validation.tissue import secreted_species_qualification as q
from validation.tissue import secreted_species_radial as radial


@pytest.fixture(scope="module")
def p():
    return q.problem()


def test_the_start_meets_both_boundary_conditions_and_is_positive(p):
    for t in (0.0, 0.3, 2.0):
        assert p.u(p.radius_m, t) == pytest.approx(q.C0, rel=1e-13)
        assert p.u(p.outer_m, t) == pytest.approx(q.TRACE, abs=1e-15 * q.C0)
    r = np.linspace(p.radius_m, p.outer_m, 2001)
    assert np.all(p.u(r, 0.0) >= p.u(r, math.inf) - 1e-18) and np.all(p.u(r, math.inf) > 0)


def test_exact_shell_integrals_equal_quadrature(p):
    edges = radial.Geometry(q.R, 2.5e-6, 48).edges
    for t in (0.0, 0.5):
        exact = p.shell_averages(edges, t)
        assert np.max(np.abs(exact - cf.gauss_shell_averages(p, edges, t)) / exact) < 1e-12


def test_the_mass_balance_closes_and_the_solution_relaxes_to_steady(p):
    for t in (0.1, 0.5, 1.0, 4.0):
        change = p.amount_fmol(t) - p.amount_fmol(0.0)
        booked = p.source_supplied_fmol(t) + p.outer_supplied_fmol(t) - p.cleared_fmol(t)
        assert abs(change - booked) <= 1e-13 * abs(p.source_supplied_fmol(t))
    assert p.source_supplied_fmol(1.0) > 0 > p.outer_supplied_fmol(1.0)
    edges = q.COARSE.edges
    late = p.shell_averages(edges, 40.0)
    assert np.max(np.abs(late - p.shell_averages(edges, math.inf))) < 1e-15 * q.C0


def coarse_error(width, faces, p, t=0.5):
    from scipy.linalg import expm

    g = radial.Geometry(q.R, width, int(round((q.OUTER - q.R) / width)))
    m, b = radial.operator(
        g, diffusivity=q.D, clearance=q.K, c0_mM=q.C0, outer_mM=q.TRACE, faces=faces
    )
    n, v = g.shells, g.volumes_pL
    kappa = q.D * g.faces(faces)[0][2] / g.faces(faces)[0][3] * 1e15
    big = np.zeros((n + 2, n + 2))  # [c, S, 1]: the shells and the source's cumulative supply.
    big[:n, :n], big[:n, n + 1] = -m, b
    big[n, 0], big[n, n + 1] = -kappa, kappa * q.C0
    x = expm(big * t) @ np.r_[p.shell_averages(g.edges, 0.0), 0.0, 1.0]
    amounts = x[:n] * v
    ratio = n // q.COARSE.shells
    coarse = amounts.reshape(q.COARSE.shells, ratio).sum(axis=1) / q.COARSE.volumes_pL
    return (
        np.max(np.abs(coarse - p.shell_averages(q.COARSE.edges, t))) / q.C0,
        abs(amounts.sum() - p.amount_fmol(t)) / p.amount_fmol(t),
        abs(x[n] - p.source_supplied_fmol(t)) / p.source_supplied_fmol(t),
    )


def test_the_declared_system_converges_at_second_order_and_planar_faces_do_worse(p):
    widths = (5e-6, 2.5e-6, 1.25e-6)
    late = [coarse_error(w, "exact", p, 2.0) for w in widths]  # The steady flux dominates.
    for i in range(2):
        for k in range(3):
            assert 1.8 < math.log2(late[i][k] / late[i + 1][k]) < 2.3, (i, k, late)
    # Early, the start's transient near the source makes the supply's order irregular (1.2 and
    # 1.8 at 0.25 s, 3.2 and 2.6 at 0.5 s), but every error still falls with each halving.
    early = [coarse_error(w, "exact", p, 0.25) for w in widths]
    assert all(early[i + 1][k] < early[i][k] for i in range(2) for k in range(3)), early
    planar = coarse_error(2.5e-6, "planar", p)
    assert planar[0] > 5 * coarse_error(2.5e-6, "exact", p)[0]  # The probes' faces: 6.4 x.
