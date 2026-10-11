"""Synthetic source/object routing tests, not evidence of an executed native loop."""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from native_event_observer import NativeEventObserver, PreparationFence
from native_observer import NativeStepObserver

SCIENCE = Path("/synthetic-betse/science")


def fixture(fault=None):
    scope = {}
    exec(
        compile("def electroflux(p):\n    return 1\n", str(SCIENCE / "sim_toolbox.py"), "exec"),
        scope,
    )
    exec(
        compile(
            """
class Tissue:
    def fire_events(self, phase, t):
        if phase.sim.fault == "event_error":
            raise RuntimeError("event error")
        phase.sim.control = [1.0]
""",
            str(SCIENCE / "tissue/tishandler.py"),
            "exec",
        ),
        scope,
    )
    exec(
        compile(
            """
class Simulator:
    def __init__(self):
        self.amount = [0.0]
        self.voltage = [0.0]
        self.control = [1.0]
        self.movingIons = [0, 1]
        self.saved = []
        self.fault = None

    def _run_sim_core_loop(self, phase, time_steps, time_steps_sampled):
        for t in time_steps:
            if self.fault == "flux_first":
                i = 0
                electroflux(phase.p)
            if self.fault == "update_first":
                self.update_all_concs()
            if self.fault != "missing_event":
                phase.dyna.fire_events(phase=phase, t=t + (1 if self.fault == "clock" else 0))
            if self.fault == "duplicate":
                phase.dyna.fire_events(phase=phase, t=t)
            indices = self.movingIons[::-1] if self.fault == "flux_order" else self.movingIons
            for i in indices:
                if self.fault != "missing_flux":
                    electroflux(phase.p)
            self.update_all_concs()
            if self.fault != "missing_voltage":
                self.update_V()
            if t in time_steps_sampled:
                self.write2storage(t)

    def update_all_concs(self):
        if self.fault == "update_error":
            raise RuntimeError("update error")
        self.amount[0] += 1

    def update_V(self):
        self.voltage[0] = 2 * self.amount[0]

    def write2storage(self, t):
        self.saved.append((t, self.amount[0], self.voltage[0]))
""",
            str(SCIENCE / "sim.py"),
            "exec",
        ),
        scope,
    )
    phase = SimpleNamespace(sim=scope["Simulator"](), dyna=scope["Tissue"](), p=SimpleNamespace())
    phase.sim.fault = fault
    return phase


def snapshot(sim):
    return {"amount": list(sim.amount), "voltage": list(sim.voltage)}


def fluxes(sim):
    return {"flux": [1.0]}


def event_snapshot(sim):
    return snapshot(sim) | {"control": list(sim.control)}


def observer(phase, labels=None):
    return NativeEventObserver(phase, SCIENCE, snapshot, fluxes, event_snapshot, labels)


@pytest.mark.parametrize("count", [2, 40, 80, 160])
def test_one_dispatch_before_flux_each_step_keeps_legacy_trace_and_state_exact(count):
    phase, plain, legacy = fixture(), fixture(), fixture()
    labels = [i * 0.001 / (count - 1) for i in range(count)]
    sampled = set(labels[1:])
    watched = observer(phase)
    with watched:
        phase.sim._run_sim_core_loop(phase, labels, sampled)
    plain.sim._run_sim_core_loop(plain, labels, sampled)
    previous = NativeStepObserver(legacy.sim, SCIENCE / "sim.py", snapshot, fluxes)
    with previous:
        legacy.sim._run_sim_core_loop(legacy, labels, sampled)
    assert vars(phase.sim) == vars(plain.sim) == vars(legacy.sim)
    assert watched.result() == previous.result()
    events = watched.event_result()
    assert len(events["events"]) == count and events["integration_calls"] == 1
    for i, row in enumerate(events["events"]):
        assert row["index"] == i and row["raw_label_s"] == labels[i]
        assert row["flux_ion_indices"] == [0, 1]
        assert row["before"] == row["after"] == row["before_update"]
    saved = copy.deepcopy(events)
    phase.sim.control[0] = 999
    phase.sim.amount[0] = 999
    assert watched.event_result() == saved
    assert sys.getprofile() is None


@pytest.mark.parametrize(
    "fault",
    [
        "missing_event",
        "duplicate",
        "clock",
        "flux_first",
        "update_first",
        "missing_flux",
        "flux_order",
        "missing_voltage",
    ],
)
def test_rejects_missing_repeated_mistimed_or_out_of_order_work(fault):
    phase = fixture(fault)
    with pytest.raises(ValueError), observer(phase):
        phase.sim._run_sim_core_loop(phase, [0.0, 0.001], {0.001})
    assert sys.getprofile() is None


@pytest.mark.parametrize("fault", ["event_error", "update_error"])
def test_native_errors_propagate_and_hooks_are_restored(fault):
    phase = fixture(fault)
    watched = observer(phase)
    with pytest.raises(RuntimeError, match="error"), watched:
        phase.sim._run_sim_core_loop(phase, [0.0, 0.001], {0.001})
    with pytest.raises(ValueError):
        watched.event_result()
    assert sys.getprofile() is None


@pytest.mark.parametrize(
    "wrong", ["source", "tissue_identity", "phase_identity", "flux_source", "simulator_identity"]
)
def test_exact_source_object_and_phase_routing(wrong):
    phase = fixture()
    watched = observer(phase)
    if wrong == "source":
        watched.tissue_file = "/wrong/tishandler.py"
    elif wrong == "flux_source":
        watched.flux_file = "/wrong/sim_toolbox.py"
    elif wrong == "tissue_identity":
        watched.phase = SimpleNamespace(sim=phase.sim, p=phase.p, dyna=fixture().dyna)
    elif wrong == "phase_identity":
        watched.phase = SimpleNamespace(**vars(phase))
    else:
        watched.simulator = fixture().sim
    with pytest.raises(ValueError), watched:
        phase.sim._run_sim_core_loop(phase, [0.0, 0.001], {0.001})
    assert sys.getprofile() is None


def test_events_on_unrelated_objects_are_ignored():
    phase, unrelated = fixture(), fixture()
    watched = observer(phase)
    with watched:
        unrelated.dyna.fire_events(unrelated, 123.0)
        unrelated.sim._run_sim_core_loop(unrelated, [0.0, 0.001], {0.001})
        phase.sim._run_sim_core_loop(phase, [0.0, 0.001], {0.001})
    assert len(watched.event_result()["events"]) == 2


def test_existing_hook_is_not_replaced():
    hook = lambda *args: None  # noqa: E731
    sys.setprofile(hook)
    try:
        with pytest.raises(ValueError, match="existing profiling"), observer(fixture()):
            pass
        assert sys.getprofile() is hook
    finally:
        sys.setprofile(None)


def test_changed_hook_is_rejected_and_cleared():
    with pytest.raises(ValueError, match="hook changed"), observer(fixture()):
        sys.setprofile(lambda *args: None)
    assert sys.getprofile() is None


def test_preparation_dispatch_mode_is_explicitly_not_a_loop():
    phase = fixture()
    labels = [0.0, 0.0005, 0.001]
    watched = observer(phase, labels)
    with watched:
        for t in labels:
            phase.dyna.fire_events(phase, t)
    result = watched.event_result()
    assert result["mode"] == "preparation_dispatch_only" and result["integration_calls"] == 0
    assert all(row["before"] == row["after"] for row in result["events"])
    assert all(row["flux_ion_indices"] == [] for row in result["events"])
    with pytest.raises(ValueError, match="not a native step trace"):
        watched.result()
    with pytest.raises(ValueError, match="single-use"), watched:
        pass


@pytest.mark.parametrize("labels", [[], [True], [float("nan")], [0.0, 0.0], [1.0, 0.0]])
def test_invalid_probe_labels_fail_before_hook_installation(labels):
    with pytest.raises(ValueError, match="labels"):
        observer(fixture(), labels)
    assert sys.getprofile() is None


def test_missing_probe_dispatches_rejected():
    phase = fixture()
    with pytest.raises(ValueError, match="Incomplete"), observer(phase, [0.0, 0.001]):
        phase.dyna.fire_events(phase, 0.0)


@pytest.mark.parametrize("mode", ["fence", "probe_observer"])
@pytest.mark.parametrize(
    "name",
    [
        "run_sim_core",
        "_run_sim_core_loop",
        "_run_fast_sim_core_loop",
        "update_all_concs",
        "init",
        "sim",
        "electroflux",
        "pumpNaKATP",
        "update_Co",
    ],
)
def test_preparation_fences_reject_entry_before_any_body_runs(mode, name):
    filename = next(
        filename for filename, names in PreparationFence.FORBIDDEN.items() if name in names
    )
    scope = {"entered": []}
    exec(
        compile(f"def {name}():\n    entered.append(True)\n", str(SCIENCE / filename), "exec"),
        scope,
    )
    guard = PreparationFence(SCIENCE) if mode == "fence" else observer(fixture(), [0.0])
    with pytest.raises(ValueError, match="Preflight forbids"), guard:
        scope[name]()
    assert scope["entered"] == [] and sys.getprofile() is None
