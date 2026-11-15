"""S1 to S3 across a restart through a written snapshot (FR-1; design §3.3).

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, in the
live-owner world W+ (ARS(2,2,2) at 1 ms, every step observed), whose export rate changes at 5 ms.
A run, then its checkpoint at the change written as a snapshot, loaded and resumed: the resumed
history bitwise against the run, and silence on every resumed row. The restart in process, with
the planted control (a) on the scalar program's compile it reuses, is
test_cell_owned_compartments_restart.py (this file was split from it for the 90 s cap). Not
tier 1.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT, CHANGE = 0.012, 1e-3, 0.005


def world(**kwargs):
    return parse_spec(cfx.live_compartment(end=END, dt=DT, changes=[(CHANGE, 0.5)], **kwargs))


def test_a_restart_through_a_snapshot_is_bitwise_and_silent(tmp_path):
    from cells.io import load_snapshot, write_snapshot

    spec = world()
    result = run(spec)
    checkpoint = result.checkpoint_at(CHANGE)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    cfx.assert_silent_and_live(loaded.spec, again.observations)
