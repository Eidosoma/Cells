"""Self-tests of the excitable-tissue references (validation/excitable/): the laws, the fast
right-hand side against the appendix's readable form, conservation through junctions, the rests,
the kick, the observables against brute force, the passive cable against the discrete linear
cable, the strong-coupling limit, and the chain's activation and CV.

The references must stay independent of the engine and of Track E's probe: nothing under
validation/excitable/ imports `cells`, the probe (validation.tissue) or validation.division,
statically or in a fresh process; the one import from another reference is
validation.coupling.piecewise_ode. Fast settings (rtol 1e-8, short horizons) keep this tier 1;
the protocol numbers come from validation/excitable/excitable_protocols.py.
"""

import ast
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from validation.excitable import excitable_limits as el
from validation.excitable import excitable_protocols as ep
from validation.excitable import excitable_reference as er

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "excitable"
FAST = dict(rtol=1e-8)
V2 = -0.0795589  # about point 2's rest (§8.1); the tests need only a nearby rest


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


def test_references_import_nothing_from_cells_or_the_probe():
    files = sorted(REFERENCES.glob("*.py"))
    assert len(files) >= 3
    for path in files:
        for name, names in _imports(path):
            assert name != "<dynamic import>" and not name.startswith("."), (path.name, name)
            assert name.split(".")[0] not in {"cells", "jax", "jaxlib"}, (path.name, name)
            if name.startswith("validation") and not name.startswith("validation.excitable"):
                assert name == "validation.coupling" and names == ("piecewise_ode",), name


def test_references_load_no_cells_probe_or_division_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.excitable.{m}\n" for m in modules)
        + "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')\n"
        + "  or m.startswith(('validation.tissue', 'validation.division')))\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0, out.stdout + out.stderr


# ------------------------------------------------------------------------ laws


def test_bernoulli_series_identity_and_tails():
    x = np.array([-1e-5 * (1 + 1e-12), -1e-5 * (1 - 1e-12), 1e-5 * (1 - 1e-12),
                  1e-5 * (1 + 1e-12)])
    b = er.bernoulli(x)
    assert abs(b[0] - b[1]) < 1e-15 and abs(b[2] - b[3]) < 1e-15  # continuous at the switch
    assert er.bernoulli(np.array([0.0]))[0] == 1.0
    z = np.linspace(-30, 30, 121)
    assert np.allclose(er.bernoulli(-z), er.bernoulli(z) + z, rtol=1e-14, atol=1e-14)
    with np.errstate(all="raise"):  # no overflow, even far outside the gate laws' domain
        assert 0.0 <= er.bernoulli(np.array([800.0]))[0] < 1e-300
        assert er.bernoulli(np.array([-800.0]))[0] == pytest.approx(800.0)
        er.bernoulli(np.linspace(-700, 700, 11))


def test_nav12_against_the_appendix_rate_forms():
    def B(x):
        return x / math.expm1(x) if x != 0 else 1.0

    for V in (-0.110, -0.08, -0.065000123, -0.055, -0.040, -0.025, 0.0, 0.05):
        u = (V + 0.025) / 0.009
        am, bm = 0.182 * 9 * B(-u), 0.124 * 9 * B(u)
        ah = 0.024 * 5 * B(-(V + 0.040) / 0.005)
        bh = 0.0091 * 5 * B((V + 0.065000123) / 0.005)
        m_inf, tau_m, h_inf, tau_h = (float(np.asarray(x)[0]) for x in er.nav12(np.array([V])))
        assert m_inf == pytest.approx(am / (am + bm), rel=1e-13)
        assert tau_m == pytest.approx(0.001 / (am + bm), rel=1e-13)
        assert tau_h == pytest.approx(0.001 / (ah + bh), rel=1e-13)
        assert h_inf == pytest.approx(1 / (1 + math.exp((V + 0.055) / 0.0062)), rel=1e-13)
    # The appendix's note: h_inf is not alpha_h/(alpha_h + beta_h).
    V = -0.060
    ah, bh = 0.024 * 5 * B(-(V + 0.040) / 0.005), 0.0091 * 5 * B((V + 0.065000123) / 0.005)
    assert abs(float(er.nav12(np.array([V]))[2][0]) - ah / (ah + bh)) > 0.01


def test_gate_laws_are_bounded_with_positive_times_over_their_domain():
    V = np.linspace(*er.GATE_DOMAIN_V, 181)
    for law in (er.kv15, er.kir21, er.nav12):
        m_inf, tau_m, h_inf, tau_h = law(V)
        assert np.all((m_inf > 0) & (m_inf < 1) & (h_inf > 0) & (h_inf < 1))
        assert np.all(tau_m > 0) and np.all(tau_h > 0)


def test_pump_vanishes_at_its_equilibrium_and_runs_downhill():
    tissue = er.appendix_tissue("point2")
    c = er.appendix_constants()
    cin = np.array(er.H_MM)[:, None]
    cout = np.array(tissue.bath_mM)[:, None]
    pump = tissue.pump
    rt, F = c.rt, c.faraday_C_per_mol
    drive = pump.dG0_J_per_mol + rt * math.log(pump.ADP_mM * pump.Pi_mM / (pump.ATP_mM * 1000.0))
    # G = drive - 3 (RT ln r_Na + F V) + 2 (RT ln r_K + F V) = 0 at V_eq:
    V_eq = (drive - 3 * rt * math.log(cin[0, 0] / cout[0, 0])
            + 2 * rt * math.log(cin[1, 0] / cout[1, 0])) / F
    nu_eq = er.pump_rate(pump, c, tissue.area_m2, cin, cout, np.array([V_eq]))[0]
    nu_rest = er.pump_rate(pump, c, tissue.area_m2, cin, cout, np.array([V2]))[0]
    assert abs(nu_eq) < 1e-12 * abs(nu_rest) and nu_rest > 0.0


# ------------------------------------------------------------------------ the model


def random_states(model, rng, k=10):
    n = model.n
    for _ in range(k):
        y = model.y0.copy().reshape(n, er.PER_CELL)
        y[:, 0] *= rng.uniform(-1.4, 1.3, n)
        y[:, 1:3] *= rng.uniform(0.8, 1.2, (n, 2))
        y[:, 3:] = rng.uniform(0.01, 0.99, (n, 6))
        yield y.ravel(), rng.uniform(0.0, 1e-6, n)


@pytest.mark.parametrize("n", [1, 4])
def test_fast_rhs_equals_the_appendix_form(n):
    tissue = er.appendix_tissue("point2", n=n, s_c=300.0)
    model = er.Model(tissue, er.Start(V=V2, gates_at_V=V2))
    for y, p in random_states(model, np.random.default_rng(n)):
        a, b = model.rhs(y, p), model.rhs_reference(y, p)
        scale = np.maximum(np.abs(b), np.abs(b).reshape(n, -1).max(axis=0).repeat(n * 0 + 1)
                           .reshape(1, -1).repeat(n, 0).ravel() * 1e-3)
        assert np.max(np.abs(a - b) / scale) < 1e-10


def test_junctions_conserve_every_species_and_the_charge_follows():
    tissue = er.appendix_tissue("point2", n=5, s_c=1000.0, leak_m_s=(0.0, 0.0, 0.0, 0.0),
                                availability_NaV=0.0, availability_Kir=0.0, availability_Kv=0.0,
                                pump_on=False)
    model = er.Model(tissue, er.Start(V=np.linspace(-0.09, -0.03, 5), gates_at_V=V2))
    for y, p in random_states(model, np.random.default_rng(5), k=3):
        d = model.rhs(y, 0.0 * p).reshape(5, er.PER_CELL)
        assert abs(d[:, 1].sum()) <= 1e-12 * np.abs(d[:, 1]).max()  # Na
        assert abs(d[:, 2].sum()) <= 1e-12 * np.abs(d[:, 2]).max()  # K
        assert abs(d[:, 0].sum()) <= 1e-12 * np.abs(d[:, 0]).max()  # net charge


def test_the_heredity_rest_and_point_2s_relaxation():
    model = er.Model(er.appendix_tissue("heredity"), er.Start(V=er.V_H, gates_at_V=er.V_H))
    assert abs(model.dVdt(model.y0, np.zeros(1))[0]) < 1e-12  # V/s: H is a rest
    V = ep.rest_potential("point2", **FAST)
    assert abs(V - er.V_H) < 1e-5 and V != er.V_H


def test_the_kick_raises_sodium_and_keeps_the_gates():
    kick = 0.012
    model = er.Model(er.appendix_tissue("point2"), er.Start(V=V2, gates_at_V=V2, kick_V=kick))
    V, N, g = model.unpack(model.y0)
    assert V[0] == pytest.approx(V2 + kick, abs=1e-15)
    C, F = model.capacitance[0], model.F
    assert N[er.NA, 0] - er.H_MM[0] * 0.7505222518670602 == pytest.approx(
        C * kick / (F * er.FMOL), rel=1e-12)
    assert np.array_equal(g[0], er.gate_steady_state(V2))


def test_observables_against_brute_force():
    start = er.Start(V=V2, gates_at_V=V2, kick_V=0.04)
    tissue = er.appendix_tissue("point2")
    run = er.simulate(tissue, start, 0.03, **FAST)
    t_peak, v_peak = run.extremum(0, 0.0, 0.03)
    t_up, dvdt = run.extremum(0, 0.0, 0.03, quantity="dVdt")
    t_c = run.crossing(0, -0.03)
    assert v_peak > 0.0 and t_up < t_peak and t_c < t_up
    grid = np.linspace(t_peak - 1e-5, t_peak + 1e-5, 11)
    fine = er.simulate(tissue, start, 0.03, record=tuple(grid), **FAST)
    assert v_peak >= max(fine.at[t]["V"][0] for t in grid) - 1e-12
    assert abs(float(fine.V(t_c)[0]) + 0.03) < 1e-10
    grid = np.linspace(t_up - 2e-6, t_up + 2e-6, 11)
    fine = er.simulate(tissue, start, 0.03, record=tuple(grid), **FAST)
    best = max(fine.model.dVdt(fine.state(t), np.zeros(1))[0] for t in grid)
    assert dvdt >= best - 1e-6 * abs(best)
    m = ep.ap_measures(run, V2)
    assert m["APD50_s"] < m["APD90_s"] and m["overshoot"]


# ------------------------------------------------------------------------ limits


def test_neumann_modes_and_the_discrete_space_constant():
    g_m, g_j, n = 2e-11, 1e-9, 7
    mu, vec = el.neumann_modes(n, g_m, g_j)
    G = el.cable_matrix(n, g_m, g_j)
    assert np.allclose(G @ vec, vec * mu, rtol=0, atol=1e-21)
    assert np.allclose(vec.T @ vec, np.eye(n), atol=1e-12)
    lam, r = el.space_constant_cells(g_m, g_j)
    assert r + 1 / r == pytest.approx(2 + g_m / g_j, rel=1e-13) and lam == pytest.approx(
        -1 / math.log(r))


def test_the_passive_chain_is_the_linear_discrete_cable():
    n, times = 6, (0.0025, 0.004)
    tissue = er.appendix_tissue("point2", n=n, s_c=1000.0)
    out = {}
    for P in (0.0, 1e-9):
        coeffs = el.passive_linearisation(tissue, V2, p_stim=P)
        run = ep.chain(V2, n, 1000.0, P_stim=P, nav=0.0, kv=0.0, kir=0.0, t_end=0.004,
                       record=times, **FAST)
        lin = el.linear_cable_response(n, float(run.model.capacitance[0]), coeffs, V2,
                                       (0, 1, 2), ((0.002, 0.003),), times)
        out[P] = max(float(np.max(np.abs(run.at[t]["V"] - V2 - lin[t]))) for t in times), \
            max(float(np.max(np.abs(lin[t]))) for t in times)
    assert out[0.0][0] < 1e-9  # the drift from a rest that is not the passive one
    assert out[1e-9][0] < 1e-4 * out[1e-9][1]  # the response, to its frozen-composition limit


def test_the_strong_coupling_limit_is_the_lumped_cell():
    """During the stimulus, where the chain's spread of V is O(1/s_c): it falls tenfold per
    decade of s_c, towards one cell with the stimulus averaged over the chain (3 of 4 cells)."""
    n, times = 4, (0.0025, 0.003)
    diffs = {}
    for s_c in (1e4, 1e5):
        run = ep.chain(V2, n, s_c, t_end=0.003, record=times, **FAST)
        lumped = er.simulate(el.lumped_cell(run.model.t), er.Start(V=V2, gates_at_V=V2), 0.003,
                             record=times, **FAST)
        diffs[s_c] = max(float(np.max(np.abs(run.at[t]["V"] - lumped.at[t]["V"][0])))
                         for t in times)
    assert diffs[1e5] < 3e-4  # measured 1.8e-4 (and 1.5e-5 at 1e6)
    assert 0.05 < diffs[1e5] / diffs[1e4] < 0.2  # first order in 1/s_c (measured 0.10)


def test_a_chain_activates_in_order_and_its_cv():
    run = ep.chain(V2, 8, 1000.0, t_end=0.012, **FAST)
    times = ep.activation_times(run)
    assert all(t is not None for t in times)
    assert all(b > a for a, b in zip(times[2:], times[3:], strict=False))
    cv = ep.conduction_velocity(times, 8)
    assert cv is not None and cv > 0
    for i in (4, 7):
        lin = ep.sampled_activation(run, i, times[i], 1e-4)
        assert abs(lin - times[i]) < 1e-4
    assert (math.ceil(20 / 3), math.floor(40 / 3)) == (7, 13)
    ex = run.excursions()
    assert not ex["junction_over_limit"] and ex["V_max"] < er.GATE_DOMAIN_V[1]
