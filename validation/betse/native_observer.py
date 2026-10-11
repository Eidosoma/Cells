"""Copy native FULL step boundaries via profiling, without replacing any model method."""

import sys
from pathlib import Path

import contact as c


class NativeStepObserver:
    def __init__(self, simulator, source_file, snapshot, fluxes):
        self.simulator = simulator
        self.source_file = str(Path(source_file).resolve())
        self.snapshot = snapshot
        self.fluxes = fluxes
        self.hook = self._observe
        self.loop_frame = None
        self.pending = None
        self.initial = None
        self.labels = []
        self.sampled_indices = []
        self.steps = []
        self.storage = []
        self.loop_calls = 0
        self.loop_returns = 0
        self.update_returns = 0

    def __enter__(self):
        c.require(sys.getprofile() is None, "Refuse to replace an existing profiling hook")
        c.require(self.loop_calls == 0, "Observer instances are single-use")
        sys.setprofile(self.hook)
        return self

    def __exit__(self, kind, error, traceback):
        active = sys.getprofile()
        sys.setprofile(None)
        self.loop_frame = None
        if kind is None:
            c.require(active is self.hook, "Profiling hook changed during native execution")
            self.validate_complete()
        return False

    def _observe(self, frame, event, argument):
        if (
            event not in ("call", "return")
            or frame.f_code.co_filename != self.source_file
            or frame.f_locals.get("self") is not self.simulator
        ):
            return
        name = frame.f_code.co_name
        if name == "_run_sim_core_loop":
            if event == "call":
                c.require(self.loop_calls == 0, "Repeated native loop")
                self.loop_calls += 1
                self.loop_frame = frame
                self.initial = self.snapshot(self.simulator)
                self.labels = [float(v) for v in frame.f_locals["time_steps"]]
                self.sampled_indices = [
                    i
                    for i, v in enumerate(self.labels)
                    if v in frame.f_locals["time_steps_sampled"]
                ]
            else:
                self.loop_returns += 1
                self.loop_frame = None
        elif self.loop_frame is not None:
            if name == "update_all_concs":
                if event == "call":
                    c.require(self.pending is None, "Overlapping native concentration updates")
                    self.pending = {
                        "index": len(self.steps),
                        "raw_label_s": float(self.loop_frame.f_locals["t"]),
                        "before": self.snapshot(self.simulator),
                        **self.fluxes(self.simulator),
                    }
                else:
                    c.require(self.pending is not None, "Unexpected update return")
                    self.update_returns += 1
            elif name == "update_V" and event == "return":
                c.require(self.pending is not None, "Voltage update without concentration step")
                c.require(
                    self.update_returns == len(self.steps) + 1, "Voltage precedes update return"
                )
                self.pending["after"] = self.snapshot(self.simulator)
                self.steps.append(self.pending)
                self.pending = None
            elif name == "write2storage" and event == "return":
                c.require(self.pending is None and self.steps, "Storage before a completed step")
                self.storage.append(
                    {
                        "index": self.steps[-1]["index"],
                        "raw_label_s": float(frame.f_locals["t"]),
                    }
                )

    def validate_complete(self):
        c.require(
            self.loop_calls == self.loop_returns == 1
            and self.initial is not None
            and self.pending is None
            and len(self.steps) == self.update_returns == len(self.labels),
            "Incomplete native observer coverage",
        )
        c.require(
            [v["index"] for v in self.storage] == self.sampled_indices, "Storage coverage differs"
        )
        c.require(
            all(
                v["index"] == i and v["raw_label_s"] == self.labels[i]
                for i, v in enumerate(self.steps)
            ),
            "Native step order differs",
        )

    def result(self):
        self.validate_complete()
        return {
            "initial": self.initial,
            "steps": self.steps,
            "labels_s": self.labels,
            "sampled_indices": self.sampled_indices,
            "storage": self.storage,
            "loop_calls": self.loop_calls,
            "loop_returns": self.loop_returns,
            "concentration_updates": self.update_returns,
            "hook_restored": sys.getprofile() is None,
        }
