"""Time-varying kind controls on the composite and vector-window paths (§7.4 (l) of
docs/INNER_MODEL_V4_DESIGN.md); split from test_kind_schedules_runs.py, whose run of the scheduled
world it repeats once for this module, to keep each file under the tier cap (16 November 2026):
- an empty composition of the scheduled world is its cells.model.resolved_pump_tissue@3 run, bitwise, with the
  kind's change records as its breakpoints;
- on the vector-window path each world's move is exact at its own schedule, and the first world's
  equals its scalar run.
"""

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions import surface_pump_v3_spec as ionic
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry import kind_registry
from cells.registry.models import get_model
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
    from cells.execution import vector_windows
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.windows import WindowPolicy

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
