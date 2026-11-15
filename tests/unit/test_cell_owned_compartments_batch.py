"""S1 to S3 in the batch program (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, checked on every
row of core/batch.run_batch (every step observed): every world's observations. The batch is three
live-owner worlds W+ with different export rates and, as a fourth world, the planted control (a), a
K route on the bounding patch (the refusal bypassed by monkeypatch, the same composition and
program), which must break S1 and S2. One program's compile: not tier 1.
"""

import jax
import numpy as np

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.specs import parse_spec
from cells.models.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.008, 1e-3
ROWS = int(round(END / DT)) + 1
RATES = (0.2, 0.5, 0.05)


def test_the_batch_program_is_silent_and_its_planted_control_is_not(monkeypatch):
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    specs = [parse_spec(cfx.live_compartment(end=END, dt=DT, export=r)) for r in RATES]
    specs.append(parse_spec(cfx.live_compartment(end=END, dt=DT, planted_route=cfx.PLANTED_ROUTE)))
    batch = BatchSpec(
        tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), len(specs), 10**6, 2**31
    )
    result = run_batch(batch)
    for i, spec in enumerate(specs[: len(RATES)]):
        observations = result.worlds[i + 1].observations
        assert cfx.assert_silent_and_live(spec, observations) == ROWS
    cfx.assert_broken(specs[-1], result.worlds[len(specs)].observations, route=True)
    finals = [
        np.asarray(result.worlds[i + 1].final.state.exchange_moved_fmol) for i in range(len(RATES))
    ]
    assert len({f.tobytes() for f in finals}) == len(RATES)  # Each world its own rate.
