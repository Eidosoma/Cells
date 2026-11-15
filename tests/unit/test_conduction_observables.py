"""Track E's conduction observables (validation/tissue/conduction_observables.py; M1).

Synthetic series with known answers, no engine: crossings interpolate exactly on linear
segments and respect the arming time; conduction velocity recovers a planted front and refuses
a gap; a passive cell has no inward charge and an active cell's equals its planted pulse; the
launched-front rule accepts a front that outruns its stimulus and refuses a synchronous firing,
a front still inside its stimulus and a source that fires late; APD is measured from the
declared reference; brackets order.
"""

import numpy as np
import pytest

from validation.tissue import conduction_observables as co


def test_crossings_interpolate_and_respect_arming():
    t = np.linspace(0.0, 1.0, 11)
    v = np.where(t < 0.5, -0.08 + 0.2 * t, 0.02 - 0.2 * (t - 0.5))  # up, then down
    v = np.concatenate([v, v[1:]])
    t = np.concatenate([t, 1.0 + t[1:]])
    first = co.crossings(t, v, -0.03)
    assert first[0] == pytest.approx(0.25, abs=1e-12)  # -0.08 + 0.2 t = -0.03
    assert len(first) == 2
    assert co.crossings(t, v, -0.03, after=0.3) == pytest.approx([1.25], abs=1e-12)


def test_activation_times_per_column():
    t = np.linspace(0.0, 1.0, 101)
    vm = np.stack([-0.08 + 0.1 * t, np.full_like(t, -0.08)], axis=1)
    first, every = co.activation_times(t, vm, level=-0.03)
    assert first[0] == pytest.approx(0.5, abs=1e-12)
    assert first[1] is None and every[1] == []


def test_conduction_velocity_recovers_a_planted_front():
    distance = np.arange(10)
    activation = [1e-3 + d / 8000.0 for d in distance]
    cv = co.conduction_velocity(activation, distance, range(2, 8))
    assert cv["per_unit"] == pytest.approx(8000.0, rel=1e-9)
    assert cv["rms_residual_s"] < 1e-15
    activation[5] = None
    assert co.conduction_velocity(activation, distance, range(2, 8)) is None


def test_upstroke_passive_and_active():
    dt = 1e-6
    t = np.arange(0.0, 2e-3, dt)
    rise = (t >= 0.5e-3) & (t < 1.0e-3)
    v = np.full_like(t, -0.08)
    v[rise] = -0.08 + (t[rise] - 0.5e-3) * 200.0  # to +0.02 V at 1 ms
    v[t >= 1.0e-3] = 0.02
    vm = np.stack([v, v], axis=1)
    im = np.zeros_like(vm)
    im[:, 0] = 1e-12  # passive: outward throughout
    pulse = rise & (t >= 0.7e-3) & (t < 0.8e-3)  # inside the rise window (from -50 mV, 0.65 ms)
    im[pulse, 1] = -2e-10  # active: a 0.1 ms inward pulse of 2e-10 A
    dvdt = np.gradient(vm, t, axis=0)
    cap = np.array([1e-12, 1e-12])
    up = co.upstroke(t, vm, im, dvdt, cap, after=0.0, rest_index=0)
    assert up["inward_charge_C"][0] == 0.0 and up["source_fraction"][0] == 0.0
    assert up["inward_charge_C"][1] == pytest.approx(2e-10 * 1e-4, rel=1e-2)
    assert up["rise_charge_C"][1] == pytest.approx(1e-12 * 0.1, rel=1e-9)
    assert up["source_fraction"][1] == pytest.approx(0.2, rel=1e-2)
    assert up["max_dvdt_V_s"][1] == pytest.approx(200.0, rel=1e-2)


def chain_edges(n):
    return [(i, i + 1) for i in range(n - 1)]


def test_launched_front_accepts_an_outrunning_front():
    act = [2.05e-3 + 1.2e-4 * i for i in range(12)]
    out = co.launched_front(act, [0], chain_edges(12), on_s=2e-3, off_s=2.1e-3)
    assert out["launched"]


def test_launched_front_refuses_three_failures():
    edges = chain_edges(12)
    synchronous = [9.97e-3 - 1e-6 * i for i in range(12)]  # the s = 1000 latency firing
    assert not co.launched_front(synchronous, [0], edges, on_s=2e-3, off_s=3e-3)["launched"]
    inside = [2.05e-3 + 1.2e-4 * i for i in range(12)]  # ring 2 at 2.29 ms, stimulus to 3 ms
    out = co.launched_front(inside, [0], edges, on_s=2e-3, off_s=3e-3)
    assert out["rings_rise"] and not out["outruns_stimulus"] and not out["launched"]
    late_source = [3.5e-3 + 1.2e-4 * i for i in range(12)]
    out = co.launched_front(late_source, [0], edges, on_s=2e-3, off_s=3e-3)
    assert not out["sources_within_stimulus"] and not out["launched"]


def test_action_potential_from_the_declared_reference():
    dt = 1e-6
    t = np.arange(0.0, 20e-3, dt)
    v = np.full_like(t, -0.08)
    v[(t >= 2e-3) & (t < 3e-3)] = 0.04  # held up during a 2-3 ms stimulus
    fall = (t >= 3e-3) & (t < 15e-3)
    v[fall] = 0.04 - (t[fall] - 3e-3) * 10.0  # 10 V/s down to -0.08 at 15 ms
    ap = co.action_potential(t, v, reference_s=3e-3, rest_V=-0.08)
    # APD50: V = -0.02 at 9 ms; APD90: V = -0.068 at 13.8 ms; both from the stimulus end.
    assert ap["apd50_s"] == pytest.approx(6e-3, abs=2e-6)
    assert ap["apd90_s"] == pytest.approx(10.8e-3, abs=2e-6)
    assert co.largest_dvdt_time(t, v) == pytest.approx(2e-3, abs=2e-6)


def test_bracket_orders():
    assert co.bracket([(0.5, False), (0.2, True), (0.1, True)]) == dict(
        largest_flipping=0.2, smallest_not_flipping=0.5, ordered=True
    )
    assert not co.bracket([(0.7, True), (0.25, False), (0.1, True)])["ordered"]
