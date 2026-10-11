"""Explicit parameter-input hook, separate from the read-only native observer."""

from pathlib import Path

import release_input as prior
import timed_context as ctx

c, old, lifecycle = ctx.c, prior.old, prior.observer


class TimedInput(lifecycle.InitialConditionHook):
    def __init__(self, phase, science, initialise, schedule, duration, observer=None):
        super().__init__(phase, science, initialise, observer)
        self.net_source = str(Path(science).resolve() / "chemistry/networks.py")
        self.schedule = schedule
        self.table = ctx.intervals(schedule, duration, phase.p.dt)
        self.frame = self.controller = None
        self.entries, self.applications = [], []
        self.completed = 0

    def apply(self, entry):
        phase = self.phase
        before = old.snapshot(phase.sim)
        inventory = prior.numeric_inventory(phase)
        receipt = self.controller.apply(old.channel(phase.sim), entry["availability"])
        after, after_inventory = old.snapshot(phase.sim), prior.numeric_inventory(phase)
        c.require(
            before == after and inventory == after_inventory, "Timed input changed native state"
        )
        self.applications.append(
            receipt
            | {
                "index": entry["index"],
                "elapsed_s": entry["start_s"],
                "before": before,
                "after": after,
                "numeric_inventory": inventory,
                "numeric_inventory_after": after_inventory,
                "completed_updates": self.completed,
            }
        )

    def _dispatch(self, frame, event, argument):
        own = (
            frame.f_code.co_filename == self.source and frame.f_locals.get("self") is self.phase.sim
        )
        name = frame.f_code.co_name
        returned = event == "return" and lifecycle.successful_return(frame)
        if own and name == "_run_sim_core_loop" and event == "call":
            c.require(self.frame is None and not self.entries, "Repeated native timed loop")
            self.frame = frame
            self.controller = prior.AvailabilityInput(float(old.channel(self.phase.sim).maxDm))
            c.require(
                len(frame.f_locals["time_steps"]) == len(self.table), "Actual native interval count"
            )
            self.apply(self.table[0])
        if (
            self.frame is not None
            and event == "call"
            and name == "clear_run_loop"
            and frame.f_code.co_filename == self.net_source
            and frame.f_locals.get("self") is self.phase.sim.molecules.core
        ):
            i = len(self.entries)
            c.require(
                i == self.completed and i < len(self.table), "Repeated/incomplete input interval"
            )
            entry = self.table[i]
            if i and entry["start_s"] in [r["time"] for r in self.schedule]:
                self.apply(entry)
            current = float(old.channel(self.phase.sim).maxDm)
            c.require(
                current == self.controller.baseline_maxDm * entry["availability"],
                "Held input drifted",
            )
            self.entries.append(
                entry | {"raw_label_s": float(self.frame.f_locals["t"]), "maxDm_m2_per_s": current}
            )
        super()._dispatch(frame, event, argument)
        if own and name == "update_V" and returned and self.frame is not None:
            self.completed += 1
            c.require(self.completed == len(self.entries), "Native voltage boundary order")
        if own and name == "_run_sim_core_loop" and returned:
            self.frame = None

    def __exit__(self, kind, error, trace):
        try:
            super().__exit__(kind, error, trace)
            if kind is None:
                c.require(
                    self.completed == len(self.entries) == len(self.table)
                    and len(self.applications) == len(self.schedule),
                    "Incomplete full-loop timed input",
                )
        finally:
            self.frame = None
        return False

    def result(self):
        return {
            "schedule": self.schedule,
            "intervals": self.entries,
            "applications": self.applications,
            "completed_updates": self.completed,
            "parameter": "maxDm = immutable_baseline * availability",
            "builtin_tissue_event": False,
            "native_clock_modified": False,
        }
