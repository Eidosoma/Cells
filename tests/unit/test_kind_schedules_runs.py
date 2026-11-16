"""Time-varying kind controls through the run paths (docs/INNER_MODEL_V4_DESIGN.md §7.4 (l)).

The scheduled exchange of tests/kind_fixtures.py (test_kind_schedules.py has the definition-level
tests), run once for the module:
- each step's control is the schedule's value at the step's start, held over the step, so the
  move is exact: rate x sum(availability x duration), on the scalar runner and the vector-window
  path, and an observation reads the value held from its time;
- branch_checkpoint refuses a branch that rewrites a kind's past schedule and admits one that
  changes its future;
- a restart across a breakpoint continues bitwise, in a fresh process as well;
- an empty composition of the scheduled world is its resolved_pump_tissue@3 run, bitwise.
"""

import subprocess
import sys

import numpy as np
import pytest

from cells.core import kind_registry
from cells.core import pump_composite_spec as cs
from cells.core import surface_pump_v3_spec as ionic
from cells.core.runner import branch_checkpoint, run
from cells.core.specs import ConfigError, parse_spec
from cells.io import write_snapshot
from cells.models.registry import get_model
from tests.unit.test_kind_schedules import GRID, MOVED, POINTS, RATE, scheduled, world
from validation.tissue import composite_guard as guard


@pytest.fixture(scope="module")
def whole():
    """(registry, spec, result): the scheduled world run once, every row checked on the host. Its
    types are those of its registry (cached by registry), so the tests build under that one."""
    registry = scheduled()
    with kind_registry.scope(registry):
        spec = parse_spec(world())
        return registry, spec, run(spec)


def test_a_scheduled_mover_moves_exactly_its_held_rate(whole):
    _, spec, result = whole
    assert tuple(result.times) == GRID
    moved = float(result.final.state.exchange_moved_fmol[0])
    assert moved == pytest.approx(MOVED, rel=1e-12)
    row = list(spec.model.species_ids).index("B")
    assert float(result.final.state.amount_increment[row, 0]) == pytest.approx(-moved, rel=1e-12)
    # The readout at an observation time is the rate held from that time (right-continuous).
    assert list(result.observations.exchange_rate_column[:, 0]) == [RATE * 1.0, RATE * 0.5]


def test_a_branch_keeps_a_kinds_past_schedule_and_may_change_its_future(whole):
    registry, spec, result = whole
    checkpoint = result.checkpoint_at(0.002)
    with kind_registry.scope(registry):
        past = parse_spec(world(((0.0, 0.5), (0.002, 0.25), (0.0025, 0.0), (0.003, 0.5))))
        with pytest.raises(ConfigError, match="cannot rewrite the input schedule"):
            branch_checkpoint(spec, checkpoint, past)
        future = parse_spec(world(((0.0, 1.0), (0.002, 0.25), (0.0025, 0.0), (0.003, 0.75))))
        later = run(future, branch_checkpoint(spec, checkpoint, future))
    moved = float(later.final.state.exchange_moved_fmol[0])
    assert moved == pytest.approx(MOVED + RATE * 0.25 * 0.001, rel=1e-12)


def test_a_restart_across_a_breakpoint_continues_bitwise(whole, tmp_path):
    registry, spec, result = whole
    checkpoint = result.checkpoint_at(0.002)
    with kind_registry.scope(registry):
        resumed = run(spec, checkpoint)
        path = write_snapshot(tmp_path / "snapshot", spec, checkpoint)
    for name, a, b in zip(
        result.final.state._fields, result.final.state, resumed.final.state, strict=True
    ):
        assert np.array_equal(np.asarray(a), np.asarray(b)), name
    script = (
        "import sys\n"
        "from cells.core import kind_registry\n"
        "from cells.core.runner import run\n"
        "from cells.io import load_snapshot\n"
        "from tests import kind_fixtures as kf\n"
        "with kind_registry.scope(kf.registry(exchange=kf.SCHEDULED_EXCHANGE)):\n"
        "    snapshot = load_snapshot(sys.argv[1])\n"
        "    result = run(snapshot.spec, snapshot.checkpoint)\n"
        "print(repr(float(result.final.state.exchange_moved_fmol[0])))\n"
        "print(*(repr(float(t)) for t in result.times))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script, str(path)], capture_output=True, text=True, check=True
    )
    value, times = done.stdout.splitlines()
    assert float(value) == float(result.final.state.exchange_moved_fmol[0])
    assert tuple(float(t) for t in times.split()) == GRID[2:]


def test_an_empty_composition_holds_the_same_controls_bitwise(whole):
    registry, _, reference = whole
    with kind_registry.scope(registry):
        spec = parse_spec(cs.frozen_definition(world()))
        assert [c.time for c in spec.experiment.changes] == [t for t, _ in POINTS]
        assert all(type(c.inner) is ionic.KindChange for c in spec.experiment.changes)
        result = run(spec)
    assert guard.assert_same(reference, result)["bitwise"]
    assert tuple(result.times) == GRID


def test_the_vector_window_path_holds_the_same_controls(whole):
    from cells.core import vector_windows
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.windows import WindowPolicy

    registry, spec, result = whole
    big = 2**53 - 1
    with kind_registry.scope(registry):
        specs = [spec, parse_spec(world(((0.0, 0.5), (0.0025, 1.0))))]
        batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, big, big)
        window = next(
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(8, "checkpoints")))
        )
        names = get_model(specs[0].model).STATE_TYPE._fields
    expected = (MOVED, RATE * (0.5 * 0.0025 + 1.0 * 0.0015))
    for world_id, moved in enumerate(expected, start=1):
        final = window.checkpoints[world_id].state
        value = float(np.ravel(final[names.index("exchange_moved_fmol")])[0])
        assert value == pytest.approx(moved, rel=1e-12)
    alone = float(result.final.state.exchange_moved_fmol[0])
    first = float(np.ravel(window.checkpoints[1].state[names.index("exchange_moved_fmol")])[0])
    assert first == pytest.approx(alone, rel=1e-12)
