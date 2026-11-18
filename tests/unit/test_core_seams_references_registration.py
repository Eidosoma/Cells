"""The registered core-seams references: inputs, values and design stay as registered.

- the inputs equal their generator;
- registered values agree with a fresh computation on a sample of states (the full
  ``design --check`` regenerates everything in about a minute);
- every registered plant has power where the design says it does, and the zero-power list is there;
- nothing here imports the engine.
"""

from __future__ import annotations

import json
import math
import re

import pytest

from validation.core_seams.references import api, design, worlds


@pytest.fixture(scope="module")
def registered():
    return (json.loads(worlds.INPUTS.read_text()), json.loads(design.VALUES_FILE.read_text()),
            json.loads(design.DESIGN_FILE.read_text()))


def test_the_inputs_equal_their_generator(registered):
    inputs, values, des = registered
    assert worlds.INPUTS.read_text() == json.dumps(worlds.build(), indent=1) + "\n"
    blob = design.git_blob_id(worlds.INPUTS)
    assert values["inputs_git_blob"] == blob and des["inputs"]["git_blob"] == blob


def test_sampled_values_agree_with_a_fresh_computation(registered):
    inputs, values, _des = registered
    A = inputs["seam_a"]
    laws = {law["id"]: law for law in A["laws"]}
    for lid in ("d2_slip_exchanger", "v1_proton_n2", "fb_shift", "ff_neutral_n1",
                "d2_slip_exchanger_Nb"):
        law, pop = laws[lid], A["populations"][lid]
        for k in (0, 5):
            st = A["states"][lid][k]
            fresh = api.cycle_state(law, pop, A["registry"], st, A["volumes_pL"],
                                    with_slopes=law["kind"] != "net_flow")
            assert json.dumps(fresh) == json.dumps(values["seam_a"]["laws"][lid]["states"][k])
    Cc = inputs["seam_c"]
    for name in ("S3", "S6"):
        sysd = Cc["systems"][name]
        st = Cc["manufactured_states"][name][-1]
        rec, _sp, _sy = api.binding_state({"ligands": sysd["ligands"], "binders": sysd["binders"]},
                                          Cc["registry"], st["totals"], sysd["volume_pL"])
        reg = values["seam_c"]["systems"][name]["states"][-1]
        assert json.dumps(rec["x_mM"]) == json.dumps(reg["x_mM"])
        assert json.dumps(rec["G_star_pJ"]) == json.dumps(reg["G_star_pJ"])


def test_the_registered_power(registered):
    _inputs, _values, des = registered
    p = des["power"]
    gen = p["A2_wegscheider"]["generic_sets"]
    assert all(g["rank"] == g["states"] == len(g["variables"]) for g in gen.values())
    for lid, w in p["A2_wegscheider"].items():
        if lid == "generic_sets":
            continue
        planted = "__" in lid
        assert w["verdict"] == ("refused" if planted else "admitted"), lid
        if planted and "basis" not in lid:
            failing = [c for c in w["cycles"].values()
                       if not c["structurally_zero"] or c["r0_over_terms_eps"] > 64]
            assert failing and min(c["min_residual_eps_over_generic"] for c in failing) > 640
    # A4 and A5: weak only where the zero-power list says
    for lid, o in p["A4_one_way_fluxes"].items():
        for cid, plants in o["plants"].items():
            assert all(t.endswith("_+0") or t == "unit_activity_zero_voltage"
                       for t in plants["exponent_flipped"]["weak_at"]), (lid, cid)
    no_flux = {"capacity_twice", "rows_scattered", "work_sign"}
    for lid, plants in p["A5_two_layouts"].items():
        for plant, keys in plants.items():
            if plant == "voltage_dropped" and lid.startswith("v1_neutral"):
                continue
            for key, row in keys.items():
                allowed = {"static_head_+0"} if plant in no_flux else set()
                assert set(row["weak_at"]) <= allowed, (lid, plant, key)
    # amendment 1: the stored rate has power, and N = b is weak only at its symmetric unit state
    a8 = p["A8_finite_fuel_stored_rate"]
    assert a8["stored_rate_max_abs_pJ_per_s"] > 1e-3
    for plant in ("stored_frame_1M", "stored_dropped", "stored_sign"):
        assert set(a8[plant]["stored"]["weak_at"]) <= {"static_head_+0"}, plant
    for plant, keys in p["A9_orientation_N_b"].items():
        for key, row in keys.items():
            assert set(row["weak_at"]) <= {"unit_activity_zero_voltage"}, (plant, key)
    g = p["A3_population_guard"]
    assert g["fb_shift"]["fires_at"] and g["fb_shift"]["min_total_over_allowance_where_fires"] > 10
    lo, hi = g["fb_shift"]["verdicts_hold_for_a_band_in_eps"]
    assert lo < 1 and hi > 1000
    assert not g["fb_masked"]["fires_at"] and g["fb_masked"]["a_mode_against_its_dG_at"]
    assert not g["fb_basis"]["fires_at"] and g["fb_basis"]["a_mode_against_its_dG_at"]
    for name, c in p["C1_C2_C4_binding"].items():
        for plant, row in c["plants"].items():
            assert row["min"] > design.MIN_MARGIN, (name, plant)
        assert c["conservation_max_rel"] < 1e-45 and c["charge_max_abs_fmol_e"] < 1e-45
    assert p["C5_p1"]["P1a"]["ratio_stored_over_free"] > 1e5
    # amendment C4: every registered state is jointly valid; the per-ligand floors admit the
    # two planted invalid states
    c4 = p["C4_amendment_joint_validity"]
    assert all(r["every_state_valid"] and r["exact_vs_lp_max_abs_fmol"] < 1e-9
               for r in c4["registered"].values())
    assert sorted(c4["per_ligand_floor_admits_an_invalid_state"]) == ["boundary",
                                                                        "joint_infeasible"]
    assert c4["planted"]["joint_infeasible"]["t_star_exact"] == "-1/2"
    assert c4["planted"]["feasible_near"]["dual"] == c4["planted"]["feasible_near"]["primal"] \
        == "solved"
    # amendment F4: every slope pair, route pair and basis total compared, none skipped
    for lid, c in p["A6_slopes"].items():
        e = c["exact_vs_differences"]
        assert e["failures"] == 0 and e["worst_over_floor"] < 1, lid
        if lid.startswith(("v1_neutral", "ff_neutral")):
            assert e["zero_cases_with_zero_floor"] == e["states"], lid
    for lid, o in p["A4_one_way_fluxes"].items():
        assert o["routes_failures"] == 0 and max(o["routes_over_floor"].values()) < 1, lid
        if "basis_readout" in o:
            assert o["basis_readout"]["every_state_agrees"]
            assert o["basis_readout"]["states_with_a_zero_hill_total"]
    for lid, row in p["A1_sign_and_zero"].items():
        assert row.get("backward_zero_mismatches", 0) == 0, lid
    # amendment C3: the envelope's planted per-step minimum flips E1's verdict; first order holds
    ec = p["C3_amendment_envelope"]
    assert ec["E1_chain"]["verdict_first_order"] == "outside"
    assert ec["E1_chain"]["verdict_per_step"] == "inside"
    assert ec["E0_b4"]["b4_formula_vs_general_rel"] < 1e-12
    assert abs(ec["scalings"]["E1_chain_over_kon100"] - 100) < 1e-6
    assert 8 < ec["scalings"]["second_order_ratio"] < 12
    assert ec["reachability"]["unreach2"]["verdict"] == "refused"
    assert all(v["verdict"] == "admitted" for b, v in ec["reachability"].items() if b != "unreach2")
    # amendment C2: the scales part only in S4, and by 1e9 at its cancelling state
    for name, c in p["C2_amendment_convergence_scale"].items():
        if name == "S4":
            assert c["at"] == "near_zero_H_total" and c["min_total_over_scale"] < 1e-8
            assert c["old_scale_tolerance_ulps_at_min"] < 1
        elif name != "S7":                     # S7 (amendment C4) has a count of −1 as well
            assert c["states_where_the_scales_differ"] == [], name
    # amendment C1: the booked term's plants, its identity and the primal route
    for name, c in p["C1_amendment_booked_term_and_primal"].items():
        assert c["identity_E_c_minus_S_c_minus_ideal_max_pJ"] < 1e-50, name
        assert c["primal_vs_dual_max_abs_dln"] < 1e-45 and c["primal_certificate_max"] <= 1e-50
        for plant, row in c["plants"].items():
            assert row["max"] > 1e3 * design.MIN_MARGIN, (name, plant)
        nonpositive = [st["tag"] for st in _inputs["seam_c"]["manufactured_states"][name]
                       if any(v <= 0 for v in st["totals"]["ligands_fmol"].values())]
        assert c["states_where_S_c_is_undefined"] == nonpositive, name
    assert {m: v["verdict"] for m, v in p["C3_movers"].items()} == \
        {m["id"]: m["expected"] for m in worlds.MOVERS}
    assert len(des["zero_power"]) >= 15 and des["readings"]
    assert all(math.isfinite(x) for x in (p["A3_population_guard"]["fb_shift"]
                                          ["min_total_over_allowance_where_fires"],))


def test_nothing_imports_the_engine():
    for path in sorted(design.HERE.glob("*.py")):
        text = path.read_text()
        assert not re.search(r"^\s*(import cells|from cells)", text, re.M), path
        assert "validation.tissue" not in text, path
        assert "src/cells" not in text, path
