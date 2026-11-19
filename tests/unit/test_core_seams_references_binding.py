"""Seam C's references (CORE_SEAMS_DESIGN §5, §17, §19) on their own, each with a planted error.

- the speciation by Newton, by nested bisection and against a manufactured solution; a K off by
  1e-6 moves it past the residual's floor;
- conservation and charge from totals, which a mis-declared form valence breaks;
- a form below its base, with a negative ligand total;
- G*'s gradient equals the free base forms' potentials, which the rows' own potentials do not;
- P1's node: today's predictor goes negative while the equilibrated free amount does not;
- the movers' verdicts.
"""

from __future__ import annotations

import copy
import math
from decimal import Decimal

import pytest

from validation.core_seams.references import api, exact, worlds
from validation.core_seams.references import binding as B

REG = worlds.REGISTRY_C
S4 = {"ligands": ["H", "Mg"], "binders": ["nuc4", "nuc3", "pi2"]}


@pytest.fixture(scope="module")
def s4():
    sy = B.System(S4, REG)
    free = {"H": 10 ** (3 - 7.1), "Mg": 0.6}
    tB = {"nuc4": 8.0, "nuc3": 1.0, "pi2": 6.0}
    TL = {k: float(v) for k, v in B.manufacture(sy, free, tB, 2.0).items()}
    return sy, free, tB, TL


def test_newton_bisection_and_the_manufactured_solution_agree(s4):
    sy, free, tB, TL = s4
    sp = B.solve(sy, TL, tB, 2.0)
    bi = B.solve_bisection(sy, TL, tB, 2.0, bits=90)
    with exact.context():
        for L in sy.ligands:
            assert abs(sp["x_mM"][L] / bi["x_mM"][L] - 1) < Decimal("1e-24")
            assert abs(sp["x_mM"][L] / exact.dec(free[L]) - 1) < Decimal("1e-13")
        sens = B.sensitivities(sy, sp, TL, tB, 2.0)
        floor = max(sens["residual_bound"]["x"].values())
        # planted: one form's K off by 1e-6 moves a free form far beyond the residual's floor
        reg = copy.deepcopy(REG)
        f = next(f for f in reg["binders"]["nuc4"]["forms"] if f["id"] == "nuc4_MgH")
        f["mu0_RT"] -= math.log1p(1e-6)
        sp2 = B.solve(B.System(S4, reg), TL, tB, 2.0)
        dev = max(abs((sp2["forms_mM"]["nuc4"][k] / sp["forms_mM"]["nuc4"][k]).ln())
                  for k in sp["forms_mM"]["nuc4"])
        assert dev > 10 * floor


def test_conservation_and_charge_from_totals_and_a_planted_valence(s4):
    sy, _free, tB, TL = s4
    sp = B.solve(sy, TL, tB, 2.0)
    assert max(B.conservation(sy, sp, TL, tB, 2.0).values()) < Decimal("1e-50")
    ch = B.charge(sy, sp, TL, tB, 2.0)
    assert abs(ch["difference_fmol_e"]) < Decimal("1e-50")
    # planted: MgATP declared at −1, not z_base + z_Mg = −2
    bad = B.charge(sy, sp, TL, tB, 2.0, declared_valence={("nuc4", "nuc4_Mg"): -1})
    with exact.context():
        moved = 2 * sp["forms_mM"]["nuc4"]["nuc4_Mg"]
        assert abs(bad["difference_fmol_e"] - moved) < Decimal("1e-40")
    assert sy.form_valence("nuc4", sy.forms["nuc4"][3]) == -2


def test_a_form_below_its_base_admits_a_negative_ligand_total():
    sy = B.System(S4, REG)
    free = {"H": 10 ** (3 - 11.0), "Mg": 0.5}
    tB = {"nuc4": 10.0, "nuc3": 1.0, "pi2": 40.0}
    TL = {k: float(v) for k, v in B.manufacture(sy, free, tB, 2.0).items()}
    assert TL["H"] < 0 and TL["H"] > float(sy.admissible_floor(tB)["H"])
    sp = B.solve(sy, TL, tB, 2.0)
    assert max(B.conservation(sy, sp, TL, tB, 2.0).values()) < Decimal("1e-45")
    assert abs(B.charge(sy, sp, TL, tB, 2.0)["difference_fmol_e"]) < Decimal("1e-45")
    with pytest.raises(ValueError):
        B.solve(sy, dict(TL, H=float(sy.admissible_floor(tB)["H"]) - 1.0), tB, 2.0)


def test_the_gradient_of_G_star_is_the_free_potentials_not_the_rows_own():
    spec = {"ligands": ["H", "Mg"], "binders": ["nuc4"]}
    sy = B.System(spec, REG)
    tB = {"nuc4": 5.0}
    TL = {k: float(v) for k, v in B.manufacture(sy, {"H": 1e-4, "Mg": 0.3}, tB, 1.0).items()}
    sp = B.solve(sy, TL, tB, 1.0)
    pot = B.potentials(sy, sp)
    gd = B.gradient_by_differences(sy, TL, tB, 1.0)
    with exact.context():
        for r in pot:
            assert abs(pot[r] / gd[r] - 1) < Decimal("1e-25")
        RT = exact.RT_J_per_mol(310.0)
        own_H = RT * (exact.dec(0.0) + (exact.dec(TL["H"]) / (1000 * exact.dec(1.0))).ln())
        assert abs(own_H - gd["H"]) > 1000           # planted: the row's own ideal potential
        G = B.free_energy(sy, sp, 1.0)
        reg = copy.deepcopy(REG)
        reg["binders"]["nuc4"]["forms"] = [f for f in reg["binders"]["nuc4"]["forms"]
                                           if f["id"] != "nuc4_Mg"]
        sp2 = B.solve(B.System(spec, reg), TL, tB, 1.0)
        sp2["forms_mM"]["nuc4"]["nuc4_Mg"] = Decimal(0)
        assert B.free_energy(sy, sp2, 1.0) > G       # planted: a speciation that is not the minimum


def test_p1_today_predictor_turns_negative_while_the_free_amount_does_not():
    node = worlds.P1_NODES["P1a"]
    tot = worlds.totals_from_manufactured(node["system"], {"free_mM": node["free_mM"],
                                                           "binders_mM": node["binders_mM"]},
                                          node["volume_pL"])
    out = api.p1(dict(node, totals=tot), REG)
    assert out["ratio_stored_over_free"] > 1e5 and out["ratio_linearised_over_free"] > 1e5
    for row in out["ladder"]:
        if row["drawn_over_free"] > 1:
            assert row["today_predictor_fmol"] < 0
            assert row["free_after_fmol"] > 0


def test_mover_verdicts():
    got = {m["id"]: api.mover_verdict(m, REG)["verdict"] for m in worlds.MOVERS}
    assert got == {m["id"]: m["expected"] for m in worlds.MOVERS}


def test_the_booked_term_holds_in_either_split_and_each_plant_is_its_named_sum(s4):
    """Amendment C1 (§19 amended at 19:52 UTC): E_c = G* − Σ T μ°′ = S_c + Σ ideal; across two
    states of one system each planted booking misses ΔE_c by exactly its named sum."""
    sy, free, tB, TL = s4
    tB2 = {"nuc4": 6.0, "nuc3": 1.5, "pi2": 9.0}
    TL2 = {k: float(v) for k, v in B.manufacture(sy, {"H": 10 ** (3 - 6.8), "Mg": 0.9}, tB2,
                                                 2.0).items()}
    a = B.booked(sy, B.solve(sy, TL, tB, 2.0), TL, tB, 2.0)
    b = B.booked(sy, B.solve(sy, TL2, tB2, 2.0), TL2, tB2, 2.0)
    with exact.context():
        for x in (a, b):
            assert abs(x["E_c_pJ"] - x["S_c_pJ"] - x["ideal_total_pJ"]) < Decimal("1e-50")
        dE = b["E_c_pJ"] - a["E_c_pJ"]
        whole = (b["G_star_pJ"] - a["G_star_pJ"]) - dE
        assert abs(whole - (b["standard_total_pJ"] - a["standard_total_pJ"])) < Decimal("1e-45")
        b4 = (b["B4_term_pJ"] - a["B4_term_pJ"]) - (b["S_c_pJ"] - a["S_c_pJ"])
        binders = sum(b["standard_parts_pJ"][r] - a["standard_parts_pJ"][r] for r in tB)
        assert abs(b4 - binders) < Decimal("1e-45") and abs(binders) > Decimal("1e-3")
        masked = (b["S_c_pJ"] - a["S_c_pJ"]) - dE
        assert abs(masked + (b["ideal_total_pJ"] - a["ideal_total_pJ"])) < Decimal("1e-45")
    # at a negative H total, E_c and G* are defined and S_c is not
    TLn = {k: float(v) for k, v in B.manufacture(sy, {"H": 1e-8, "Mg": 0.5},
                                                 {"nuc4": 5.0, "nuc3": 0.5, "pi2": 20.0},
                                                 2.0).items()}
    tBn = {"nuc4": 10.0, "nuc3": 1.0, "pi2": 40.0}
    assert TLn["H"] < 0
    n = B.booked(sy, B.solve(sy, TLn, tBn, 2.0), TLn, tBn, 2.0)
    assert n["S_c_pJ"] is None and n["E_c_pJ"] is not None


def test_E_c_gradient_is_the_free_potential_in_the_1_mM_frame(s4):
    sy, _free, tB, TL = s4
    sp = B.solve(sy, TL, tB, 2.0)
    g3 = B.booked(sy, sp, TL, tB, 2.0)["gradient_at3_J_per_mol"]
    gd = B.booked_gradient_by_differences(sy, TL, tB, 2.0)
    with exact.context():
        for r in g3:
            assert abs(g3[r] - gd[r]) < Decimal("1e-20")
        # planted: G*'s gradient (the registry's frame) is off by each row's μ°′
        g = B.potentials(sy, sp)
        assert abs(g["H"] - gd["H"]) > 1000


def test_the_primal_route_agrees_with_the_dual_and_a_planted_K_does_not(s4):
    """Amendment C1: the primal Gibbs minimum by Newton on extents (primal.py), sharing only the
    registry's inputs with the dual, certifies itself and agrees with the dual solve."""
    from validation.core_seams.references import primal
    sy, _free, tB, TL = s4
    sp = B.solve(sy, TL, tB, 2.0)
    pr = primal.solve_primal(S4, REG, TL, tB, 2.0)
    assert pr["certificate"] <= Decimal("1e-50")
    with exact.context():
        for L in sy.ligands:
            assert abs((pr["x_mM"][L] / sp["x_mM"][L]).ln()) < Decimal("1e-45")
        for Bn in sy.binders:
            for f, c in sp["forms_mM"][Bn].items():
                assert abs((pr["forms_mM"][Bn][f] / c).ln()) < Decimal("1e-45")
        # planted: one form's K off by 1e-6 in the primal's inputs
        reg = copy.deepcopy(REG)
        f = next(f for f in reg["binders"]["nuc4"]["forms"] if f["id"] == "nuc4_MgH")
        f["mu0_RT"] -= math.log1p(1e-6)
        bad = primal.solve_primal(S4, reg, TL, tB, 2.0)
        dev = max(abs((bad["forms_mM"]["nuc4"][k] / c).ln())
                  for k, c in sp["forms_mM"]["nuc4"].items())
        assert dev > Decimal("1e-8")


def test_the_convergence_scale_is_the_total_unless_counts_mix_signs(s4):
    """Amendment C2 (§19 amended at 19:52 UTC): |g_L| ≤ 1e-13 V A_L, A_L = x_L + Σ|n| c. It is
    |T_L| where every count is ≥ 0; at a cancelling H total the |T_L| scale asks for less than one
    ulp of the residual's terms, which no solver can meet, and the reference converges only on
    V A_L (its own solver failed there before the amendment)."""
    spec3 = {"ligands": ["H", "Mg"], "binders": ["nuc4"]}
    sy3 = B.System(spec3, REG)
    tB3 = {"nuc4": 5.0}
    TL3 = {k: float(v) for k, v in B.manufacture(sy3, {"H": 1e-4, "Mg": 0.3}, tB3, 1.0).items()}
    sc3 = B.residual_scale(sy3, B.solve(sy3, TL3, tB3, 1.0), 1.0)
    with exact.context():
        for L in sy3.ligands:
            assert abs(sc3[L] / exact.dec(TL3[L]) - 1) < Decimal("1e-40")
    sy, _free, _tB, _TL = s4
    tB = {"nuc4": 10.0, "nuc3": 1.0, "pi2": 40.0}
    TL = {k: float(v) for k, v in B.manufacture(sy, {"H": 2.791027282207225e-07, "Mg": 0.5}, tB,
                                                2.0).items()}
    sp = B.solve(sy, TL, tB, 2.0)
    sc = B.residual_scale(sy, sp, 2.0)
    with exact.context():
        ratio = abs(exact.dec(TL["H"])) / sc["H"]
        assert ratio < Decimal("1e-6")
        # planted: the |T_L| scale's tolerance at this state, in ulps of the residual's terms
        assert Decimal("1e-13") * ratio / exact.dec(exact.EPS) < 1
        assert abs(sp["residual_fmol"]["H"]) <= Decimal("1e-50") * sc["H"]


def test_the_per_ligand_floors_admit_a_jointly_infeasible_state_and_the_margin_refuses_it():
    """Amendment C4 (§19 amended at 19:52 UTC): mgx_MgmH frees a proton only by binding Mg²⁺. At
    T_H = −2, T_Mg = 1, T_B = 10 fmol each per-ligand floor passes (H > −10, Mg > 0), but freeing
    the protons takes more Mg²⁺ than there is. The exact margin is t* = −1/2 fmol; the LP agrees;
    the dual and primal solves both refuse. At T_Mg = 3 it is +1/2 and both solve, alike."""
    from fractions import Fraction

    from validation.core_seams.references import primal
    spec = {"ligands": ["H", "Mg"], "binders": ["mgx"]}
    sy = B.System(spec, REG)
    tB = {"mgx": 10.0}
    bad = B.joint_margin(sy, {"H": -2.0, "Mg": 1.0}, tB)
    assert bad["per_ligand_valid"] and not bad["valid"]
    assert bad["t_star"] == Fraction(-1, 2)
    assert abs(B.joint_margin_lp(sy, {"H": -2.0, "Mg": 1.0}, tB) + 0.5) < 1e-12
    with pytest.raises(ValueError, match="jointly infeasible"):
        B.solve(sy, {"H": -2.0, "Mg": 1.0}, tB, 1.0)
    with pytest.raises(ValueError):
        primal.solve_primal(spec, REG, {"H": -2.0, "Mg": 1.0}, tB, 1.0)
    assert B.joint_margin(sy, {"H": -2.0, "Mg": 2.0}, tB)["t_star"] == 0      # the boundary
    ok = B.joint_margin(sy, {"H": -2.0, "Mg": 3.0}, tB)
    assert ok["valid"] and ok["t_star"] == Fraction(1, 2)
    d = B.solve(sy, {"H": -2.0, "Mg": 3.0}, tB, 1.0)
    p = primal.solve_primal(spec, REG, {"H": -2.0, "Mg": 3.0}, tB, 1.0)
    with exact.context():
        for L in ("H", "Mg"):
            assert abs((d["x_mM"][L] / p["x_mM"][L]).ln()) < Decimal("1e-45")
    # where no count is negative, the margin is the per-ligand floors' product region
    s3 = B.System({"ligands": ["H", "Mg"], "binders": ["nuc4"]}, REG)
    m = B.joint_margin(s3, {"H": 0.3, "Mg": 0.2}, {"nuc4": 5.0})
    assert m["valid"] and m["t_star"] == min(m["per_ligand"].values())
