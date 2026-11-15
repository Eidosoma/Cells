"""S1 to S3 across a restart (FR-1; design §3.3): the scalar program resumed from a checkpoint.

The criteria are test_cell_owned_compartments_silence.py's, fixed before any run, in the
live-owner world W+ (ARS(2,2,2) at 1 ms, every step observed), whose export rate changes at 5 ms.
A run, then a restart from the checkpoint at the change, in process and through a written
snapshot: each resumed history bitwise against the run, and silence on every resumed row. The
planted control (a), a K route on the bounding patch (the refusal bypassed by monkeypatch, the
same composition), resumed the same way, must break S1 and S2 on its resumed rows. Not tier 1.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import compartments as comp
from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END, DT, CHANGE = 0.012, 1e-3, 0.005


def world(**kwargs):
    return parse_spec(cfx.live_compartment(end=END, dt=DT, changes=[(CHANGE, 0.5)], **kwargs))


def test_a_restart_is_bitwise_and_silent_and_its_planted_control_is_not(tmp_path, monkeypatch):
    from cells.io import load_snapshot, write_snapshot

    spec = world()
    result = run(spec)
    checkpoint = result.checkpoint_at(CHANGE)
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    cfx.assert_silent_and_live(spec, resumed.observations)
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    cfx.assert_silent_and_live(loaded.spec, again.observations)
    monkeypatch.setattr(comp, "refuse_ion_routes", lambda *a: None)
    routed = world(planted_route=cfx.PLANTED_ROUTE)
    planted = run(routed)
    cfx.assert_broken(routed, run(routed, planted.checkpoint_at(CHANGE)).observations, route=True)
