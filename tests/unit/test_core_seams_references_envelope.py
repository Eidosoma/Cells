"""Seam C's envelope reference (amendments C3 and C5, CORE_SEAMS_DESIGN §19 amended at 19:52 UTC).

The first-order lag of the linearised binding network, with k_on per (binder, ligand), against
B4's formula, against the full kinetic network, and against a planted per-step minimum λ:
- one two-form buffer gives B4's lag;
- a cooperative chain's slowest mode is slower than every single step, so a per-step minimum
  puts an outside case inside the budget;
- the kinetic network meets the first order at second order, and the lag falls as 1/k_on;
- a form not reachable from its base by unit steps is refused;
- amendment C5: release steps (forms below their base) are found, a release buffer gives B4's lag,
  a mixed-sign release under an Mg²⁺ drive defeats a per-step bound, a release network meets its
  kinetic reference, and the release steps' flipped sign is caught.
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


# --------------------------------------------------------------------------------------------
# Amendment C5: release steps (forms below their base, single-sign and mixed-sign)
# --------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def release_cases():
    c = {"manufactured_states": {}}
    worlds.amendment_c3(c)
    worlds.amendment_c5(c)
    return {cid: c["envelope"]["cases"][cid] for cid in c["envelope"]["amendment_c5"]["cases"]}


def test_a_release_buffer_gives_b4s_lag_with_the_release_form_free(release_cases):
    r = En.run_case(release_cases["E3_rel1_b4"], REG, kinetic=False)
    assert r["release_steps"] == [{"from": "rel1_mH", "ligand": "H", "to": "rel1_base"}]
    assert abs(r["b4_formula_pH"] / r["first_order_pH"] - 1) < 1e-12
    # plant: the release step's ligand with the wrong sign
    rv = En.run_case(release_cases["E3_rel1_b4"], REG, kinetic=False, flip_release=True)
    assert abs(rv["first_order_dln"]["H"] / r["first_order_dln"]["H"] - 1) > 1e-3


def test_release_steps_are_found_and_their_flipped_sign_is_caught(release_cases):
    expected = {"pi2": ("pi2_PO4", "H", "pi2_base"), "mgx": ("mgx_MgmH", "H", "mgx_Mg"),
                "rel1": ("rel1_mH", "H", "rel1_base")}
    for cid, case in release_cases.items():
        r = En.run_case(case, REG, kinetic=False)
        got = {(s["from"], s["ligand"], s["to"]) for s in r["release_steps"]}
        want = {expected[B] for B in case["binders"] if B in expected}
        assert got == want, cid
        rv = En.run_case(case, REG, kinetic=False, flip_release=True)["first_order_dln"]
        floor = 8 * 2.0 ** -52 * max(s["lambda_per_s"] for s in r["steps"]) / \
            r["slowest_network_rates_per_s"][0]
        dev = max(abs(rv[L] / r["first_order_dln"][L] - 1) for L in case["ligands"])
        assert dev > 1e3 * floor, cid


def test_a_mixed_sign_release_under_an_mg_drive_defeats_a_per_step_bound(release_cases):
    r = En.run_case(release_cases["E4_mgx_mixed_mg_drive"], REG, kinetic=False)
    assert r["first_order_pH"] > 1.3 * r["per_step_pH"]
    assert r["slowest_network_rates_per_s"][0] < 0.1 * r["min_step_rate_per_s"]


def test_a_release_network_meets_its_kinetic_reference(release_cases):
    r = En.run_case(release_cases["E3_pi2_release"], REG)
    last = r["kinetic"]["rows"][-1]
    assert abs(last["lag_dln"]["H"] / last["first_order_dln"]["H"] - 1) < 5e-3
    assert max(max(x["floor_dln"].values()) for x in r["kinetic"]["rows"]) < 1e-10
