"""species_regulated_availability@1: compiled guards beyond the routine gate (tier 3).

docs/INVENTORY_COUPLING_DESIGN.md §1.9, §1.10 and §4.4. Seven compiled programs, so this file is
deliberately tier 3 (the lead's ruling, 14 November 2026; D152's compiled guards are too); the
tier-1 smoke keeps the declaration-only idleness check, and _bitwise holds the routine one-program
checks.
* **Identity (D136's claim 2).** The shared coupled structure with every coupling switched off
  gives @3's step and observations bit for bit what the world without the operator gives, at each
  pair of availabilities _bitwise schedules (junction_0 and kir_3: 1 and 1, 1/2 and 1/2, 0 and 0,
  1/8 and 1/2); a declared idle operator does too. With _bitwise, every factored arm there equals
  the world without the operator over the same availabilities.
* **RK4, admitted "split" (§1.9).** On the sheet at dt 2.5 µs (@3's explicit bound), 40 steps: a
  and k at 1/2 give what junction_0 and kir_3 scheduled at 1/2 without the operator give, bit for
  bit; a moving state (k_on 2e4, k_off 1e4, its input held) follows its closed form to rounding.
* **vmap batches (§1.9).** Three worlds of one signature (regulated_availability_fixtures.
  pair_world) with every parameter, s0, θ, the switch and the write varied, in one batch: each
  world's final state is its own windowed run's (floats within 1e-12, integers exact), and the
  batch in reverse order is bitwise the same.
Every @3 state field of every accepted row and every @3 observation column is compared where the
check is bitwise.
"""

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy, run_windowed
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


VARIANTS = [
    dict(),
    dict(
        clearance=(8.0, 1.0),
        half_saturation=2e-3,
        coefficient=2.0,
        basal=0.1,
        on=8.0,
        off=2.0,
        s0=(0.4, 0.1),
        level=0.3,
        write=(0.005, 0.8),
        switch=(0.004, 0.010),
    ),
    dict(
        clearance=(2.0, 6.0),
        half_saturation=5e-4,
        coefficient=0.5,
        basal=0.6,
        on=3.0,
        off=0.5,
        s0=(0.7, 0.6),
        level=0.9,
        write=(0.011, 0.95),
        switch=exact_event_times((9, 15), 1e-3),  # 0.009 is not 9 dt in binary.
    ),
]
POLICY = WindowPolicy(4, "checkpoints")


def test_a_vector_batch_reproduces_each_worlds_own_run():
    specs = [parse_spec(rf.pair_world(**v)) for v in VARIANTS]

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(BatchSpec(worlds, len(worlds), 10**6, 2**31), POLICY)

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    for k, spec in enumerate(specs):
        mine = forward.worlds[k + 1].final.state
        for a, b in zip(mine, backward.worlds[3 - k].final.state, strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k
        own = run_windowed(spec, POLICY).final.state
        for name, a, b in zip(type(own)._fields, mine, own, strict=True):
            a, b = np.asarray(a), np.asarray(b)
            assert a.shape == b.shape and a.dtype == b.dtype, (k, name)
            if a.dtype.kind != "f":
                assert a.tobytes() == b.tobytes(), (k, name)
                continue
            scale = float(np.max(np.abs(b), initial=0.0))
            assert float(np.max(np.abs(a - b), initial=0.0)) <= 1e-12 * scale + 1e-30, (k, name)
    finals = [forward.worlds[k + 1].final.state for k in range(3)]
    writes = [list(np.asarray(f.regulatory_writes_applied)) for f in finals]
    assert writes == [[0, 1]] * 3  # Each world applied its own write.
    counts = {int(np.asarray(f.coupling_step_count)[0]) for f in finals}
    assert counts == {round(END / 1e-3)}  # Padded steps advance nothing.
