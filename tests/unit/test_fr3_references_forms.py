"""FR-3's reference forms (SITE_OCCUPANCY_DESIGN.md Appendix A), on their own.

R-ode is held against the closed forms, the equilibrium solver and its own ledger, with a
planted error that must fail in each:
- K_M taken as K_d;
- the site free energy dropped from the ledger;
- a heat of the wrong sign;
- accessibility as a kinetic factor (K) or an affinity factor (A);
- a binding multiplier that leaves binding running.
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.fr3.references import closed as C
from validation.fr3.references import energy as G
from validation.fr3.references import equilibrium as E
from validation.fr3.references import kinetics as K
from validation.fr3.references.exact import RT_pJ_per_fmol

RT = float(RT_pJ_per_fmol(310))
S = float(K.sites_fmol(1e5, 1, 1.0))           # 1.66e-4 fmol
T = np.linspace(0.0, 5.0, 11)


@pytest.fixture(scope="module")
def closed_node():
    net = K.Network({"o": 1.0}, {"o": 1e-4}, [K.Population("o", S, 1e3, 1.0)], RT)
    return net, K.integrate(net, T)


def test_sites_and_the_closed_node_against_its_riccati_form(closed_node):
    assert float(K.sites_fmol(602214076, 1, 1.0)) == 1.0
    assert float(K.sites_fmol(1e5, 2, 0.5)) == S
    _net, r = closed_node
    d = C.depletion(0.0, 1e-4, S, 1e3, 1.0, 1.0, T)
    assert np.abs(r["B_fmol"][:, 0] - d["B_fmol"]).max() < 1e-17
    assert np.all(np.abs(r["B_fmol"][:, 0] - d["B_fmol"]) <= r["B_fmol_floor"][:, 0] + 1e-17)
    eq = E.shared_node(1e-4, 1.0, [S], [1e-3])
    assert eq["B_fmol"][0] == d["B_eq_fmol"]
    # planted: K_M = (k_off + k_int)/k_on is not K_d; the wrong constant moves the equilibrium
    wrong = E.shared_node(1e-4, 1.0, [S], [1.1e-3])
    assert abs(wrong["B_fmol"][0] - d["B_eq_fmol"]) > 1e-7


def test_the_ledger_closes_and_a_planted_booking_fails(closed_node):
    net, r = closed_node
    scale = abs(G.node_free_energy(1e-4, 1.0, RT))
    assert np.abs(r["ledger_residual_pJ"]).max() < 1e-12 * scale
    assert np.all(np.diff(r["heat_pJ"]) >= 0) and r["heat_pJ"][-1] > 0
    # planted: the site free energy dropped from the ledger
    Gs = np.array([G.site_free_energy(b, S, 1e-3, RT) for b in r["B_fmol"][:, 0]])
    assert np.abs(r["ledger_residual_pJ"] - (Gs - Gs[0])).max() > 1e-6 * scale
    # planted: a heat of the wrong sign
    assert np.abs(r["ledger_residual_pJ"] - 2 * r["heat_pJ"]).max() > 1e-6 * scale
    # the relaxation's heat to equilibrium
    long = K.integrate(net, [0.0, 200.0])
    heat = E.relaxation_heat(1e-4, [0.0], 1.0, [S], [1e-3], RT)["heat_pJ"]
    assert abs(long["heat_pJ"][-1] - heat) < 1e-12 * abs(heat)


def test_internalisation_matches_its_fixed_c_form_within_the_depletion_term():
    V, c = 1000.0, 1e-4
    net = K.Network({"o": V, "cell": 1.0}, {"o": c * V, "cell": 1e-12},
                    [K.Population("o", S, 1e3, 1.0, 0.1, "cell")], RT)
    r = K.integrate(net, T)
    f = C.internalisation(0.0, S, 1e3, 1.0, 0.1, c, T)
    depletion = S / (V * (1e-3 + c))
    assert np.abs(r["B_fmol"][:, 0] - f["B_fmol"]).max() / S < depletion
    assert np.abs(r["internalised_fmol"][:, 0] - f["internalised_fmol"]).max() / S < depletion
    scale = abs(G.node_free_energy(c * V, V, RT))
    assert np.abs(r["ledger_residual_pJ"]).max() < 1e-13 * scale
    gained = r["n_fmol"][:, 0] - 1e-12           # nodes sorted: "cell" first
    assert np.allclose(gained, r["internalised_fmol"][:, 0], rtol=1e-9, atol=1e-22)


def test_qss_converges_at_first_order_in_epsilon_and_K_d_for_K_M_does_not():
    V, c0, kon, koff, kint = 1.0, 1e-4, 1e3, 1.0, 0.1
    KM = (koff + kint) / kon
    tt = np.linspace(0.0, 50.0, 11)
    rel = []
    for eps in (1e-1, 1e-2):
        Sx = eps * V * (KM + c0)
        Bq = Sx * c0 / (KM + c0)
        net = K.Network({"o": V, "cell": 1.0}, {"o": c0 * V, "cell": 1e-12},
                        [K.Population("o", Sx, kon, koff, kint, "cell", Bq)], RT)
        r = K.integrate(net, tt)
        q = C.qss(c0 * V, Sx, kon, koff, kint, V, tt)
        assert np.isclose(q["epsilon"], eps, rtol=1e-12)
        uptake = c0 * V - r["n_fmol"][-1, 1]
        rel.append(np.abs(r["n_fmol"][:, 1] - q["n_fmol"]).max() / uptake)
        if eps == 1e-2:
            # planted: the sink at K_M = K_d, internalisation left out of K_M (k_off - k_int
            # in place of k_off gives (k_off - k_int + k_int)/k_on = K_d)
            bad = C.qss(c0 * V, Sx, kon, koff - kint, kint, V, tt)
            assert np.isclose(bad["K_M_mM"], koff / kon, rtol=1e-12)
            assert np.abs(r["n_fmol"][:, 1] - bad["n_fmol"]).max() / uptake > 10 * rel[-1]
    assert 0.85 < np.log10(rel[0] / rel[1]) < 1.15


@pytest.mark.parametrize("c_over_Kd", [1e-2, 100.0])
def test_accessibility_scales_occupancy_and_not_the_rate(c_over_Kd):
    kon, koff, V = 1e3, 1.0, 1e6
    Kd = koff / kon
    c = c_over_Kd * Kd
    theta = {}
    for alpha in (1.0, 0.5, 0.25):
        Sa = float(K.sites_fmol(1e5, 1, alpha))
        eq = E.shared_node(c * V + 0.0, V, [Sa], [Kd])
        theta[alpha] = eq["B_fmol"][0] / float(K.sites_fmol(1e5, 1, 1.0))
    for alpha in (0.5, 0.25):
        assert abs(theta[alpha] / theta[1.0] - alpha) < 1e-6        # depletion term at V = 1e6
    # the relaxation rate k_on c + k_off does not depend on alpha (fixed c)
    t = np.array([0.0, 0.3])
    a1 = C.association(0.0, S, kon, koff, c, t)
    a2 = C.association(0.0, S / 2, kon, koff, c, t)
    # the unrelaxed fraction e^{-(k_on c + k_off) t} is the same at alpha = 1 and 1/2
    assert np.isclose(1 - a2[1] / (S / 2 * c / (Kd + c)), 1 - a1[1] / (S * c / (Kd + c)),
                      rtol=1e-12)
    # planted (K): a kinetic factor leaves the occupancy at alpha = 1's
    theta_K = c / (Kd + c)
    assert abs(theta_K - theta[0.5]) > 0.1 * theta[1.0]
    # planted (A): an affinity factor saturates every site at large c
    theta_A = (c * 0.5) / (Kd + c * 0.5)
    if c_over_Kd > 1:
        assert abs(theta_A - theta[0.5]) > 0.4


def test_two_populations_on_one_node_reach_the_shared_equilibrium():
    S2 = float(K.sites_fmol(4e3, 2, 1.0))
    pops = [K.Population("o", S, 1e3, 1.0), K.Population("o", S2, 5e2, 0.5, B0=0.1 * S2)]
    net = K.Network({"o": 0.5}, {"o": 5e-5}, pops, RT)
    r = K.integrate(net, [0.0, 100.0])
    N = 5e-5 + 0.1 * S2
    eq = E.shared_node(N, 0.5, [S, S2], [1e-3, 1e-3])
    assert np.allclose(r["B_fmol"][-1], eq["B_fmol"], rtol=1e-9, atol=0)
    assert abs(eq["residual_fmol"]) < 1e-40


def test_a_zero_binding_multiplier_holds_the_pools():
    net = K.Network({"o": 1.0}, {"o": 1e-4}, [K.Population("o", S, 1e3, 1.0, B0=0.2 * S)], RT,
                    epochs=[(0.0, None), (1.0, {0: (0.0, 0.0)}), (2.0, None)])
    r = K.integrate(net, [0.0, 1.0, 1.5, 2.0, 3.0])
    assert r["B_fmol"][1, 0] == r["B_fmol"][2, 0] == r["B_fmol"][3, 0]
    assert r["B_fmol"][4, 0] != r["B_fmol"][3, 0]
    held = K.Network({"o": 1.0}, {"o": 1e-4}, [K.Population("o", S, 1e3, 1.0, B0=0.2 * S)], RT,
                     epochs=[(0.0, None), (1.0, {0: (1e-3, 0.0)}), (2.0, None)])
    leak = K.integrate(held, [0.0, 1.0, 2.0])
    assert leak["B_fmol"][2, 0] != leak["B_fmol"][1, 0]          # planted: binding still runs


def test_stable_increments_equal_free_energy_differences():
    for a, d in ((0.3 * S, 0.1 * S), (0.3 * S, -0.3 * S), (0.0, 0.2 * S)):
        g0 = G.site_free_energy(a, S, 1e-3, RT) if a > 0 else 0.0
        g1 = G.site_free_energy(a + d, S, 1e-3, RT)
        # the bound pool's increment (mu0 = dG0) plus the free pool's (mu0 = 0, -d)
        dG0 = RT * np.log(1e-3)
        inc = G.pool_increment(a, d, S, RT, mu0=dG0) + G.pool_increment(S - a, -d, S, RT)
        assert abs(inc - (g1 - g0)) <= 1e-15 * max(abs(g1), abs(g0), 1e-30)
    assert G.pool_increment(0.0, 0.0, S, RT) == 0.0
    n_inc = G.node_increment(1e-4, -2e-5, 1.0, RT)
    diff = G.node_free_energy(8e-5, 1.0, RT) - G.node_free_energy(1e-4, 1.0, RT)
    assert abs(n_inc - diff) <= 1e-15 * abs(diff)
