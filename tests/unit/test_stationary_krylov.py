"""stationary_continuation_analysis@1 matrix-free paths on the default-world cell (@1).

Newton-Krylov (GMRES on JAX JVPs of the law's derivative) reaches the same
stationary state as dense Newton, and Arnoldi on the JVP of the engine's step
map gives the same leading growth rate as the dense spectrum, through
log(mu)/T.
"""

import jax
import numpy as np
import pytest

from cells.analysis import stationary as sa
from cells.core.specs import parse_spec
from validation.stationary import worlds


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def cell():
    pb = sa.problem(parse_spec(worlds.default_world_cell()), mode="slow")
    return pb, sa.newton(pb, pb.anchor)


def test_gmres_newton_matches_dense(cell):
    pb, dense = cell
    krylov = sa.newton(pb, pb.anchor, linear_solver="gmres")
    assert krylov.converged
    assert np.max(np.abs(krylov.u - dense.u)) <= 10 * (dense.error_estimate + 1e-12)


def test_arnoldi_step_map_matches_dense_spectrum(cell):
    pb, dense = cell
    reference = sa.stability(pb, dense.u)
    arnoldi = sa.stability(pb, dense.u, method="arnoldi", count=1, steps=1000)
    assert arnoldi["operator"]["kind"] == "arnoldi_step_map_jvp"
    lead, rate = reference["eigenvalues_per_s"][0][0], arnoldi["eigenvalues_per_s"][0][0]
    # T = 1 s: the slowest mode's multiplier is exp(-6e-5); log(mu)/T recovers it.
    assert rate == pytest.approx(lead, rel=1e-6)
    assert arnoldi["classification"] == "stable"
