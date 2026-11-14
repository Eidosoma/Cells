"""Tier-1 checks of the held sphere's closed forms (D150 v1's R-continuum; NumPy only).

validation/tissue/secreted_species_closed_forms.py. Its independence check (the lead's review, 14
November 2026): the closed form, taken as a black box, solves the PDE itself without the builder
(the residual of u_t = D lap u - k u by fourth-order differences, falling at fourth order, with
1e-6 errors in D and k caught), both boundary conditions hold over time, and the start and the
steady state equal their sinh forms. Beside it: the start is positive; the exact shell integrals
equal Gauss-Legendre quadrature; the amount, the two supplies
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


def pde_residual(p, r, t, hr, ht=1e-3, diffusivity=None, clearance=None):
    """(u_t - D lap u + k u, |u_t| + D |lap u| + k |u|) by fourth-order central differences of
    p.u alone, the closed form taken as a black box: no builder, no finite-volume system."""
    d = p.diffusivity if diffusivity is None else diffusivity
    k = p.clearance if clearance is None else clearance
    u = p.u
    ut = (-u(r, t + 2 * ht) + 8 * u(r, t + ht) - 8 * u(r, t - ht) + u(r, t - 2 * ht)) / (12 * ht)
    ur = (-u(r + 2 * hr, t) + 8 * u(r + hr, t) - 8 * u(r - hr, t) + u(r - 2 * hr, t)) / (12 * hr)
    urr = (
        -u(r + 2 * hr, t) + 16 * u(r + hr, t) - 30 * u(r, t) + 16 * u(r - hr, t) - u(r - 2 * hr, t)
    ) / (12 * hr**2)
    lap = urr + 2.0 / r * ur  # (1/r^2) d/dr (r^2 du/dr).
    return ut - d * lap + k * u(r, t), np.abs(ut) + d * np.abs(lap) + k * np.abs(u(r, t))


PDE_TIMES = (0.01, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0)  # The transient is live: u_t up to 1.2 k u.


def worst_relative_residual(p, hr, **wrong):
    r = np.linspace(p.radius_m + 0.5e-6, p.outer_m - 0.5e-6, 400)
    worst = 0.0
    for t in PDE_TIMES:
        residual, scale = pde_residual(p, r, t, hr, **wrong)
        worst = max(worst, float(np.max(np.abs(residual) / scale)))
    return worst


def test_the_closed_form_solves_the_pde_itself(p):
    """The lead's review: R-continuum against u_t = D (1/r^2) (r^2 u_r)_r - k u, at 400 radii
    across the medium and seven times, without the builder. The residual falls at fourth order
    with the difference step (a solution, not a near-solution), and an error of 1e-6 in D or k
    shows far above it."""
    coarse, fine, finest = (worst_relative_residual(p, h) for h in (1e-6, 0.5e-6, 0.25e-6))
    assert coarse / fine > 10 and finest < 1e-8, (coarse, fine, finest)
    assert worst_relative_residual(p, 0.25e-6, diffusivity=q.D * (1 + 1e-6)) > 30 * finest
    assert worst_relative_residual(p, 0.25e-6, clearance=q.K * (1 + 1e-6)) > 30 * finest


def test_both_boundary_conditions_hold_over_time(p):
    for t in (*np.linspace(0.0, 8.0, 801), math.inf):
        assert p.u(p.radius_m, t) == pytest.approx(q.C0, rel=1e-13)
        assert p.u(p.outer_m, t) == pytest.approx(q.TRACE, abs=1e-15 * q.C0)


def test_the_start_and_the_steady_state_equal_their_sinh_forms(p):
    """v_ss = [R c0 sinh((R_out - r)/lambda) + R_out c_out sinh((r - R)/lambda)] / sinh(L/lambda),
    written here from its boundary-value problem, against the closed form's scaled exponentials;
    the start is v_ss plus the declared modes, and lies above v_ss (so it is positive)."""
    r = np.linspace(p.radius_m, p.outer_m, 2001)
    lam, big_l = p.lam, p.outer_m - p.radius_m
    v_ss = (
        p.radius_m * q.C0 * np.sinh((p.outer_m - r) / lam)
        + p.outer_m * q.TRACE * np.sinh((r - p.radius_m) / lam)
    ) / math.sinh(big_l / lam)
    start = v_ss + sum(a * np.sin(m * math.pi * (r - p.radius_m) / big_l) for m, a in q.MODES)
    for t, expected in ((math.inf, v_ss / r), (0.0, start / r)):
        assert np.all(np.abs(p.u(r, t) - expected) <= 1e-12 * np.abs(expected) + 1e-18)
    assert np.all(start >= v_ss) and np.all(v_ss > 0)


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
