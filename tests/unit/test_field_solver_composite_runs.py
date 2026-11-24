"""D147 for composite definitions (D156), the runs: the minimal free-offset composite of
tests/field_solver_fixtures.py stepped under field solver versions 2 and 3.

1. Version 3, the auto choice, is admitted at run time: the run binds the floor layout and is
   bitwise version 2's, version 2 converging there (version 3 iterates as version 2 does), with
   the same diagnostics.
2. A checkpoint from the middle of a run (each run's end, 4 ms of a 6 ms branch) does not resume
   across the solver change, either way, directly or through a saved snapshot, while the same
   branch without the change is admitted.
The sparse field solver (FR-17 stage 1) joins both as a row: the engine admits it on this world,
which field_solver_choice refuses it for (a free offset, D147), and it runs bitwise as version 2
(the capacitor reduction is diagonal and the IMEX operator's 2 x 2 block is eliminated in the
dense order). It is a composite without kinds, so its steps read the adapter's module-level
layout selection.
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID
from tests.field_solver_fixtures import minimal, refused_across_the_change, with_solver
from validation.tissue import field_solver_choice as choice


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def runs():
    built = minimal()
    auto = choice.declare(built)
    assert auto == with_solver(built, FLOOR_SOLVER_ID)
    sparse = with_solver(built, SPARSE_SOLVER_ID)
    return {
        FACTORED_SOLVER_ID: (built, run(parse_spec(built))),
        FLOOR_SOLVER_ID: (auto, run(parse_spec(auto))),
        SPARSE_SOLVER_ID: (sparse, run(parse_spec(sparse))),
    }


@pytest.mark.parametrize(
    ("candidate", "layout"), [(FLOOR_SOLVER_ID, "FloorLayout"), (SPARSE_SOLVER_ID, "SparseLayout")]
)
def test_version_3_runs_the_free_offset_composite_bitwise_as_version_2(runs, candidate, layout):
    (_, two), (_, three) = runs[FACTORED_SOLVER_ID], runs[candidate]
    assert type(three.final.layout).__name__.endswith(layout)
    assert not type(two.final.layout).__name__.endswith(layout)
    np.testing.assert_array_equal(two.times, three.times)
    for name, a, b in zip(two.history._fields, two.history, three.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b), err_msg=name)
    assert two.diagnostics == three.diagnostics


@pytest.mark.parametrize("version", [FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID])
def test_a_mid_run_checkpoint_does_not_resume_across_a_solver_change(runs, version, tmp_path):
    raw, result = runs[version]
    assert result.final.step_index > 0
    refused_across_the_change(raw, result.final, tmp_path / "run")
