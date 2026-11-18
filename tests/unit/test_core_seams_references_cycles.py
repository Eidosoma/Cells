"""Seam A's references (CORE_SEAMS_DESIGN §3, §16, §19) on their own, each with a planted error.

- the diagram's two routes and the edge-cycle consistency, which an incomplete cycle set breaks;
- Wegscheider's residual: exactly zero for the passing laws, refused for each plant, and blind at
  the one reference state §19 rules out;
- the factored form's sign, and a planted S < 0;
- the population guard: a band that fires, a mask it cannot see, and a basis it must not refuse;
- one-way fluxes, slopes against differences, and the parse-time charge and moiety checks.
"""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from validation.core_seams.references import cycles as C
from validation.core_seams.references import diagrams as D
from validation.core_seams.references import exact, worlds

REG = worlds.REGISTRY_A
EPS = exact.EPS


@pytest.fixture(scope="module")
def d2():
    return worlds.law_d2()


@pytest.fixture(scope="module")
def state():
    return {"phi_V": {"N": -0.04, "P": 0.0},
            "c_mM": {"N": {"X": 12.0, "Y": 2e-4, "H": 6e-5},
                     "P": {"X": 140.0, "Y": 1.5, "H": 4e-5}}}


def test_two_routes_and_the_edge_cycle_consistency(d2, state):
    rates = D.edge_rates(d2, state, REG)
    a = D.cycle_fluxes(d2, rates, "trees")
    b = D.cycle_fluxes(d2, rates, "minors")
    p = D.steady_state(d2, rates)
    with exact.context():
        for c in d2["cycles"]:
            assert abs(a[c["id"]]["j_plus"] / b[c["id"]]["j_plus"] - 1) < Decimal("1e-50")
        assert max(abs(x - y) for x, y in zip(a["_p"], p, strict=True)) < Decimal("1e-55")
        assert D.hill_consistency(d2, rates, a, p) < Decimal("1e-55")
        # planted: an incomplete cycle set (C dropped) cannot carry every edge's flux
        w = copy.deepcopy(d2)
        w["cycles"] = [c for c in w["cycles"] if c["id"] != "C"]
        aw = D.cycle_fluxes(w, rates, "trees")
        assert D.hill_consistency(w, rates, aw, p) > Decimal("1e-6")
    assert D.cycle_set_complete(d2)["complete"] and D.basis_shares_an_edge(d2)
    assert not D.cycle_set_complete(w)["complete"]


def test_wegscheider_is_zero_for_the_passing_laws_and_refuses_each_plant(state):
    for law in (worlds.law_d1(), worlds.law_d2(), worlds.law_d3(), worlds.law_d4()):
        for c in law["cycles"]:
            aff = D.affine_residual(law, c, REG)
            assert not aff["b"] and aff["b_psi"] == 0, (law["id"], c["id"])
            assert abs(aff["r0"]) < Decimal("1e-14")
    d2 = worlds.law_d2()
    plants = {p["id"]: p for p in worlds.planted_diagrams(worlds.law_d1(), d2, worlds.law_d3(),
                                                          worlds.law_d4())}
    expect = {"__k_1pct": ("const", None), "__k_1e-6": ("const", None),
              "__charge": ("psi", None), "__conc": ("b", {("X", "P")}),
              "__swap": ("b", {("Y", "N"), ("Y", "P")})}
    for suffix, (kind, keys) in expect.items():
        law = plants["d2_slip_exchanger" + suffix]
        affs = {c["id"]: D.affine_residual(law, c, REG) for c in law["cycles"]}
        failing = [a for a in affs.values()
                   if a["b"] or a["b_psi"] or abs(a["r0"]) > Decimal("1e-12")]
        assert failing, suffix
        if kind == "psi":
            assert any(a["b_psi"] != 0 for a in failing)
        if kind == "b":
            assert any(set(a["b"]) == keys for a in failing)
    # the one-reference-state blind spot (§19 item 2): at a = 1 and ψ = 0 only r0 is left
    unit = {"phi_V": {"N": 0.0, "P": 0.0},
            "c_mM": {"N": {"X": 1000.0, "Y": 1000.0, "H": 1000.0},
                     "P": {"X": 1000.0, "Y": 1000.0, "H": 1000.0}}}
    for suffix in ("__charge", "__conc", "__swap"):
        law = plants["d2_slip_exchanger" + suffix]
        assert all(abs(D.residual(law, c, REG, unit)) < Decimal("1e-14") for c in law["cycles"])
        assert any(abs(D.residual(law, c, REG, state)) > Decimal("1e-3") for c in law["cycles"])


def test_the_factored_sign_and_a_planted_negative_S():
    law = worlds.law_v1_neutral(1)
    pop = {"capacity_fmol_per_s": 0.2, "availability": 0.75, "orientation": {"N": "a"},
           "held_rows": [["ATP", "a"], ["ADP", "a"], ["Pi", "a"]]}
    base = {"phi_V": {"a": 0.0, "b": 0.0},
            "c_mM": {"a": {"Z": 2.0, "ATP": 3.0, "ADP": 0.2, "Pi": 2.0},
                     "b": {"Z": 4.0, "ATP": 0.5, "ADP": 1.0, "Pi": 1.0}}}
    for zb in (0.5, 4.0, 4e3, 4e5):
        st = copy.deepcopy(base)
        st["c_mM"]["b"]["Z"] = zb
        q = C.population_rates(law, pop, REG, st)["modes"]["cyc"]
        assert q["J"] * q["dG_RT"] <= 0 and q["S"] >= 0
    # planted: S − 0.05 runs against its ΔG wherever S < 0.05
    bad = worlds.law_v1_neutral(1, offset=0.05)
    st = copy.deepcopy(base)
    st["c_mM"]["a"]["Z"] = 0.02
    q = C.population_rates(bad, pop, REG, st)["modes"]["cyc"]
    assert q["S"] < 0 and q["J"] * q["dG_RT"] > 0


def test_the_guard_fires_in_the_band_misses_the_mask_and_spares_the_basis():
    laws = {g["id"]: g for g in worlds.guard_laws()}
    pop = {"capacity_fmol_per_s": 1.0, "availability": 1.0, "orientation": {"N": "a"}}
    F, R, T = float(exact.FARADAY), float(exact.GAS_CONSTANT), worlds.T_K
    st = {"phi_V": {"a": 0.0, "b": 0.0},
          "c_mM": {"a": {"X": 10.0, "Y": 1e-4}, "b": {"X": 140.0, "Y": 1.8}}}
    chem = worlds._dG_RT_float(worlds.NU_A, REG, st)
    mid = copy.deepcopy(st)
    mid["phi_V"]["a"] = 0.5 * (-chem - chem / 1.2) * R * T / F
    out = copy.deepcopy(st)
    out["phi_V"]["a"] = (-chem - 0.5 * chem) * R * T / F
    tot, _t = C.population_total_JdG(laws["fb_shift"], pop, REG, mid)
    assert tot > 0
    tot, _t = C.population_total_JdG(laws["fb_shift"], pop, REG, out)
    assert tot <= 0
    tot, terms = C.population_total_JdG(laws["fb_masked"], pop, REG, mid)
    assert tot < 0 and terms["ex"] > 0              # the guard cannot see the exchange
    seen = False
    for v in (-0.12, -0.08, -0.06, -0.05, -0.04, 0.0, 0.05):
        s = copy.deepcopy(st)
        s["phi_V"]["a"] = v
        tot, terms = C.population_total_JdG(laws["fb_basis"], pop, REG, s)
        assert tot <= 0                             # never refused
        seen = seen or any(x > 0 for x in terms.values())
    assert seen                                     # yet a basis mode runs against its ΔG


def test_one_way_fluxes_obey_the_contract_and_a_flipped_exponent_does_not(d2, state):
    pop = {"capacity_fmol_per_s": 0.1, "availability": 0.8, "orientation": {"N": "a"}}
    host = {"phi_V": {"a": state["phi_V"]["N"], "b": 0.0},
            "c_mM": {"a": state["c_mM"]["N"], "b": state["c_mM"]["P"]}}
    fl = C.population_rates(d2, pop, REG, host)["modes"]
    with exact.context():
        for c in d2["cycles"]:
            q = fl[c["id"]]
            assert q["J_minus"] == q["J_plus"] * q["dG_RT"].exp()
            assert abs((q["J_minus_diagram"] / q["J_minus"]).ln()) < Decimal("1e-13")
            flipped = q["J_plus"] * (-q["dG_RT"]).exp()
            if abs(q["dG_RT"]) > Decimal("0.01"):
                assert abs(flipped / q["J_minus"] - 1) > Decimal("0.01")


def test_slopes_exact_against_differences_and_a_planted_static_head_formula():
    law = worlds.law_v1_proton(2)
    pop = {"capacity_fmol_per_s": 0.2, "availability": 0.75, "orientation": {"N": "a"},
           "held_rows": [["ATP", "a"], ["ADP", "a"], ["Pi", "a"]]}
    st = {"phi_V": {"a": -0.03, "b": 0.0},
          "c_mM": {"a": {"H": 6e-5, "ATP": 3.0, "ADP": 0.1, "Pi": 2.0}, "b": {"H": 1e-3}}}
    vol = {"a": 2.0, "b": 0.25}
    ex = C.slopes(law, pop, REG, st, vol)
    fd = C.slopes_by_differences(law, pop, REG, st, vol)
    with exact.context():
        assert abs(ex["conductance_pS"] / fd["conductance_pS"] - 1) < Decimal("1e-25")
        for k in ex["material"]:
            r = (ex["material"][k]["row_self_slope_per_s"] /
                 fd["material"][k]["row_self_slope_per_s"])
            assert abs(r - 1) < Decimal("1e-25")
        q = C.population_rates(law, pop, REG, st)["modes"]["cyc"]
        F, RT = exact.F_C_per_mol(), exact.RT_J_per_mol(REG["temperature_K"])
        k = Decimal("0.2") * Decimal("0.75")
        static = 4 * F * F * k * q["S"] / RT / 1000      # n_q² F² k a S/RT, in pS
        assert abs(static / ex["conductance_pS"] - 1) > Decimal("1")   # off static head: wrong


def test_parse_checks_refuse_each_planted_mode():
    rc = worlds.REGISTRY_C
    rows_c = {"species": dict(rc["species"], **{b: {"valence": v["base_valence"], "mu0_RT": 0.0}
                                               for b, v in rc["binders"].items()}),
              "moieties": rc["moieties"]}
    got = {p["id"]: C.parse_checks(p["nu"], REG if p["registry"] == "A" else rows_c)
           for p in worlds.PARSE_PLANTS}
    assert got["mode_species_unbalanced"]["charge_sum"] == 1
    assert not got["mode_species_unbalanced"]["admitted"]
    assert got["mode_moiety_unbalanced"]["charge_sum"] == 0
    assert got["mode_moiety_unbalanced"]["moiety_sums"]["phosphate"] == -1
    assert got["mode_base_forms_no_proton"]["charge_sum"] == -1
    assert got["mode_base_forms_hydrolysis"]["admitted"]
    for law in (worlds.law_d1(), worlds.law_d2(), worlds.law_d3(), worlds.law_d4(),
                worlds.law_v1_proton(2), worlds.law_v1_neutral(2)):
        for m in C.modes(law):
            assert C.parse_checks(m["nu"], REG)["admitted"], (law["id"], m["id"])
