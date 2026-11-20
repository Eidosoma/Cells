"""Integrity of the independent Beard 2005 reference (validation/mitochondria/references).

The model file parses and compiles; every parameter equals its printed value in the 2006
corrected Table 1, and exactly nine differ from the 2005 table; Eq. 22 conserves exactly the
matrix Mg2+ total and the matrix charge (the web XML's stale proton row does not); the
balanced rate laws vanish at their reactions' equilibria and the printed Eqs. 11, 16 and 24
miss theirs by the documented amounts; one steady state solves exactly. No engine code is
imported. About 3 s on one core.
"""

from __future__ import annotations

import math
import os
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from validation.mitochondria.references import audit as A
from validation.mitochondria.references import model as M

CHANGED_2006 = {"X_KH", "K_MgATP", "K_MgADP", "k_dH", "km_ADP", "k_O2", "C_IM", "X_AK", "X_MgA"}


@pytest.fixture(scope="module")
def mod():
    return M.load()


def test_model_parses_and_compiles(mod):
    assert len(mod["states"]) == 17 and tuple(s["name"] for s in mod["states"]) == M.STATES
    assert set(mod["ode"]["rows"]) == set(M.STATES)
    for arm in (M.Arm.published(), M.Arm.without_control(), M.Arm.published(table="e36"),
                M.Arm.published(J_PiHt="eq16_symport", J_C3="eq24_with_eq7_proton_term", J_F1="eq11_with_proton_term")):
        comp = M.compile_model(mod, arm)
        h = M.held(mod, comp, ADP_e=1.3e-3, Pi_e=3e-3)
        y = M.initial_state(comp, h) * (1 + 0.05 * np.arange(17) / 17)   # off every equilibrium
        d = comp.rhs(y, h)
        assert len(d) == 17 and all(math.isfinite(v) for v in d)
        dd = comp.rhs(y, h, kind="decimal")
        assert all(abs(float(a) - b) <= 1e-9 * (abs(b) + 1e-12) for a, b in zip(dd, d))
    with pytest.raises(ValueError):
        M.check_expr("__import__('os')", set())
    with pytest.raises(ValueError):
        M.check_expr("X_C1.real", {"X_C1"})


def test_parameters_match_their_printed_provenance(mod):
    P = mod["parameters"]
    assert len(P) == 35
    assert sorted(p["class"] for p in P.values()).count("A") == 16
    assert sorted(p["class"] for p in P.values()).count("B") == 17
    assert sorted(p["class"] for p in P.values()).count("C") == 2
    changed = {n for n, p in P.items() if p["e36"] != p["e8"]}
    assert changed == CHANGED_2006
    for n in changed:
        for col in ("without", "with"):
            a, b = M.parse_printed(P[n]["e36"][col]), M.parse_printed(P[n]["e8"][col])
            if n == "X_KH" and col == "without":
                assert a == b                      # only the with-control column changed
            else:
                assert a != b
    for col in ("without", "with"):
        vals = M.parameters(mod, M.Arm(column=col))
        for n, p in P.items():
            if p["e8"][col] is None:
                assert n in ("k_Pi3", "k_Pi4") and col == "without"
                continue
            assert vals[n] == M.parse_printed(p["e8"][col]) * p["scale"]
            if p["class"] in ("B", "C"):
                assert p["e8"]["with"] == p["e8"]["without"]
    tc = mod["text_constants"]
    assert (tc["DGo_C1"]["value"], tc["DGo_C3"]["value"], tc["DGo_C4"]["value"], tc["DGo_ATP"]["value"]) == \
        (-69.37, -32.53, -122.94, 36.03)
    assert M.parameters(mod, M.Arm(DGo_ATP_sign=-1))["DGo_ATP"] == -36.03
    assert mod["constants"]["T"]["value"] == M.Arm().T == 298.15          # the declared temperature (Q24)
    ids = [d["id"] for d in mod["discrepancies"]]
    assert len(ids) == len(set(ids)) and {"Q01", "Q02", "Q03", "Q06", "Q13", "Q25"} <= set(ids)


def test_eq22_conserves_matrix_mg_and_charge_exactly(mod):
    laws = M.conservation_laws(mod, M.Arm.published())
    one = Fraction(1)
    assert laws == [{"Mg_x": one, "mATP_x": one, "mADP_x": one},
                    {"H_x": one, "K_x": one, "NADH_x": -one, "ATP_x": -one, "Pi_x": -2 * one, "dPsi": one}]
    # the same laws for every documented switch, and the stale web-XML proton row (a plant)
    # loses the matrix-charge law: its invariant counts NADH with the wrong sign and the
    # intermembrane-space cytochrome c
    assert M.conservation_laws(mod, M.Arm.without_control()) == laws
    stale = M.conservation_laws(mod, M.Arm.published(H_x_row="stale_web_xml"))
    assert stale != laws and "cytCred" in stale[1] and stale[1]["NADH_x"] == one
    # each reaction's declared charge (matrix -> outside) is its coefficient in Eq. 22's dPsi row
    env = {k: Fraction(repr(v)) for k, v in M.parameters(mod, M.Arm.published()).items()}
    row = mod["ode"]["rows"]["dPsi"]["terms"]
    for name, f in mod["fluxes"].items():
        assert M.eval_fraction(str(f["charge_N_to_P"]), env) == M.eval_fraction(row.get(name, "0"), env), name


def test_rate_law_zeros(mod):
    """Delta G where each law vanishes: 0 for balanced laws; the printed Eqs. 24, 11 and 16
    stop short of their reactions' equilibria by the documented amounts."""
    comp = M.compile_model(mod, M.Arm.published())
    h = M.held(mod, comp, ADP_e=1.3e-3, Pi_e=3e-3)
    y = M.initial_state(comp, h, pH_x=7.3)
    RT = comp.params["R"] * comp.params["T"]
    hx = math.log(10 ** -7.3 / 1e-7)
    z = A.zero_offset(comp, y, h)
    for k in ("J_C1", "J_C3", "J_C4", "J_ANT", "J_KH", "J_Hle", "J_AK"):
        assert abs(z[k]) < 1e-7, (k, z[k])
    assert z["J_F1"] == pytest.approx(-RT * hx, abs=1e-7)        # Q11: Eq. 11 as printed (and as run)
    assert abs(z["J_PiHt"]) > 0.1                                 # Q03: Eq. 16 as printed (and as run)
    typeset = A.zero_offset(M.compile_model(mod, M.Arm.published(J_C3="eq24_printed")), y, h)
    assert typeset["J_C3"] == pytest.approx(2 * RT * hx, abs=1e-7)   # Q02: Eq. 24 as typeset
    fixed = M.compile_model(mod, M.Arm.published(J_F1="eq11_with_proton_term", J_PiHt="eq16_symport"))
    zf = A.zero_offset(fixed, y, h)
    for k in ("J_C3", "J_F1", "J_PiHt"):
        assert abs(zf[k]) < 1e-7, (k, zf[k])
    # planted control: ANT exponent shares that do not sum to one move the zero
    bad = M.load()
    bad["fluxes"]["J_ANT"]["expr"] = bad["fluxes"]["J_ANT"]["expr"].replace("0.65*u", "0.70*u")
    zb = A.zero_offset(M.compile_model(bad, M.Arm.published()), y, h)
    assert zb["J_ANT"] == pytest.approx(0.05 * comp.params["F"] * y[M.STATES.index("dPsi")], rel=1e-6)


def test_one_steady_state_exactly(mod):
    """State 4 at [Pi]e = 0: the 50-digit Newton solve from a rounded guess."""
    comp = M.compile_model(mod, M.Arm.published())
    h = M.held(mod, comp, ADP_e=0.0, Pi_e=0.0)
    guess = M.initial_state(comp, h, pH_x=7.14, dPsi=172.0, NADH_frac=0.6, cytc_red_frac=0.08)
    inv = [1.0e-3 * comp.params["V_x"], -0.0182]
    ss = M.steady_state(comp, h, guess, invariant_values=inv,
                        pinned=("ATP_i", "ADP_i", "AMP_i", "mATP_i", "mADP_i"))
    assert ss.residual < 1e-30
    y = ss.floats()
    fl = comp.fluxes(y, h)
    J = fl["J_C4"]
    for k in ("J_DH", "J_C1", "J_C3"):
        assert fl[k] == pytest.approx(J, rel=1e-25)
    assert fl["J_F1"] == pytest.approx(0, abs=1e-30) and fl["J_ANT"] == 0
    assert fl["J_Hle"] == pytest.approx(10 * J, rel=1e-20)            # charge balance with no ATP turnover
    S = dict(zip(M.STATES, y))
    assert S["K_x"] / h["K_e"] == pytest.approx(S["H_x"] / h["H_e"], rel=1e-20)   # J_KH = 0
    assert [float(v) for v in ss.invariant_values] == pytest.approx(inv, rel=1e-30)
    assert S["dPsi"] == pytest.approx(REGRESSION["dPsi"], rel=1e-9)
    assert S["NADH_x"] / comp.params["NAD_tot"] == pytest.approx(REGRESSION["NADH_frac"], rel=1e-9)


REGRESSION = {"dPsi": 169.61840978312566, "NADH_frac": 0.599482310978628}   # this reference, 19 Nov 2026


@pytest.mark.skipif(not os.environ.get("MITO_REF_PAPERS"), reason="set MITO_REF_PAPERS to a local download of both XMLs")
def test_printed_values_against_the_publisher_xml(mod):
    from validation.mitochondria.references import sources as SRC
    d = Path(os.environ["MITO_REF_PAPERS"])
    rep = SRC.check_model(mod, SRC.read(SRC.ARTICLE, d), SRC.read(SRC.CORRECTION, d))
    assert len(rep) == 140 and all(r["status"] == "ok" for r in rep)
