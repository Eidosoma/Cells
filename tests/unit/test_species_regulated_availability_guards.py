"""cells.operator.species_regulated_availability@1: compiled guards beyond the routine gate (tier 3).

docs/INVENTORY_COUPLING_DESIGN.md §1.9, §1.10 and §4.4. Seven compiled programs, so this file is
deliberately tier 3 (the lead's rulings, 14 November 2026; D152's compiled guards are too); the
tier-1 smoke keeps the declaration-only idleness check, _bitwise holds the routine one-program
checks, and _execution the batch, windows and fresh-process guards.
* **Identity (D136's claim 2).** The shared coupled structure with every coupling switched off
  gives @3's step and observations bit for bit what the world without the operator gives, at each
  pair of availabilities _bitwise schedules (junction_0 and kir_3: 1 and 1, 1/2 and 1/2, 0 and 0,
  1/8 and 1/2); a declared idle operator does too. With _bitwise, every factored arm there equals
  the world without the operator over the same availabilities.
* **RK4, admitted "split" (§1.9).** On the sheet at dt 2.5 µs (@3's explicit bound), 40 steps: a
  and k at 1/2 give what junction_0 and kir_3 scheduled at 1/2 without the operator give, bit for
  bit (and those schedules change the RK4 step); a moving state (k_on 2e4, k_off 1e4, its input
  held) follows its closed form to rounding.
* **Nine species (FR-9's cap at 16, D165).** The sheet with four more neutral species: the shared
  structure's arms against every coupling off over the same schedules, and every coupling off
  against the world without the operator, bit for bit.
Every @3 state field of every accepted row and every @3 observation column is compared where the
check is bitwise.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import regulated_availability_fixtures as rf

END = 0.02
SCHEDULES = [(1.0, 1.0), (0.5, 0.5), (0.0, 0.0), (0.125, 0.5)]
RK4 = dict(dt=2.5e-6, end=40 * 2.5e-6, solver="rk4")
EPS = np.finfo(float).eps


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


def test_rk4_the_factored_path_is_the_scheduled_one():
    factored = run(parse_spec(rf.shared_structure(on=("a", "k"), s0=(0.5, 0.5), **RK4)))
    assert factored.spec.execution.solver == "rk4"
    assert_same(factored, run(parse_spec(rf.scheduled(junction=0.5, channel=0.5, **RK4))))


def test_rk4_a_moving_state_follows_its_closed_form():
    """Its input, R at its 1 µM anchor, is held (nothing moves R): u = 1/2, λ = k_on/2 + k_off."""
    k_on, k_off, s0 = 2e4, 1e4, np.asarray([0.2, 0.7])
    result = run(parse_spec(rf.shared_structure(s0=tuple(s0), rates=(k_on, k_off), **RK4)))
    u = 0.5
    lam = k_on * u + k_off
    target = k_on * u / lam
    times = np.asarray(result.times)
    s = np.asarray(result.history.regulatory_state)
    for k, t in enumerate(times):
        expected = target + (s0 - target) * np.exp(-lam * t)
        assert np.all(np.abs(s[k] - expected) <= 64 * max(k, 1) * EPS), (k, s[k], expected)


def test_rk4_the_schedules_matter_here():
    """The negative control: junction_0 and kir_3 at 1/2 against 1 change the RK4 step."""
    half = run(parse_spec(rf.scheduled(junction=0.5, channel=0.5, **RK4)))
    whole = run(parse_spec(rf.scheduled(**RK4)))
    fields, _ = rf.differing(half, whole)
    assert {"junction_transferred", "channel_transferred"} <= set(fields)


# ------------------------------------------------------------------ above the old species cap


NINE = 4  # The sheet's five species and four more neutral ones: nine, above the old cap of 7.
NINE_ARMS = [  # (couplings on, s0, junction and kir_3 scheduled under every coupling off)
    (("a", "k"), (0.5, 0.5), dict(junction=0.5, channel=0.5)),
    (("a", "k"), (0.0, 0.0), dict(junction=0.0, channel=0.0)),
    (("a", "b", "k"), (0.5, 0.5), dict(junction=0.125, channel=0.5)),
]


@pytest.mark.parametrize("on, s0, schedules", NINE_ARMS, ids=["one half", "zero", "two couplings"])
def test_nine_species_the_factored_path_is_the_world_without_the_operator(on, s0, schedules):
    """FR-9's cap at 16 (D165): with nine species, the shared structure's arms against every
    coupling off over the same schedules, and every coupling off against the world without the
    operator, bit for bit (the two-coupling arm runs over junction_0 at 1/2)."""
    over = dict(junction=0.5) if len(on) == 3 else {}
    factored = run(parse_spec(rf.shared_structure(on=on, s0=s0, end=END, extra=NINE, **over)))
    assert len(factored.spec.model.species_ids) == 9
    off = run(parse_spec(rf.shared_structure(end=END, extra=NINE, **schedules)))
    assert_same(factored, off)
    assert_same(off, run(parse_spec(rf.scheduled(end=END, extra=NINE, **schedules))))
