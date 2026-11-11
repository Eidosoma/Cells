"""apical_vertex_mechanics@1: padded capacities follow the same trajectory.

The same world in larger vertex, junction, cell and half-edge capacities runs to
the same positions and energies (to rounding: reductions may reorder), and its
padding stays exactly zero.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from tests.apical_vertex_fixtures import honeycomb

jax.config.update("jax_enable_x64", True)


def test_padded_capacities_follow_the_same_trajectory():
    base = honeycomb(displacement=0.05, seed=7, end_time=2.0, observation_times=[0.0, 2.0])
    padded = honeycomb(
        displacement=0.05, seed=7, end_time=2.0, observation_times=[0.0, 2.0], padding=3
    )
    plain, wide = run(parse_spec(base)), run(parse_spec(padded))
    v = len(base["model"]["vertices"])
    np.testing.assert_allclose(
        np.asarray(wide.final.state.position)[:v],
        np.asarray(plain.final.state.position),
        rtol=0,
        atol=1e-14,
    )
    assert np.all(np.asarray(wide.final.state.position)[v:] == 0)
    np.testing.assert_allclose(wide.observations.energy, plain.observations.energy, rtol=1e-14)
