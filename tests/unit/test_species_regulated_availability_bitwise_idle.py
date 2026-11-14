"""species_regulated_availability@1, milestone 1: a declared but idle operator changes nothing (D136).

docs/INVENTORY_COUPLING_DESIGN.md §1.10, claim 2. On the seven-cell heredity sheet, the operator
declared with no state and no coupling (statically idle) gives every @3 state field of every
accepted row and every @3 observation column bit for bit what the world without it gives. The
switched-off coupling is in _bitwise.
"""

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

END = 0.03


def test_an_idle_operator_changes_nothing():
    world = rf.sheet(end=END)
    fields, columns = rf.differing(run(parse_spec(rf.with_coupling(world))), run(parse_spec(world)))
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)
