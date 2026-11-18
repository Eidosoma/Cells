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
