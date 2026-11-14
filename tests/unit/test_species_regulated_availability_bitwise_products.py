"""species_regulated_availability@1, milestone 1: two couplings multiply (A3's multiple case).

docs/INVENTORY_COUPLING_DESIGN.md §1.7 and §4.4 A3. Independent mechanisms multiply: on the
seven-cell heredity sheet, junction_0 scheduled at 1/2 under two couplings, one on each side, each
1/2 (frozen states of 1/2 in cell_0 and cell_3), gives @3 bit for bit what junction_0 scheduled at
1/8 gives. A negative control shows 1/8 and 1/2 differ in the step, so a product that dropped a
factor would be seen. One coupling read on both sides is in _bitwise_both.
"""

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

END = 0.03
JUNCTION = "junction_0"


def test_two_couplings_multiply():
    world = rf.sheet(end=END)
    eighth = run(parse_spec(rf.schedule_junction(world, JUNCTION, 0.125)))
    half = rf.schedule_junction(world, JUNCTION, 0.5)
    two = run(
        parse_spec(
            rf.with_coupling(
                half,
                species=["R"],
                states=[rf.frozen("s1", ["cell_0"], 0.5), rf.frozen("s2", ["cell_3"], 0.5)],
                couplings=[
                    rf.fraction("a", "junction", [JUNCTION], "s1", side="first"),
                    rf.fraction("b", "junction", [JUNCTION], "s2", side="second"),
                ],
            )
        )
    )
    fields, columns = rf.differing(two, eighth)
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)
    fields, _ = rf.differing(eighth, run(parse_spec(half)))
    assert "junction_transferred" in fields
