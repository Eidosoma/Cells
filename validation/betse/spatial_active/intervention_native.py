"""Declared boundary interventions plus a separate neutral native observer.

The input hook runs in observed AND bare captures. It sets availability after
each completed update_V return, before the next native pump evaluation; it
never uses BETSE's endpoint-labelled time as physical elapsed time.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

native = u.private("intervention_active_native", Path(__file__).with_name("native.py"))
configuration = native.configuration
fixture = native.fixture
snapshot = native.snapshot
Observer = native.Observer


def hook(phase, science, initialise, observer, protocol, case, applied):
    import numpy as np
    from loop_observer import InitialConditionHook, successful_return

    class ScheduledInputs(InitialConditionHook):
        def __init__(self):
            super().__init__(phase, science, initialise, observer)
            self.loop = None
            self.completed = self.entries = self.exits = 0
            self.record = dict(
                clock="completed_updates_times_dt",
                events=case["interventions"],
                steps=[],
                native_methods_replaced=False,
            )
            applied["interventions"] = self.record

        def apply(self):
            dt = phase.p.dt
            choices = case["interventions"]
            indices = [round(v["time_s"] / dt) for v in choices]
            u.need(
                indices[0] == 0
                and all(a < b for a, b in zip(indices, indices[1:], strict=False))
                and all(
                    abs(v["time_s"] - i * dt) <= 8 * np.finfo(float).eps * max(dt, v["time_s"])
                    for v, i in zip(choices, indices, strict=True)
                ),
                "Intervention must lie on a completed native step",
            )
            index = max(i for i, step in enumerate(indices) if step <= self.completed)
            entry = choices[index]
            owner = np.asarray(phase.cells.mem_to_cells)
            targets = entry["target_cells"]
            if targets == "all":
                selected = np.ones(owner.shape, dtype=bool)
            else:
                u.need(bool(targets) and set(targets) <= set(owner.tolist()), "Unknown target cell")
                selected = np.isin(owner, targets)
            pump = np.ones(owner.shape)
            channel = pump.copy()
            pump[selected] = entry["pump_fraction"]
            channel[selected] = entry["channel_fraction"]
            u.need(
                np.all((pump >= 0) & (pump <= 1)) and np.all((channel >= 0) & (channel <= 1)),
                "Invalid availability",
            )
            original = np.asarray(applied["active"]["pump_availability"])
            phase.sim.NaKATP_block = original * pump
            permeability = applied["active"]["channel_permeability_m_s"] * channel
            phase.sim.molecules.core.channels["Kv1p5_spatial"].maxDm = phase.p.tm * permeability
            self.record["steps"].append(
                dict(
                    index=self.completed,
                    before_elapsed_s=self.completed * dt,
                    event_index=index,
                    pump_available=phase.sim.NaKATP_block.tolist(),
                    channel_permeability_m_s=permeability.tolist(),
                )
            )

        def _dispatch(self, frame, event, argument):
            super()._dispatch(frame, event, argument)
            if (
                frame.f_code.co_filename != self.source
                or frame.f_locals.get("self") is not phase.sim
                or event not in ("call", "return")
                or (event == "return" and not successful_return(frame))
            ):
                return
            name = frame.f_code.co_name
            if name == "_run_sim_core_loop":
                if event == "call":
                    self.entries += 1
                    u.need(self.entries == 1 and self.completed == 0, "Repeated native loop")
                    self.loop = frame
                    self.apply()
                else:
                    self.exits += 1
                    u.need(self.completed == phase.p.init_tsteps, "Incomplete intervention clock")
                    self.loop = None
            elif name == "update_V" and event == "return" and self.loop is not None:
                self.completed += 1
                if self.completed < phase.p.init_tsteps:
                    self.apply()

        def __exit__(self, kind, error, traceback):
            value = super().__exit__(kind, error, traceback)
            if kind is None:
                u.need(
                    self.entries == self.exits == 1
                    and self.loop is None
                    and len(self.record["steps"]) == phase.p.init_tsteps,
                    "Incomplete native intervention lifecycle",
                )
            return value

    return ScheduledInputs()


if __name__ == "__main__":
    native.main(adapter=sys.modules[__name__])
