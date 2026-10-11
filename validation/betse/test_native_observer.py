"""Synthetic profiling lifecycle/ordering checks; not an executed BETSE result."""

import copy
import sys

import pytest
from native_observer import NativeStepObserver


class SimulatorFixture:
    def __init__(self, fail=False):
        self.amount = [0.0]
        self.voltage = [0.0]
        self.saved = []
        self.fail = fail

    def _run_sim_core_loop(self, time_steps, time_steps_sampled):
        for t in time_steps:
            self.update_all_concs()
            self.update_V()
            if t in time_steps_sampled:
                self.write2storage(t)

    def update_all_concs(self):
        if self.fail:
            raise RuntimeError("synthetic native failure")
        self.amount[0] += 1

    def update_V(self):
        self.voltage[0] = 2 * self.amount[0]

    def write2storage(self, t):
        self.saved.append((t, self.amount[0], self.voltage[0]))


def observer(sim, source=__file__):
    return NativeStepObserver(
        sim,
        source,
        lambda s: {"amount": list(s.amount), "voltage": list(s.voltage)},
        lambda s: {"flux": [1.0]},
    )


@pytest.mark.parametrize("count", [2, 10, 20, 40])
def test_real_function_boundaries_include_unsampled_first_step(count):
    labels = [i * 0.001 / (count - 1) for i in range(count)]
    sim, plain = SimulatorFixture(), SimulatorFixture()
    watched = observer(sim)
    with watched:
        sim._run_sim_core_loop(labels, set(labels[1:]))
    plain._run_sim_core_loop(labels, set(labels[1:]))
    assert vars(sim) == vars(plain)
    result = watched.result()
    assert result["initial"] == {"amount": [0.0], "voltage": [0.0]}
    assert result["concentration_updates"] == count
    assert result["sampled_indices"] == list(range(1, count))
    assert result["steps"][0]["after"]["amount"] == [1.0]
    assert result["storage"][0]["index"] == 1
    saved = copy.deepcopy(result)
    sim.amount[0] = 999
    assert result == saved  # copied values, not views into native buffers
    assert sys.getprofile() is None


def test_exception_is_not_swallowed_and_hook_is_restored():
    sim = SimulatorFixture(fail=True)
    watched = observer(sim)
    with pytest.raises(RuntimeError, match="synthetic native failure"), watched:
        sim._run_sim_core_loop([0.0, 0.001], {0.001})
    assert sys.getprofile() is None
    with pytest.raises(ValueError, match="Incomplete"):
        watched.result()


def test_existing_profiler_is_not_replaced():
    hook = lambda *args: None  # noqa: E731
    sys.setprofile(hook)
    try:
        with pytest.raises(ValueError, match="existing profiling"), observer(SimulatorFixture()):
            pass
        assert sys.getprofile() is hook
    finally:
        sys.setprofile(None)


@pytest.mark.parametrize("wrong", ["source", "identity", "no_loop"])
def test_unobserved_work_cannot_claim_complete_coverage(wrong):
    sim = SimulatorFixture()
    watched = observer(sim, "/not/the/source.py") if wrong == "source" else observer(sim)
    with pytest.raises(ValueError, match="Incomplete"), watched:
        if wrong != "no_loop":
            target = SimulatorFixture() if wrong == "identity" else sim
            target._run_sim_core_loop([0.0, 0.001], {0.001})
    assert sys.getprofile() is None


def test_reuse_and_duplicate_loops_are_rejected():
    sim = SimulatorFixture()
    watched = observer(sim)
    with watched:
        sim._run_sim_core_loop([0.0, 0.001], {0.001})
    with pytest.raises(ValueError, match="single-use"), watched:
        pass
    watched = observer(sim)
    with pytest.raises(ValueError, match="Repeated"), watched:
        sim._run_sim_core_loop([0.0, 0.001], {0.001})
        sim._run_sim_core_loop([0.0, 0.001], {0.001})
    assert sys.getprofile() is None


def test_changed_hook_is_reported_and_cleared():
    with pytest.raises(ValueError, match="hook changed"), observer(SimulatorFixture()):
        sys.setprofile(lambda *args: None)
    assert sys.getprofile() is None
