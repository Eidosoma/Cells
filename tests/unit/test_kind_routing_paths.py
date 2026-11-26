"""The routing door on the consumer's run paths (docs/INNER_MODEL_V4_DESIGN.md §7.4 (n)).

FR-5's judged world runs through the composite (FR-1's compartment operator), and its start runs on
the vector-window path. With test_kind_routing.py's closed pair, its route factored by a planted
source (factor 0.3):
- an empty composition of the factored world is its cells.model.resolved_pump_tissue@3 run, bitwise;
- the vector-window path gives the scalar run's transfer and heat, with every device check passed.
"""

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests.unit.test_kind_routing import pair, with_routes
from validation.tissue import composite_guard as guard


@pytest.fixture(scope="module")
def scalar():
    """(registry, raw, result): the factored pair run once on the scalar runner."""
    registry = with_routes()
    raw = pair(("f_c",), end=0.005)
    with kind_registry.scope(registry):
        return registry, raw, run(parse_spec(raw))


def test_an_empty_composition_of_a_factored_world_is_its_run_bitwise(scalar):
    registry, raw, reference = scalar
    with kind_registry.scope(registry):
        spec = parse_spec(cs.frozen_definition(raw))
        assert get_model(spec.model).inner.structure.routes  # The door is on the inner model.
        result = run(spec)
    assert guard.assert_same(reference, result)["bitwise"]


def test_the_vector_window_path_gives_the_scalar_runs_transfer_and_heat(scalar):
    from cells.execution import vector_windows
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.windows import WindowPolicy

    registry, raw, reference = scalar
    big = 2**53 - 1
    with kind_registry.scope(registry):
        spec = parse_spec(raw)
        batch = BatchSpec((WorldSpec(1, spec),), 1, big, big)
        window = next(  # Every row passed the device checks, the door's factor check included.
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(8, "checkpoints")))
        )
        names = get_model(spec.model).STATE_TYPE._fields
    final = window.checkpoints[1].state
    for name in ("passive_transferred", "passive_dissipated_energy_pJ"):
        got = np.asarray(final[names.index(name)])
        want = np.asarray(getattr(reference.final.state, name))
        np.testing.assert_allclose(got, want, rtol=1e-12, atol=0)
