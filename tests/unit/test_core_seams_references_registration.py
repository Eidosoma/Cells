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
    for lid in ("d2_slip_exchanger", "v1_proton_n2", "fb_shift"):
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
