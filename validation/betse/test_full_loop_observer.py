"""Synthetic lifecycle tests, not claims of a native full-loop execution."""

import copy
import sys

import contact as c
import pytest
import test_native_event_observer as synthetic
from full_loop_observer import PRE_LOOP_CALLS, FullLoopObserver, save_entry
from native_observer import NativeStepObserver


def phase_fixture(fault=None, count=40):
    phase = synthetic.fixture(fault)
    scope = {"Simulator": type(phase.sim)}
    exec(
        compile(
            """
class NormalSimulator(Simulator):
    def run_sim_core(self, phase):
        if self.fault != "no_setup":
            self.init_dynamics(phase)
            if self.fault == "repeated_setup":
                self.init_dynamics(phase)
            if self.fault != "no_clear":
                self.clear_storage()
            if self.fault != "no_closure":
                self.update_V()
        self._run_sim_core_loop(phase, self.labels, set(self.labels[1:]))
        self.serialized = True

    def init_dynamics(self, phase):
        if self.fault == "setup_error":
            raise RuntimeError("setup error")

    def clear_storage(self):
        self.saved = []
""",
            str(synthetic.SCIENCE / "sim.py"),
            "exec",
        ),
        scope,
    )
    phase.sim = scope["NormalSimulator"]()
    phase.sim.fault = fault
    phase.sim.labels = [i * 0.001 / (count - 1) for i in range(count)]
    phase.sim.serialized = False
    return phase


def observe(phase, directory, metadata=None):
    return FullLoopObserver(
        phase,
        synthetic.SCIENCE,
        synthetic.snapshot,
        synthetic.fluxes,
        synthetic.event_snapshot,
        directory,
        lambda p: synthetic.snapshot(p.sim),
        metadata or (lambda: {"phase": "synthetic_SIM", "serialized": phase.sim.serialized}),
    )


@pytest.mark.parametrize("count", [2, 40, 80, 160])
def test_normal_lifecycle_keeps_unobserved_and_legacy_outputs_exact(tmp_path, count):
    phase, plain, old = (phase_fixture(count=count) for _ in range(3))
    observer = observe(phase, tmp_path)
    with observer:
        phase.sim.run_sim_core(phase)
    plain.sim.run_sim_core(plain)
    previous = NativeStepObserver(
        old.sim, synthetic.SCIENCE / "sim.py", synthetic.snapshot, synthetic.fluxes
    )
    with previous:
        old.sim.run_sim_core(old)
    assert vars(phase.sim) == vars(plain.sim) == vars(old.sim)
    assert observer.result() == previous.result()
    assert observer.lifecycle_result() == {
        "calls": PRE_LOOP_CALLS,
        "run_returns": 1,
        "hook_restored": True,
    }
    entry = c.read(tmp_path / "loop-entry.json")
    assert entry["pre_loop_calls"] == PRE_LOOP_CALLS
    assert entry["initial"] == observer.result()["initial"]
    assert c.read(tmp_path / "loop-metadata.json")["serialized"] is False
    assert phase.sim.serialized is True and sys.getprofile() is None


@pytest.mark.parametrize(
    "fault", ["no_setup", "repeated_setup", "no_clear", "no_closure", "missing_event", "flux_first"]
)
def test_incomplete_or_repeated_setup_and_step_order_rejected(tmp_path, fault):
    phase = phase_fixture(fault)
    observer = observe(phase, tmp_path)
    with pytest.raises(ValueError), observer:
        phase.sim.run_sim_core(phase)
    assert sys.getprofile() is None
    assert observer.partial()["status"] == "partial_not_qualified"
    with pytest.raises(ValueError):
        observer.result()


@pytest.mark.parametrize("fault", ["setup_error", "event_error", "update_error"])
def test_native_exceptions_propagate_and_partial_copies_remain(tmp_path, fault):
    phase = phase_fixture(fault)
    observer = observe(phase, tmp_path)
    with pytest.raises(RuntimeError, match="error"), observer:
        phase.sim.run_sim_core(phase)
    partial = observer.partial()
    assert partial["hook_restored"] is True and phase.sim.serialized is False
    assert partial["loop_calls"] == (0 if fault == "setup_error" else 1)
    with pytest.raises(ValueError):
        observer.event_result()


def test_metadata_failure_preserves_entry_and_dynamics_before_first_step(tmp_path):
    phase = phase_fixture()

    def fail():
        assert (tmp_path / "loop-entry.json").is_file()
        raise AttributeError("metadata is unavailable")

    observer = observe(phase, tmp_path, fail)
    with pytest.raises(AttributeError, match="unavailable"), observer:
        phase.sim.run_sim_core(phase)
    assert (tmp_path / "dynamics.json").is_file()
    assert c.read(tmp_path / "loop-entry.json")["state"] == synthetic.event_snapshot(phase.sim)
    assert not (tmp_path / "loop-metadata.json").exists()
    assert observer.partial()["events"] == [] and observer.partial()["steps"] == []
    assert sys.getprofile() is None


def test_exclusive_entry_cannot_be_overwritten(tmp_path):
    save_entry(tmp_path, {"state": [1]}, lambda: {"phase": "synthetic"})
    with pytest.raises(FileExistsError):
        save_entry(tmp_path, {"state": [2]}, lambda: {})
    assert c.read(tmp_path / "loop-entry.json") == {"state": [1]}


def test_copies_do_not_alias_native_state(tmp_path):
    phase = phase_fixture()
    observer = observe(phase, tmp_path)
    with observer:
        phase.sim.run_sim_core(phase)
    before = copy.deepcopy(observer.event_result())
    phase.sim.amount[0] = phase.sim.control[0] = 999
    assert observer.event_result() == before


def test_existing_hook_is_never_replaced(tmp_path):
    hook = lambda *args: None  # noqa: E731
    phase = phase_fixture()
    sys.setprofile(hook)
    try:
        with pytest.raises(ValueError, match="existing profiling"), observe(phase, tmp_path):
            phase.sim.run_sim_core(phase)
        assert sys.getprofile() is hook
    finally:
        sys.setprofile(None)
    assert list(tmp_path.iterdir()) == []


def test_single_use_and_changed_hook_guard(tmp_path):
    phase = phase_fixture()
    observer = observe(phase, tmp_path)
    with observer:
        phase.sim.run_sim_core(phase)
    with pytest.raises(ValueError, match="single-use"), observer:
        pass
    second = observe(phase_fixture(), tmp_path)
    with pytest.raises(ValueError, match="hook changed"), second:
        sys.setprofile(lambda *args: None)
    assert sys.getprofile() is None
