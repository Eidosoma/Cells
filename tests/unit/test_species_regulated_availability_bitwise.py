"""cells.operator.species_regulated_availability@1: the factored path is the scheduled one, in one program.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 (M1, A3) and probe P1 (§7.3). One coupled structure on the
seven-cell heredity sheet (20 steps at 1 ms; regulated_availability_fixtures.shared_structure)
serves every arm, so the file compiles one program: a frozen state s in cell_0 and cell_3 (per-cell
s0, k_on = k_off = 0) and four state_fraction couplings (b = 0) switched on or off per arm: a on
junction_0's first side (s in cell_0), b on its second side (s in cell_3), d on both sides, k on
cell_3's Kir population (kir_3). Each arm sets a junction factor and a channel factor at once and
gives @3's step and @3's observations bit for bit what the same structure with every coupling
switched off gives over both availabilities scheduled:
* M1 and P1 at 1/2: a and k at 1/2, against junction_0 and kir_3 scheduled at 1/2;
* A3, zero: a and k at 0, against both scheduled at 0 (no transfer through either; no heat through
  junction_0, whose gate still evolves);
* A3, multiple: a and b at 1/2 each, and d at 1/2 on both sides, over 1/2, against 1/8 scheduled
  (with k at 1/2 against kir_3 at 1/2);
* the identity: a and k at 1, against both at 1.
Every @3 state field of every accepted row and every @3 observation column is compared, and each
arm's observed factors are exact. Non-vacuous: at 1 both elements carry transfer that the zero arm
removes, and 1/8 and 1/2 differ in the step. That every coupling switched off is the world without
the operator at each of these schedules, and that a declared idle operator is too, is in _guards
(tier 3: D136's claim 2).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import regulated_availability_fixtures as rf

END = 0.02
ROUTES = ("a", "b", "d", "d", "k")  # Route order: a, b, d's two sides (cell_0, cell_3), k.
ROUTE_CELLS = ("cell_0", "cell_3", "cell_0", "cell_3", "cell_3")
_cache = {}


def go(on=(), s0=(1.0, 1.0), junction=1.0, channel=1.0):
    key = (tuple(on), tuple(s0), junction, channel)
    if key not in _cache:
        raw = rf.shared_structure(on=on, s0=s0, junction=junction, channel=channel, end=END)
        _cache[key] = run(parse_spec(raw))
    return _cache[key]


def off(junction=1.0, channel=1.0):
    return go(junction=junction, channel=channel)


def assert_same(a, b):
    fields, columns = rf.differing(a, b)
    assert not fields and not columns, dict(state_fields=fields, observation_columns=columns)


def assert_factors(result, on, s0):
    level = dict(cell_0=s0[0], cell_3=s0[1])
    expected = [
        level[cell] if coupling in on else 1.0
        for coupling, cell in zip(ROUTES, ROUTE_CELLS, strict=True)
    ]
    observed = np.asarray(result.observations.coupling_factor)
    assert observed.shape[1] == len(ROUTES)
    assert np.all(observed == np.asarray(expected)), (observed[0], expected)


def history(result, field, index):
    return np.asarray(getattr(result.history, field))[..., index]


@pytest.fixture(scope="module")
def indices():
    spec = parse_spec(rf.shared_structure(end=END))
    junctions = [j.id for j in spec.model.junctions]
    channels = [c.id for c in spec.model.channels]
    return junctions.index(rf.SHARED_JUNCTION), channels.index(rf.SHARED_CHANNEL)


def test_m1_and_p1_at_one_half():
    arm = dict(on=("a", "k"), s0=(0.5, 0.5))
    factored = go(**arm)
    assert_factors(factored, **arm)
    assert_same(factored, off(junction=0.5, channel=0.5))


def test_a3_zero_makes_both_elements_unavailable(indices):
    j, k = indices
    arm = dict(on=("a", "k"), s0=(0.0, 0.0))
    zero = go(**arm)
    assert_factors(zero, **arm)
    assert_same(zero, off(junction=0.0, channel=0.0))
    assert np.all(history(zero, "junction_transferred", j) == 0)
    assert np.all(history(zero, "junction_dissipated_energy_pJ", j) == 0)
    assert np.all(history(zero, "channel_transferred", k) == 0)
    assert np.any(np.diff(history(zero, "junction_gate", j)) != 0)  # The gate still evolves.
    # Not vacuous: at availability 1 both elements carry transfer, and junction_0 heat.
    assert np.any(history(off(), "junction_transferred", j) != 0)
    assert np.any(history(off(), "junction_dissipated_energy_pJ", j) != 0)
    assert np.any(history(off(), "channel_transferred", k) != 0)


@pytest.mark.parametrize("on", [("a", "b", "k"), ("d", "k")], ids=["two couplings", "both sides"])
def test_a3_multiple_factors_multiply(on):
    product = go(on=on, s0=(0.5, 0.5), junction=0.5)
    assert_factors(product, on=on, s0=(0.5, 0.5))
    assert_same(product, off(junction=0.125, channel=0.5))
    fields, _ = rf.differing(off(junction=0.125, channel=0.5), off(junction=0.5, channel=0.5))
    assert "junction_transferred" in fields  # A dropped factor would be seen.


def test_the_identity_at_one():
    arm = dict(on=("a", "k"), s0=(1.0, 1.0))
    factored = go(**arm)
    assert_factors(factored, **arm)
    assert_same(factored, off())
