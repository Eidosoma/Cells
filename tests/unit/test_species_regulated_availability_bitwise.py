"""species_regulated_availability@1, milestone 1: the factored junction path is the scheduled one.

docs/INVENTORY_COUPLING_DESIGN.md §4.4, M1 and A3's zero case. On the seven-cell heredity sheet, a
coupling at an exactly representable factor (a frozen regulatory state, b = 0) gives @3's step and
@3's observations bit for bit what the same availability scheduled gives:
* M1: F = 1/2 on junction_0 against junction_0 scheduled at 1/2;
* the same composition both ways: on over a schedule of 1 against off over a schedule of 1/2, the
  operator declared in both (separates the factor path from the composite's split-step wrapper);
* A3, zero: F = 0 against 0 scheduled: the target unavailable, carrying no transport and no heat
  while its gate still evolves;
* A3, identity: the coupling switched off (F exactly 1) against the world without the operator.
Every case compares every @3 state field of every accepted row and every @3 observation column. A
negative control shows the comparison is not vacuous: junction_0 carries a transfer and heat at
availability 1, and 1/2 changes the step. The idle operator is in _bitwise_idle, the products in
_bitwise_both and _bitwise_products. Worlds of one structure share one compiled program.
"""

import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

END = 0.03
JUNCTION = "junction_0"  # cell_0 (H) to cell_3, the sheet's D centre: a current flows.


def plain(availability=None):
    raw = rf.sheet(end=END)
    return raw if availability is None else rf.schedule_junction(raw, JUNCTION, availability)


def coupled(world, value, *, switches=None):
    return rf.with_coupling(
        world,
        species=["R"],
        states=[rf.frozen("s", ["cell_0"], value)],
        couplings=[rf.fraction("c", "junction", [JUNCTION], "s", side="first")],
        switches=switches,
    )


def go(raw):
    return run(parse_spec(raw))


def assert_same(a, b):
    fields, columns = rf.differing(a, b)
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)


def junction(result, field):
    index = [j.id for j in parse_spec(plain()).model.junctions].index(JUNCTION)
    return np.asarray(getattr(result.history, field))[..., index]


@pytest.fixture(scope="module")
def unscheduled():
    return go(plain())


def test_half_factor_and_both_ways(unscheduled):
    half = go(coupled(plain(), 0.5))
    assert_same(half, go(plain(0.5)))
    assert np.all(np.asarray(half.observations.coupling_factor) == 0.5)
    off_over_half = go(coupled(plain(0.5), 0.5, switches={"c": [(0.0, 0)]}))
    assert_same(half, off_over_half)
    fields, _ = rf.differing(half, unscheduled)
    assert "junction_transferred" in fields  # Not vacuous: 1/2 changes the step.


def test_zero_factor_is_the_zero_schedule(unscheduled):
    zero = go(coupled(plain(), 0.0))
    assert_same(zero, go(plain(0.0)))
    assert np.all(junction(zero, "junction_transferred") == 0)
    assert np.all(junction(zero, "junction_dissipated_energy_pJ") == 0)
    assert np.any(np.diff(junction(zero, "junction_gate")) != 0)  # The gate still evolves.
    # Not vacuous: junction_0 transfers and dissipates at availability 1.
    assert np.any(junction(unscheduled, "junction_transferred") != 0)
    assert np.any(junction(unscheduled, "junction_dissipated_energy_pJ") != 0)


def test_switched_off_is_the_world_without_the_operator(unscheduled):
    off = go(coupled(plain(), 0.5, switches={"c": [(0.0, 0)]}))
    assert_same(off, unscheduled)
    assert np.all(np.asarray(off.observations.coupling_factor) == 1.0)
