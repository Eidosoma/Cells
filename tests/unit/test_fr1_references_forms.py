"""FR-1's reference forms (CLOSED_COMPARTMENT_DESIGN.md Appendix A.2 to A.10), on their own.

Each form is held against an independent integration or identity, with a planted error that
must fail: a rate 1% off, b on the wrong volume, K_M as an amount, a Lie (non-palindromic)
splitting, a flipped patch orientation and a dropped "-1".
"""

from __future__ import annotations

from decimal import localcontext

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.fr1.references import capacitor, energy, forms, stepmap
from validation.fr1.references.exact import DIGITS, RT, dec, exact

T = np.linspace(0.0, 3.0, 31)


def _ode(f, y0, times):
    sol = solve_ivp(f, (0.0, times[-1]), y0, method="DOP853", rtol=1e-13, atol=1e-22,
                    t_eval=times)
    assert sol.success
    return sol.y.T


def test_A2_loading_closed_forms():
    r = forms.loading_first_order(1e-3, 1e-15, 0.7, T)
    y = _ode(lambda t, y: [-0.7 * y[0], 0.7 * y[0]], [1e-3, 1e-15], T)
    assert np.abs(r["n_c_fmol"] - y[:, 0]).max() < 1e-16
    assert np.abs(r["n_o_fmol"] - y[:, 1]).max() < 1e-16
    bad = forms.loading_first_order(1e-3, 1e-15, 0.707, T)
    assert np.abs(bad["n_c_fmol"] - y[:, 0]).max() > 1e-6
    f = forms.loading_flux(1e-3, 0.0, 4e-4, T)
    assert f["n_o_fmol"][10] == float(exact(4e-4) * exact(T[10]))
    assert np.all(f["valid"] == (T < 2.5))


def test_A3_two_way_exchange_and_its_Fick_equilibrium():
    P, A, Vc, Vo = 1e-6, 1e-9, 1.0, 0.1         # a = 1/s, b = 10/s
    a = float(forms.kappa(P, A, Vc))           # k_e = 1e15 P A / V_c
    b = float(forms.kappa(P, A, Vo))           # k_u = P on the compartment's side
    r = forms.two_way(1e-3, 0.0, a, b, T)
    y = _ode(lambda t, y: [-a * y[0] + b * y[1], a * y[0] - b * y[1]], [1e-3, 0.0], T)
    assert np.abs(r["n_c_fmol"] - y[:, 0]).max() < 1e-16
    assert np.allclose(r["n_c_fmol"] + r["n_o_fmol"], 1e-3, rtol=1e-15, atol=0)
    assert np.isclose(r["x_eq"], Vc / (Vc + Vo), rtol=1e-15)
    late = forms.two_way(1e-3, 0.0, a, b, [200.0])
    assert np.isclose(late["n_c_fmol"][0] / Vc, late["n_o_fmol"][0] / Vo, rtol=1e-12)
    # planted: kappa on the cytosol's volume gives no equal concentrations
    wrong = forms.two_way(1e-3, 0.0, a, a, [200.0])
    assert abs(wrong["n_c_fmol"][0] / Vc - wrong["n_o_fmol"][0] / Vo) > 1e-4


def test_A5_saturable_release_against_its_equation():
    A, Vmax, KM, Vo = 1e-10, 5e6, 2e-3, 0.1
    a, b = A * Vmax, KM * Vo
    r = forms.saturable_release(1e-3, 0.0, a, b, T)
    y = _ode(lambda t, y: [-a * y[0] / (b + y[0])], [1e-3], T)
    assert np.abs(r["n_o_fmol"] - y[:, 0]).max() < 1e-15          # DOP853's own accuracy
    assert np.allclose(r["n_o_fmol"] + r["n_c_fmol"], 1e-3, rtol=1e-15, atol=0)
    assert r["floor_fmol"].max() < 1e-17
    # planted: K_M taken as an amount (b = K_M) on a compartment that is not 1 pL
    yb = _ode(lambda t, y: [-a * y[0] / (KM + y[0])], [1e-3], T)
    assert np.abs(r["n_o_fmol"] - yb[:, 0]).max() > 1e-5


@pytest.mark.parametrize("ke, k", [(1.0, 0.5), (0.8, 0.8)])
def test_A6_degradation_with_loading(ke, k):
    r = forms.degradation(1e-3, 2e-4, ke, k, T)
    y = _ode(lambda t, y: [-ke * y[0], ke * y[0] - k * y[1], k * y[1]], [1e-3, 2e-4, 0.0], T)
    for i, key in enumerate(("n_c_fmol", "n_o_fmol", "cleared_fmol")):
        assert np.abs(r[key] - y[:, i]).max() < 1e-16
    assert np.allclose(r["n_c_fmol"] + r["n_o_fmol"] + r["cleared_fmol"], 1.2e-3, rtol=1e-15,
                       atol=0)
    bad = _ode(lambda t, y: [-ke * y[0], ke * y[0] - k * y[1], ke * y[1]], [1e-3, 2e-4, 0.0], T)
    if ke != k:
        assert np.abs(r["cleared_fmol"] - bad[:, 2]).max() > 1e-6


def test_A7_reaction_inside_conserves_its_moiety():
    r = forms.reaction_inside(1e-3, 0.0, 1e-6, 1.2, 0.4, T)
    y = _ode(lambda t, y: [-1.2 * y[0], 1.2 * y[0] - 0.4 * y[1], 0.4 * y[1]], [1e-3, 0, 1e-6], T)
    assert np.abs(np.column_stack([r["n_c_fmol"], r["n_S_fmol"], r["n_P_fmol"]]) - y).max() \
        < 1e-16
    total = r["n_c_fmol"] + r["n_S_fmol"] + r["n_P_fmol"]
    assert np.allclose(total, 1e-3 + 1e-6, rtol=1e-15, atol=0)


def test_A8_uptake_path_with_and_without_a_face():
    ku, ke = 2.0, 1.0
    r = forms.uptake(1e-3, 0.0, 0.0, ku, ke, T)
    y = _ode(lambda t, y: [-ku * y[0], ku * y[0] - ke * y[1], ke * y[1]], [1e-3, 0, 0], T)
    assert np.abs(np.column_stack([r["n_e_fmol"], r["n_c_fmol"], r["n_o_fmol"]]) - y).max() \
        < 1e-16
    kf, Ve, cb = 10.0, 0.5, 2e-3
    r = forms.uptake(1e-3, 0.0, 0.0, ku, ke, T, face=(kf, Ve, cb))
    y = _ode(lambda t, y: [-ku * y[0] + kf * (cb - y[0] / Ve), ku * y[0] - ke * y[1],
                           ke * y[1]], [1e-3, 0, 0], T)
    assert np.abs(np.column_stack([r["n_e_fmol"], r["n_c_fmol"], r["n_o_fmol"]]) - y).max() \
        < 1e-14                                       # DOP853's own accuracy here
    gain = r["n_e_fmol"] + r["n_c_fmol"] + r["n_o_fmol"] - 1e-3
    assert np.allclose(r["supply_fmol"], gain, rtol=1e-13, atol=1e-19)
    assert np.all(r["supply_fmol"][1:] > 0)


def test_A4_step_map_fixed_point_and_splitting_term():
    a, b = 1.0, 2.0
    for dt in (1e-2, 1e-3):
        fp = stepmap.fixed_point(a, b, dt)
        assert abs(fp["ratio"] - 1.0) < 10 * dt          # -a(a + 2b) dt^2/96, to O(dt)
    it = stepmap.iterate(1e-3, 0.0, a, b, 1e-2, 3000, every=3000)
    x_end = it["n_c_fmol"][-1] / 1e-3
    assert abs(x_end - stepmap.fixed_point(a, b, 1e-2)["x_star"]) < 1e-15
    halves = stepmap.iterate(1e-3, 0.0, a, b, 1e-2, 3000, plan="halves", every=3000)
    assert halves["n_c_fmol"][-1] == it["n_c_fmol"][-1]          # one map in exact arithmetic
    allow = stepmap.rounding_allowance(1e-3, 3000, "halves")
    assert abs(halves["n_c_float64_fmol"][-1] - halves["n_c_fmol"][-1]) <= allow
    # planted: a Lie splitting E(h) I(h) has a first-order bias, not -a(a + 2b) dt^2/96
    with localcontext() as ctx:
        ctx.prec = DIGITS
        h = dec(1e-3) / 2
        al, be = (-dec(a) * h).exp(), (-dec(b) * h).exp()
        lie = float(al * (1 - be) / (1 - al * be))     # the fixed point of E(h) after I(h)
    lead = -a * (a + 2 * b) * 1e-6 / 96
    assert abs((lie / (b / (a + b)) - 1) / lead) > 10


def test_A9_capacitor_relations_and_orientation():
    C_pm, C_b = 1e-12, 2e-14
    for q_cell, q_comp in ((-6e-14, 0.0), (-6e-14, 1e-17), (3e-14, -2e-16)):
        r = capacitor.cell_compartment(C_pm, C_b, q_cell, q_comp)
        assert r["V_b_V"] == r["V_b_closed_V"]
        assert r["V_pm_V"] == r["V_pm_closed_V"]
    silent = capacitor.cell_compartment(C_pm, C_b, -6e-14, 0.0)
    assert silent["V_b_V"] == 0.0 and silent["V_pm_V"] == float(exact(-6e-14) / exact(C_pm))
    live = capacitor.cell_compartment(C_pm, C_b, -6e-14, 1e-17)
    flipped = live["solve"]["phi_V"]["comp"] - live["solve"]["phi_V"]["cell"]
    assert abs(flipped - live["V_b_closed_V"]) > 1e-4                # planted orientation
    with pytest.raises(ValueError, match="no path to a held bath"):
        capacitor.solve(["a", "b"], {"bath": 0.0}, [("a", "b", 1e-12)], {"a": 0.0})


def test_A10_free_energy_and_each_law_s_work():
    T_K, V = 310, 0.1
    n, dn = exact(2e-4), exact(-5e-5)
    with localcontext() as ctx:
        ctx.prec = DIGITS
        G = [dec(RT(T_K)) * dec(x) * ((dec(x) / dec(V)).ln() - 1) / 1000 for x in (n, n + dn)]
        assert abs(float(G[1] - G[0]) - float(energy.node_change(n, dn, V, T_K))) < 1e-30
    w = energy.clearance_work(2e-4, 5e-5, V, T_K)
    assert w > 0          # below 1 mM the potential is negative, so removing material costs
    # planted: without the "-1" the clearance's work changes by 1e-3 RT dn
    with localcontext() as ctx:
        ctx.prec = DIGITS
        no_minus_one = float(energy.node_change(n, dn, V, T_K) +
                             dec(RT(T_K)) * dec(dn) / 1000)
    assert abs(no_minus_one - w) > 1e-4
    # a move m at equal concentrations costs only its second-order term,
    # 1e-3 RT m^2 (1/n_1 + 1/n_2)/2
    m = 1e-12
    tiny = energy.exchange_work(1e-3, 1e-4, m, 1.0, 0.1, T_K)
    second = 1e-3 * float(RT(T_K)) * m * m * (1 / 1e-3 + 1 / 1e-4) / 2
    assert abs(tiny / second - 1) < 1e-6
    assert energy.closure(1.0, [0.25, 0.5], bath_work=0.5, face_heat=0.25) == 0.0
