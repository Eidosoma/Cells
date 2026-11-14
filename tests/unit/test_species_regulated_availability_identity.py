"""species_regulated_availability@1: switched off, or declared idle, it is the world without it.

docs/INVENTORY_COUPLING_DESIGN.md §1.10, D136's claim 2. Three compiled programs on the seven-cell
heredity sheet (20 steps at 1 ms), so this file is deliberately tier 3 (the lead's ruling, 14
November 2026); the tier-1 smoke keeps the declaration-only idleness check.
* Switched off: the shared coupled structure (regulated_availability_fixtures.shared_structure)
  with every coupling off gives @3's step and @3's observations bit for bit what the world without
  the operator gives, at each pair of availabilities _bitwise schedules (junction_0 and kir_3: 1
  and 1, 1/2 and 1/2, 0 and 0, 1/8 and 1/2). With _bitwise, every factored arm there equals the
  world without the operator over the same availabilities scheduled.
* Declared idle: the operator with no state and no coupling (statically idle) gives the same.
Every @3 state field of every accepted row and every @3 observation column is compared.
"""

import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

SCHEDULES = [(1.0, 1.0), (0.5, 0.5), (0.0, 0.0), (0.125, 0.5)]
END = 0.02


def assert_same(a, b):
    fields, columns = rf.differing(a, b)
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)


@pytest.mark.parametrize("junction, channel", SCHEDULES)
def test_every_coupling_switched_off_is_the_world_without_the_operator(junction, channel):
    off = run(parse_spec(rf.shared_structure(junction=junction, channel=channel, end=END)))
    assert np.all(np.asarray(off.observations.coupling_factor) == 1.0)
    assert_same(off, run(parse_spec(rf.scheduled(junction=junction, channel=channel, end=END))))


def test_a_declared_idle_operator_changes_nothing():
    idle = run(parse_spec(rf.with_coupling(rf.sheet(end=END))))
    assert_same(idle, run(parse_spec(rf.scheduled(end=END))))
