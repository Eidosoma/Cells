"""S1 to S3 in the windowed, vector-window and batch programs (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, and checked on
every row each program exposes, every step observed:
- windowed (core/windows.run_windowed, observations policy): every window's observations;
- vector-window (core/vector_windows.run_vector_windowed): every round's observations of every
  world, for three worlds of W with different export rates;
- batch (core/batch.run_batch): every world's observations, for the same three worlds.
A few compiles: not tier 1.
"""

import jax
import numpy as np

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy, run_windowed
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.008, 1e-3
ROWS = int(round(END / DT)) + 1
RATES = (0.2, 0.5, 0.05)


def silent(spec, observations):
    found = cfx.silence(spec, observations)
    assert found["s1"], "S1: an ion row of the compartment changed"
    assert found["s2"] <= 1.0 and found["s3"] <= 1.0, found
    return found["rows"]


def specs():
    return [parse_spec(cfx.loaded_compartment(end=END, dt=DT, export=r)) for r in RATES]


def batch():
    return BatchSpec(
        tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs())), len(RATES), 10**6, 2**31
    )


def test_the_windowed_program_is_silent():
    spec = specs()[0]
    seen = []
    run_windowed(spec, WindowPolicy(3, "observations"), sink=seen.append)
    assert len(seen) > 1
    assert sum(silent(spec, window.observations) for window in seen) == ROWS


def test_the_vector_window_program_is_silent():
    seen = []
    spec = batch()
    run_vector_windowed(spec, WindowPolicy(3, "checkpoints"), sink=seen.append)
    rows = {w.world_id: 0 for w in spec.worlds}
    for window in seen:
        for identity, observations in window.observations.items():
            rows[identity] += silent(spec.worlds[identity - 1].simulation, observations)
    assert rows == {w.world_id: ROWS for w in spec.worlds}


def test_the_batch_program_is_silent():
    spec = batch()
    result = run_batch(spec)
    for world in spec.worlds:
        observations = result.worlds[world.world_id].observations
        assert silent(world.simulation, observations) == ROWS
    finals = [
        np.asarray(result.worlds[w.world_id].final.state.exchange_moved_fmol) for w in spec.worlds
    ]
    assert len({f.tobytes() for f in finals}) == len(RATES)  # Each world its own rate.
