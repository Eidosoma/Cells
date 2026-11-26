"""T7 of cells.operator.scheduled_membrane_trafficking@1 (FR-2 version 1), restart: resumed before, at and after
a schedule change, and through a written snapshot, the cycle world's run is bitwise the original's
in every history field (the fixtures' cycle: 5 ms, observed every step, the change at 2 ms).

Every resume here leaves two steps or more. A resume that leaves one step compiles a scan of one
step, which XLA's while-loop simplifier replaces by its body: shown on a 4 ms cycle world, whose
3 ms resume differed in the carriers' work (up to 109 ulp) at one version of this operator and was
bitwise with that pass disabled, and at the next version, whose valid steps compute the same
arithmetic (FR-2's probes restart_one_step, reported to the lead). That the inlined body rounds
differently through its fusion and fused multiply-adds is inferred, not shown.

"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from validation.tissue import membrane_trafficking_fixtures as fx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def cycle_run():
    spec = parse_spec(fx.cycle())
    return spec, run(spec)


def test_restart_across_the_schedule_change_is_bitwise(cycle_run, tmp_path):
    spec, value = cycle_run
    names = type(value.history)._fields
    for time in (0.001, fx.CYCLE_CHANGE, 0.003):  # Before, at and after the change (2+ steps left).
        checkpoint = value.checkpoint_at(time)
        resumed = run(spec, checkpoint)
        rows = zip(names, resumed.history, value.history, strict=True)
        for name, a, b in rows:  # Each field named, so a difference says where it is.
            assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), (
                time,
                name,
            )
    checkpoint = value.checkpoint_at(0.003)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for name, a, b in zip(names, resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :]), name
