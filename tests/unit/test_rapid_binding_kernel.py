"""The general closure's kernel against the core-seams references (laws/reactions/rapid_binding.py;
docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026; the references are
validation/core_seams/references, registered with their amendments C1-C3 before this output).

The engine runs on the references' registered inputs (the seam-C registry, systems S1-S6 with their
71 states' totals, the P1 nodes and the envelope's eight cases). It is compared with their recorded
values at the tolerances frozen before any read of the values
(core-pass-binding-20261118/frozen_constants.json, 23:13:29 UTC):
- the solve meets |g_L| <= 1e-13 A_L at every state, and its free ligands and forms lie within twice
  the references' floor_residual_1e-13. Its plants: a constant x1.01, a dropped form and a count
  off by one;
- B4's path is B4's kernel bit for bit, and Newton agrees with it within the floor. A node's
  disjoint ligand sets solve exactly as if alone;
- the booked terms E_c, G* and S_c are within 16 eps of their terms, with S4[10]'s S_c undefined;
- the registered law declares the general form (seam F's fields), its free_energy G*.
  The pairs' changes are within twice their floor, and each of the three planted bookings misses by
  its named sum;
- P1's nodes: the free amount, the admissible floor and the ladder's equilibrated free amounts,
  where today's predictor turns negative past n_free;
- the envelope's first-order lag lies within twice its floor on all eight cases, and equals B4's
  estimate for one two-form buffer. The cooperative chain is outside the budget, and a per-step
  minimum puts it inside (that plant flips the verdict); k_on swapped between ligands is caught;
- the fixed iteration count converges at a seeded random sweep, and too few iterations do not.
Held (CORE_SEAMS §19, C4 to come): nothing here tests or claims the refusal of jointly
infeasible totals with mixed-sign counts.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cells.laws.electrochemistry import R
from cells.laws.reactions import rapid_binding as kernel
from cells.laws.reactions import rapid_proton_buffer as b4

REFS = Path(__file__).resolve().parents[2] / "validation" / "core_seams" / "references"
INPUTS = json.loads((REFS / "reference_inputs.json").read_text())["seam_c"]
VALUES = json.loads((REFS / "designs" / "core_seams_reference_values.json").read_text())["seam_c"]
REGISTRY = INPUTS["registry"]
C0 = REGISTRY["standard_concentration_mM"]
T_K = REGISTRY["temperature_K"]
EPS = np.finfo(float).eps


def binder_spec(binder, ligands, kon=None, *, plant=None):
    """(binder, forms base first with ln beta at c0, c0, k_on per ligand) from the registry, with an
    optional plant on the binder's forms: (form id, "constant" | "count")."""
    mu = {s: REGISTRY["species"][s]["mu0_RT"] for s in ligands}
    forms = REGISTRY["binders"][binder]["forms"]
    base = forms[0]["mu0_RT"]
    out = []
    for f in forms:
        pairs = tuple(f.get("counts", {}).items())
        beta = 0.0 if not pairs else base + sum(n * mu[s] for s, n in pairs) - f["mu0_RT"]
        if plant and plant[0] == f["id"] and plant[1] == "constant":
            beta += math.log(1.01)
        if plant and plant[0] == f["id"] and plant[1] == "count":
            pairs = ((pairs[0][0], pairs[0][1] + 1),) + pairs[1:]
        out.append((f["id"], pairs, beta))
    rates = tuple((s, (kon or {}).get((binder, s), 1.0)) for s in ligands)
    return (binder, tuple(out), C0, rates)


def system(name, *, plant=None, drop=None):
    s = INPUTS["systems"][name]
    ligands, binders = tuple(s["ligands"]), tuple(s["binders"])
    net = kernel.network(ligands, tuple(binder_spec(b, ligands, plant=plant) for b in binders))
    if drop is not None:  # Planted: the designated form dropped.
        for b, binder in enumerate(binders):
            for f, form in enumerate(REGISTRY["binders"][binder]["forms"]):
                if form["id"] == drop:
                    net["present"][b, f] = False
    return ligands, binders, s["volume_pL"], net


def totals(name, ligands, binders):
    states = INPUTS["manufactured_states"][name]
    volume = INPUTS["systems"][name]["volume_pL"]
    tl = np.array([[st["totals"]["ligands_fmol"][s] / volume for st in states] for s in ligands])
    tb = np.array([[st["totals"]["binders_fmol"][b] / volume for st in states] for b in binders])
    return tl, tb


def masks(net, nodes):
    member = np.ones((net["counts"].shape[0], nodes), dtype=bool)
    return kernel.connected_sets(member, net["counts"])


def one_step_k(binders, ligand):
    """Each binder's K as version 1 computes it: c0 exp(mu°_f - mu°_base - mu°_L)."""
    mu_l = REGISTRY["species"][ligand]["mu0_RT"]
    out = []
    for b in binders:
        forms = REGISTRY["binders"][b]["forms"]
        out.append(C0 * math.exp(forms[1]["mu0_RT"] - forms[0]["mu0_RT"] - mu_l))
    return np.array(out)


def solve(name, *, path=None, steps=kernel.NEWTON_STEPS, **planted):
    ligands, binders, volume, net = system(name, **planted)
    tl, tb = totals(name, ligands, binders)
    held, comp_l, comp_b = masks(net, tl.shape[1])
    use = path or net["path"]
    k = one_step_k(binders, ligands[0]) if use == "b4" else None
    u, valid = kernel.free_ligands(
        tl, tb, net["log_beta"], net["counts"], net["present"], held, comp_l, comp_b, k,
        path=use, steps=steps, xp=np,
    )  # fmt: skip
    return ligands, binders, volume, net, tl, tb, held, u, valid


def deviations(name, ligands, binders, net, tb, u):
    """Per state, max over the free ligands and every present form of |ln c - ln c_ref| over twice
    the references' floor_residual_1e-13 (> 1 is outside the tolerance)."""
    states = VALUES["systems"][name]["states"]
    x, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    worst = []
    for k, st in enumerate(states):
        floor = st["floor_residual_1e-13"]
        ratios = [abs(math.log(x[l, k]) - math.log(st["x_mM"][s])) / (2 * floor["x"][s])
                  for l, s in enumerate(ligands)]
        for b, binder in enumerate(binders):
            for f, form in enumerate(REGISTRY["binders"][binder]["forms"]):
                if not net["present"][b, f] or forms[b, f, k] <= 0:
                    continue
                ref = st["forms_mM"][binder][form["id"]]
                key = f"{binder}|{form['id']}"
                ratios.append(abs(math.log(forms[b, f, k]) - math.log(ref)) / (2 * floor["forms"][key]))
        worst.append(max(ratios))
    return np.array(worst)


SYSTEMS = sorted(INPUTS["systems"])


@pytest.mark.parametrize("name", SYSTEMS)
def test_the_solve_meets_the_references_at_every_registered_state(name):
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    assert valid.all()
    g, scale = kernel.residual(u, tl, tb, net["log_beta"], net["counts"], net["present"], held,
                               xp=np)
    assert np.all(np.abs(g) <= kernel.RESIDUAL_RTOL * scale)
    assert np.all(deviations(name, ligands, binders, net, tb, u) <= 1.0)
    designated = INPUTS["systems"][name]["designated"]
    for planted in (dict(plant=(designated, "constant")), dict(drop=designated),
                    dict(plant=(designated, "count"))):
        p_ligands, p_binders, _, p_net, _, p_tb, _, p_u, _ = solve(name, path="newton", **planted)
        assert np.max(deviations(name, p_ligands, p_binders, p_net, p_tb, p_u)) > 1.0, planted


@pytest.mark.parametrize("name", ["S1", "S2"])
def test_b4s_path_is_b4_bit_for_bit_and_newton_agrees(name):
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    assert net["path"] == "b4"
    k = one_step_k(binders, ligands[0])
    h, ok = b4.free_proton(tl[0], tb, k[:, None], xp=np)
    assert np.array_equal(u[0], np.log(h)) and np.array_equal(valid, ok)
    *_, u_newton, valid_newton = solve(name, path="newton")
    assert valid_newton.all()
    assert np.all(deviations(name, ligands, binders, net, tb, u_newton) <= 1.0)


def test_disjoint_ligand_sets_solve_exactly_as_if_alone():
    """S5: H on buf1 and Ca on cab0 at one node. The joint solve equals each set solved alone, bit
    for bit (Cholesky solves a block-diagonal system blockwise; the line search is per set).
    Planted: one shared line search per node makes the iterates differ."""
    ligands, binders, volume, net, tl, tb, held, u, valid = solve("S5")
    assert ligands == ("H", "Ca") and binders == ("buf1", "cab0")
    for keep_l, keep_b in ((0, 0), (1, 1)):
        alone = kernel.network((ligands[keep_l],), (binder_spec(binders[keep_b], (ligands[keep_l],)),))
        a_tl, a_tb = tl[keep_l : keep_l + 1], tb[keep_b : keep_b + 1]
        a_held, a_cl, a_cb = masks(alone, tl.shape[1])
        a_u = kernel.newton_ligands(a_tl, a_tb, alone["log_beta"], alone["counts"],
                                    alone["present"], a_held, a_cl, a_cb, xp=np)
        assert np.array_equal(a_u[0], u[keep_l])
    merged_l = held[None].astype(float).repeat(1, axis=0)  # One set holding both ligands.
    merged_b = np.ones((1, 2, tl.shape[1]))
    one = kernel.newton_ligands(tl, tb, net["log_beta"], net["counts"], net["present"], held,
                                merged_l, merged_b, xp=np)
    assert not np.array_equal(one, u)


def mu0p(ligands, binders):
    lig = np.array([REGISTRY["species"][s]["mu0_RT"] - math.log(C0) for s in ligands])
    bind = np.array([REGISTRY["binders"][b]["forms"][0]["mu0_RT"] - math.log(C0) for b in binders])
    return lig, bind


def booked(name):
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    lig, bind = mu0p(ligands, binders)
    return kernel.booked_terms_pJ(u, tl, tb, net["log_beta"], net["counts"], net["present"], held,
                                  lig, bind, volume, T_K, xp=np)


@pytest.mark.parametrize("name", SYSTEMS)
def test_the_booked_terms_meet_the_references(name):
    e_c, g_star, s_c, defined = booked(name)
    states = VALUES["systems"][name]["states"]
    for k, st in enumerate(states):
        term = st["booked_term"]
        floor = 16 * EPS * term["terms_abs_pJ"]
        assert abs(e_c[k] - term["E_c_pJ"]) <= floor, (k, e_c[k], term["E_c_pJ"])
        assert abs(g_star[k] - term["G_star_pJ"]) <= floor, (k, g_star[k], term["G_star_pJ"])
        assert bool(defined[k]) is (term["S_c_pJ"] is not None)
        if term["S_c_pJ"] is not None:
            assert abs(s_c[k] - term["S_c_pJ"]) <= floor
    if name == "S4":
        assert not defined[10] and np.isfinite(e_c[10])  # H total < 0: E_c defined, S_c not.


def test_the_registered_law_declares_the_general_form_and_its_free_energy_is_g_star():
    """rapid_binding@1 as registered carries seam F's BindingLaw fields. Its forms are the
    registry's, its envelope and P1's free amounts are the kernel's, and its free_energy is G*,
    bit for bit with booked_terms_pJ's at S3's states. Planted: G* and E_c differ there, so a
    free_energy that returned E_c would be caught."""
    from cells.registry import laws

    law = laws.active().lookup(kernel.READ_ID)
    assert law is kernel.LAW and law.forms == "registry"
    assert law.envelope is kernel.lag_first_order and law.free_amounts is kernel.free_amounts
    ligands, binders, volume, net, tl, tb, held, u, valid = solve("S3")
    lig, bind = mu0p(ligands, binders)
    args = (u, tl, tb, net["log_beta"], net["counts"], net["present"], held, lig, bind, volume, T_K)
    e_c, g_star, _, _ = kernel.booked_terms_pJ(*args, xp=np)
    assert np.array_equal(law.free_energy(*args, xp=np), g_star)
    assert np.all(np.abs(g_star - e_c) > 16 * EPS * np.abs(g_star))


@pytest.mark.parametrize("name", SYSTEMS)
def test_each_pair_changes_by_dE_c_and_each_planted_booking_misses_by_its_sum(name):
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    e_c, g_star, s_c, defined = booked(name)
    lig, bind = mu0p(ligands, binders)
    rt = 1e-3 * R * T_K
    caught = dict.fromkeys(("G_star_booked_whole", "B4_formula_on_moved_binders",
                            "S_c_alone_ideal_masked"), False)
    for pair in VALUES["systems"][name]["pairs"]:
        k, n = pair["pair"]
        floor = 2 * pair["floor_pJ"]
        d_e = e_c[n] - e_c[k]
        assert abs(d_e - pair["dE_c_pJ"]) <= floor, (pair["pair"], d_e, pair["dE_c_pJ"])
        # The references record each plant's miss as an amount, unsigned.
        misses = dict(
            G_star_booked_whole=d_e - (g_star[n] - g_star[k]),
            B4_formula_on_moved_binders=-rt * float(bind @ (tb[:, n] - tb[:, k])) * volume,
            S_c_alone_ideal_masked=(d_e - (s_c[n] - s_c[k])) if defined[k] and defined[n] else None,
        )
        for plant, miss in misses.items():
            ref = pair["plants_pJ"][plant]
            if miss is None or ref is None:
                continue
            assert abs(abs(miss) - ref) <= floor, (plant, pair["pair"], miss, ref)
            caught[plant] |= abs(miss) > floor
    assert all(caught.values()), caught


def p1_network(node):
    spec = INPUTS["p1_nodes"][node]["system"]
    ligands, binders = tuple(spec["ligands"]), tuple(spec["binders"])
    return ligands, binders, kernel.network(ligands, tuple(binder_spec(b, ligands) for b in binders))


def admitted_bound(u, tb, net, held):
    """The criterion's first-order worst case in ln x per ligand (its own scale, A_L)."""
    hess = kernel._hessian(u, tb, net["log_beta"], net["counts"], net["present"], held, xp=np)
    _, scale = kernel.residual(u, np.zeros_like(u), tb, net["log_beta"], net["counts"],
                               net["present"], held, xp=np)
    out = []
    for n in range(u.shape[1]):
        inverse = np.abs(np.linalg.inv(hess[:, :, n]))
        out.append(kernel.RESIDUAL_RTOL * inverse @ scale[:, n])
    return np.array(out).T


@pytest.mark.parametrize("node", ["P1a", "P1b"])
def test_p1s_free_amount_floor_and_ladder(node):
    """P1 (CORE_SEAMS §17): the closure's free amount at the node's stored totals, its admissible
    floor, and after each of the ladder's draws of k n_free from the ligand's total, the
    equilibrated free amount. Today's predictor (the free amount less the draw) turns negative past
    n_free, while the equilibrated free amount stays positive."""
    case, ref = INPUTS["p1_nodes"][node], VALUES["p1"][node]
    ligands, binders, net = p1_network(node)
    volume, ligand = case["volume_pL"], case["ligand"]
    tl = np.array([[case["totals"]["ligands_fmol"][s]] for s in ligands])
    tb = np.array([[case["totals"]["binders_fmol"][b]] for b in binders])
    draws = [r["drawn_fmol"] for r in ref["ladder"]]
    which = ligands.index(ligand)
    tl_all = np.repeat(tl, 1 + len(draws), axis=1)
    tl_all[which, 1:] -= np.array(draws)
    tb_all = np.repeat(tb, 1 + len(draws), axis=1)
    held, comp_l, comp_b = masks(net, tl_all.shape[1])
    k = one_step_k(binders, ligands[0]) if net["path"] == "b4" else None
    free, _, valid = kernel.free_amounts(tl_all, tb_all, volume, net["log_beta"], net["counts"],
                                         net["present"], held, comp_l, comp_b, k,
                                         path=net["path"], xp=np)
    assert valid.all()
    u = np.log(free / volume)
    bound = 2 * admitted_bound(u, tb_all / volume, net, held)[which]
    assert abs(free[which, 0] / ref["n_free_fmol"] - 1) <= bound[0]
    floor = kernel.admissible_floor(tb / volume, net["counts"], net["present"], xp=np)[which, 0]
    assert abs(floor * volume - ref["admissible_floor_fmol"]) <= 16 * EPS * abs(tb).sum()
    for r, rung in enumerate(ref["ladder"], start=1):
        assert abs(free[which, r] / rung["free_after_fmol"] - 1) <= bound[r], rung
        assert free[which, r] > 0
        today = ref["n_free_fmol"] - rung["drawn_fmol"]
        assert (today < 0) is (rung["drawn_over_free"] > 1)


def envelope_case(name, *, swap=False):
    case = INPUTS["envelope"]["cases"][name]
    ligands, binders = tuple(case["ligands"]), tuple(case["binders"])
    kon = {(b, l): k for b, l, k in case["kon_per_mM_per_s"]}
    if swap:  # Planted: k_on swapped between the two ligands.
        kon = {(b, l): kon[(b, other)] for (b, l) in kon for other in ligands if other != l}
    net = kernel.network(ligands, tuple(binder_spec(b, ligands, kon) for b in binders))
    volume = case["volume_pL"]
    tl = np.array([[case["totals"]["ligands_fmol"][s] / volume] for s in ligands])
    tb = np.array([[case["totals"]["binders_fmol"][b] / volume] for b in binders])
    held, comp_l, comp_b = masks(net, 1)
    u, valid = kernel.free_ligands(tl, tb, net["log_beta"], net["counts"], net["present"], held,
                                   comp_l, comp_b, path="newton", xp=np)
    drives = dict(case["drive_fmol_per_s"])
    d_l = np.array([[drives.get(s, 0.0) / volume] for s in ligands])
    d_b = np.array([[drives.get(b, 0.0) / volume] for b in binders])
    _, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    lag = kernel.lag_first_order(u, forms, tb, d_l, d_b, net["log_beta"], net["counts"],
                                 net["present"], held, net["step_matrix"], net["step_from"],
                                 net["step_ligand"], net["step_kon"], net["conservation"], xp=np)
    return ligands, binders, net, tl, tb, u, valid, lag


@pytest.mark.parametrize("name", sorted(INPUTS["envelope"]["cases"]))
def test_the_first_order_lag_meets_the_envelope_reference(name):
    ligands, _, _, _, _, _, valid, lag = envelope_case(name)
    ref = VALUES["envelope"]["cases"][name]
    assert valid.all()
    for l, s in enumerate(ligands):
        expected = ref["first_order_dln"][s]
        assert abs(lag[l, 0] - expected) <= 2 * ref["first_order_floor_rel"] * abs(expected), (
            s, lag[l, 0], expected)  # fmt: skip
    ph = abs(lag[ligands.index("H"), 0]) / kernel.LN10  # The references' pH: H's lag.
    assert abs(ph - ref["first_order_pH"]) <= 2 * ref["first_order_floor_rel"] * ref["first_order_pH"]
    assert bool(ph > kernel.LAG_BUDGET_PX) == bool(ref["first_order_pH"] > kernel.LAG_BUDGET_PX)


def test_the_envelope_reduces_to_b4_and_its_plants_are_caught():
    ligands, binders, net, tl, tb, u, _, lag = envelope_case("E0_b4")
    case = INPUTS["envelope"]["cases"]["E0_b4"]
    kon = case["kon_per_mM_per_s"][0][2]
    rate = dict(case["drive_fmol_per_s"])["H"] / case["volume_pL"]
    k = one_step_k(binders, "H")
    ph = b4.lag_estimate_ph(np.exp(u[0]), tb, k[:, None], np.array([[kon]]), rate,
                            np.ones_like(tb, dtype=bool), xp=np)
    assert np.allclose(np.abs(lag[0]) / kernel.LN10, ph, rtol=1e-12)
    # The cooperative chain: outside the budget. A per-step minimum relaxation (B4's form with
    # lambda the slowest single step) puts it inside: the plant flips the verdict.
    ligands, binders, net, tl, tb, u, _, lag = envelope_case("E1_chain")
    assert np.max(np.abs(lag)) / kernel.LN10 > kernel.LAG_BUDGET_PX
    ref = VALUES["envelope"]["cases"]["E1_chain"]
    per_step = max(abs(v) for v in ref["per_step_estimate_dln"]["min_over_all_steps"].values())
    assert per_step / kernel.LN10 < kernel.LAG_BUDGET_PX
    # k_on swapped between the ligands: caught against the reference.
    _, _, _, _, _, _, _, swapped = envelope_case("E1_chain", swap=True)
    expected = np.array([ref["first_order_dln"][s] for s in ligands])
    tolerance = 2 * ref["first_order_floor_rel"] * np.abs(expected)
    assert np.any(np.abs(swapped[:, 0] - expected) > tolerance)


def test_the_fixed_iteration_count_converges_and_too_few_do_not():
    rng = np.random.default_rng(1118)
    for name in ("S4", "S6"):
        ligands, binders, volume, net = system(name)
        nodes = 64
        x = np.array([10.0 ** rng.uniform(-10, -1 if s == "H" else 1.5, nodes) for s in ligands])
        tb = 10.0 ** rng.uniform(-3, 2, (len(binders), nodes))
        _, forms = kernel.speciation(np.log(x), tb, net["log_beta"], net["counts"],
                                     net["present"], xp=np)
        tl = x + np.einsum("bfn,bfl->ln", forms, net["counts"])
        held, comp_l, comp_b = masks(net, nodes)
        args = (net["log_beta"], net["counts"], net["present"], held, comp_l, comp_b)
        _, valid = kernel.free_ligands(tl, tb, *args, xp=np)
        assert valid.all()
        _, few = kernel.free_ligands(tl, tb, *args, steps=3, xp=np)
        assert not few.all()


def test_the_solve_runs_compiled_and_agrees_with_the_host():
    import jax
    import jax.numpy as jnp

    ligands, binders, volume, net, tl, tb, held, u, valid = solve("S6")
    _, comp_l, comp_b = masks(net, tl.shape[1])
    arrays = [jnp.asarray(a) for a in (net["log_beta"], net["counts"], net["present"], held,
                                       comp_l, comp_b)]

    @jax.jit
    def run(tl, tb):
        return kernel.free_ligands(tl, tb, *arrays, xp=jnp)

    u_dev, valid_dev = run(jnp.asarray(tl), jnp.asarray(tb))
    assert np.asarray(valid_dev).all()
    assert np.allclose(np.asarray(u_dev), u, rtol=0, atol=1e-12)
