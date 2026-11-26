"""The bounding patch as an implicit route kind (bounding_patch_constant_field@1): the slot pieces,
the per-compartment Newton stage solve with its Sherman-Morrison Jacobian, the patch-wide booking,
and a planted error. The world is the charged-patch test's: lysosomal Cl- on a 250 nm compartment,
where explicit stepping fails above 0.05 ms."""

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from cells.laws.electrochemistry import CHARGE_PER_FMOL, R, bernoulli, ghk_leak
from cells.laws.routes import passive_permeation as passive
from cells.laws.routes import patch_electrodiffusion as pe

T = 310.0
V_I = 4 / 3 * math.pi * (5e-6) ** 3 * 1e15
V_J = 4 / 3 * math.pi * (250e-9) ** 3 * 1e15
A_B = 4 * math.pi * (250e-9) ** 2
C_B = 0.01 * A_B
P_CL = 1.2e-7
Z = np.array([-1.0])
X0 = 110.0 * V_J  # lumen Cl (fmol)
N_TOTAL = X0 + 10.0 * V_I


def test_bernoulli_slope_matches_a_finite_difference_everywhere():
    for x in (-40.0, -3.0, -1e-2, -1e-4, 0.0, 1e-4, 1e-2, 3.0, 40.0):
        h = 1e-6 * max(1.0, abs(x))
        fd = (bernoulli(x + h, xp=np) - bernoulli(x - h, xp=np)) / (2 * h)
        assert pe.bernoulli_slope(np.float64(x), xp=np) == pytest.approx(fd, rel=1e-6, abs=1e-12)


def test_flux_slope_matches_a_finite_difference_of_the_constant_field_flux():
    ci, co, v = 10.0, 110.0, -0.03
    w = pe.flux_slope(ci, co, v, -1, T, A_B, P_CL, 1.0, xp=np)
    dv = 1e-7
    fd = (ghk_leak(ci, co, v + dv, -1, T, A_B, P_CL, 1.0, xp=np)
          - ghk_leak(ci, co, v - dv, -1, T, A_B, P_CL, 1.0, xp=np)) / (2 * dv)
    assert w == pytest.approx(fd, rel=1e-6)


def test_the_slot_pieces_split_the_flux_exactly_and_give_a_psd_block():
    ci = np.array([10.0, 140.0])
    co = np.array([110.0, 5.0])
    z = np.array([-1.0, 1.0])
    w, g = pe.weights(ci, co, -0.02, z, T, A_B, np.array([P_CL, 7.1e-9]), 1.0, xp=np)
    assert g > 0
    for v in (-0.08, 0.0, 0.05):
        total = pe.flux_fmol_s(ci, co, v, z, T, A_B, np.array([P_CL, 7.1e-9]), 1.0, xp=np)
        split = pe.implicit_flux(w, v) + pe.explicit_remainder(
            ci, co, v, z, T, A_B, np.array([P_CL, 7.1e-9]), 1.0, w, xp=np)
        np.testing.assert_allclose(split, total, rtol=1e-13, atol=1e-30)
    block = pe.laplacian_block(g, 0, 2, 3, xp=np)
    np.testing.assert_allclose(block, block.T)
    np.testing.assert_allclose(block.sum(axis=1), 0.0, atol=1e-30)
    assert np.all(np.linalg.eigvalsh(block) >= -1e-30)


def implicit_euler(dt, end, sign=1.0):
    """Implicit Euler with the per-compartment stage solve; the owner's concentration is frozen
    over each step (the owner is about 8,000 times larger). Returns times, x, V_b, heats, valid."""
    steps = int(round(end / dt))
    x = np.array([X0])
    xs, vs, heats, ok = [x[0]], [0.0], [], True
    for _ in range(steps):
        ci = np.array([(N_TOTAL - x[0]) / V_I])
        x_new, v_new, valid = pe.stage_solve(
            x, ci, Z, T, A_B, np.array([P_CL]), 1.0, V_J, X0, 0.0, C_B, dt, xp=np,
            sign_of_rank_one=sign)
        ok = ok and bool(valid)
        if not valid:
            break
        moved_in = x - x_new  # into the cell
        mu_j = passive.divided_potential_RT(x, x_new, V_J, xp=np)
        n_i0, n_i1 = N_TOTAL - x, N_TOTAL - x_new
        mu_i = passive.divided_potential_RT(n_i0, n_i1, V_I, xp=np)
        heats.append(float(pe.step_heat_pJ(moved_in, mu_i, mu_j, Z, vs[-1], float(v_new), T,
                                           xp=np)))
        x = x_new
        xs.append(x[0])
        vs.append(float(v_new))
    return np.array(xs), np.array(vs), np.array(heats), ok


def reference(times):
    def rhs(_t, y):
        nj = y[0]
        ci, cj = (N_TOTAL - nj) / V_I, nj / V_J
        v = -(CHARGE_PER_FMOL * (-(nj - X0))) / C_B
        return [-ghk_leak(ci, cj, v, -1, T, A_B, P_CL, 1.0, xp=np)]

    sol = solve_ivp(rhs, (0, times[-1]), [X0], method="Radau", rtol=1e-12, atol=1e-22,
                    dense_output=True)
    nj = sol.sol(times)[0]
    return nj, -(CHARGE_PER_FMOL * (-(nj - X0))) / C_B


@pytest.mark.parametrize("dt", [1e-3, 1e-2])
def test_the_implicit_patch_is_stable_where_explicit_steps_are_refused(dt):
    # dt x G/C_b is 1.8-4.8 at 1 ms and 18-48 at 10 ms (explicit ARS was refused above 0.09).
    xs, vs, heats, ok = implicit_euler(dt, 0.2)
    assert ok
    assert vs[-1] * 1e3 == pytest.approx(-64.037, abs=2e-3)  # E_Cl, as the CP reference
    assert np.all(heats >= -1e-18)


def test_the_stage_solve_converges_at_first_order_to_the_reference():
    errors = []
    for dt in (1e-4, 5e-5, 2.5e-5):
        xs, vs, _, ok = implicit_euler(dt, 2e-3)
        assert ok
        _, v_ref = reference(np.linspace(0, 2e-3, len(vs)))
        errors.append(np.abs(vs - v_ref).max())
    assert errors[0] / errors[1] == pytest.approx(2.0, rel=0.15)
    assert errors[1] / errors[2] == pytest.approx(2.0, rel=0.15)


def test_the_booking_closes_the_energy_ledger_to_rounding():
    xs, vs, heats, ok = implicit_euler(1e-3, 0.05)
    assert ok

    def g(n, v):
        return 1e-3 * R * T * n * (math.log(n / v) - 1)

    stored0 = g(xs[0], V_J) + g(N_TOTAL - xs[0], V_I) + 0.5 * C_B * vs[0] ** 2 * 1e12
    stored1 = g(xs[-1], V_J) + g(N_TOTAL - xs[-1], V_I) + 0.5 * C_B * vs[-1] ** 2 * 1e12
    assert heats.sum() == pytest.approx(stored0 - stored1, rel=1e-9)


def test_planted_error_a_flipped_rank_one_term_fails_the_solve():
    _, _, _, ok = implicit_euler(1e-2, 0.05, sign=-1.0)
    assert not ok


def test_patch_wide_booking_splits_by_route_and_sums_to_the_whole():
    z = np.array([-1.0, 1.0])
    moved = np.array([[2e-6, 0.0], [0.0, -1e-6]])  # route 0 moves Cl in, route 1 moves K out
    mu_in = np.array([math.log(10.0), math.log(140.0)])
    mu_out = np.array([math.log(110.0), math.log(5.0)])
    per_route = pe.patch_booking_pJ(moved, np.array([0.0, 0.0]), mu_in, mu_out, z, -0.03, -0.031,
                                    T, xp=np)
    whole = pe.step_heat_pJ(moved.sum(axis=0), mu_in, mu_out, z, -0.03, -0.031, T, xp=np)
    assert per_route.sum() == pytest.approx(whole, rel=1e-14)
    assert pe.SOLVER_ID == "cells.solver.imex_ars222_face_patch_electromigration@1"
