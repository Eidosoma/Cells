"""S1 to S3 in the batch program (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row the program exposes, every step observed: core/batch.run_batch for the same three worlds, every
world's observations. The scalar program is test_cell_owned_compartments_silence.py and RK4
test_cell_owned_compartments_silence_rk4.py. One program's compile per file: not tier 1.
"""

import jax
import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
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


def test_the_batch_program_is_silent():
    from cells.core.batch import run_batch

    spec = batch()
    result = run_batch(spec)
    for world in spec.worlds:
        assert silent(world.simulation, result.worlds[world.world_id].observations) == ROWS
    finals = [
        np.asarray(result.worlds[w.world_id].final.state.exchange_moved_fmol) for w in spec.worlds
    ]
    assert len({f.tobytes() for f in finals}) == len(RATES)  # Each world its own rate.
