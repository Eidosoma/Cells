"""FR-45's shared site sets on the batch paths, compiled (D327, the lead's ruling 2 of 27 November 2026:
the batch and vector rows; invented values only, FR-45's first-run rule).

Seconds and reason (D224): about 63 s on one core, measured at landing. The batch paths' own compiled programs, run_batch's mapped scan
and run_vector_windowed's vectorized windows, on a set world, each bitwise against the scalar run. Split
from test_site_competition_runs.py, which with this row came within 9 s of the tier cap on one core.
run_batch_windowed on a set world is covered in the D148 round (results_baseline.run_paths on an
invented set world), since its own compile would add about 13 s here.
"""

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec, run_batch
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)


def test_a_two_world_batch_and_vector_windows_are_the_scalar_runs_bits():
    """The compiled file's world beside a second world of another chase, through run_batch and
    run_vector_windowed: the first is the scalar run's bits on every row, the second the same on
    both paths and its own (its books are the paths' host checks)."""
    spec = parse_spec(sfx.chase_world())
    result = run(spec)
    other = parse_spec(sfx.chase_world(chase_mM=2.6e-4))
    batch = BatchSpec((WorldSpec(1, spec), WorldSpec(2, other)), 2, 2**53 - 1, 2**53 - 1)
    batched = run_batch(batch)
    names = type(result.history)._fields
    for name in names:
        a = np.asarray(getattr(batched.worlds[1].history, name))
        assert a.tobytes() == np.asarray(getattr(result.history, name)).tobytes(), name
    bound = [np.asarray(batched.worlds[w].final.state.site_bound_increment_fmol) for w in (1, 2)]
    assert not np.array_equal(*bound)  # Two worlds, not one copied.
    vector = run_vector_windowed(batch, WindowPolicy(64, "checkpoints"))
    for w, reference in ((1, result.final), (2, batched.worlds[2].final)):
        final = vector.worlds[w].final
        assert final.step_index == reference.step_index
        for name, a, b in zip(names, final.state, reference.state, strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), (w, name)
