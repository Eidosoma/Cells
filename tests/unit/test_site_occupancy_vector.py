"""B4 of FR-3's milestone 1: a vector-window batch (restart is test_site_occupancy_restart.py).

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
* restart from a checkpoint mid-run, in process and through a written snapshot: bitwise against the
  run (the binding multiplier changes at the checkpoint's time);
* a vector-window batch of three worlds with different k_on: each within 1e-12 of its scalar run's
  final state (relative to each field's scale), and bitwise against the reversed batch.
The mixed face-free world under ARS(2,2,2) at 1 ms. A few compiles: not tier 1.
"""

import jax
import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
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


def test_a_vector_batch_matches_scalar_runs_and_its_reverse():
    specs = [world(k_on) for k_on in (1e3, 2e3, 5e2)]

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(
            BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
        )

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    for k, spec in enumerate(specs):
        final = forward.worlds[k + 1].final.state
        reverse = backward.worlds[3 - k].final.state
        for name in type(final)._fields:
            assert (
                np.asarray(getattr(final, name)).tobytes()
                == np.asarray(getattr(reverse, name)).tobytes()
            ), (k, name)
        single = run(spec).history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (k, name)
