"""Seam C's envelope reference (amendment C3, CORE_SEAMS_DESIGN §19 amended at 19:52 UTC).

The first-order lag of the linearised binding network, with k_on per (binder, ligand), against
B4's formula, against the full kinetic network, and against a planted per-step minimum λ:
- one two-form buffer gives B4's lag;
- a cooperative chain's slowest mode is slower than every single step, so a per-step minimum
  puts an outside case inside the budget;
- the kinetic network meets the first order at second order, and the lag falls as 1/k_on;
- a form not reachable from its base by unit steps is refused.
"""

from __future__ import annotations

import copy

import pytest

from validation.core_seams.references import envelope as En
from validation.core_seams.references import worlds

REG = worlds.REGISTRY_C


@pytest.fixture(scope="module")
def cases():
    c = {"manufactured_states": {}}
    worlds.amendment_c3(c)
    return c["envelope"]["cases"]


def test_one_two_form_buffer_gives_b4s_lag(cases):
    r = En.run_case(cases["E0_b4"], REG, kinetic=False)
    assert abs(r["first_order_pH"] / r["b4_formula_pH"] - 1) < 1e-12
    assert len(r["steps"]) == 1
    assert abs(r["slowest_network_rates_per_s"][0] / r["min_step_rate_per_s"] - 1) < 1e-9


def test_a_chain_makes_a_per_step_minimum_non_conservative(cases):
    r = En.run_case(cases["E1_chain"], REG, kinetic=False)
    assert r["slowest_network_rates_per_s"][0] < 0.1 * r["min_step_rate_per_s"]
    # planted: the per-step minimum λ puts a case outside the budget inside it
    assert r["first_order_pH"] > 1e-3 > r["per_step_pH"]
    assert r["first_order_pH"] > 10 * r["per_step_pH"]


def test_the_kinetic_network_meets_the_first_order_at_second_order(cases):
    big = En.run_case(cases["E1_chain"], REG)
    small = En.run_case(cases["E1_chain_small"], REG)
    dev = []
    for r in (big, small):
        last = r["kinetic"]["rows"][-1]
        assert last["floor_dln"]["H"] < 1e-9
        dev.append(abs(last["lag_dln"]["H"] / last["first_order_dln"]["H"] - 1))
    assert 8 < dev[0] / dev[1] < 12 and dev[1] < 1e-3
    fast = En.run_case(cases["E1_chain_kon10"], REG, kinetic=False)
    assert abs(big["first_order_dln"]["H"] / fast["first_order_dln"]["H"] - 10) < 1e-6


def test_a_k_on_per_binder_and_ligand_matters_and_a_planted_shared_one_is_caught(cases):
    case = cases["E2_nuc4"]
    r = En.run_case(case, REG, kinetic=False)
    same = copy.deepcopy(case)
    same["kon_per_mM_per_s"] = [[B, L, 1e7] for B, L, _k in case["kon_per_mM_per_s"]]
    rv = En.run_case(same, REG, kinetic=False)
    assert abs(rv["first_order_dln"]["Mg"] / r["first_order_dln"]["Mg"] - 1) > 0.5


def test_an_unreachable_form_is_refused():
    reg = copy.deepcopy(REG)
    reg["binders"]["unreach2"] = {"base_valence": -2, "forms": [
        {"id": "unreach2_base", "mu0_RT": 0.0},
        {"id": "unreach2_H2", "counts": {"H": 2}, "mu0_RT": -20.0}]}
    with pytest.raises(ValueError, match="not reachable"):
        En.Network({"ligands": ["H"], "binders": ["unreach2"]}, reg, {("unreach2", "H"): 1.0}, 1.0)
    En.Network({"ligands": ["H", "Mg"], "binders": ["coop2"]}, REG,
               {("coop2", "H"): 1.0, ("coop2", "Mg"): 1.0}, 1.0)
