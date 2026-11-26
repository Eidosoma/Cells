"""The general closure's kernel against the core-seams references (laws/reactions/rapid_binding.py;
docs/CORE_SEAMS_DESIGN.md §5 and §19 as amended on 18 November 2026; the references are
validation/core_seams/references, registered with their amendments C1-C3 before this output).

The engine runs on the references' registered inputs: the seam-C registry, systems S1-S7 with their
states' totals, the P1 nodes and the envelope's eight cases. S7, C4's binder mgx with its
H-releasing form, came with amendment C4 on 19 November 2026. It is compared with their recorded
values at the tolerances frozen before any read of the values
(core-pass-binding-20261118/frozen_constants.json, 23:13:29 UTC):
- the solve meets |g_L| <= 1e-13 A_L at every state, and its free ligands and forms lie within twice
  the references' floor_residual_1e-13. Its plants are a constant x1.01, a dropped form and a
  count off by one, each caught by a deviation or by the solve's failure (S7 without its
  H-releasing form has no speciation at some states);
- B4's path is B4's kernel bit for bit, and Newton agrees with it within the floor. A node's
  disjoint ligand sets solve exactly as if alone;
- the booked terms E_c, G* and S_c are within 16 eps of their terms, with S4[10]'s S_c undefined.
  The pairs' changes are within twice their floor, and each of the three planted bookings misses by
  its named sum;
- the booked change formed from increments (booked_change_pJ, the @3 owner's finding under X2) is
  the bulk difference within its rounding at a 1e-3 change, and S_c's first-order change within
  second order and rounding at the change's own scale at 1e-9 and 1e-13 (S1, S3, S7). Planted:
  the bulk difference booked whole misses the 1e-13 change by far more;
- K3b's derivative d ln c_free / d n_total (free_log_sensitivity_block) meets central differences
  of the solve at every registered state of S1-S7 (each row stepped at its own scale,
  Richardson-extrapolated), within 1e-6 relative per entry, and stays finite at an emptied
  binder. Planted: the dual's Hessian without the binders' covariance misses;
- the registered law declares the general form (seam F's fields), its free_energy G*;
- P1's nodes: the free amount, the admissible floor and the ladder's equilibrated free amounts,
  where today's predictor turns negative past n_free;
- the envelope's first-order lag lies within twice its floor on all eight cases, and equals B4's
  estimate for one two-form buffer. The cooperative chain is outside the budget, and a per-step
  minimum puts it inside (that plant flips the verdict); k_on swapped between ligands is caught;
- the fixed iteration count converges at a seeded random sweep, and too few iterations do not.
- the joint margin t* (amendment C4) meets the references' exact value and their LP's at every
  registered state, and each recorded lambda* is among the margin's vertices. Every registered
  state is valid. At C4's four planted states the margin and the verdicts are the references',
  with feasible_near inside the residual criterion. The lead's plant, two forms below base in
  different ligands, is refused at -0.9 and admitted at -0.4, and the enumeration's caps refuse.
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
        # A planted network may have no speciation at some states (S7, C4's binder: without its
        # H-releasing form, the H totals cannot be met), where its solve fails. A failed solve
        # is caught too: numpy's overflow there is silenced, its validity asserted.
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            p_ligands, p_binders, _, p_net, _, p_tb, _, p_u, p_valid = solve(
                name, path="newton", **planted
            )
            dev = deviations(name, p_ligands, p_binders, p_net, p_tb, p_u)
        caught = ~np.asarray(p_valid) | (np.nan_to_num(dev, nan=np.inf) > 1.0)
        assert caught.any(), planted


def margin_bound(tl, tb, net):
    """The frozen t* tolerance (frozen_constants_c4.json, 06:20:55 UTC), per state, in the totals'
    units: 16 eps (sum_L |T_L| + sum_B T_B max_f sum_L |n_L,f|)."""
    spread = np.max(np.where(net["present"], np.abs(net["counts"]).sum(axis=2), 0.0), axis=1)
    return 16 * EPS * (np.abs(tl).sum(axis=0) + (spread[:, None] * tb).sum(axis=0))


def exact_float(text):
    from fractions import Fraction

    return float(Fraction(text))


@pytest.mark.parametrize("name", SYSTEMS)
def test_the_joint_margin_meets_the_references_at_every_registered_state(name):
    """Amendment C4: t* at every state against the references' exact value and their LP's, within
    the frozen bound; every registered state valid; each recorded lambda* among the vertices."""
    from fractions import Fraction

    ligands, binders, volume, net = system(name)
    tl, tb = totals(name, ligands, binders)
    held, _, _ = masks(net, tl.shape[1])
    exact, _ = kernel.margin_vertices(net["counts"], net["present"])
    t = kernel.joint_margin(tl, tb, net["counts"], net["present"], net["margin_vertices"], held,
                            xp=np) * volume  # fmol
    bound = margin_bound(tl, tb, net) * volume
    for k, ref in enumerate(VALUES["validity"]["systems"][name]):
        assert abs(t[k] - exact_float(ref["t_star_exact"])) <= bound[k], (k, t[k], ref)
        assert abs(t[k] - ref["lp_t_star_fmol"]) <= bound[k], (k, t[k], ref)
        assert ref["valid"] and t[k] > 0
        assert tuple(Fraction(v) for v in ref["lambda_star"]) in exact


def planted_system(state):
    ligands, binders, volume, net = system(state["system"])
    tl = np.array([[state["totals"]["ligands_fmol"][s] / volume] for s in ligands])
    tb = np.array([[state["totals"]["binders_fmol"][b] / volume] for b in binders])
    held, comp_l, comp_b = masks(net, 1)
    return ligands, volume, net, tl, tb, held, comp_l, comp_b


def test_the_four_planted_states_meet_their_margins_and_verdicts():
    """C4's planted states (S7's mgx): t* -1/2, 0, +1/2 and -1 fmol within the frozen bound, each
    lambda* among the vertices; the read valid only at feasible_near, there inside the residual
    criterion at the frozen 48 steps. At the boundary (t* = 0 exactly) the read is refused by the
    margin or the solve's convergence; it is not asserted from t*'s float sign."""
    from fractions import Fraction

    for name, state in INPUTS["validity"]["planted"].items():
        ref = VALUES["validity"]["planted"][name]
        ligands, volume, net, tl, tb, held, comp_l, comp_b = planted_system(state)
        exact, _ = kernel.margin_vertices(net["counts"], net["present"])
        t = float(kernel.joint_margin(tl, tb, net["counts"], net["present"],
                                      net["margin_vertices"], held, xp=np)[0]) * volume
        bound = float(margin_bound(tl, tb, net)[0]) * volume
        assert abs(t - exact_float(ref["t_star_exact"])) <= bound, (name, t, ref["t_star_exact"])
        assert tuple(Fraction(v) for v in ref["lambda_star"]) in exact
        with np.errstate(all="ignore"):
            u, valid = kernel.free_ligands(tl, tb, net["log_beta"], net["counts"], net["present"],
                                           held, comp_l, comp_b, vertices=net["margin_vertices"],
                                           xp=np)  # fmt: skip
        assert bool(valid[0]) is ref["valid"], name
        if ref["valid"]:
            g, scale = kernel.residual(u, tl, tb, net["log_beta"], net["counts"], net["present"],
                                       held, xp=np)  # fmt: skip
            assert np.all(np.abs(g) <= kernel.RESIDUAL_RTOL * scale)


# The Lean lane's signed proton totals at float64 resolution (21 November 2026): copies of the
# registry's rel1 binder (forms holding 0 and -1 H), whose exact margin is T_H + sum T_B. Their
# margins are within an ulp of 0, where the margin's float sign misclassifies (exact 0 admitted,
# +2^-54 refused; -2^-53 admitted by NumPy, refused by compiled JAX).
LEAN_SIGNED = (
    (-1.7, (0.5, 0.6, 0.6), "exact margin 0"),
    (-0.8999999999999999, (0.3, 0.3, 0.3), "exact margin +2^-54"),
    (-3.8000000000000003, (0.3, 0.3, 1.0, 1.1, 1.1), "exact margin -2^-53"),
)


@pytest.mark.parametrize("h_total, binders, label", LEAN_SIGNED, ids=[c[2] for c in LEAN_SIGNED])
def test_the_closures_read_refuses_a_signed_held_total_on_its_own_sign(h_total, binders, label):
    """The read's precondition by construction (kinds/proton_buffer.py, positive_held_totals; host
    only, under 0.1 s each): each of the Lean lane's three cases holds a negative H total, so the
    closure's read refuses it on the total's own sign, whatever the margin's float verdict. Planted,
    the guard lifted: the read is the kernel's verdict alone, and the exact-zero case is admitted
    with its non-positive total unrefused."""
    from cells.kinds import proton_buffer

    specs = tuple((f"rel1_{k}",) + binder_spec("rel1", ("H",))[1:] for k in range(len(binders)))
    net = kernel.network(("H",), specs)
    tl, tb = np.array([[h_total]]), np.array([[b] for b in binders])
    held, comp_l, comp_b = masks(net, 1)
    with np.errstate(all="ignore"):
        _, admitted = kernel.free_ligands(tl, tb, net["log_beta"], net["counts"], net["present"],
                                          held, comp_l, comp_b, vertices=net["margin_vertices"],
                                          xp=np)  # fmt: skip
    guard = proton_buffer.positive_held_totals(tl, held, xp=np)
    assert not bool(guard[0]) and not bool(admitted[0] & guard[0]), label
    if label == "exact margin 0":  # Planted: the guard lifted, the kernel's verdict alone.
        assert bool(admitted[0]), "the misclassification the guard closes"


def test_two_forms_below_base_in_different_ligands_meet_the_joint_margin():
    """The lead's plant: one binder X with A {H: -1} and B {Mg: -1}. At T_X = 1 mM both per-ligand
    floors are -1 mM, yet both cannot be met at once. T_H = T_Mg = -0.9 mM has t* = -0.4 mM:
    refused, by the margin (the per-ligand floors pass). -0.4 mM has t* = +0.1 mM: admitted, the
    read converged."""
    spec_x = ("X", (("X_base", (), 0.0), ("X_A", (("H", -1),), 2.0), ("X_B", (("Mg", -1),), 2.0)),
              1000.0, (("H", 1.0), ("Mg", 1.0)))  # fmt: skip
    net = kernel.network(("H", "Mg"), (spec_x,))
    held, comp_l, comp_b = masks(net, 2)
    tl = np.array([[-0.9, -0.4], [-0.9, -0.4]])
    tb = np.array([[1.0, 1.0]])
    floor = kernel.admissible_floor(tb, net["counts"], net["present"], xp=np)
    assert np.all(tl > floor)  # The per-ligand floors pass at both.
    t = kernel.joint_margin(tl, tb, net["counts"], net["present"], net["margin_vertices"], held,
                            xp=np)  # fmt: skip
    assert np.allclose(t, [-0.4, 0.1], rtol=0, atol=float(np.max(margin_bound(tl, tb, net))))
    with np.errstate(all="ignore"):
        _, valid = kernel.free_ligands(tl, tb, net["log_beta"], net["counts"], net["present"],
                                       held, comp_l, comp_b, vertices=net["margin_vertices"],
                                       xp=np)  # fmt: skip
    assert valid.tolist() == [False, True]


def test_the_margins_enumeration_is_refused_past_its_caps():
    """A network whose arrangement has more vertices than the cap is refused (planted: a cap of
    two vertices on S3's two ligands), as is one whose combinations pass theirs."""
    _, _, _, net = system("S3")
    with pytest.raises(ValueError, match="more than 2 vertices"):
        kernel.margin_vertices(net["counts"], net["present"], vertex_cap=2)
    with pytest.raises(ValueError, match="past the cap of 1"):
        kernel.margin_vertices(net["counts"], net["present"], combination_cap=1)


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
    """cells.binding.rapid_binding@1 as registered carries seam F's BindingLaw fields. Its forms are the
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


CHANGE_SCALES = (1e-3, 1e-9, 1e-13)  # Each a relative change of every total.


@pytest.mark.parametrize("scale", CHANGE_SCALES)
@pytest.mark.parametrize("name", ["S1", "S3", "S7"])
def test_the_booked_change_is_formed_at_its_own_scale(name, scale):
    """booked_change_pJ (the @3 owner's finding under X2): from each registered state, every
    total moved by `scale` of its free species' amount (each ligand up by its free amount, each
    binder down by half its free base form's), so that S_c's first-order change,
    sum_r RT ln(free_r / total_r) dN_r, is good to that relative order (times a factor bounded
    here by 1e3, large where a row is nearly all free and its log-ratio near 0). The change formed
    from increments meets it within that and rounding at the change's own scale, and at 1e-3 it is
    the bulk difference within the bulk's rounding. Planted: the bulk difference S_c(now) -
    S_c(start), booked whole, misses the change at 1e-13 by far more (its rounding is S_c's, not
    the change's)."""
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    lig, bind = mu0p(ligands, binders)
    member = tb > 0
    keep = np.all(np.where(held, tl > 0, True), axis=0) & valid
    x, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    n_l, n_b = tl * volume, tb * volume
    d_l = np.where(held, scale * x * volume, 0.0)
    d_b = np.where(member, -0.5 * scale * forms[:, 0] * volume, 0.0)
    tl2, tb2 = (n_l + d_l) / volume, (n_b + d_b) / volume
    _, comp_l, comp_b = masks(net, tl.shape[1])
    u2, ok = kernel.free_ligands(tl2, tb2, net["log_beta"], net["counts"], net["present"], held,
                                 comp_l, comp_b, xp=np)
    change, defined = kernel.booked_change_pJ(
        u2, u, n_l, d_l, n_b, d_b, net["log_beta"], net["counts"], net["present"], held, member,
        volume, T_K, xp=np,
    )  # fmt: skip
    rt = 1e-3 * R * T_K
    base = np.where(member, forms[:, 0], 1.0) / np.where(member, tb, 1.0)
    ratio = np.where(held & (tl > 0), x / np.where(tl > 0, tl, 1.0), 1.0)  # Totals <= 0 kept out.
    reference = rt * (np.sum(np.where(held, np.log(ratio) * d_l, 0.0), axis=0)
                      + np.sum(np.where(member, np.log(base) * d_b, 0.0), axis=0))  # fmt: skip
    args = (net["log_beta"], net["counts"], net["present"])
    _, _, s1, _ = kernel.booked_terms_pJ(u, tl, tb, *args, held, lig, bind, volume, T_K, xp=np)
    _, _, s2, _ = kernel.booked_terms_pJ(u2, tl2, tb2, *args, held, lig, bind, volume, T_K, xp=np)
    bulk = s2 - s1
    keep &= ok & defined
    assert np.any(keep)
    error = np.abs(change - reference)[keep]
    if scale == CHANGE_SCALES[0]:  # Second order shows here: the bulk is the reference.
        assert np.all(np.abs(change - bulk)[keep] <= 64 * EPS * np.abs(s1)[keep])
    else:
        allowed = (1e3 * scale + 1e-11) * np.abs(reference)[keep] + 1e-30  # Second order, rounding.
        assert np.all(error <= allowed), (name, scale, np.max(error / allowed))
    if scale == CHANGE_SCALES[-1]:  # Planted: the bulk difference, booked whole.
        assert np.max(np.abs(bulk - reference)[keep]) > 1e3 * np.max(error)


def log_free(u, tb, net):
    """ln of every closure row's free form [L + B, ...]: ln x, then each binder's free base form."""
    _, log_p, _ = kernel._forms(u, net["log_beta"], net["counts"], net["present"], xp=np)
    return np.concatenate((u, np.log(tb) - log_p), axis=0)


def sensitivity(u, tl, tb, net, held, volume):
    """free_log_sensitivity_block on the closure's own rows (ligands, then binders)."""
    x, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    member = tb > 0
    rows = np.arange(tl.shape[0] + tb.shape[0])
    return kernel.free_log_sensitivity_block(
        u, forms[:, 0], net["log_beta"], net["counts"], net["present"], held, member,
        np.full(tl.shape[1], volume), rows, rows.size, xp=np,
    )  # fmt: skip


def central_block(tl, tb, net, volume, steps):
    """Central differences of the closure's ln free forms by each row's total (1/fmol), every other
    total held, for each step [L + B, states] (mM) in `steps`, every moved total solved in one
    batch: ([len(steps), L + B, L + B, states], valid [states] where every moved solve is)."""
    totals = np.concatenate((tl, tb), axis=0)
    n_rows, n_states = totals.shape
    n_l = tl.shape[0]
    moved = []
    for step in steps:
        for k in range(n_rows):
            for sign in (1.0, -1.0):
                one = totals.copy()
                one[k] = one[k] + sign * step[k]
                moved.append(one)
    batch = np.concatenate(moved, axis=1)
    held, comp_l, comp_b = masks(net, batch.shape[1])
    u, ok = kernel.free_ligands(batch[:n_l], batch[n_l:], net["log_beta"], net["counts"],
                                net["present"], held, comp_l, comp_b, xp=np)
    ln = log_free(u, batch[n_l:], net).reshape(n_rows, len(steps), n_rows, 2, n_states)
    out = (ln[:, :, :, 0] - ln[:, :, :, 1]) / (2 * np.stack(steps)[None] * volume)
    return np.moveaxis(out, 1, 0), np.all(ok.reshape(-1, n_states), axis=0)


@pytest.mark.parametrize("name", SYSTEMS)
def test_the_free_log_sensitivity_meets_central_differences(name, monkeypatch):
    """K3b's derivative (free_log_sensitivity_block): d ln c_i / d n_k over the closure's rows at
    every registered state, against central differences of the solve, every other total held. Each
    row moves by 1e-4 of its own scale (a ligand's residual scale A_L, since its total can sit far
    below its free and bound parts where forms release it; a binder's total), and the differences
    are Richardson-extrapolated from that step and half of it. They agree within 1e-6 relative per
    entry (the kinds owner's need) and a floor of 1e-9 of the block's largest entry; held marks
    every row. An emptied binder leaves D finite and the rest of the block unchanged. Planted: the
    dual's Hessian without the binders' covariance (the unbuffered slope) misses by far more."""
    ligands, binders, volume, net, tl, tb, held, u, valid = solve(name)
    d, marked = sensitivity(u, tl, tb, net, held, volume)
    assert bool(np.all(marked))
    _, a_l = kernel.residual(u, np.zeros_like(u), tb, net["log_beta"], net["counts"],
                             net["present"], held, xp=np)
    own = np.concatenate((a_l, tb), axis=0)
    (coarse, fine), ok = central_block(tl, tb, net, volume, (1e-4 * own, 5e-5 * own))
    keep = valid & ok  # Every valid state, a held total at or below zero included (S4, S7).
    assert np.array_equal(keep, valid), name
    fd = (4 * fine - coarse) / 3
    floor = 1e-6 * np.abs(fd) + 1e-9 * np.max(np.abs(fd), axis=(0, 1))
    error = np.abs(d - fd) - floor
    assert np.all(error[..., keep] <= 0), (name, np.max(error[..., keep]))
    # An empty binder (T_B = 0, still a member): D stays finite, and off its own row and column it
    # is the block without the binder; its own 1/T_B, unbounded there, is left out.
    _, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    base = forms[:, 0].copy()
    base[0] = 0.0
    rows = np.arange(tl.shape[0] + tb.shape[0])
    member = np.ones(tb.shape, dtype=bool)
    block = [
        kernel.free_log_sensitivity_block(
            u, base, net["log_beta"], net["counts"], net["present"], held, kept, np.full(
                tl.shape[1], volume), rows, rows.size, xp=np,
        )[0] for kept in (member, member & (np.arange(tb.shape[0]) > 0)[:, None])
    ]  # fmt: skip
    other = rows != tl.shape[0]  # Off the emptied binder's row and column.
    empty, absent = (b[other][:, other][..., valid] for b in block)
    assert np.all(np.isfinite(block[0][..., valid])), name
    assert np.allclose(empty, absent, rtol=1e-14, atol=0), name
    # Planted: the Hessian without the binders' covariance.
    original = kernel._hessian

    def unbuffered(u, total_binder, *args, **kwargs):
        return original(u, 0.0 * total_binder, *args, **kwargs)

    monkeypatch.setattr(kernel, "_hessian", unbuffered)
    planted, _ = sensitivity(u, tl, tb, net, held, volume)
    assert np.max((np.abs(planted - fd) - floor)[..., keep]) > 0, name


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


C5_CASES = tuple(INPUTS["envelope"]["amendment_c5"]["cases"])


def release_steps_of(net, binders):
    """The network's release steps, ((step, from form, ligand, to form), ...) by the registry's IDs:
    a unit step whose bound form holds count_f(L) <= 0 (amendment C5)."""
    _, width, nl = net["counts"].shape
    m = net["step_matrix"]
    out = []
    for s in range(m.shape[1]):
        ligand = int(net["step_ligand"][s])
        to = int(np.flatnonzero(m[nl:, s] > 0)[0]) + nl
        b, g = divmod(to - nl, width)
        if net["counts"][b, g, ligand] <= 0:
            f = (int(net["step_from"][s]) - nl) % width
            forms = REGISTRY["binders"][binders[b]]["forms"]
            out.append((s, forms[f]["id"], ligand, forms[g]["id"]))
    return out


@pytest.mark.parametrize("name", C5_CASES)
def test_the_first_order_lag_bounds_the_kinetic_lag_on_every_release_step_case(name):
    """Amendment C5, the comparison frozen at 07:11:51 UTC (frozen_constants_c5.json):
    - the network's release steps are the references';
    - every ligand's kinetic lag at the last record time is at most the engine's first-order lag,
      to the first order's registered accuracy, (1 + 2e-3) |lag| + two floors (the first
      order's and the kinetic row's), the cross-row drives included;
    - the budget verdict over every ligand is the kinetic reference's.
    The first order meeting the references' first order within twice its floor is the envelope
    test above, which reads every case."""
    ligands, binders, net, _, _, _, valid, lag = envelope_case(name)
    ref = VALUES["envelope"]["cases"][name]
    assert valid.all()
    found = [(f, ligands[l], g) for _, f, l, g in release_steps_of(net, binders)]
    assert sorted(found) == sorted((r["from"], r["ligand"], r["to"]) for r in ref["release_steps"])
    last = ref["kinetic"]["rows"][-1]
    for l, s in enumerate(ligands):
        mine = abs(float(lag[l, 0]))
        floors = ref["first_order_floor_rel"] * abs(ref["first_order_dln"][s]) + last["floor_dln"][s]
        assert abs(last["lag_dln"][s]) <= (1 + 2e-3) * mine + 2 * floors, (s, last, mine)
    engine = max(abs(float(v)) for v in lag[:, 0]) / kernel.LN10 > kernel.LAG_BUDGET_PX
    kinetic = max(abs(v) for v in last["lag_dln"].values()) / kernel.LN10 > kernel.LAG_BUDGET_PX
    assert engine is kinetic, (name, engine, kinetic)


@pytest.mark.parametrize("name", C5_CASES)
def test_a_release_steps_sign_flip_is_caught(name):
    """C5's plant: the release steps' ligand written with the wrong sign (taken to release L where
    it binds it), the forward flux unchanged. The engine's lag then misses the references' first
    order by more than twice its floor on some ligand."""
    ligands, binders, net, tl, tb, u, _, _ = envelope_case(name)
    ref = VALUES["envelope"]["cases"][name]
    matrix = net["step_matrix"].copy()
    for s, _, ligand, _ in release_steps_of(net, binders):
        matrix[ligand, s] = -matrix[ligand, s]
    case = INPUTS["envelope"]["cases"][name]
    volume = case["volume_pL"]
    drives = dict(case["drive_fmol_per_s"])
    d_l = np.array([[drives.get(s, 0.0) / volume] for s in ligands])
    d_b = np.array([[drives.get(b, 0.0) / volume] for b in binders])
    held, _, _ = masks(net, 1)
    _, forms = kernel.speciation(u, tb, net["log_beta"], net["counts"], net["present"], xp=np)
    planted = kernel.lag_first_order(u, forms, tb, d_l, d_b, net["log_beta"], net["counts"],
                                     net["present"], held, matrix, net["step_from"],
                                     net["step_ligand"], net["step_kon"], net["conservation"],
                                     xp=np)  # fmt: skip
    misses = [abs(float(planted[l, 0]) - ref["first_order_dln"][s])
              / (ref["first_order_floor_rel"] * abs(ref["first_order_dln"][s]))
              for l, s in enumerate(ligands)]  # fmt: skip
    assert max(misses) > 2, (name, misses)


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
