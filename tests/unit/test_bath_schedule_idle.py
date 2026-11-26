"""B5, idleness of cells.operator.scheduled_bath_composition@1 (FR-10; docs/BATH_SCHEDULE_DESIGN.md §4).

The operator declared with no event runs every inner field bitwise equal to the same composition
without it: the species-only dose leg (validation/tissue/bath_schedule_fixtures) under ARS(2,2,2) at
1 ms, 30 steps, every step observed. Before a bath's first event its control is its declared
content itself, so the event map selects the start state and the view is the declared array bit for
bit. Two compiles: not tier 1.
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx


def test_b5_an_operator_with_no_event_runs_bitwise_as_the_composition_without_it():
    end = 0.03
    plain = bfx.dosed_world(dt=1e-3, end=end, observation_times=fx.grid_times(end, 1e-3, 1e-3))
    idle = bfx.with_bath_schedule(plain, ["bath"], bfx.CARGO, [])
    a, b = run(parse_spec(plain)), run(parse_spec(idle))
    inner = get_model(a.spec.model).STATE_TYPE._fields
    for name in inner:
        assert (
            np.asarray(getattr(a.history, name)).tobytes()
            == np.asarray(getattr(b.history, name)).tobytes()
        ), name
