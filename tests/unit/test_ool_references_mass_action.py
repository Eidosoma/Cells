"""OL5 references, row OL1-4b: mass action in the large-system limit.

The deterministic limit has two independent references (the Riccati closed form and SciPy's
Radau on the world's declared network); the exact master equation approaches it as O(1/X); the
registered ladder has power of at least 0.99 against each planted control, and its test passes
on exact samples of the honest chain and fails on samples of planted chains.
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.ool.references import mass_action as MA
from validation.ool.references.common import MIN_POWER
from validation.ool.references.standin import sample_paths
from validation.ool.references.world import Conventions

CONV = Conventions(condensed_measure="multinomial", last_molecule="kept")


@pytest.fixture(scope="module")
def design():
    return MA.design_numbers(CONV)


def test_two_deterministic_references_agree():
    y_cf = MA.riccati_wb(MA.OBSERVATION_TIMES)
    y_ivp = MA.ode_solve(MA.rung_world(5), MA.OBSERVATION_TIMES)
    assert np.max(np.abs(y_cf - y_ivp[:, MA.rung_world(5).index("T@pool")])) < 1e-10
    assert MA.riccati_wb([50.0])[0] == pytest.approx((9 - 17 ** 0.5) / 8, rel=1e-12)


def test_the_master_equation_approaches_the_ode_as_one_over_X(design):
    gaps = np.array([design["rung"][M]["ode_gap"] for M in design["rungs"]])
    ratios = gaps[:-1] / gaps[1:]
    assert np.all((ratios > 3.6) & (ratios < 4.4)), ratios  # X grows fourfold per rung
    assert np.max(np.abs(gaps[-1])) < 5e-4


def test_registered_null_means_and_power(design):
    assert design["runs"] == 2000 and design["z_critical"] == pytest.approx(4.0026, abs=1e-3)
    assert np.allclose(design["rung"][5]["mean_T"], [1.4838, 2.1626, 2.7109, 2.9594], atol=1e-4)
    assert np.allclose(design["rung"][320]["mean_T"], [100.8847, 144.5703, 178.6244, 193.0238], atol=1e-4)
    assert not design["underpowered"]
    assert all(p["family"] >= MIN_POWER for p in design["power"].values())
    assert design["power"]["power_propensity"]["family"] == pytest.approx(0.998, abs=1e-3)


def test_underpowered_design_is_refused():
    small = MA.design_numbers(CONV, rungs=(5,), R=200)
    assert "power_propensity" in small["underpowered"]
    res = MA.ensemble_test({5: np.zeros((200, 4))}, small)
    assert not res.passed and res.detail["problem"] == "underpowered design"


def _samples(design, form, seed):
    rng = np.random.default_rng(seed)
    out = {}
    for M in design["rungs"]:
        if form is None:
            from validation.ool.references.laws import Law

            law = Law(MA.rung_world(M), CONV)
            states, Q = MA.chain(law)
            n0 = law.world.state_from(law.world.initial_state)
        else:
            states, Q, n0 = MA.planted_chain(M, form, CONV)
        x = sample_paths(states, Q, n0, MA.OBSERVATION_TIMES, design["runs"], rng)
        out[M] = x[:, :, MA.rung_world(M).index("T@pool")]
    return out


def test_exact_samples_pass_and_planted_samples_fail(design):
    assert MA.ensemble_test(_samples(design, None, 1), design).passed
    for form in ("wrong_sign", "coefficient", "biased_selection"):
        res = MA.ensemble_test(_samples(design, form, 2), design)
        assert not res.passed, form
