"""junction_tension_inference@1 on synthetic periodic tissues with known tensions.

A heterogeneous honeycomb relaxed to force balance gives back its total junction
tensions T_j = Lambda_j + Gamma (L_a + L_b), with pressures known or jointly (two
gauges: scale and pressure offset); the regular honeycomb is degenerate (uniform
tension is a self-stress and every cell has a pressure-tension mode); the
Bayesian MAP is the closed-form ridge solution at the ABIC-chosen prior.
"""

import jax
import numpy as np

from cells.analysis import junction_tension_inference as jti
from cells.analysis import mechanical_equilibrium as me
from cells.core.specs import parse_spec
from tests.apical_vertex_fixtures import honeycomb

jax.config.update("jax_enable_x64", True)


def relaxed(sigma, seed=0):
    d = honeycomb()
    rng = np.random.Generator(np.random.PCG64(seed))
    for j in d["model"]["junctions"]:
        j["line_tension"] = 0.12 * (1 + sigma * rng.standard_normal())
    pb = me.problem(parse_spec(d))
    eq = me.minimize(pb, pb.position + 1e-3 * rng.standard_normal(pb.position.shape))
    mech = jax.tree.map(np.asarray, pb.mechanics)
    truth = jti.true_tensions(eq.position, pb.host_topology, eq.box, mech)
    return pb, eq, truth, rng


def test_tensions_recovered_with_known_and_unknown_pressures():
    pb, eq, (tension, pressure), _ = relaxed(0.2)
    b = jti.balance(eq.position, pb.host_topology, eq.box)
    assert np.max(np.abs(b.tension_matrix @ tension + b.pressure_matrix @ pressure)) < 1e-13
    known = jti.known_pressure(b, pressure)
    assert np.max(np.abs(known.tension - tension)) <= 1e-11 * np.mean(tension)
    joint = jti.joint(b, mean_tension=np.mean(tension), mean_pressure=np.mean(pressure))
    assert joint.null_dimension == 2
    assert np.max(np.abs(joint.tension - tension)) <= 1e-10 * np.mean(tension)
    assert np.max(np.abs(joint.pressure - pressure)) <= 1e-10 * np.max(np.abs(pressure))


def test_regular_honeycomb_is_degenerate():
    pb = me.problem(parse_spec(honeycomb()))
    b = jti.balance(pb.position, pb.host_topology, pb.box)
    assert jti.known_pressure(b, np.zeros(16)).null_dimension >= 1
    assert jti.joint(b).null_dimension >= 16


def test_bayesian_map_is_the_ridge_solution_at_the_abic_minimum():
    pb, eq, (tension, _), rng = relaxed(0.2, seed=1)
    noisy = eq.position + 1e-3 * rng.standard_normal(eq.position.shape)
    b = jti.balance(noisy, pb.host_topology, eq.box)
    result = jti.bayesian(b)
    assert np.all(np.isfinite(result.abic))
    i = int(np.argmin(result.abic))
    assert 0 < i < len(result.hyperparameter_grid) - 1  # an interior ABIC minimum
    u, s, _ = np.linalg.svd(b.pressure_matrix)
    a = u[:, int(np.sum(s > 1e-12 * s[0])) :].T @ b.tension_matrix
    mu = result.hyperparameter
    ridge = mu * np.linalg.solve(a.T @ a + mu * np.eye(a.shape[1]), np.ones(a.shape[1]))
    np.testing.assert_allclose(result.tension, ridge, rtol=1e-12)
    assert np.corrcoef(result.tension, tension)[0, 1] > 0.5
