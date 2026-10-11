"""Read-only normal-lifecycle checkpoints around the frozen SIM event observer."""

import sys

import contact as c
from native_event_observer import NativeEventObserver

PRE_LOOP_CALLS = {
    "run_sim_core": 1,
    "init_dynamics": 1,
    "clear_storage": 1,
    "pre_loop_update_V": 1,
}


def save_entry(directory, entry, metadata_factory):
    """Persist copied physical evidence before a potentially failing metadata read."""
    c.write(directory / "loop-entry.json", entry)
    metadata = metadata_factory()
    c.write(directory / "loop-metadata.json", metadata)
    return metadata


class FullLoopObserver(NativeEventObserver):
    """One hook, no wrappers; run_sim_core still owns all native setup and stepping."""

    def __init__(
        self,
        phase,
        science_dir,
        snapshot,
        fluxes,
        event_snapshot,
        directory,
        core_snapshot,
        metadata_factory,
    ):
        super().__init__(phase, science_dir, snapshot, fluxes, event_snapshot)
        self.directory = directory
        self.core_snapshot = core_snapshot
        self.metadata_factory = metadata_factory
        self.lifecycle_calls = dict.fromkeys(PRE_LOOP_CALLS, 0)
        self.run_returns = 0

    def _observe(self, frame, event, argument):
        own = (
            event in ("call", "return")
            and frame.f_code.co_filename == self.source_file
            and frame.f_locals.get("self") is self.simulator
        )
        name = frame.f_code.co_name
        if own:
            if event == "call":
                if name in ("run_sim_core", "init_dynamics", "clear_storage"):
                    c.require(self.loop_calls == 0, "Repeated native setup during/after loop")
                    self.lifecycle_calls[name] += 1
                    c.require(self.lifecycle_calls[name] == 1, "Repeated native setup: " + name)
                elif name == "update_V" and self.loop_calls == 0:
                    self.lifecycle_calls["pre_loop_update_V"] += 1
                elif name == "_run_sim_core_loop":
                    c.require(self.lifecycle_calls == PRE_LOOP_CALLS, "Incomplete native setup")
            elif name == "init_dynamics":
                c.write(self.directory / "dynamics.json", self.core_snapshot(self.phase))
            elif name == "run_sim_core":
                self.run_returns += 1
        super()._observe(frame, event, argument)
        if own and name == "_run_sim_core_loop" and event == "call":
            save_entry(
                self.directory,
                {
                    "state": self.initial_event_state,
                    "initial": self.initial,
                    "pre_loop_calls": dict(self.lifecycle_calls),
                    "labels_s": self.labels,
                    "sampled_indices": self.sampled_indices,
                },
                self.metadata_factory,
            )

    def validate_complete(self):
        super().validate_complete()
        c.require(
            self.lifecycle_calls == PRE_LOOP_CALLS and self.run_returns == 1,
            "Incomplete normal run_sim_core lifecycle",
        )

    def lifecycle_result(self):
        self.validate_complete()
        return {
            "calls": dict(self.lifecycle_calls),
            "run_returns": self.run_returns,
            "hook_restored": sys.getprofile() is None,
        }

    def partial(self):
        """Unvalidated copies for failure diagnosis, never a completed trace."""
        return {
            "status": "partial_not_qualified",
            "lifecycle_calls": dict(self.lifecycle_calls),
            "run_returns": self.run_returns,
            "initial_event_state": self.initial_event_state,
            "events": self.events,
            "open_event": self.open_event,
            "initial": self.initial,
            "steps": self.steps,
            "pending_step": self.pending,
            "labels_s": self.labels,
            "storage": self.storage,
            "loop_calls": self.loop_calls,
            "loop_returns": self.loop_returns,
            "concentration_updates": self.update_returns,
            "hook_restored": sys.getprofile() is None,
        }
