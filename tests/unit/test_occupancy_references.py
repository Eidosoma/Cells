"""Self-tests of the independent references for cells.operator.site_occupancy@1 (validation/occupancy/): R-ode,
R-closed, R-qss, R-eq and R-dG (FR-3).

They are checked against closed forms, against each other where they overlap, and for
internal consistency (the ledger, the 50-digit free energy, convergence orders). The first tests
check independence: nothing under validation/occupancy/ imports `cells` or validation.tissue
(the engine's fixtures live there), statically or in a fresh process; the one import from another
reference is validation.coupling.piecewise_ode. Every world is synthetic.
"""

import ast
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from validation.occupancy import site_bookings as sb
from validation.occupancy import site_closed as sc
from validation.occupancy import site_equilibrium as se
from validation.occupancy import site_reference as sr

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "occupancy"
EPS = float(np.finfo(float).eps)
RT = 2.5775  # pJ/fmol at about 310 K, an input (the references never hold it)
TRACE = 1e-15  # mM


# ------------------------------------------------------------------------ independence


def _imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None
        elif isinstance(node, ast.ImportFrom):
            yield "." * node.level + (node.module or ""), tuple(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in {"__import__", "import_module", "run_module", "run_path"}:
                yield "<dynamic import>", None


def test_references_import_nothing_from_cells_or_the_engine_fixtures():
    files = sorted(REFERENCES.glob("*.py"))
    assert len(files) >= 4
    for path in files:
        for name, names in _imports(path):
            assert name != "<dynamic import>" and not name.startswith("."), (path.name, name)
            assert name.split(".")[0] not in {"cells", "jax", "jaxlib"}, (path.name, name)
            if name.startswith("validation") and not name.startswith("validation.occupancy"):
                assert name == "validation.coupling" and names == ("piecewise_ode",), name


def test_references_load_no_cells_or_tissue_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.occupancy.{m}\n" for m in modules)
        + "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')\n"
        + "  or m.startswith(('validation.tissue', 'validation.division')))\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0, out.stdout + out.stderr


# ------------------------------------------------------------------------ worlds


def q1_world(eps, *, k_on=1e4, k_off=10.0, k_int=10.0, V=1.0, c0=1e-3):
    """§8.3 Q1: one population on a closed node, occupancy pre-formed at its quasi-steady value
    at c0, binding and internalisation into a cell at the trace; S set by epsilon."""
    K_M = (k_off + k_int) / k_on
    S = eps * V * (K_M + c0)
    B0 = sc.quasi_steady_bound(S, c0, K_M)
    return sr.World(RT, nodes={"ecs": sr.Node(V, c0 * V), "cell": sr.Node(2.0, TRACE * 2.0)},
                    populations={"r": sr.Population("ecs", k_on, k_off, sites_fmol=S,
                                                    initial_occupancy=B0 / S, k_int_per_s=k_int,
                                                    receiving="cell")},
                    trace_mM=TRACE), S


# ------------------------------------------------------------------------ rules


def test_sites_from_copies_and_the_domain():
    p = sr.Population("n", 1e3, 1.0, copies=1e5, sites_per_copy=2, accessible_fraction=0.5)
    assert p.S == 0.5 * 2 * 1e5 / 602_214_076.0
    assert sr.N_F == 6.02214076e23 * 1e-15
    good = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)}, populations={"p": p})
    sr.check_world(good)
    bad = [
        sr.Population("n", 0.0, 1.0, sites_fmol=1e-4),  # k_on = 0 is a zero multiplier
        sr.Population("n", 1e3, 0.0, sites_fmol=1e-4),  # irreversible binding refused
        sr.Population("n", 1e3, 1.0, copies=1e5, sites_per_copy=1, accessible_fraction=0.0),
        sr.Population("n", 1e3, 1.0, sites_fmol=1e-4, k_int_per_s=1.0),  # no receiving node
        sr.Population("n", 1e3, 1.0, sites_fmol=1e-4, initial_occupancy=1.5),
        sr.Population("n", 1e3, 1.0, sites_fmol=1e-4, binding_schedule=((0.5, 1.0),)),
    ]
    for q in bad:
        with pytest.raises(ValueError):
            sr.check_world(sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)}, populations={"p": q}))
    with pytest.raises(ValueError):
        sr.check_world(sr.World(RT, nodes={"n": sr.Node(1.0, 0.0)}, populations={"p": p}))


def test_the_trace_rule_as_built():
    p = sr.Population("n", 1e3, 1.0, sites_fmol=1e-4)  # K_d = 1e-3 mM
    ok = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3), "m": sr.Node(1.0, 1e-9)},
                  populations={"p": p}, trace_mM=1e-9)  # exactly 1e-6 K_d: admitted
    sr.check_world(ok)
    high = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)}, populations={"p": p},
                    trace_mM=1.01e-9)
    with pytest.raises(ValueError, match="1e-6 K_d"):
        sr.check_world(high)
    below = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3), "m": sr.Node(1.0, 0.5e-12)},
                     populations={"p": p}, trace_mM=1e-12)
    with pytest.raises(ValueError, match="below the declared trace"):
        sr.check_world(below)
    sr.check_world(below, trace_rule=False)  # the reference-side override
    edge = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-12 * (1 - 1e-13))}, populations={"p": p},
                    trace_mM=1e-12)
    sr.check_world(edge)  # within 1e-12 relative


# ------------------------------------------------------------------------ R-closed against R-ode


def test_riccati_and_the_depletion_quadratic_against_r_ode():
    kon, koff, V, S, n0 = 1e3, 1.0, 0.5, 4e-4, 3e-4
    w = sr.World(RT, nodes={"n": sr.Node(V, n0)},
                 populations={"p": sr.Population("n", kon, koff, sites_fmol=S)})
    rec = (0.001, 0.1, 1.0, 30.0)
    run = sr.integrate(w, 30.0, record=rec)
    for t in rec:
        exact = float(sc.depletion(t, 0.0, n0, S, V, kon, koff, exact=True))
        assert abs(sc.depletion(t, 0.0, n0, S, V, kon, koff) - exact) <= 4 * EPS * S
        assert abs(run.at[t]["B_fmol"]["p"] - exact) <= 1e-12 * S
        assert abs(run.at[t]["n_fmol"]["n"] - (n0 - exact)) <= 1e-12 * n0
    rm, rp = sc.depletion_roots(n0, S, koff / kon, V)
    assert rm * rm - (n0 + S + koff / kon * V) * rm + n0 * S == pytest.approx(0.0, abs=1e-22)
    eq = se.equilibrium(w)
    assert eq["B_fmol"]["p"] == pytest.approx(rm, rel=1e-14)
    assert run.at[30.0]["heat_pJ"] == pytest.approx(eq["heat_pJ"], rel=1e-10)


def test_fixed_c_forms_hold_to_their_depletion_term():
    Vbig, c, S, kon, koff, kint = 1e4, 2e-3, 1e-4, 1e3, 1.0, 0.5
    term = sc.depletion_term(S, Vbig, koff / kon, c)
    w = sr.World(RT, nodes={"big": sr.Node(Vbig, c * Vbig), "cell": sr.Node(1.0, 1e-6)},
                 populations={"p": sr.Population("big", kon, koff, sites_fmol=S, k_int_per_s=kint,
                                                 receiving="cell")})
    run = sr.integrate(w, 3.0, record=(0.5, 3.0), method="DOP853", rtol=1e-12)
    for t in (0.5, 3.0):
        B, U = sc.internalisation_fixed(t, 0.0, S, c, kon, koff, kint)
        assert abs(run.at[t]["B_fmol"]["p"] - B) <= 3 * term * S
        assert abs(run.at[t]["internalised_fmol"]["p"] - U) <= 3 * term * max(U, S)
    # association and dissociation, no internalisation
    w2 = sr.World(RT, nodes={"big": sr.Node(Vbig, c * Vbig)},
                  populations={"p": sr.Population("big", kon, koff, sites_fmol=S,
                                                  initial_occupancy=0.25)})
    run2 = sr.integrate(w2, 2.0, record=(2.0,), method="DOP853", rtol=1e-12)
    assert abs(run2.at[2.0]["B_fmol"]["p"] - sc.association(2.0, 0.25 * S, S, c, kon, koff)) \
        <= 3 * term * S
    w3 = sr.World(RT, nodes={"big": sr.Node(Vbig, 1e-12 * Vbig)},
                  populations={"p": sr.Population("big", kon, koff, sites_fmol=S,
                                                  initial_occupancy=0.8)})
    run3 = sr.integrate(w3, 1.0, record=(1.0,), method="DOP853", rtol=1e-12)
    rebinding = 0.8 * S / Vbig / (koff / kon)  # the released ligand's c over K_d
    assert run3.at[1.0]["B_fmol"]["p"] == pytest.approx(sc.dissociation(1.0, 0.8 * S, koff),
                                                        rel=2 * rebinding)


# ------------------------------------------------------------------------ R-ode and R-qss (Q1)


def test_q1_converges_to_the_saturable_sink_at_order_one_in_epsilon():
    errors = {}
    for eps in (1e-1, 1e-2):
        w, S = q1_world(eps)
        k = sc.sink_constants(S, 1.0, 1e4, 10.0, 10.0)
        T = 2 * sc.sink_half_time(1e-3, k["a"], k["b"])
        rec = tuple(np.linspace(0, T, 11)[1:])
        run = sr.integrate(w, T, record=rec, method="DOP853", rtol=1e-13)
        errors[eps] = max(abs(run.at[t]["n_fmol"]["ecs"] - sc.sink_amount(t, 1e-3, k["a"],
                                                                            k["b"]))
                          for t in rec) / 1e-3
        last = run.at[rec[-1]]
        assert abs(last["closure_pJ"]) <= 1e-12 * RT * 1e-3
        assert abs(last["material_residual_fmol"]) <= 1e-13 * 1e-3
    order = math.log10(errors[1e-1] / errors[1e-2])
    assert 0.95 < order < 1.02  # A.5: O(epsilon); measured 0.980
    assert errors[1e-1] < 0.05


def test_sink_amount_solves_its_law():
    n0, a, b = 1e-3, 3e-3, 2e-3
    for t in (0.0, 0.1, 1.0, 5.0):
        n = sc.sink_amount(t, n0, a, b)
        assert b * math.log(n0 / n) + (n0 - n) == pytest.approx(a * t, abs=1e-18)
    assert sc.sink_amount(sc.sink_half_time(n0, a, b), n0, a, b) == pytest.approx(n0 / 2)


def test_r_ode_methods_agree_to_the_floor_and_the_heat_is_regular_at_b_zero():
    w, S = q1_world(0.1)
    rec = (0.05, 0.15)
    radau = sr.integrate(w, 0.15, record=rec)
    dop = sr.integrate(w, 0.15, record=rec, method="DOP853", rtol=1e-13)
    d = sr.compare(radau, dop, rec)
    assert d["n"] <= 1e-13 * 1e-3 and d["B"] <= 1e-13 * S and d["heat"] <= 1e-15
    # From empty sites (B = 0): the regular heat form starts finite, and the closure holds.
    empty = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)},
                     populations={"p": sr.Population("n", 1e4, 10.0, sites_fmol=S)})
    run = sr.integrate(empty, 0.2, record=(1e-6, 0.2), method="DOP853", rtol=1e-13)
    for t in (1e-6, 0.2):
        assert run.at[t]["heat_pJ"] > 0.0
        assert abs(run.at[t]["closure_pJ"]) <= 1e-13 * RT * 1e-3  # the energy scale
    # A closed passive relaxation's heat is minus its free-energy change (no work).
    assert run.at[0.2]["work_pJ"] == 0.0
    assert run.at[0.2]["heat_pJ"] == pytest.approx(-run.at[0.2]["free_energy_change_pJ"],
                                                   rel=1e-12)


def test_records_at_a_multiplier_change_give_both_sides():
    w = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3), "cell": sr.Node(1.0, 1e-6)},
                 populations={"p": sr.Population("n", 1e4, 10.0, sites_fmol=1e-4,
                                                 initial_occupancy=0.5, k_int_per_s=5.0,
                                                 receiving="cell",
                                                 internalisation_schedule=((0.0, 1.0),
                                                                           (0.1, 0.0)))})
    run = sr.integrate(w, 0.2, record=(0.1, 0.2))
    r = run.at[0.1]
    assert r["internalisation_rate_left_fmol_per_s"]["p"] > 0.0
    assert r["internalisation_rate_fmol_per_s"]["p"] == 0.0
    late = run.at[0.2]
    assert late["internalised_fmol"]["p"] == pytest.approx(r["internalised_fmol"]["p"],
                                                           rel=1e-15)


def test_background_guard_moves_little():
    w = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-4), "far": sr.Node(1.0, 1e-12)},
                 populations={"p": sr.Population("n", 1e3, 1.0, sites_fmol=1e-4),
                              "q": sr.Population("far", 1e3, 1.0, sites_fmol=1e-4)},
                 trace_mM=1e-12)
    a, b, d = sr.background_guard(w, 1.0, (1.0,), rtol=1e-11, method="DOP853")
    # The far pool's occupancy is at most trace/K_d = 1e-9: lowering the trace by 1e3 moves its
    # bound amount by less than 1e-9 S, and the pool facing the declared ligand only within the
    # integration's tolerance.
    assert d["B"] <= 1e-9 * 1e-4
    assert a.at[1.0]["B_fmol"]["q"] == pytest.approx(1e3 * b.at[1.0]["B_fmol"]["q"], rel=1e-3)
    # (one solver step sequence serves both nodes, so the near pool moves within its tolerance)
    assert a.at[1.0]["B_fmol"]["p"] == pytest.approx(b.at[1.0]["B_fmol"]["p"], rel=1e-10)


# ------------------------------------------------------------------------ R-eq


def test_equilibrium_with_two_populations_on_one_node_against_r_ode():
    w = sr.World(RT, nodes={"a": sr.Node(1.0, 2e-4), "b": sr.Node(2.0, 1e-4)},
                 populations={"p1": sr.Population("a", 2e3, 1.0, sites_fmol=3e-4,
                                                  initial_occupancy=0.2),
                              "p2": sr.Population("a", 5e2, 0.1, sites_fmol=1e-4),
                              "p3": sr.Population("b", 1e3, 2.0, sites_fmol=5e-5,
                                                  initial_occupancy=0.9)})
    eq = se.equilibrium(w)
    for k, p in w.populations.items():
        c = eq["c_mM"][p.facing]
        assert eq["B_fmol"][k] == pytest.approx(p.S * c / (p.K_d + c), rel=1e-15)
    total = 2e-4 + 0.2 * 3e-4
    assert eq["n_fmol"]["a"] + eq["B_fmol"]["p1"] + eq["B_fmol"]["p2"] == pytest.approx(total,
                                                                                        rel=1e-14)
    run = sr.integrate(w, 300.0, record=(300.0,), method="DOP853", rtol=1e-12)
    for k in w.populations:
        assert run.at[300.0]["B_fmol"][k] == pytest.approx(eq["B_fmol"][k], rel=1e-9)
    assert run.at[300.0]["heat_pJ"] == pytest.approx(eq["heat_pJ"], rel=1e-9)
    assert eq["heat_pJ"] > 0.0
    with pytest.raises(ValueError, match="passive binding only"):
        se.equilibrium(q1_world(0.1)[0])


# ------------------------------------------------------------------------ R-dG


def mixed_world():
    """A cell that receives internalised cargo and is faced by an inward population (§3.4's
    world 1 configuration), all in one component."""
    return sr.World(RT, nodes={"ecs": sr.Node(1.0, 1e-3), "cell": sr.Node(2.0, 2e-4)},
                    populations={"r": sr.Population("ecs", 1e4, 10.0, sites_fmol=3e-4,
                                                    initial_occupancy=0.3, k_int_per_s=10.0,
                                                    receiving="cell"),
                                 "q": sr.Population("cell", 5e3, 2.0, sites_fmol=1e-4)})


def test_half_step_ledger_and_fifty_digit_free_energy_on_random_states():
    w = mixed_world()
    L = sb.Layout(w)
    rng = np.random.default_rng(11)
    seen = set()
    for trial in range(150):
        n = np.array([10 ** rng.uniform(-5, -2), 10 ** rng.uniform(-6, -3)])
        B = L.S * rng.uniform(0, 1, 2)
        if trial % 7 == 0:
            B[0] = 0.0
        mb, mi = rng.choice([0.0, 0.5, 1.0], 2), rng.choice([0.0, 1.0], 2)
        st = sb.half_step(w, n, B, L.S - B, 10 ** rng.uniform(-6, -3), mb, mi)
        if not st.admitted:
            continue
        seen |= set(st.branch) | set(st.component_class)
        scale = np.maximum(st.delta_G_terms + st.heat_terms, 1e-30)
        assert np.all(np.abs(st.ledger_residual) <= 4 * EPS * scale)
        exact = sb.exact_delta_G(w, n, B, L.S - B, *st.delta)
        for c in range(L.components):
            assert abs(float(exact[c]) - st.delta_G[c]) <= 4 * EPS * max(st.delta_G_terms[c],
                                                                         1e-30)
        assert np.all(st.heat >= 0.0)  # §4.4: no negative heat in these steps
        for k in range(2):
            assert math.isclose(st.start[1][k] + st.start[2][k], L.S[k], rel_tol=1e-15)
            assert math.isclose(st.end[1][k] + st.end[2][k], L.S[k], rel_tol=1e-14,
                                abs_tol=1e-30)
    assert {"node", "share", "off", "idle", "mixed", "passive"} <= seen


def test_zero_multipliers_select_the_start_bitwise_and_book_nothing():
    w = mixed_world()
    n, B, R = sb.Layout(w).initial_state()
    st = sb.half_step(w, n, B, R, 1e-3, np.zeros(2), np.zeros(2))
    assert st.component_class == ["idle"]
    assert all(np.array_equal(a, b) for a, b in zip(st.end, st.start, strict=True))
    assert not st.heat.any() and not st.work.any()


def test_the_quadrature_branch_forced_by_a_washout():
    kon, koff, kint, S = 1e4, 10.0, 50.0, 3e-4
    c = 1e-6
    B_eq = S * c / (koff / kon + c)
    w = sr.World(RT, nodes={"ecs": sr.Node(1.0, c), "cell": sr.Node(1.0, 1e-4)},
                 populations={"r": sr.Population("ecs", kon, koff, sites_fmol=S,
                                                 initial_occupancy=B_eq * 1.001 / S,
                                                 k_int_per_s=kint, receiving="cell")})
    n, B, R = sb.Layout(w).initial_state()
    st = sb.half_step(w, n, B, R, 2e-3)
    assert st.admitted and st.branch == ["quadrature"]
    assert st.stage_binding[0, 0] < 0.0 < st.stage_binding[1, 0]  # reverses within the step
    assert st.route_heat[0] == st.heat_quadrature[0] > 0.0
    assert abs(st.ledger_residual[0]) <= 4 * EPS * (st.delta_G_terms[0] + st.heat_terms[0])
    # The other side of the selection: B below its binding equilibrium, so binding runs forward
    # through the step while internalisation drains B further: the share is booked.
    below = sr.World(RT, nodes=w.nodes, populations={"r": sr.Population(
        "ecs", kon, koff, sites_fmol=S, initial_occupancy=B_eq * 0.999 / S, k_int_per_s=kint,
        receiving="cell")})
    st2 = sb.half_step(below, *sb.Layout(below).initial_state(), 2e-3)
    assert st2.admitted and st2.branch == ["share"] and st2.non_reversing[0]
    assert st2.route_heat[0] == st2.heat_share[0] > 0.0


def test_the_stage_condition_is_inclusive_and_refuses_beyond():
    # k_off = 10 /s: h L_B = 1/2 exactly at every stage at h = 0.05 s; L_R = k_on c = 10 /s at Y1.
    w = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)},
                 populations={"p": sr.Population("n", 1e4, 10.0, sites_fmol=1e-4)})
    n, B, R = sb.Layout(w).initial_state()
    h_edge = 0.05
    assert h_edge * 10.0 == 0.5 and 1e4 * (1e-3 / 1.0) == 10.0
    st = sb.half_step(w, n, B, R, h_edge)
    assert float(st.hL.max()) == 0.5 and st.stage_condition_ok  # equality is admitted
    assert not sb.half_step(w, n, B, R, h_edge * 1.01).stage_condition_ok


def test_half_steps_converge_to_r_ode_third_order_and_heat_second_order():
    w, S = q1_world(0.1)
    T = 0.064
    ref = sr.integrate(w, T, record=(T,), method="DOP853", rtol=1e-13).at[T]
    errs = []
    for dt in (8e-3, 4e-3, 2e-3):
        run = sb.run_half_steps(w, dt / 2, int(round(2 * T / dt)))
        assert run.refused_at is None
        errs.append((abs(run.n[-1, 0] - ref["n_fmol"]["ecs"]),
                     abs(run.heat[-1].sum() - ref["heat_pJ"]),
                     abs(run.work[-1, 0] - ref["work_pJ"])))
    for (a, ha, wa), (b, hb, wb) in zip(errs, errs[1:], strict=False):
        assert 7.0 < a / b < 9.0  # third order (prototype at epsilon = 0.1: 8.39, 8.19)
        assert 3.5 < ha / hb < 4.5 and 3.5 < wa / wb < 4.5  # the share: second order


def test_the_small_helpers():
    S, V, kon, koff, kint, c0 = 3e-4, 2.0, 1e4, 10.0, 5.0, 1e-3
    K_M = (koff + kint) / kon
    assert sc.epsilon(S, V, kon, koff, kint, c0) == (S / V) / (K_M + c0)
    assert sc.langmuir(S, c0, koff / kon) == S * c0 / (koff / kon + c0)
    n_total = 4e-4
    c = sc.free_concentration_closed(n_total, S, koff / kon, V)
    assert c * V + sc.langmuir(S, c, koff / kon) == pytest.approx(n_total, rel=1e-14)
    start = dict(n={"n": 1e-3}, B={"p": 1e-5}, R={"p": 2e-4})
    end = dict(n={"n": 9.9e-4}, B={"p": 2e-5}, R={"p": 1.9e-4})
    w = sr.World(RT, nodes={"n": sr.Node(1.0, 1e-3)},
                 populations={"p": sr.Population("n", 1e3, 1.0, sites_fmol=2.1e-4)})
    exact = sr.exact_free_energy_change(w, start, end)
    approx = (sr.node_increment(1e-3, -1e-5, 1.0, RT)
              + sr.pool_increment(1e-5, 1e-5, 2.1e-4, RT * math.log(1e-3), RT)
              + sr.pool_increment(2e-4, -1e-5, 2.1e-4, 0.0, RT))
    assert float(exact["total"]) == pytest.approx(approx, rel=1e-12)
    run, tight, d = sr.floor(w, 0.05, (0.05,), method="DOP853", rtol=1e-11)
    assert d["n"] <= 1e-12 * 1e-3 and tight.at[0.05]["B_fmol"]["p"] > 0


def test_heat_by_node_and_work_by_population_converge_in_a_mixed_two_population_world():
    w = mixed_world()
    T = 0.064  # at 0.032 s the cell's heat error is still pre-asymptotic (ratios 6.6 to 4.6)
    ref = sr.integrate(w, T, record=(T,), method="DOP853", rtol=1e-13).at[T]
    assert ref["heat_pJ"] == pytest.approx(math.fsum(ref["heat_by_node_pJ"].values()), rel=1e-14)
    errs = []
    for dt in (2e-3, 1e-3):
        run = sb.run_half_steps(w, dt / 2, int(round(2 * T / dt)))
        errs.append([abs(run.heat[-1, i] - ref["heat_by_node_pJ"][x])
                     for i, x in enumerate(("ecs", "cell"))]
                    + [abs(run.work[-1, 0] - ref["work_by_population_pJ"]["r"])])
    for a, b in zip(errs[0], errs[1], strict=True):
        assert 3.5 < a / b < 4.5  # second order, per node and per population


def test_a_class_switch_through_the_multipliers():
    w = mixed_world()
    run = sb.run_half_steps(w, 5e-4, 8, multipliers=lambda k: (np.ones(2), np.array(
        [0.0 if k < 4 else 1.0, 0.0])))
    assert run.refused_at is None
    assert all(b == ["node", "node"] for b in run.branches[:4])  # passive-only
    assert all(b[0] in ("share", "quadrature") for b in run.branches[4:])  # mixed
    assert not run.work[4].any() and run.work[-1, 0] != 0.0
