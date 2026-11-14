"""species_regulated_availability@1, milestone 1: a junction's two sides multiply (A3, ruling 4).

docs/INVENTORY_COUPLING_DESIGN.md §1.3 and §4.4 A3. On the seven-cell heredity sheet, junction_0
scheduled at 1/2 under one coupling read on both of its cells (side "both": two routes, each a
frozen state of 1/2) gives @3 bit for bit what junction_0 scheduled at 1/8 gives. Two couplings
are in _bitwise_products.
"""

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

END = 0.03
JUNCTION = "junction_0"


def test_both_sides_multiply():
    world = rf.sheet(end=END)
    eighth = run(parse_spec(rf.schedule_junction(world, JUNCTION, 0.125)))
    both = run(
        parse_spec(
            rf.with_coupling(
                rf.schedule_junction(world, JUNCTION, 0.5),
                species=["R"],
                states=[rf.frozen("s", ["cell_0", "cell_3"], 0.5)],
                couplings=[rf.fraction("c", "junction", [JUNCTION], "s", side="both")],
            )
        )
    )
    fields, columns = rf.differing(both, eighth)
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)
