"""B4 of FR-3's milestone 1: restart (the vector-window batch is test_site_occupancy_vector.py).

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
* restart from a checkpoint mid-run, in process and through a written snapshot: bitwise against the
  run (the binding multiplier changes at the checkpoint's time);
* a vector-window batch of three worlds with different k_on: each within 1e-12 of its scalar run's
  final state (relative to each field's scale), and bitwise against the reversed batch.
The mixed face-free world under ARS(2,2,2) at 1 ms. A few compiles: not tier 1.
"""

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

END, DT, CHANGE = 0.01, 1e-3, 0.005


def world(k_on=1e3):
    pops = [
        sfx.population("out", k_int=0.5, k_on=k_on),
        sfx.population("in", patch="wall_cell_0", face="inside", k_on=2e3, k_off=0.5),
    ]
    controls = {("out", "binding"): [(0.0, 1.0), (CHANGE, 0.5)]}
    return parse_spec(sfx.face_free_sites(pops, end=END, dt=DT, controls=controls))


def test_restart_in_process_and_through_a_snapshot_is_bitwise(tmp_path):
    from cells.io import load_snapshot, write_snapshot

    spec = world()
    result = run(spec)
    checkpoint = result.checkpoint_at(CHANGE)
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
