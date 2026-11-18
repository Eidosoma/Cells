"""B4 of FR-3's milestone 1: a vector-window batch against its scalar runs.

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
* restart from a checkpoint mid-run, in process and through a written snapshot: bitwise against the
  run (the binding multiplier changes at the checkpoint's time);
* a vector-window batch of three worlds with different k_on: each within 1e-12 of its scalar run's
  final state (relative to each field's scale), and bitwise against the reversed batch.
This file holds the scalar arm of the second; its reversed arm is
test_site_occupancy_vector_reverse.py (split from this file for the 90 s cap), and restart is
test_site_occupancy_restart.py. The mixed face-free world under ARS(2,2,2) at 1 ms. Two compiles:
not tier 1.
"""

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

END, DT, CHANGE = 0.01, 1e-3, 0.005
K_ON = (1e3, 2e3, 5e2)


def world(k_on=1e3):
    pops = [
        sfx.population("out", k_int=0.5, k_on=k_on),
        sfx.population("in", patch="wall_cell_0", face="inside", k_on=2e3, k_off=0.5),
    ]
    controls = {("out", "binding"): [(0.0, 1.0), (CHANGE, 0.5)]}
    return parse_spec(sfx.face_free_sites(pops, end=END, dt=DT, controls=controls))


def test_a_vector_batch_matches_its_scalar_runs():
    specs = [world(k_on) for k_on in K_ON]
    worlds = tuple(WorldSpec(i + 1, spec) for i, spec in enumerate(specs))
    batch = run_vector_windowed(
        BatchSpec(worlds, len(worlds), 10**6, 2**31), WindowPolicy(4, "checkpoints")
    )
    for k, spec in enumerate(specs):
        final = batch.worlds[k + 1].final.state
        single = run(spec).history
        for name in type(final)._fields:
            a, b = np.asarray(getattr(final, name)), np.asarray(getattr(single, name))[-1]
            scale = np.max(np.abs(b), initial=0.0)
            assert np.max(np.abs(a - b), initial=0.0) <= 1e-12 * scale + 1e-30, (k, name)
