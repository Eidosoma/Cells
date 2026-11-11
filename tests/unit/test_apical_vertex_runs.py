"""apical_vertex_mechanics@1 runs: relaxation to the ground state and refusals.

Relaxation reaches the case-I ground state with both solvers, with every ledger
inside its bound; an oversized step is refused before the run and an edge that
falls below the length floor is refused during it. Events (ablation, restart,
vmap) are in test_apical_vertex_events.py.
"""

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from tests.apical_vertex_fixtures import (
    A_STAR,
    E_STAR,
    honeycomb,
)

jax.config.update("jax_enable_x64", True)


@pytest.mark.parametrize("solver", ["rk4", "euler"])
def test_relaxation_reaches_case_one_ground_state(solver):
    dt = 0.125 if solver == "rk4" else 0.0625
    definition = honeycomb(
        displacement=0.05,
        seed=1,
        end_time=240.0,
        observation_times=[0.0, 240.0],
        dt=dt,
        solver=solver,
    )
    result = run(parse_spec(definition))
    obs = result.observations
    assert abs(obs.energy[-1] / 16 - E_STAR) <= 1e-10
    np.testing.assert_allclose(obs.cell_area[-1][:16], A_STAR, atol=1e-8)
    assert obs.max_force[-1] < 1e-9
    d = result.diagnostics
    assert d["max_energy_balance_allowance_used"] < 1.0
    assert d["max_momentum_drift"] < 1e-11 and d["max_area_identity_error"] < 1e-12
    assert np.all(np.diff(obs.energy) <= 0)


def test_step_bound_and_edge_collapse_are_refused():
    with pytest.raises(ConfigError, match="bound"):
        run(parse_spec(honeycomb(dt=0.5, end_time=1.0, observation_times=[0.0, 1.0])))
    definition = honeycomb(end_time=20.0, observation_times=[0.0, 20.0], dt=0.015625)
    definition["model"]["length_floor"] = 0.3
    definition["model"]["junctions"][0]["line_tension"] = 3.0
    with pytest.raises(NumericalError, match="domain|refused|invalid"):
        run(parse_spec(definition))
