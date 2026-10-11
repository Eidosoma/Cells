"""One read-only dispatcher for SIM events, source flux calls and native step copies.

Preparation mode observes explicitly requested event calls only and rejects model
integration. Neither mode installs wrappers or writes to native state.
"""

import math
import sys
from pathlib import Path

import contact as c
from native_observer import NativeStepObserver


class PreparationFence:
    """Refuse entry to native integration/transport before its function body runs."""

    FORBIDDEN = {
        "sim.py": {
            "run_sim_core",
            "_run_sim_core_loop",
            "_run_fast_sim_core_loop",
            "update_all_concs",
        },
        "simrunner.py": {"init", "sim"},
        "sim_toolbox.py": {"electroflux", "pumpNaKATP", "update_Co"},
    }

    def __init__(self, science_dir):
        directory = Path(science_dir).resolve()
        self.forbidden = {str(directory / f): names for f, names in self.FORBIDDEN.items()}
        self.calls = {}
        self.hook = self.observe

    def observe(self, frame, event, argument):
        if event != "call" or frame.f_code.co_filename not in self.forbidden:
            return
        name = frame.f_code.co_name
        c.require(name not in self.forbidden[frame.f_code.co_filename], "Preflight forbids " + name)
        if name in ("seed", "init_core", "init_dynamics", "clear_storage", "update_V"):
            self.calls[name] = self.calls.get(name, 0) + 1

    def __enter__(self):
        c.require(sys.getprofile() is None, "Refuse to replace an existing profiling hook")
        sys.setprofile(self.hook)
        return self

    def __exit__(self, kind, error, traceback):
        active = sys.getprofile()
        sys.setprofile(None)
        if kind is None:
            c.require(active is self.hook, "Preparation profiling hook changed")
        return False


class NativeEventObserver(NativeStepObserver):
    def __init__(self, phase, science_dir, snapshot, fluxes, event_snapshot, probe_labels=None):
        directory = Path(science_dir).resolve()
        super().__init__(phase.sim, directory / "sim.py", snapshot, fluxes)
        self.phase = phase
        self.tissue_file = str(directory / "tissue/tishandler.py")
        self.flux_file = str(directory / "sim_toolbox.py")
        self.event_snapshot = event_snapshot
        self.probe_labels = None if probe_labels is None else list(probe_labels)
        if self.probe_labels is not None:
            c.require(
                self.probe_labels
                and all(type(t) is float and math.isfinite(t) for t in self.probe_labels)
                and all(
                    a < b for a, b in zip(self.probe_labels, self.probe_labels[1:], strict=False)
                ),
                "Invalid preparation dispatch labels",
            )
        self.fence = PreparationFence(directory)
        self.events = []
        self.open_event = None
        self.initial_event_state = None
        self.entered = False

    def __enter__(self):
        c.require(not self.entered, "Observer instances are single-use")
        result = super().__enter__()
        self.entered = True
        return result

    def _observe(self, frame, event, argument):
        if self.probe_labels is not None:
            self.fence.observe(frame, event, argument)
        if event not in ("call", "return"):
            return
        source, name = frame.f_code.co_filename, frame.f_code.co_name
        native_self = frame.f_locals.get("self")
        if source == self.tissue_file and native_self is self.phase.dyna and name == "fire_events":
            c.require(frame.f_locals.get("phase") is self.phase, "Event belongs to another phase")
            labels = self.labels if self.probe_labels is None else self.probe_labels
            if event == "call":
                index = len(self.events)
                c.require(self.open_event is None and index < len(labels), "Repeated/extra event")
                c.require(float(frame.f_locals["t"]) == labels[index], "Event clock/order differs")
                if self.probe_labels is None:
                    c.require(
                        self.loop_frame is not None
                        and index == len(self.steps)
                        and self.pending is None,
                        "Event outside its native step",
                    )
                self.open_event = {
                    "index": index,
                    "raw_label_s": float(frame.f_locals["t"]),
                    "before": self.event_snapshot(self.simulator),
                    "flux_ion_indices": [],
                }
            else:
                c.require(self.open_event is not None, "Unexpected event return")
                self.open_event["after"] = self.event_snapshot(self.simulator)
                self.events.append(self.open_event)
                self.open_event = None
            return
        if self.probe_labels is not None:
            return
        if (
            source == self.flux_file
            and name == "electroflux"
            and event == "call"
            and frame.f_back is self.loop_frame
            and self.loop_frame is not None
        ):
            c.require(frame.f_locals.get("p") is self.phase.p, "Flux uses another parameter object")
            c.require(
                self.open_event is None
                and len(self.events) == len(self.steps) + 1
                and self.pending is None,
                "Flux precedes completed event dispatch",
            )
            self.events[-1]["flux_ion_indices"].append(int(self.loop_frame.f_locals["i"]))
        if source == self.source_file and native_self is self.simulator:
            if name == "_run_sim_core_loop" and event == "call":
                c.require(
                    frame.f_locals.get("phase") is self.phase, "Loop belongs to another phase"
                )
                self.initial_event_state = self.event_snapshot(self.simulator)
            if name == "update_all_concs" and event == "call" and self.loop_frame is not None:
                c.require(
                    self.open_event is None and len(self.events) == len(self.steps) + 1,
                    "Concentration update without one completed event",
                )
                row = self.events[-1]
                c.require(
                    row["flux_ion_indices"] == [int(i) for i in self.simulator.movingIons],
                    "Incomplete/out-of-order native flux coverage",
                )
                row["before_update"] = self.event_snapshot(self.simulator)
        super()._observe(frame, event, argument)

    def validate_complete(self):
        c.require(self.open_event is None, "Incomplete event dispatch")
        if self.probe_labels is not None:
            c.require(
                len(self.events) == len(self.probe_labels) and self.loop_calls == 0,
                "Incomplete preparation dispatch coverage",
            )
        else:
            super().validate_complete()
            c.require(
                len(self.events) == len(self.steps)
                and self.initial_event_state is not None
                and all("before_update" in row for row in self.events),
                "Incomplete SIM event coverage",
            )

    def event_result(self):
        self.validate_complete()
        return {
            "mode": "preparation_dispatch_only"
            if self.probe_labels is not None
            else "full_sim_loop",
            "initial": self.initial_event_state,
            "events": self.events,
            "hook_restored": sys.getprofile() is None,
            "integration_calls": self.loop_calls,
        }

    def result(self):
        c.require(self.probe_labels is None, "Preparation is not a native step trace")
        return super().result()
