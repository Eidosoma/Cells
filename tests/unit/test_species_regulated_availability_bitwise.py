"""species_regulated_availability@1: the factored path is the scheduled one, in one program.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 (M1, A3) and probe P1 (§7.3). One coupled structure on the
seven-cell heredity sheet (30 steps at 1 ms; regulated_availability_fixtures.shared_structure)
serves every arm, so the file compiles one program: a frozen state s in cell_0 and cell_3 (per-cell
s0, k_on = k_off = 0) and four state_fraction couplings (b = 0) switched on or off per arm: a on
junction_0's first side (s in cell_0), b on its second side (s in cell_3), d on both sides, k on
cell_3's Kir population (kir_3). Each arm with couplings on gives @3's step and @3's observations
bit for bit what the same structure with every coupling switched off gives over the same
availability scheduled:
* M1, the junction: a at 1/2 over 1, against 1/2 scheduled;
* A3, zero: a at 0, against 0 scheduled (no transfer and no heat through junction_0, while its
  gate still evolves);
* A3, multiple: a and b at 1/2 each, and d at 1/2 on both sides, over 1/2, against 1/8 scheduled;
* P1, the channel: k at 1/2, 0 and 1, against kir_3 scheduled at 1/2, 0 and 1.
Every @3 state field of every accepted row and every @3 observation column is compared, and each
arm's observed factors are exact. Negative controls show 1/2, 1/8 and kir_3's 1/2 change the step.
That every coupling switched off is the world without the operator at each of these schedules,
and that a declared idle operator is too, is in _identity (three programs, tier 3: D136's claim 2).
"""

import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf

ROUTES = ("a", "b", "d", "d", "k")  # Route order: a, b, d's two sides (cell_0, cell_3), k.
ROUTE_CELLS = ("cell_0", "cell_3", "cell_0", "cell_3", "cell_3")
_cache = {}


def go(on=(), s0=(1.0, 1.0), junction=1.0, channel=1.0):
    key = (tuple(on), tuple(s0), junction, channel)
    if key not in _cache:
        raw = rf.shared_structure(on=on, s0=s0, junction=junction, channel=channel)
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
    spec = parse_spec(rf.shared_structure())
    junctions = [j.id for j in spec.model.junctions]
    channels = [c.id for c in spec.model.channels]
    return junctions.index(rf.SHARED_JUNCTION), channels.index(rf.SHARED_CHANNEL)


def test_m1_the_junction_at_one_half():
    arm = dict(on=("a",), s0=(0.5, 1.0))
    factored = go(**arm)
    assert_factors(factored, **arm)
    assert_same(factored, off(junction=0.5))
    fields, _ = rf.differing(off(junction=0.5), off())
    assert "junction_transferred" in fields  # Not vacuous: 1/2 changes the step.


def test_a3_zero_is_the_junction_unavailable(indices):
    j, _ = indices
    arm = dict(on=("a",), s0=(0.0, 1.0))
    zero = go(**arm)
    assert_factors(zero, **arm)
    assert_same(zero, off(junction=0.0))
    assert np.all(history(zero, "junction_transferred", j) == 0)
    assert np.all(history(zero, "junction_dissipated_energy_pJ", j) == 0)
    assert np.any(np.diff(history(zero, "junction_gate", j)) != 0)  # The gate still evolves.
    assert np.any(history(off(), "junction_transferred", j) != 0)  # Not vacuous at 1.
    assert np.any(history(off(), "junction_dissipated_energy_pJ", j) != 0)


@pytest.mark.parametrize("on", [("a", "b"), ("d",)], ids=["two couplings", "both sides"])
def test_a3_multiple_factors_multiply(on):
    product = go(on=on, s0=(0.5, 0.5), junction=0.5)
    assert_factors(product, on=on, s0=(0.5, 0.5))
    assert_same(product, off(junction=0.125))
    fields, _ = rf.differing(off(junction=0.125), off(junction=0.5))
    assert "junction_transferred" in fields  # A dropped factor would be seen.


@pytest.mark.parametrize("level", [0.5, 0.0, 1.0])
def test_p1_the_channel(level, indices):
    _, k = indices
    arm = dict(on=("k",), s0=(1.0, level))
    factored = go(**arm)
    assert_factors(factored, **arm)
    assert_same(factored, off(channel=level))
    fields, _ = rf.differing(off(channel=0.5), off())
    assert "channel_transferred" in fields  # Not vacuous: kir_3 at 1/2 changes the step.
    if level == 0.0:
        assert np.all(history(factored, "channel_transferred", k) == 0)
