"""Field solver version 3 on resolved_pump_tissue@3, the W1 hold's model: runs (guard 6).

tests/unit/test_field_floor.py covers version 3 (capacitive_reduction_gauged_damped_newton@3)
on the @1 and @2 fixtures; this file and test_field_floor_held.py cover @3
(docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md). On the @3 fixtures (three cells, five outside nodes,
one or two free field offsets) version 3 runs bitwise as version 2 wherever version 2
converges, and its checkpoints round-trip and resume bitwise.
"""

import copy

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import surface_pump_v3 as model
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_v3_fixtures as fixtures


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(arm, solver):
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["execution"]["field_solver"] = solver
    return raw


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_version_3_is_bitwise_version_2_where_version_2_converges(arm):
    two = run(parse_spec(definition(arm, field.FACTORED_SOLVER_ID)))
    three = run(parse_spec(definition(arm, field.FLOOR_SOLVER_ID)))
    assert type(three.final.layout) is model.FLOOR_LAYOUT_TYPE
    assert np.any(three.final.layout.field_offset_free)  # The Newton has unknowns.
    np.testing.assert_array_equal(two.times, three.times)
    for name, a, b in zip(two.history._fields, two.history, three.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b), err_msg=name)
    assert two.diagnostics == three.diagnostics


def test_version_3_checkpoint_round_trips_and_resumes_bitwise(tmp_path):
    """A version 3 snapshot of @3 loads with its own layout type and resumes as run."""
    from cells.core.runner import branch_checkpoint
    from cells.io import load_snapshot, write_snapshot

    raw = definition("release", field.FLOOR_SOLVER_ID)
    whole = run(parse_spec(raw))
    half = copy.deepcopy(raw)
    half["experiment"].update(end_time=0.001, observation_times=[0.0, 0.001])
    for key, groups in half["experiment"].items():
        if key.endswith("_controls"):
            for group in groups:
                group["schedule"] = [c for c in group["schedule"] if c["time"] <= 0.001]
    first = run(parse_spec(half))
    saved = load_snapshot(write_snapshot(tmp_path / "half", parse_spec(half), first.final))
    assert type(saved.checkpoint.layout) is model.FLOOR_LAYOUT_TYPE
    spec = parse_spec(raw)
    resumed = run(spec, branch_checkpoint(saved.spec, saved.checkpoint, spec))
    for a, b in zip(resumed.final.state, whole.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
