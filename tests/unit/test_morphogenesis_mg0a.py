"""MG0a driver: references, graphs and a tiny engine run (reaction_transport@1).

The references are checked against closed forms (discrete cosh profile, the
slowest eigenvalue); a small strip run through the windowed runner matches the
exact transient and conserves mass; a cut schedule survives windowing.
"""

import math

import jax
import numpy as np

from validation.morphogenesis import mg0a_gradient as mg

jax.config.update("jax_enable_x64", True)


def test_quasi_steady_reference_matches_closed_forms():
    graph = mg.strip(8)
    mu, phi, dirichlet = mg.quasi_steady(graph)
    s = 1 / np.sqrt(graph.volume)
    matrix = mg._matrix(graph).toarray()
    slowest = np.linalg.eigvalsh(s[:, None] * matrix * s[None, :])[-1]
    assert abs(-slowest / mu - 1) < 1e-9
    n, a = 8, mg.CELL_WIDTH_UM
    theta = math.acosh(1 + mg.KICHEVA_2007["k_per_s"] * a * a / mg.KICHEVA_2007["D_um2_s"] / 2)
    exact = [math.cosh((n + 0.5 - i) * theta) / math.cosh((n + 0.5) * theta) for i in range(1, 9)]
    np.testing.assert_allclose(dirichlet[1:], exact, rtol=1e-13)
    fit = mg.cosh_fit(dirichlet[1:], a)
    assert abs(fit["lambda_um"] * theta / a - 1) < 1e-12
    assert abs(mg.strip_exponent(graph) * theta / a - 1) < 1e-14
    assert 0 < phi[1:].min() and np.all(np.abs(phi[1:] / dirichlet[1:] - 1) < 1e-5)


def test_polygon_graph_is_consistent():
    graph = mg.polygon(rows=4, cols=6, seed=3)
    assert graph.n == 1 + 24
    assert np.all(graph.volume > 0) and np.all(graph.conductance > 0)
    assert len({tuple(e) for e in graph.edges}) == len(graph.edges)
    assert np.all(graph.edges[:, 0] < graph.edges[:, 1])
    assert graph.meta["source_cells"] == 4
    assert graph.rate[0] == 0 and np.all(graph.rate[1:] == mg.KICHEVA_2007["k_per_s"])


def test_tiny_strip_run_matches_exact_transient_and_conserves_mass():
    graph = mg.strip(6)
    raw = mg.definition(graph, end_time=800.0, dt=8.0, observation_times=[0.0, 400.0, 800.0])
    result, info = mg.run_segmented(raw, segment_steps=32)
    assert info["windows"] == 4
    exact = mg.Transient(graph).solve(result["times"])
    for i in (1, 2):
        ref = exact["A"][i][1:]
        assert np.max(np.abs(result["A"][i][1:] - ref)) / np.max(ref) < 1e-6
        np.testing.assert_allclose(result["B"][i][1:], exact["B"][i][1:], rtol=1e-6)
    checks = mg.ledger_checks(graph, result)
    assert checks["tissue_mass_balance_rel_max"] < 1e-12
    assert checks["cell_ledger_rel_max"] < 1e-12
    assert checks["min_amount_fmol"] >= 0


def test_cut_schedule_survives_windowing():
    graph = mg.strip(6)
    m = len(graph.edges)
    cut = np.ones(m)
    cut[3] = 0.0
    schedule = [(0.0, np.ones(m)), (200.0, cut), (480.0, np.ones(m))]
    raw = mg.definition(
        graph,
        end_time=800.0,
        dt=8.0,
        observation_times=[0.0, 200.0, 480.0, 800.0],
        schedule=schedule,
    )
    result, _ = mg.run_segmented(raw, segment_steps=16)
    exact = mg.Transient(graph, schedule).solve(result["times"])
    for i in (1, 2, 3):
        ref = exact["A"][i][1:]
        assert np.max(np.abs(result["A"][i][1:] - ref)) / np.max(ref) < 1e-6
    # During the cut no material crosses the closed contact.
    assert abs(result["transferred"][2][3] - result["transferred"][1][3]) < 1e-15


def test_evaluate_applies_comparisons():
    protocol = dict(
        criteria=[
            dict(id="a", metrics=["x.y"], comparison="le", threshold=1.0),
            dict(id="b", metrics=["x.z"], comparison="within", threshold=[0, 2]),
            dict(id="c", metrics=["x.w"], comparison="abs_le", threshold=0.1, judged=False),
        ]
    )
    verdict = mg.evaluate(protocol, dict(x=dict(y=0.5, z=[1, 3], w=-0.2)))
    assert [c["passed"] for c in verdict["criteria"]] == [True, False, False]
    assert verdict["passed"] is False
