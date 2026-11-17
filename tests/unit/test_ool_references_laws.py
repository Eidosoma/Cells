"""OL5 references, rows OL1-1 and OL1-4a: the event-pair law, exactly, and its checks' teeth.

The reference law is checked as a theorem (Kolmogorov exactly on registered squares and
two-cycles; the products' rule equal to the F path; the edge identity), under all four
admissible token pairs. The checks are then shown to catch every planted form on a slice of the
registered probe, each by the check README.md names.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest

from validation.ool.references import closed_world as CW
from validation.ool.references import detailed_balance as DB
from validation.ool.references import probes as P
from validation.ool.references import registered as R
from validation.ool.references.exact import RatExp
from validation.ool.references.laws import Law
from validation.ool.references.ssa_oracle import FloatRates
from validation.ool.references.world import Conventions, every_convention

PAIRS = every_convention()
PHYSICAL = Conventions(condensed_measure="multinomial", last_molecule="kept")
GARD_LIMIT = Conventions(condensed_measure="multinomial_less_one", last_molecule="extinct")
PP = dict(step="r3", place="D@membrane", lam=1)


@pytest.fixture(scope="module")
def wa():
    w = R.registered_world("ol1_wa")
    return w, [tuple(int(v) for v in s) for s in P.kernel_probe_states(w)]


@pytest.fixture(scope="module")
def probe_slice(wa):
    """Every square and two-cycle based at the first 12 base states, with their corners."""
    w, states = wa
    nus = [w.nu(st) for st in w.steps]
    keep = set(P.boundary_states(w))
    for n in P.base_states(w)[:12]:
        keep.add(n)
        for r, q in P.step_pairs(w):
            corners = [P.add(n, nus[r]), P.add(n, nus[q]), P.add(P.add(n, nus[r]), nus[q])]
            if all(P.valid(c) for c in corners):
                keep.update(corners)
        for r in range(len(nus)):
            if P.valid(P.add(n, nus[r])):
                keep.add(P.add(n, nus[r]))
    return np.array(sorted(keep), dtype=np.int64)


@pytest.mark.parametrize("conv", PAIRS, ids=lambda c: f"{c.condensed_measure}+{c.last_molecule}")
def test_reference_law_closes_every_cycle_exactly(wa, probe_slice, conv):
    w, _ = wa
    law = Law(w, conv)
    nus = [w.nu(st) for st in w.steps]
    sq = P.squares(w, probe_slice)
    checked = 0
    for n, r, q in sq:
        sr, sq_ = w.steps[r], w.steps[q]
        top = P.add(P.add(n, nus[r]), nus[q])
        rates = (law.forward(sr, n), law.forward(sq_, P.add(n, nus[r])), law.reverse(sr, top),
                 law.reverse(sq_, P.add(n, nus[q])), law.forward(sq_, n), law.forward(sr, P.add(n, nus[q])),
                 law.reverse(sq_, top), law.reverse(sr, P.add(n, nus[r])))
        if any(x.is_zero() for x in rates):
            continue
        checked += 1
        a, b, c, d, e, f, g, h = rates
        assert ((a * b * c * d) / (e * f * g * h)).is_one(), (n, sr.name, sq_.name)
    assert checked >= 80
    for n, r, q in P.two_cycles(w, probe_slice):
        p = P.add(n, nus[r])
        x = (law.forward(w.steps[r], n), law.reverse(w.steps[q], p), law.forward(w.steps[q], n),
             law.reverse(w.steps[r], p))
        if not any(v.is_zero() for v in x):
            assert ((x[0] * x[1]) / (x[2] * x[3])).is_one()


@pytest.mark.parametrize("conv", PAIRS, ids=lambda c: f"{c.condensed_measure}+{c.last_molecule}")
def test_products_rule_equals_the_F_path_and_the_edge_identity_holds(wa, probe_slice, conv):
    w, _ = wa
    law = Law(w, conv)
    listed = {tuple(int(v) for v in s) for s in probe_slice}
    for s in listed:
        for st in w.steps:
            assert law.reverse(st, s) == law.products_rule(st, s), (s, st.name)
            f = law.forward(st, s)
            p = P.add(s, law.nu[st.name])
            if f.is_zero() or law.one_way_forward(st, s) or p not in listed:
                continue
            assert f * law.weight(s) == law.reverse(st, p) * law.weight(p) / RatExp(law.exp_minus_w(st))


def test_the_extinct_boundary_is_the_cancelled_pair_rule_not_zero(wa):
    w, _ = wa
    x1 = w.step("x1")
    e_A = tuple(1 if p.name == "A@membrane" else 0 for p in w.finite)
    empty = tuple(0 for _ in w.finite)
    k_minus = x1.rate.exact * Fraction(1, 8)  # k+ exp(mu0_bil - mu0_sol) = k+ * (1/8)/1
    leave = Law(w, GARD_LIMIT).reverse(x1, e_A)
    assert leave == RatExp(k_minus)                       # G1's k-, by the cancelled form (§0.2a)
    assert Law(w, GARD_LIMIT).forward(x1, empty).is_zero()  # the empty membrane is absorbing
    assert Law(w, PHYSICAL).reverse(x1, e_A).is_zero()      # kept: the last molecule stays
    rev = Conventions(condensed_measure="multinomial", last_molecule="reversible")
    assert Law(w, rev).reverse(x1, e_A) == RatExp(k_minus) and not Law(w, rev).forward(x1, empty).is_zero()
    # planted: an engine that evaluates the leave through F with F_mem(empty) = 0 reports a literal zero
    states = np.array([empty, e_A])
    ref = DB.reference_table(Law(w, GARD_LIMIT), states)
    a_minus = ref["a_minus"].copy()
    a_minus[1, 0] = 0.0
    res = DB.compare_rates(Law(w, GARD_LIMIT), states, ref["a_plus"], a_minus, "reverse", ref)
    assert not res.passed and res.detail["zero_pattern_mismatches"] == 1


def test_float_rates_match_the_exact_law(wa):
    w, states = wa
    for conv in (PHYSICAL, GARD_LIMIT):
        law = Law(w, conv)
        fr = FloatRates(law)
        ref = DB.reference_table(law, states[::7])
        for k, s in enumerate(states[::7]):
            for r in range(len(w.steps)):
                for got, want in ((fr.forward(r, s), ref["a_plus"][k, r]), (fr.reverse(r, s), ref["a_minus"][k, r])):
                    assert (got == 0) == (want == 0)
                    if want:
                        assert abs(got / want - 1) < 1e-13


def test_design_probes_e1_and_e2_reproduce_exactly():
    e1 = CW.e1_reproduction("at_state_factor")
    assert e1["tv_float"] == pytest.approx(CW.E1_TV, abs=1e-15) and e1["worst_cycle_ratio"] == CW.E1_WORST_CYCLE
    assert CW.e1_reproduction(None)["tv"] == 0
    e2 = CW.e2_reproduction(True)
    assert e2["tv_float"] == pytest.approx(CW.E2_TV, abs=1e-15) and e2["worst_cycle_ratio"] == CW.E2_WORST_CYCLE
    assert CW.e2_reproduction(False)["tv"] == 0


@pytest.fixture(scope="module")
def tables(wa, probe_slice):
    w, _ = wa
    out = {}
    for conv in (PHYSICAL, GARD_LIMIT):
        honest = Law(w, conv)
        out[conv] = {None: DB.reference_table(honest, probe_slice)}
        for form in ("at_state_factor", "forward_only_catalysis", "one_sided", "power_propensity",
                     "normaliser_power", "extent_offset", "dropped_c0", "wrong_sign"):
            out[conv][form] = DB.reference_table(Law(w, conv, planted=form, planted_params=PP), probe_slice)
    return out


CAUGHT_BY = {
    "at_state_factor": "kolmogorov",
    "forward_only_catalysis": "kolmogorov",
    "one_sided": "kolmogorov",
    "wrong_sign": "identity",
    "dropped_c0": "identity",
    "power_propensity": "forward_form",
    "normaliser_power": "forward_form",
}


@pytest.mark.parametrize("conv", [PHYSICAL, GARD_LIMIT], ids=["physical", "gard_limit"])
def test_honest_table_passes_and_every_planted_form_is_caught(wa, probe_slice, tables, conv):
    w, _ = wa
    honest = Law(w, conv)
    t = tables[conv][None]
    res = DB.check_kernel_table(honest, probe_slice, t["a_plus"], t["a_minus"], t)
    assert all(r.passed for r in res.values()), {k: r.detail for k, r in res.items() if not r.passed}
    for form, check in CAUGHT_BY.items():
        tp = tables[conv][form]
        res = DB.check_kernel_table(honest, probe_slice, tp["a_plus"], tp["a_minus"], t)
        assert not res[check].passed, (form, check)
    # extent_offset is an error under c = 0 only
    tp = tables[conv]["extent_offset"]
    res = DB.check_kernel_table(honest, probe_slice, tp["a_plus"], tp["a_minus"], t)
    assert res["forward_form"].passed == (conv.c == 1)
    # convention-free: Kolmogorov passes for the consistent errors, which only the identity or the form sees
    for form in ("wrong_sign", "dropped_c0", "power_propensity"):
        tp = tables[conv][form]
        assert DB.kolmogorov(w, probe_slice, tp["a_plus"], tp["a_minus"]).passed


def test_the_other_measure_is_caught_by_the_identity(wa, probe_slice, tables):
    w, _ = wa
    t = tables[GARD_LIMIT][None]
    res = DB.check_kernel_table(Law(w, PHYSICAL), probe_slice, t["a_plus"], t["a_minus"], tables[PHYSICAL][None])
    assert res["kolmogorov"].passed and not res["identity"].passed
    assert res["identity"].detail["max_abs_residual"] == pytest.approx(math.log(2), rel=1e-12)


def test_the_boundary_world_closes_its_cycles_and_its_forward_extinct_form_is_probed():
    """Amendment (17 November 2026): ol1_boundary probes §0.2a's extinct rule forward."""
    import json

    w = R.registered_world("ol1_boundary")
    states = np.asarray(json.loads((R.DESIGN_DIR / "ol1_boundary_probe_states.json").read_text())["states"])
    x3, x4 = w.step("x3"), w.step("x4")
    for conv in PAIRS:
        law = Law(w, conv)
        ref = DB.reference_table(law, states)
        res = DB.check_kernel_table(law, states, ref["a_plus"], ref["a_minus"], ref)
        assert all(r.passed for r in res.values())
        assert res["kolmogorov"].detail["cycles_checked"] >= 4  # anti-parallel x1/x3 cycles included
    law = Law(w, GARD_LIMIT)
    assert law.forward(x3, (1,)) == RatExp(x3.rate.exact)                  # k ff(1,1)/ff(0,0)
    assert law.forward(x4, (2,)) == RatExp(x4.rate.exact * 2)              # k ff(2,2)/ff(1,1)
    assert Law(w, PHYSICAL).forward(x3, (1,)).is_zero()                    # kept: never empties
    # planted: an engine that gives the emptying forward channels a literal zero under extinct
    ref = DB.reference_table(law, states)
    a_plus = ref["a_plus"].copy()
    a_plus[1, 1] = 0.0
    a_plus[2, 2] = 0.0
    res = DB.check_kernel_table(law, states, a_plus, ref["a_minus"], ref)
    assert not res["forward_form"].passed and res["forward_form"].detail["zero_pattern_mismatches"] == 2


@pytest.mark.parametrize("conv", [PHYSICAL, GARD_LIMIT], ids=["physical", "gard_limit"])
def test_a_float_kernel_passes_the_registered_tolerances(wa, conv):
    """The tolerances hold for a float64 kernel, not only for tables rounded from the exact law."""
    from validation.ool.references.standin import float_table

    w, states = wa
    states = np.asarray(states)
    law = Law(w, conv)
    t = float_table(law, states)
    res = DB.check_kernel_table(law, states, t["a_plus"], t["a_minus"])
    assert all(r.passed for r in res.values()), {k: r.detail for k, r in res.items() if not r.passed}
    assert res["kolmogorov"].detail["max_abs_log_ratio"] < 1e-13
