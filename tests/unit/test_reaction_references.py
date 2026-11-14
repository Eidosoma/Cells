"""Self-tests of the independent references for local_species_reactions@1 (validation/reactions/).

The references are checked against analytic cases, against each other where they overlap, and
against the numbers that docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.4 quotes for MG0c. They
must stay independent of the engine's operator, so the first two tests check that nothing under
validation/reactions/ imports `cells`, statically and in a fresh process.
"""

import ast
import math
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from validation.reactions import chain_reference as cr
from validation.reactions import dissipation_reference as dr
from validation.reactions import network_reference as nr
from validation.reactions import turing_reference as tu

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "reactions"
EPS = float(np.finfo(float).eps)
RT = 2.5773  # pJ/fmol at 310 K, for orientation only (Appendix A); the references take it as input.
FORBIDDEN_TOP = {"cells", "jax", "jaxlib"}


# ------------------------------------------------------------------------ independence


def _imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield "." * node.level + (node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in {"__import__", "import_module", "run_module", "run_path"}:
                yield "<dynamic import>"


def test_references_import_nothing_from_cells():
    files = sorted(REFERENCES.glob("*.py"))
    assert len(files) >= 4
    for path in files:
        for name in _imports(path):
            assert name != "<dynamic import>", (path.name, name)
            assert not name.startswith("."), (path.name, "relative import", name)
            top = name.split(".")[0]
            assert top not in FORBIDDEN_TOP, (path.name, name)
            if top == "validation":
                assert name.startswith("validation.reactions"), (path.name, name)


def test_references_load_no_cells_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.reactions.{m}\n" for m in modules)
        + "bad = sorted(m for m in sys.modules if m.split('.')[0] in {'cells', 'jax', 'jaxlib'})\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr


# ---------------------------------------------------------------------------- networks


def ab_network(K=10.0, k_f=1.0, sink=None):
    """Passive A <=> B (K = c_B/c_A), with an optional driven sink A -> 0 at `sink` (1/s)."""
    species = (nr.Species("A", 0.0, {"M": 1}), nr.Species("B", -math.log(K), {"M": 1}))
    reactions = [nr.Reaction("ab", "passive", {"A": 1}, {"B": 1}, k_f_per_s=k_f)]
    if sink is not None:
        reactions.append(nr.Reaction("sink", "mass_action", {"A": 1}, {}, rate_constant=sink))
    return nr.Network(species=species, reactions=tuple(reactions))


def enzyme_network(k_on=1e3, K_d=1e-3, k_cat=1.0, c0=1.0):
    """Probe 2d's recipe (§3.3): passive E + S <=> C, driven C -> E + P."""
    species = (
        nr.Species("E", 0.0, {"E": 1}),
        nr.Species("S", 0.0, {"S": 1}),
        nr.Species("C", math.log(K_d / c0), {"E": 1, "S": 1}),
        nr.Species("P", 0.0, {"S": 1}),
    )
    reactions = (
        nr.Reaction("bind", "passive", {"E": 1, "S": 1}, {"C": 1}, k_f_per_s=k_on * c0),
        nr.Reaction("cat", "mass_action", {"C": 1}, {"E": 1, "P": 1}, rate_constant=k_cat),
    )
    return nr.Network(species=species, reactions=reactions, c0_mM=c0)


def every_law_network(rng):
    """Every law, order and factor kind, with random parameters and potentials."""
    lu = lambda lo, hi: float(10 ** rng.uniform(math.log10(lo), math.log10(hi)))  # noqa: E731
    species = (
        nr.Species("X1", rng.normal(), {"a": 1}),
        nr.Species("X2", rng.normal(), {"b": 1}),
        nr.Species("X3", rng.normal(), {"a": 1, "b": 1}),
        nr.Species("X4", rng.normal(), {"a": 1, "b": 1}),
        nr.Species("E", rng.normal(), {"e": 1}),
    )
    reactions = (
        nr.Reaction("bind", "passive", {"X1": 1, "X2": 1}, {"X3": 1}, k_f_per_s=lu(0.1, 10)),
        nr.Reaction("iso", "passive", {"X3": 1}, {"X4": 1}, k_f_per_s=lu(0.1, 10)),
        nr.Reaction("source", "mass_action", {}, {"X1": 1}, rate_constant=lu(1e-4, 1e-2),
                    factors=(nr.Factor("hill_activation", "X4", lu(1e-4, 1e-2), lu(0.5, 4)),)),
        nr.Reaction("sink", "mass_action", {"X4": 1}, {}, rate_constant=lu(0.1, 2),
                    factors=(nr.Factor("hill_inhibition", "X2", lu(1e-4, 1e-2), lu(0.5, 4)),)),
        nr.Reaction("third", "mass_action", {"X1": 2, "X2": 1}, {"X1": 1, "X3": 1},
                    rate_constant=lu(1e2, 1e5)),
        nr.Reaction("catalysed", "michaelis_menten", {"X4": 1}, {"X1": 1, "X2": 1},
                    k_cat_per_s=lu(0.1, 10), K_M_mM=lu(1e-4, 1e-2), catalyst="E"),
        nr.Reaction("saturable_sink", "michaelis_menten", {"X3": 1}, {},
                    V_max_mM_per_s=lu(1e-5, 1e-3), K_M_mM=lu(1e-4, 1e-2)),
    )
    return nr.Network(species=species, reactions=reactions, c0_mM=lu(0.1, 10))


def random_amounts(rng, S, N, volumes, lo=1e-4, hi=1e-2):
    return (10 ** rng.uniform(math.log10(lo), math.log10(hi), size=(S, N))) * volumes[None, :]


# ------------------------------------------------------------------------- rate laws


def test_rate_laws_against_their_textbook_forms():
    rng = np.random.default_rng(1)
    net = every_law_network(rng)
    cn = nr.compile_network(net)
    V = np.array([0.5, 2.0, 7.0])
    n = random_amounts(rng, 5, 3, V)
    m = rng.uniform(0.2, 3.0, size=(len(cn.reactions), 3))
    r = nr.rates(net, n, V, m)
    c = n / V
    a = c / cn.c0
    idx = {s: i for i, s in enumerate(cn.species)}
    rx = {x.name: x for x in net.reactions}
    for i in range(3):
        for name, j in (("source", 2), ("sink", 3), ("third", 4)):
            x = rx[name]
            prod = math.prod(c[idx[s], i] ** v for s, v in x.reactants.items())
            F = 1.0
            for f in x.factors:
                xs, K, h = c[idx[f.species], i], f.K_mM, f.n
                top = xs**h if f.kind == "hill_activation" else K**h
                F *= top / (K**h + xs**h)
            want = m[j, i] * F * x.rate_constant * V[i] * prod
            assert r.net[j, i] == pytest.approx(want, rel=1e-13)
            assert r.factor[j, i] == pytest.approx(F, rel=1e-13)
        x = rx["catalysed"]
        cE, cS = c[idx["E"], i], c[idx["X4"], i]
        assert r.net[5, i] == pytest.approx(
            m[5, i] * V[i] * x.k_cat_per_s * cE * cS / (x.K_M_mM + cS), rel=1e-13)
        x = rx["saturable_sink"]
        cS = c[idx["X3"], i]
        assert r.net[6, i] == pytest.approx(
            m[6, i] * V[i] * x.V_max_mM_per_s * cS / (x.K_M_mM + cS), rel=1e-13)
        for j, (reac, prod) in ((0, (("X1", "X2"), ("X3",))), (1, (("X3",), ("X4",)))):
            g = sum(cn.nu[idx[s], j] * cn.mu0_RT[idx[s]] for s in cn.species)
            fwd = m[j, i] * V[i] * cn.c0 * cn.k_f[j] * math.prod(a[idx[s], i] for s in reac)
            rev = m[j, i] * V[i] * cn.c0 * cn.k_f[j] * math.exp(g) * math.prod(
                a[idx[s], i] for s in prod)
            assert r.forward[j, i] == pytest.approx(fwd, rel=1e-13)
            assert r.reverse[j, i] == pytest.approx(rev, rel=1e-13)
            assert abs(r.net[j, i] - (fwd - rev)) <= 1e-13 * (fwd + rev)
            assert r.affinity[j, i] == pytest.approx(math.log(fwd / rev), abs=1e-13)
    # L: consumption per amount with unidirectional fluxes (Appendix A).
    consumed = np.maximum(-cn.nu, 0) @ r.forward + np.maximum(cn.nu, 0) @ r.reverse
    np.testing.assert_allclose(r.consumption_rate, consumed / n, rtol=1e-14)


def test_hill_factors_stay_finite_and_bounded_at_extremes():
    species = (nr.Species("X"), nr.Species("Y"))
    for kind in ("hill_activation", "hill_inhibition"):
        net = nr.Network(species=species, reactions=(nr.Reaction(
            "make", "mass_action", {}, {"Y": 1}, rate_constant=1.0,
            factors=(nr.Factor(kind, "X", 1.0, 4.0),)),))
        r = nr.rates(net, np.array([[1e-250, 1.0, 1e250], [1.0, 1.0, 1.0]]), 1.0)
        F = r.factor[0]
        assert np.isfinite(F).all() and ((F >= 0) & (F <= 1)).all()
        lo, mid, hi = F
        assert mid == pytest.approx(0.5, rel=1e-15)
        assert (lo, hi) == ((0.0, 1.0) if kind == "hill_activation" else (1.0, 0.0))


def test_zero_multiplier_routes_are_exact_zeros():
    net = ab_network(sink=1.0)
    r = nr.rates(net, np.array([[1.0, 2.0], [3.0, 4.0]]), [1.0, 1.0], [[0.0, 1.0], [1.0, 0.0]])
    assert r.net[0, 0] == 0.0 and r.forward[0, 0] == 0.0 and r.reverse[0, 0] == 0.0
    assert r.net[1, 1] == 0.0 and r.forward[1, 1] == 0.0
    assert r.affinity[0, 0] != 0.0  # The affinity is a state function, reported whatever m is.


def test_declaration_refusals():
    sp = (nr.Species("A", 0.0, {"M": 1}), nr.Species("B", 0.0, {"M": 1}), nr.Species("C"))
    bad = [
        nr.Reaction("open_passive", "passive", {"A": 1}, {"C": 1}, k_f_per_s=1.0),
        nr.Reaction("mixed_sign", "mass_action", {"A": 1}, {"C": 1}, rate_constant=1.0),
        nr.Reaction("order4", "mass_action", {"A": 4}, {}, rate_constant=1.0),
        nr.Reaction("fraction", "mass_action", {"A": 1.5}, {}, rate_constant=1.0),
        nr.Reaction("factor_on_passive", "passive", {"A": 1}, {"B": 1}, k_f_per_s=1.0,
                    factors=(nr.Factor("hill_activation", "C", 1.0, 1.0),)),
        nr.Reaction("mm_two", "michaelis_menten", {"A": 2}, {}, V_max_mM_per_s=1.0, K_M_mM=1.0),
        nr.Reaction("mm_written_catalyst", "michaelis_menten", {"A": 1}, {"B": 1, "C": 1},
                    k_cat_per_s=1.0, K_M_mM=1.0, catalyst="C"),
        nr.Reaction("negative_k", "mass_action", {"A": 1}, {}, rate_constant=-1.0),
        nr.Reaction("zero_K_M", "michaelis_menten", {"A": 1}, {}, V_max_mM_per_s=1.0, K_M_mM=0.0),
    ]
    for rx in bad:
        with pytest.raises(nr.DeclarationError):
            nr.compile_network(nr.Network(species=sp, reactions=(rx,)))
    cn = nr.compile_network(tu.schnakenberg_network(0.1, 0.9, 0.1, 1e-3))
    assert cn.role == ("source", "sink", "source", "closed")


# ------------------------------------------------------------------------- half-step


def test_linear_decay_is_the_third_order_taylor_polynomial():
    species = (nr.Species("A"),)
    net = nr.Network(species=species, reactions=(
        nr.Reaction("decay", "mass_action", {"A": 1}, {}, rate_constant=2.0),))
    for h in (0.01, 0.1, 0.24):
        z = -2.0 * h
        st = nr.half_step(net, [3.0], 1.0, h, RT)
        assert st.end[0, 0] == pytest.approx(3.0 * (1 + z + z * z / 2 + z**3 / 6), rel=4 * EPS)
        assert st.hL_max == pytest.approx(2.0 * h, rel=4 * EPS) and st.L_max == pytest.approx(2.0)


def test_butcher_form_equals_the_shu_osher_form():
    rng = np.random.default_rng(2)
    net = every_law_network(rng)
    V = np.array([0.7, 3.0])
    n = random_amounts(rng, 5, 2, V)
    m = rng.uniform(0.5, 2.0, size=(7, 2))
    h = 0.05
    nu = nr.compile_network(net).nu

    def f(y):
        return nu @ nr.rates(net, y, V, m).net

    u1 = n + h * f(n)
    u2 = 0.75 * n + 0.25 * (u1 + h * f(u1))
    want = n / 3.0 + 2.0 / 3.0 * (u2 + h * f(u2))
    st = nr.half_step(net, n, V, h, RT, m)
    assert st.admitted
    np.testing.assert_allclose(st.end, want, rtol=1e-13)
    assert np.array_equal(st.delta, nu @ st.extents)  # Delta n = nu dxi, by construction.
    assert np.array_equal(st.end, n + st.delta)
    moieties = nr.moiety_totals(net, st.end) - nr.moiety_totals(net, n)
    np.testing.assert_allclose(moieties, nr.moiety_change_from_extents(net, st.extents),
                               rtol=1e-12, atol=1e-15 * float(np.max(n)))


def test_half_step_local_error_is_fourth_order():
    """SSPRK(3,3) is third order: one step's error against DOP853 falls 16-fold per halving."""
    net = enzyme_network()
    n0 = np.array([1e-4, 1e-3, 3e-6, 1e-6])
    errors = []
    for h in (0.04, 0.02, 0.01):
        st = nr.half_step(net, n0, 1.0, h, RT)
        exact = dr.integrate_node(net, n0, 1.0, RT, [h]).amounts[0, :, 0]
        errors.append(np.max(np.abs(st.end[:, 0] - exact) / exact))
    ratios = [errors[0] / errors[1], errors[1] / errors[2]]
    assert all(14.0 < q < 18.0 for q in ratios), ratios


def test_stage_condition_uses_unidirectional_fluxes_on_a_reverse_running_route():
    """Probe 2c's case: A <=> B, K = 10, started at c_B/c_A = 1e4 so that it runs in reverse."""
    k_f = 1.0
    net = ab_network(K=10.0, k_f=k_f)
    n = np.array([1e-4, 1.0])
    k_r = k_f / 10.0
    r = nr.rates(net, n, 1.0)
    assert r.net[0, 0] < 0
    np.testing.assert_allclose(r.consumption_rate[:, 0], [k_f, k_r], rtol=1e-14)
    for hk, admitted in ((0.50, True), (0.54, True), (0.56, False), (0.9, False)):
        st = nr.half_step(net, n, 1.0, hk / (k_f + k_r), RT)
        assert st.stage_condition_ok is admitted and st.admitted is admitted, hk
        assert st.positive_ok
        if not admitted:
            assert np.array_equal(st.accepted, st.start)


def test_positivity_refusal_and_its_flags():
    species = (nr.Species("A"),)
    net = nr.Network(species=species, reactions=(
        nr.Reaction("decay", "mass_action", {"A": 1}, {}, rate_constant=1.0),))
    st = nr.half_step(net, [1.0], 1.0, 3.0, RT)
    assert not st.positive_ok and not st.stage_condition_ok and not st.admitted
    assert np.array_equal(st.accepted, st.start)
    assert st.hL_argmax[1] == 0


# -------------------------------------------------------------------------- bookings


def test_bookings_by_node_class_and_the_ledger():
    rng = np.random.default_rng(3)
    net = every_law_network(rng)
    cn = nr.compile_network(net)
    N = 4
    V = rng.uniform(0.5, 5.0, size=N)
    n = random_amounts(rng, 5, N, V)
    m = rng.uniform(0.5, 2.0, size=(7, N))
    m[:, 0] = 0.0  # idle
    m[cn.passive, 1] = 0.0  # driven only
    m[cn.driven, 2] = 0.0  # passive only; node 3 is mixed
    st = nr.half_step(net, n, V, 0.02, RT, m)
    assert st.admitted
    assert list(st.node_class) == ["idle", "driven", "passive", "mixed"]
    assert np.array_equal(st.end[:, 0], n[:, 0]) and st.extents[:, 0].tolist() == [0.0] * 7
    assert st.heat[0] == st.work[0] == st.delta_G[0] == st.standard[0] == 0.0
    assert st.heat[1] == 0.0 and st.work[1] == st.delta_G[1]
    assert st.work[2] == 0.0 and st.heat[2] == -st.delta_G[2]
    passive = cn.passive
    assert st.heat[3] == pytest.approx(np.sum(st.route_heat[passive, 3]), rel=1e-14)
    assert set(st.branch[passive, 3]) <= {"share", "quadrature"}
    assert set(st.branch[passive, 2]) == {"node"} and set(st.branch[passive, 0]) == {"idle"}
    scale = st.delta_G_terms + np.abs(st.heat) + np.abs(st.work)
    assert (np.abs(st.ledger_residual) <= 8 * EPS * scale).all()
    np.testing.assert_allclose(st.standard, st.standard_species, rtol=1e-12,
                               atol=8 * EPS * float(np.max(st.delta_G_terms)))
    # The divided differences sum to dG exactly in exact arithmetic (separable G).
    total = np.sum(st.mu_bar * st.delta, axis=0)
    assert (np.abs(total[1:] - st.delta_G[1:]) <= 64 * EPS * st.delta_G_terms[1:]).all()


def test_switched_off_routes_select_the_single_class_booking():
    """§3.4 item 4: a mixed node with its driven routes off books H = -dG, W = 0, even where a
    passive route would take the quadrature branch; with its passive routes off, H = 0, W = dG."""
    net = ab_network(K=1.0, k_f=1.0, sink=1.0)
    n = np.array([1.0 + 0.0126, 1.0])  # Probe 2e's crossing at h L = 0.05 (k_d = 1)
    h = 0.025
    mixed = nr.half_step(net, n, 1.0, h, RT)
    assert mixed.node_class[0] == "mixed" and mixed.branch[0, 0] == "quadrature"
    assert mixed.heat_share[0, 0] < 0 <= mixed.heat[0]
    off = nr.half_step(net, n, 1.0, h, RT, [1.0, 0.0])
    assert off.node_class[0] == "passive" and off.branch[0, 0] == "node"
    assert off.work[0] == 0.0 and off.heat[0] == -off.delta_G[0] >= 0.0
    passive_off = nr.half_step(net, n, 1.0, h, RT, [0.0, 1.0])
    assert passive_off.node_class[0] == "driven"
    assert passive_off.heat[0] == 0.0 and passive_off.work[0] == passive_off.delta_G[0]
    idle = nr.half_step(net, n, 1.0, h, RT, [0.0, 0.0])
    assert idle.node_class[0] == "idle" and np.array_equal(idle.end, idle.start)


def test_branch_selection_on_each_side_and_at_it():
    h = 0.01
    # At it: a mixed node started exactly at the passive equilibrium (A = 0, J(Y1) = 0).
    net = ab_network(K=1.0, sink=1.0)
    at = nr.half_step(net, np.array([1.0, 1.0]), 1.0, h, RT)
    assert at.stage_net[0, 0, 0] == 0.0 and at.branch[0, 0] == "quadrature"
    assert at.heat_quadrature[0, 0] >= 0.0
    # One side: the route keeps its sign through the step (forward, far from equilibrium).
    far = nr.half_step(net, np.array([2.0, 1.0]), 1.0, h, RT)
    assert far.non_reversing[0, 0] and far.branch[0, 0] == "share"
    assert far.heat[0] == far.heat_share[0, 0] >= 0.0
    # The other side: the sink carries the state across the equilibrium within the step.
    cross = nr.half_step(net, np.array([1.0 + 0.0126, 1.0]), 1.0, 0.025, RT)
    assert not cross.non_reversing[0, 0] and cross.branch[0, 0] == "quadrature"
    assert cross.stage_net[0, 0, 0] > 0 > cross.end_affinity[0, 0]
    # Probe 2d's onset from a trace: the share.
    onset = nr.half_step(enzyme_network(), np.array([1e-4, 1e-3, 1e-12, 1e-12]), 1.0, 0.025, RT)
    assert onset.branch[0, 0] == "share" and onset.branch[1, 0] == ""


def test_quadrature_and_unimolecular_share_are_non_negative():
    rng = np.random.default_rng(4)
    for _ in range(40):
        K, k_f, k_d = (float(10 ** rng.uniform(-1, 1)) for _ in range(3))
        net = ab_network(K=K, k_f=k_f, sink=k_d)
        n = 10 ** rng.uniform(-3, 0, size=2)
        h = float(rng.uniform(0.05, 0.45)) / (k_f + k_d + k_f / K)
        st = nr.half_step(net, n, 1.0, h, RT)
        assert st.heat_quadrature[0, 0] >= 0.0
        if st.non_reversing[0, 0]:
            assert st.heat_share[0, 0] >= 0.0
        assert st.heat[0] >= 0.0


def test_divided_difference_series_is_continuous_at_its_switch():
    species = (nr.Species("A"),)
    net = nr.Network(species=species, reactions=())
    n = np.array([[2.0, 2.0, 2.0, 2.0]])
    x = np.array([nr.SERIES_SWITCH * (1 - 1e-9), nr.SERIES_SWITCH * (1 + 1e-9), -nr.SERIES_SWITCH
                  * (1 - 1e-9), -nr.SERIES_SWITCH * (1 + 1e-9)])
    mu = nr.divided_difference_potentials(net, n, n * x, 1.0, RT)[0]
    assert abs(mu[0] - mu[1]) <= 1e-14 * abs(mu[0]) and abs(mu[2] - mu[3]) <= 1e-14 * abs(mu[2])
    # Against the exact divided difference [g(n + d) - g(n)]/d at a resolvable x.
    d = 1e-3
    g = lambda v: RT * v * (math.log(v) - 1.0)  # noqa: E731
    exact = (g(2.0 + 2.0 * d) - g(2.0)) / (2.0 * d)
    got = nr.divided_difference_potentials(net, [[2.0]], [[2.0 * d]], 1.0, RT)[0, 0]
    assert got == pytest.approx(exact, rel=1e-12)


def test_increment_form_against_fifty_digit_values():
    """§3.4 item 4: booked W - H equals the independently computed dG (standard term included) to
    1e-12 of the summed |terms|; this float implementation is within a few eps of it."""
    rng = np.random.default_rng(5)
    worst = 0.0
    for trial in range(6):
        net = every_law_network(rng)
        N = 3
        V = rng.uniform(0.2, 5.0, size=N)
        n = random_amounts(rng, 5, N, V, 1e-12 if trial % 2 else 1e-5, 1e-2)
        st = nr.half_step(net, n, V, 10 ** rng.uniform(-4, -2), RT)
        assert st.admitted
        ex = nr.exact_energy_change(net, n, V, RT, delta_fmol=st.delta, extents_fmol=st.extents)
        err = np.abs(st.delta_G - ex.delta_G_float) / ex.terms_float
        worst = max(worst, float(np.max(err)))
        assert (np.abs((st.work - st.heat) - ex.delta_G_float) <= 1e-12 * ex.terms_float).all()
        np.testing.assert_allclose(st.standard, ex.standard_routes_float, rtol=1e-13,
                                   atol=4 * EPS * float(np.max(ex.terms_float)))
        by_end = nr.exact_energy_change(net, n, V, RT, end_fmol=n + st.delta)
        assert (np.abs(by_end.delta_G_float - ex.delta_G_float) <= 1e-9 * ex.terms_float).all()
    assert worst <= 16 * EPS, worst
    # G(end) - G(start) at 50 digits equals the increment form.
    G0 = nr.exact_free_energy(net, n, V, RT)
    G1 = nr.exact_free_energy(net, n + st.delta, V, RT)
    by_end = nr.exact_energy_change(net, n, V, RT, end_fmol=n + st.delta)
    with localcontext() as ctx:  # Python's default context keeps only 28 digits.
        ctx.prec = 60
        for i in range(N):
            assert abs((G1[i] - G0[i]) - by_end.delta_G[i]) <= Decimal("1e-45") * abs(G0[i])


# ---------------------------------------------------------------- dissipation integral


def test_passive_and_driven_nodes_against_the_exact_integral():
    net = ab_network(K=10.0, k_f=1.0)
    tr = dr.integrate_node(net, np.array([1.0, 1.0]), 1.0, RT, [0.5, 3.0])
    np.testing.assert_allclose(tr.heat[:, 0], -tr.delta_G[:, 0], rtol=1e-11)
    assert (tr.work == 0.0).all() and (np.abs(tr.closure) <= 1e-12 * np.abs(tr.heat)).all()
    species = (nr.Species("A", 0.4, {"M": 1}), nr.Species("B", -0.3, {"M": 1}))
    driven = nr.Network(species=species, reactions=(
        nr.Reaction("make", "mass_action", {}, {"A": 1}, rate_constant=0.3),
        nr.Reaction("convert", "mass_action", {"A": 1}, {"B": 1}, rate_constant=0.7),))
    tr = dr.integrate_node(driven, np.array([0.1, 0.2]), 2.0, RT, [1.0])
    assert tr.heat[0, 0] == 0.0
    assert tr.work[0, 0] == pytest.approx(tr.delta_G[0, 0], rel=1e-11)


def test_dissipation_integral_converges_between_tolerances():
    net = enzyme_network()
    n0 = np.array([1e-4, 1e-3, 1e-12, 1e-12])
    tight = dr.integrate_node(net, n0, 1.0, RT, [0.025, 0.05])
    loose = dr.integrate_node(net, n0, 1.0, RT, [0.025, 0.05], rtol=1e-11)
    np.testing.assert_allclose(loose.heat, tight.heat, rtol=1e-10)
    np.testing.assert_allclose(loose.work, tight.work, rtol=1e-10)
    assert (np.abs(tight.closure) <= 1e-10 * np.abs(tight.heat)).all()
    # Probe 2d (§3.3): the first half-step's share and quadrature against the true heat.
    st = nr.half_step(net, n0, 1.0, 0.025, RT)
    true = tight.heat[0, 0]
    assert st.heat[0] / true - 1 == pytest.approx(0.0014, abs=0.0002)
    assert st.heat_quadrature[0, 0] / true - 1 == pytest.approx(0.42, abs=0.01)


def test_mixed_node_heat_converges_at_second_order():
    """§3.4 item 4: in the non-reversing branch H converges to the integral at second order."""
    net = enzyme_network()
    n0 = np.array([1e-4, 1e-3, 1e-5, 1e-5])
    T = 0.4
    true = dr.integrate_node(net, n0, 1.0, RT, [T]).heat[0, 0]
    errors = []
    for h in (0.02, 0.01, 0.005):
        run = nr.run_half_steps(net, n0, 1.0, h, int(round(T / h)), RT)
        assert run.taken == int(round(T / h)) and all((b[0] == "share").all() for b in run.branches)
        errors.append(abs(run.heat[-1, 0] - true))
    ratios = [errors[0] / errors[1], errors[1] / errors[2]]
    assert all(3.5 < q < 4.5 for q in ratios), ratios


def test_chained_segments_carry_the_cumulative_records():
    net = ab_network(K=1.0, k_f=1.0, sink=1.0)
    first = dr.integrate_node(net, np.array([2.0, 1.0]), 1.0, RT, [0.5])
    second = dr.integrate_node(net, None, 1.0, RT, [1.0], multipliers=[1.0, 0.0],
                               continue_from=first)
    assert second.work[-1, 0] == first.work[-1, 0]  # No driven route in the second segment.
    assert second.heat[-1, 0] > first.heat[-1, 0]
    assert abs(second.closure[-1, 0]) <= 1e-11 * abs(second.heat[-1, 0])


# ------------------------------------------------------------- equilibria, closed forms


def test_passive_equilibria():
    for dmu in (-math.log(10.0), 0.7):
        species = (nr.Species("A", 0.3, {"M": 1}), nr.Species("B", 0.3 + dmu, {"M": 1}))
        net = nr.Network(species=species, reactions=(
            nr.Reaction("ab", "passive", {"A": 1}, {"B": 1}, k_f_per_s=1.0),), c0_mM=2.0)
        eq = dr.passive_equilibrium(net, [1.0, 3.0], 1.5, RT)
        ratio = dr.passive_equilibrium_ratio(0.3, 0.3 + dmu)
        assert eq.amounts[1] / eq.amounts[0] == pytest.approx(ratio, rel=4e-15)
        assert eq.amounts.sum() == pytest.approx(4.0, rel=4e-16)
        assert eq.delta_G < 0
    net = enzyme_network()
    n0 = np.array([1e-4, 1e-3, 1e-12, 1e-12])
    eq = dr.passive_equilibrium(net, n0, 1.0, RT)
    K = dr.equilibrium_constants(net)[0]
    assert eq.log_quotient[0] == pytest.approx(math.log(K), abs=1e-13)
    np.testing.assert_allclose(nr.moiety_totals(net, eq.amounts)[:, 0],
                               nr.moiety_totals(net, n0)[:, 0], rtol=1e-14)


def test_closed_passive_relaxation_heat_is_G_start_minus_G_equilibrium():
    """Probe 2's B4 (single node): c_B/c_A relaxes to K, and the total heat to -dG(eq)."""
    net = ab_network(K=10.0, k_f=1.0)
    n0 = np.array([1.0, 1.0])
    run = nr.run_half_steps(net, n0, 1.0, 0.2, 400, RT)
    assert run.taken == 400 and (run.step_heat >= -1e-18).all()
    end = run.amounts[-1, :, 0]
    assert end[1] / end[0] == pytest.approx(10.0, rel=1e-13)
    eq = dr.passive_equilibrium(net, n0, 1.0, RT)
    assert run.heat[-1, 0] == pytest.approx(-eq.delta_G, rel=1e-12)


def test_open_linear_kinetics_against_the_closed_form():
    """§6.2 world 2 (probe 2b's B9): third order for the half-steps alone, exact for DOP853."""
    species = (nr.Species("A"),)
    P, k, V, n0, T = 2e-3, 0.5, 1.0, 1e-3, 4.0
    net = nr.Network(species=species, reactions=(
        nr.Reaction("make", "mass_action", {}, {"A": 1}, rate_constant=P / V),
        nr.Reaction("clear", "mass_action", {"A": 1}, {}, rate_constant=k),))
    exact = dr.turnover_amount(n0, P, k, T)
    tr = dr.integrate_node(net, [n0], V, RT, [T])
    assert tr.amounts[0, 0, 0] == pytest.approx(exact, rel=1e-12)
    errors = [abs(nr.run_half_steps(net, [n0], V, h, int(round(T / h)), RT).amounts[-1, 0, 0]
                  - exact) / exact for h in (0.2, 0.1, 0.05)]
    ratios = [errors[0] / errors[1], errors[1] / errors[2]]
    assert all(7.5 < q < 8.6 for q in ratios), ratios


def test_michaelis_menten_depletion_against_the_closed_form():
    species = (nr.Species("S", 0.0, {"S": 1}), nr.Species("P", 0.0, {"S": 1}),
               nr.Species("E", 0.0, {"E": 1}))
    for catalyst in (None, "E"):
        kwargs = dict(k_cat_per_s=2.0, catalyst="E") if catalyst else dict(V_max_mM_per_s=4e-3)
        net = nr.Network(species=species, reactions=(nr.Reaction(
            "convert", "michaelis_menten", {"S": 1}, {"P": 1}, K_M_mM=5e-4, **kwargs),))
        V = 2.0
        n0 = np.array([2e-3, 1e-9, 2e-3]) * V  # c_E = 2e-3 mM, so V_max = k_cat c_E = 4e-3 mM/s
        times = [0.1, 0.4, 0.9]
        tr = dr.integrate_node(net, n0, V, RT, times)
        want = dr.michaelis_menten_substrate(2e-3, 5e-4, 4e-3, times)
        np.testing.assert_allclose(tr.amounts[:, 0, 0] / V, want, rtol=1e-11)
    assert dr.michaelis_menten_substrate(1.0, 1.0, 1.0, 0.0) == pytest.approx(1.0, rel=1e-15)
    deep = dr.michaelis_menten_substrate(1e3, 1.0, 1.0, 100.0)  # ln W's argument > 700
    assert 1.0 * math.log(1e3 / deep) + (1e3 - deep) == pytest.approx(100.0, rel=1e-13)


# ---------------------------------------------------------------------------- the chain


def test_neumann_cosines_are_exact_eigenvectors():
    for N, h in ((7, 1.0), (22, 5e-6)):
        Lap = cr.chain_laplacian(N, h)
        C = cr.mode_basis(N)
        lam = cr.chain_eigenvalues(N, h)
        np.testing.assert_allclose(Lap @ C.T, -C.T * lam[None, :], atol=1e-13 * lam.max())
        f = np.random.default_rng(N).normal(size=(2, N))
        np.testing.assert_allclose(cr.field_from_modes(cr.mode_coefficients(f)), f, atol=1e-14)
    lam = cr.chain_eigenvalues(1000, 0.01)  # -> (n pi/L)^2 at O(h^2): (3 pi h/(2L))^2/3 = 7.4e-6
    assert lam[3] == pytest.approx((3 * math.pi / 10.0) ** 2, rel=1e-5)


def test_passive_chain_modewise_against_the_full_exponential():
    """§6.2 world 1: passive A <=> B (K = 10) with D_A != D_B on a zero-flux chain."""
    net = ab_network(K=10.0, k_f=0.05)
    K, p = cr.linear_rates(net)
    assert not p.any()
    np.testing.assert_allclose(K, [[-0.05, 0.005], [0.05, -0.005]], rtol=1e-15)
    N, h, D = 16, 5e-6, np.array([1e-11, 4e-11])
    rng = np.random.default_rng(6)
    c0 = 1e-3 * (1.0 + 0.1 * rng.normal(size=(2, N)))
    for t in (5.0, 60.0):
        modewise = cr.propagate_field(K, D, h, c0, t)
        full = (cr.full_propagator(K, D, N, h, t) @ c0.ravel()).reshape(2, N)
        assert np.max(np.abs(modewise - full)) <= 1e-13 * np.max(np.abs(c0))
    tr = cr.integrate_chain(net, c0 * 0.5, 0.5, h, D, [60.0])
    np.testing.assert_allclose(tr.amounts[0] / 0.5, cr.propagate_field(K, D, h, c0, 60.0),
                               rtol=1e-10)


def test_open_linear_chain_puts_the_source_in_mode_zero():
    species = (nr.Species("A"),)
    net = nr.Network(species=species, reactions=(
        nr.Reaction("make", "mass_action", {}, {"A": 1}, rate_constant=2e-4),
        nr.Reaction("clear", "mass_action", {"A": 1}, {}, rate_constant=0.2),))
    K, p = cr.linear_rates(net)
    N, h, D, V = 8, 1e-5, np.array([1e-10]), 1.0
    c0 = 1e-3 * (1.0 + 0.2 * np.cos(np.pi * (np.arange(N) + 0.5) / N))[None, :]
    want = cr.propagate_field(K, D, h, c0, 7.0, source=p)
    tr = cr.integrate_chain(net, c0 * V, V, h, D, [7.0])
    np.testing.assert_allclose(tr.amounts[0] / V, want, rtol=1e-10)
    mean = c0.mean() * math.exp(-0.2 * 7.0) - (2e-4 / 0.2) * math.expm1(-0.2 * 7.0)
    assert want.mean() == pytest.approx(mean, rel=1e-13)


def test_strang_mode_map_equals_the_composed_node_space_step():
    """The engine order's linear map: half-step, ARS(2,2,2) transport polynomial, half-step."""
    net = ab_network(K=10.0, k_f=0.3)
    K, p = cr.linear_rates(net)
    N, h, D, dt, V = 12, 5e-6, np.array([1e-11, 1e-10]), 0.05, 0.5
    rng = np.random.default_rng(7)
    n = 1e-3 * V * (1.0 + 0.1 * rng.normal(size=(2, N)))
    Lap = cr.chain_laplacian(N, h)
    T = [np.eye(N) + dt * Ds * Lap + 0.5 * (dt * Ds * Lap) @ (dt * Ds * Lap) for Ds in D]
    y = nr.half_step(net, n, V, dt / 2, RT).end
    y = np.stack([T[s] @ y[s] for s in range(2)])
    y = nr.half_step(net, y, V, dt / 2, RT).end
    a = cr.mode_coefficients(n)
    lam = cr.chain_eigenvalues(N, h)
    want = np.stack([cr.strang_mode_map(K, D, lam[k], dt)[0] @ a[:, k] for k in range(N)], axis=1)
    np.testing.assert_allclose(cr.mode_coefficients(y), want, atol=1e-13 * np.max(np.abs(a)))


# ----------------------------------------------------------------------- MG0c (§6.4)

A_, B_, D_RATIO = 0.1, 0.9, 10.0
J_MG0C = tu.schnakenberg_jacobian(A_, B_)


def test_schnakenberg_uniform_state_and_jacobian():
    assert tu.schnakenberg_uniform_state(A_, B_) == pytest.approx((1.0, 0.9), rel=1e-15)
    np.testing.assert_allclose(J_MG0C, [[0.8, 1.0], [-1.8, -1.0]], atol=1e-15)
    assert np.trace(J_MG0C) == pytest.approx(-0.2) and np.linalg.det(J_MG0C) == pytest.approx(1.0)
    # The four mass-action declarations reproduce the textbook Jacobian (dimensional: k J).
    k, c_star, V = 0.1, 1e-3, 0.5
    net = tu.schnakenberg_network(A_, B_, k, c_star)
    rates = tu.schnakenberg_rate_constants(A_, B_, k, c_star)
    assert rates["autocatalysis"][0] == pytest.approx(1e5)  # §2.1's example rate constant
    nu = nr.compile_network(net).nu
    u = tu.schnakenberg_uniform_amounts(A_, B_, c_star, V)
    f0 = nu @ nr.rates(net, u, V).net[:, 0]
    assert np.max(np.abs(f0)) <= 1e-15 * k * c_star * V
    jac = np.empty((2, 2))
    for j in range(2):
        d = np.zeros(2)
        d[j] = 1e-6 * u[j]
        jac[:, j] = (nu @ (nr.rates(net, u + d, V).net - nr.rates(net, u - d, V).net))[:, 0] / (
            2 * d[j])
    np.testing.assert_allclose(jac, k * J_MG0C, rtol=1e-8, atol=1e-10)


def test_turing_numbers_of_section_6_4():
    an = tu.turing_analysis(J_MG0C, 1.0, D_RATIO)
    assert an["stable_without_diffusion"] and an["diffusion_driven_instability"]
    assert an["critical_ratio"] == pytest.approx(8.568, abs=5e-4)
    assert an["band"] == pytest.approx((0.2, 0.5), abs=1e-14)
    assert an["sigma_max"] == pytest.approx(0.0572, abs=5e-5)
    assert an["k2_fastest"] == pytest.approx(0.3186, abs=1e-4)  # §6.4; exactly 0.318545...
    # 810 q^2 + 324 q - 185.4 = 0 (fastest_growing's stationarity quadratic, worked by hand).
    assert an["k2_fastest"] == pytest.approx((-324 + math.sqrt(324**2 + 4 * 810 * 185.4)) / 1620,
                                             rel=1e-13)
    q = an["k2_fastest"]
    assert an["sigma_max"] == pytest.approx((7.0 - 20.0 * q) / 11.0, rel=1e-12)
    grid = np.linspace(0.2, 0.5, 30001)
    assert an["sigma_max"] >= np.max(tu.growth_rate(J_MG0C, 1.0, D_RATIO, grid)) - 1e-16
    assert an["wavelength"] == pytest.approx(11.13, abs=5e-3)
    k, ell_um = 0.1, 10.0
    assert 1.0 / (k * an["sigma_max"]) == pytest.approx(175.0, abs=0.5)  # e-folds in 175 s
    assert ell_um * an["wavelength"] == pytest.approx(111.0, abs=0.5)  # a wavelength of 111 um
    assert tu.band_edges(J_MG0C, 1.0, an["critical_ratio"] * (1 - 1e-9)) is None
    assert tu.critical_ratio(J_MG0C) == pytest.approx(an["critical_ratio"], rel=1e-15)
    sig = tu.growth_rate(J_MG0C, 1.0, D_RATIO, np.array([0.2, 0.5, 0.3]))
    assert abs(sig[0]) <= 1e-15 and abs(sig[1]) <= 1e-15 and sig[2] > 0
    ev = tu.dispersion_eigenvalues(J_MG0C, 1.0, D_RATIO, np.array([0.05, 0.3, 2.0]))
    np.testing.assert_allclose(tu.growth_rate(J_MG0C, 1.0, D_RATIO, [0.05, 0.3, 2.0]),
                               ev.real.max(axis=-1), rtol=1e-12)


@pytest.mark.parametrize("L, admissible, sigmas", [  # sigma_n to half a unit of its last digit
    (6, [1], {1: (0.0508, 5e-5)}),
    (8, [], {1: (-0.089, 5e-4), 2: (-0.065, 5e-4)}),
    (11, [2], {2: (0.0571, 5e-5)}),
    (16, [3], {3: (0.0556, 5e-5)}),
    (22, [4], {4: (0.0571, 5e-5), 5: (-0.0023, 5e-5)}),
])
def test_domain_table_at_half_ell(L, admissible, sigmas):
    modes = tu.domain_modes(J_MG0C, 1.0, D_RATIO, L, 0.5)
    assert len(modes["n"]) == 2 * L - 1  # N = 2 L/l nodes
    assert tu.admissible_unstable_modes(J_MG0C, 1.0, D_RATIO, L, 0.5) == admissible
    for n, (sigma, tol) in sigmas.items():
        assert modes["sigma_discrete"][n - 1] == pytest.approx(sigma, abs=tol)
    short = 1.0 - modes["k2_discrete"] / modes["k2_continuum"]
    for n in admissible:  # The discrete k^2 falls short by 0.6-0.7% near the band.
        assert 0.0055 < short[n - 1] < 0.0075


def test_staircase_continuum_and_discrete():
    lengths = np.arange(4.0, 31.0, 0.5)
    table = [(4.0, 4.0, None), (4.5, 7.0, 1), (7.5, 8.5, None), (9.0, 13.5, 2), (14.0, 19.0, 3),
             (19.5, 24.5, 4), (25.0, 30.5, 5)]
    continuum = dict(tu.staircase(J_MG0C, 1.0, D_RATIO, lengths))
    for lo, hi, n in table:
        for L in lengths[(lengths >= lo) & (lengths <= hi)]:
            assert continuum[float(L)] == n, (L, continuum[float(L)], n)
    discrete = dict(tu.staircase(J_MG0C, 1.0, D_RATIO, lengths, 0.5))
    for L in lengths[(lengths >= 4.5) & (lengths <= 30.0)]:  # Q4's sweep
        assert discrete[float(L)] == continuum[float(L)], L
    # Q5's subcritical control: at d = 8 every discrete mode decays on every domain.
    for L in lengths:
        assert (tu.domain_modes(J_MG0C, 1.0, 8.0, L, 0.5)["sigma_discrete"] < 0).all()


def test_b1_mode_eigenvalues_on_the_eleven_ell_domain():
    k, N = 0.1, 22
    lam = cr.chain_eigenvalues(N, 0.5)  # non-dimensional (h = l/2)
    want = {1: (-0.0548, 0.0443), 2: (5.71e-3, 0.0), 3: (-0.0146, 0.0), 4: (-0.0607, 0.0)}
    for n, (re, im) in want.items():
        ev = np.linalg.eigvals(k * (J_MG0C - lam[n] * np.diag([1.0, D_RATIO])))
        top = ev[np.argmax(ev.real)]
        assert top.real == pytest.approx(re, rel=5e-3)
        assert abs(top.imag) == pytest.approx(im, abs=5e-5)


def test_nonlinear_chain_at_tiny_amplitude_follows_the_mode_propagator():
    k, c_star, V, h = 0.1, 1e-3, 0.5, 5e-6
    D = np.array([1e-11, 1e-10])
    net = tu.schnakenberg_network(A_, B_, k, c_star)
    u = tu.schnakenberg_uniform_amounts(A_, B_, c_star, V)
    N, amp, t = 12, 1e-7, 40.0
    start = u[:, None] * (1.0 + amp * cr.mode_basis(N)[1][None, :])
    tr = cr.integrate_chain(net, start, V, h, D, [t])
    a0 = cr.mode_coefficients(start)[:, 1]
    lam1 = cr.chain_eigenvalues(N, h)[1]
    want = cr.mode_propagator(k * J_MG0C, D, lam1, t) @ a0
    got = cr.mode_coefficients(tr.amounts[0])[:, 1]
    assert np.max(np.abs(got - want)) <= 1e-6 * np.max(np.abs(want))
    assert cr.dominant_mode(tr.amounts[0] - u[:, None]) == 1
    # The fitted growth rate of a propagated mode is its discrete sigma (L/l = 6, n = 1).
    times = np.linspace(100.0, 400.0, 7)
    amps = [(cr.mode_propagator(k * J_MG0C, D, lam1, s) @ a0)[0] for s in times]
    rate, rms = cr.fit_growth_rate(times, amps)
    sigma = tu.domain_modes(J_MG0C, 1.0, D_RATIO, 6, 0.5)["sigma_discrete"][0]
    assert rate == pytest.approx(k * sigma, rel=1e-3) and rms < 1e-3
