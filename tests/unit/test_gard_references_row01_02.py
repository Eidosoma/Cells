"""GARD references, rows 1 and 2: the exchange law's closed form and the time rescaling.

Each test carries its planted control: a wrong k_b, and a factor on joins only.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from validation.gard.references import exchange_law as ex
from validation.gard.references import time_rescaling as tr
from validation.gard.references.kernels import ExchangeLaw, HeldReservoir, PAIR_CONSISTENT, SINGLE_EVENT
from validation.gard.references.lineage_oracle import simulate_lineage
from validation.gard.references.standin import ensemble_arrays, preprint_law
from validation.gard.references.harness import counts_at_times

D = ex.REGISTERED_DESIGN


def _integrate(k_join, k_leave, rho, n0, times):
    G = len(n0)
    sol = solve_ivp(lambda t, n: ex.rate_law_flux(np.zeros((G, G)), k_join, k_leave, rho, n),
                    (0.0, times[-1]), np.asarray(n0, float), t_eval=times, rtol=1e-12, atol=1e-12)
    return sol.y.T


def test_closed_form_solves_the_rate_law_and_catches_a_wrong_kb():
    times = np.array(D["times"])
    n_ode = _integrate(D["k_join"], D["k_leave"], D["rho"], D["founder"], times)
    n_cf, N_cf = ex.closed_form_beta0(times, D["founder"], D["k_join"], D["k_leave"], D["rho"])
    assert np.max(np.abs(n_cf - n_ode) / n_ode) < 1e-9
    assert np.allclose(N_cf, n_cf.sum(axis=1), rtol=1e-14)
    # per-type constants: the expm form reduces to the scalar form when they are uniform
    G = len(D["rho"])
    n_m, _ = ex.closed_form_beta0(times, D["founder"], np.full(G, D["k_join"]), np.full(G, D["k_leave"]), D["rho"])
    assert np.max(np.abs(n_m - n_cf) / n_cf) < 1e-12
    # planted: k_b ten per cent too large is far outside the agreement above
    n_bad, _ = ex.closed_form_beta0(times, D["founder"], D["k_join"], D["k_leave"] * ex.PLANTED_KB_FACTOR, D["rho"])
    assert np.max(np.abs(n_bad - n_ode) / n_ode) > 1e-2


def test_preprint_numbers_give_the_growth_rate_of_section_2():
    # k_f Sum(rho) - k_b with k_f = 1e-2, rho = 1/100 over 100 types, k_b = 1e-4
    n0 = np.zeros(100, dtype=np.int64)
    n0[:40] = 1
    _, N = ex.closed_form_beta0([0.0, 1.0], n0, 1e-2, 1e-4, np.full(100, 1e-2))
    assert np.isclose(np.log(N[1] / N[0]), 1e-2 - 1e-4, rtol=1e-12)


def _counts(ensemble):
    times = np.asarray(D["times"])
    return times, np.stack([counts_at_times(D["founder"], a["event_time"], a["event_channel"], times)
                            for _, _, a in ensemble])


def test_ensemble_means_pass_and_a_wrong_kb_is_caught():
    times, counts = _counts(ensemble_arrays(D["runs"], seed=101))
    res = ex.check_ensemble_means(times, counts, D["founder"], D["k_join"], D["k_leave"], D["rho"])
    assert res.passed, res.detail
    assert res.detail["planted_power"] >= ex.MIN_POWER
    times, counts = _counts(ensemble_arrays(D["runs"], kb_factor=ex.PLANTED_KB_FACTOR, seed=202))
    res_bad = ex.check_ensemble_means(times, counts, D["founder"], D["k_join"], D["k_leave"], D["rho"])
    assert not res_bad.passed


def test_underpowered_ensemble_fails_rather_than_passing_vacuously():
    times = np.array(D["times"])
    counts = np.tile(np.asarray(D["founder"])[None, None, :], (20, times.size, 1))
    res = ex.check_ensemble_means(times, counts, D["founder"], D["k_join"], D["k_leave"], D["rho"])
    assert res.detail["underpowered"] and not res.passed


@pytest.mark.parametrize("c", [1, 3])
def test_uniform_beta_propensities_are_exactly_scaled(c):
    assert tr.uniform_beta_identity_exact(3, c, 6).passed


@pytest.mark.parametrize("c", [1.0, 3.0, 0.5])
def test_uniform_beta_is_a_time_rescaling_under_shared_uniforms(c):
    law, founder = preprint_law(3, PAIR_CONSISTENT, n_types=30)
    G = law.n_types
    kw = dict(fission_mass=60, n_fissions=4, seed=17, diagnostics=False)
    _, _, a0 = simulate_lineage(law.with_beta(np.zeros((G, G))), founder, **kw)
    _, _, ac = simulate_lineage(law.with_beta(np.full((G, G), c)), founder, **kw)
    res = tr.check_time_rescaling(a0["event_channel"], a0["event_time"], ac["event_channel"], ac["event_time"], c,
                                  a0["fission_split"], ac["fission_split"], a0["fission_time"], ac["fission_time"])
    assert res.passed, res.detail
    assert res.detail["exact_power_of_two"] == (c in (1.0, 3.0))


def test_a_factor_on_joins_only_is_caught():
    law, founder = preprint_law(4, SINGLE_EVENT, n_types=30)
    G = law.n_types
    kw = dict(fission_mass=60, n_fissions=4, seed=23, diagnostics=False)
    l0 = law.with_beta(np.zeros((G, G)))
    _, _, a0 = simulate_lineage(l0, founder, **kw)
    _, _, bad = simulate_lineage(l0, founder, join_factor=2.0, **kw)  # "beta = 1" applied to joins only
    res = tr.check_time_rescaling(a0["event_channel"], a0["event_time"], bad["event_channel"], bad["event_time"], 1.0,
                                  a0["fission_split"], bad["fission_split"], a0["fission_time"], bad["fission_time"])
    assert not res.passed
