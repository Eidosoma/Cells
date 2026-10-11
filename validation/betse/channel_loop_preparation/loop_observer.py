"""A declared initial-condition hook and a separate read-only full-loop observer."""

import dis
import sys
from pathlib import Path

from loop_context import c


def successful_return(frame):
    # Python's profiler also emits "return" when a frame unwinds an exception.
    # The pinned CPython 3.13 bytecode distinguishes it from a real return. Never
    # apply a fixture, or label a step complete, while native setup is failing.
    return dis.opname[frame.f_code.co_code[frame.f_lasti]] in ("RETURN_VALUE", "RETURN_CONST")


class InitialConditionHook:
    """Set the fixture once after real native initialization, in both modes.

    The initializer is explicitly mutating experimental setup, NOT an observer.
    No native methods, clocks, controls or integrator statements are replaced.
    """

    def __init__(self, phase, science, initialise, observer=None):
        self.phase, self.initialise, self.observer = phase, initialise, observer
        self.source = str(Path(science).resolve() / "sim.py")
        self.calls = self.returns = 0
        self.hook = self._dispatch

    def __enter__(self):
        c.require(sys.getprofile() is None and self.calls == 0, "Occupied/reused profiling hook")
        sys.setprofile(self.hook)
        return self

    def __exit__(self, kind, error, traceback):
        active = sys.getprofile()
        sys.setprofile(None)
        if self.observer is not None:
            self.observer.loop_frame = None
        if kind is None:
            c.require(
                active is self.hook and self.calls == self.returns == 1,
                "Initial-condition lifecycle incomplete",
            )
            if self.observer is not None:
                self.observer.validate_complete()
        return False

    def _dispatch(self, frame, event, argument):
        if (
            frame.f_code.co_filename == self.source
            and frame.f_locals.get("self") is self.phase.sim
            and frame.f_code.co_name == "init_dynamics"
        ):
            if event == "call":
                self.calls += 1
                c.require(self.calls == 1, "Repeated native initialization")
            elif event == "return" and successful_return(frame):
                self.returns += 1
                c.require(self.calls == self.returns == 1, "Unexpected initialization return")
                self.initialise(self.phase)
        if self.observer is not None:
            self.observer.observe(frame, event, argument)


class ChannelLoopObserver:
    """Copy exact source/instance-scoped function boundaries; never write model state."""

    def __init__(self, phase, science, snapshot, persist_entry):
        self.phase, self.snapshot, self.persist_entry = phase, snapshot, persist_entry
        self.science = Path(science).resolve()
        self.sim_file = str(self.science / "sim.py")
        self.net_file = str(self.science / "chemistry/networks.py")
        self.gate_file = str(self.science / "channels/vg_k.py")
        self.loop_frame = None
        self.calls = {
            name: 0
            for name in (
                "run_sim_core",
                "init_dynamics",
                "clear_storage",
                "initial_update_V",
                "loop",
                "loop_return",
                "run_return",
            )
        }
        self.initial = None
        self.steps, self.labels, self.sampled_indices, self.storage = [], [], [], []
        self.pending = None
        self.gate_initializations = 0

    def begin(self):
        c.require(self.pending is None and self.loop_frame is not None, "Overlapping/missing step")
        i = len(self.steps)
        self.pending = {
            "index": i,
            "raw_label_s": float(self.loop_frame.f_locals["t"]),
            "before_elapsed_s": i * self.phase.p.dt,
            "after_elapsed_s": (i + 1) * self.phase.p.dt,
            "before": self.snapshot(self.phase.sim),
            "order": [],
        }

    def record(self, name):
        c.require(
            self.pending is not None and name not in self.pending, "Missing/duplicate boundary"
        )
        self.pending[name] = self.snapshot(self.phase.sim)
        self.pending["order"].append(name)

    def observe(self, frame, event, argument):
        if event not in ("call", "return"):
            return
        if event == "return" and not successful_return(frame):
            return
        name, source, obj = (
            frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_locals.get("self"),
        )
        sim = self.phase.sim
        own = source == self.sim_file and obj is sim
        if own and event == "call" and name in ("run_sim_core", "init_dynamics", "clear_storage"):
            c.require(
                self.loop_frame is None and self.calls["loop"] == 0, "Setup during/after loop"
            )
            self.calls[name] += 1
            c.require(self.calls[name] == 1, "Repeated lifecycle boundary")
        if own and name == "update_V" and event == "call" and not self.calls["loop"]:
            self.calls["initial_update_V"] += 1
        if source == self.gate_file and name == "init" and event == "call":
            c.require(self.calls["loop"] == 0, "Gate reinitialization during loop")
            self.gate_initializations += 1
        if own and name == "_run_sim_core_loop":
            if event == "call":
                c.require(
                    self.calls
                    == {
                        "run_sim_core": 1,
                        "init_dynamics": 1,
                        "clear_storage": 1,
                        "initial_update_V": 1,
                        "loop": 0,
                        "loop_return": 0,
                        "run_return": 0,
                    },
                    "Incomplete native lifecycle",
                )
                self.calls["loop"] += 1
                self.loop_frame = frame
                self.initial = self.snapshot(sim)
                self.labels = [float(v) for v in frame.f_locals["time_steps"]]
                self.sampled_indices = [
                    i
                    for i, v in enumerate(self.labels)
                    if v in frame.f_locals["time_steps_sampled"]
                ]
                self.persist_entry(self.partial())
            else:
                self.calls["loop_return"] += 1
                self.loop_frame = None
            return
        if own and name == "run_sim_core" and event == "return":
            self.calls["run_return"] += 1
        if self.loop_frame is None:
            return
        network = None if sim.molecules is None else sim.molecules.core
        channel = None if network is None else next(iter(network.channels.values()), None)
        if source == self.net_file and obj is network:
            if name == "clear_run_loop":
                if event == "call":
                    self.begin()
                else:
                    self.record("after_clear")
            elif name == "run_loop_channels":
                self.record("before_channel" if event == "call" else "after_channel")
            elif name == "run_loop":
                self.record("before_network" if event == "call" else "after_network")
        elif (
            source == self.gate_file
            and channel is not None
            and obj is channel.channel_core
            and name == "run"
        ):
            self.record("before_gate" if event == "call" else "after_gate")
        elif own:
            if name == "update_all_concs":
                if event == "call":
                    if network is None:
                        self.begin()
                    self.record("before_ordinary")
                else:
                    self.record("after_ordinary")
            elif name == "update_V" and event == "return":
                self.record("after_voltage")
                self.steps.append(self.pending)
                self.pending = None
            elif name == "write2storage" and event == "return":
                c.require(self.pending is None and self.steps, "Storage before completed step")
                self.storage.append(
                    {"index": self.steps[-1]["index"], "raw_label_s": float(frame.f_locals["t"])}
                )

    def validate_complete(self):
        c.require(
            all(value == 1 for value in self.calls.values())
            and self.initial is not None
            and self.pending is None
            and len(self.steps) == len(self.labels),
            "Incomplete full-loop observation",
        )
        c.require(
            [v["index"] for v in self.storage] == self.sampled_indices,
            "Native storage coverage differs",
        )
        c.require(
            all(
                s["index"] == i and s["raw_label_s"] == self.labels[i]
                for i, s in enumerate(self.steps)
            ),
            "Step chronology differs",
        )

    def partial(self):
        return {
            "status": "partial_not_qualified",
            "calls": dict(self.calls),
            "initial": self.initial,
            "steps": self.steps,
            "pending": self.pending,
            "labels_s": self.labels,
            "sampled_indices": self.sampled_indices,
            "storage": self.storage,
            "gate_initializations": self.gate_initializations,
            "hook_restored": sys.getprofile() is None,
        }

    def result(self):
        self.validate_complete()
        return self.partial() | {"status": "complete_observation_not_qualification"}
