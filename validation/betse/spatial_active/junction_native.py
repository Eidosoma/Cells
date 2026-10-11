"""Actual pinned dynamic junctions with active spatial transport and input records."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

native = u.private("junction_spatial_active_native", Path(__file__).with_name("native.py"))
configuration, snapshot, Observer = native.configuration, native.snapshot, native.Observer


def fixture(phase, protocol, case):
    import numpy as np
    from betse.science.channels.gap_junction import Gap_Junction

    record = native.fixture(phase, protocol, case)
    sim, cells, p = phase.sim, phase.cells, phase.p
    p.v_sensitive_gj = True
    p.gj_vthresh = 1000 * protocol["junction"]["threshold_voltage_V"]
    p.gj_min = protocol["junction"]["minimum_open_fraction"]
    sim.gj_funk = Gap_Junction(sim, cells, p)
    species = {name: getattr(sim, "i" + name) for name in case["moving_order"]}
    sim.movingIons = [species[name] for name in case["moving_order"]]
    sim.gjopen = protocol["junction"]["initial_open"] * np.asarray(cells.gj_default_weights)
    record.update(
        moving_ions=list(sim.movingIons),
        dynamic_junction=dict(
            enabled=p.v_sensitive_gj,
            native_class=type(sim.gj_funk).__name__,
            threshold_voltage_V=p.gj_vthresh / 1000,
            minimum_open_fraction=p.gj_min,
            initial_open=sim.gjopen.tolist(),
            base_block=np.broadcast_to(sim.gj_block, sim.gjopen.shape).tolist(),
            calls_per_step=len(sim.movingIons),
            clock="one_outer_dt_per_moving_ion",
            blocking="multiply_stored_opening_after_each_implicit_update",
            native_source_sha256=u.sha(Path(sys.modules[Gap_Junction.__module__].__file__)),
        ),
    )
    return record


def hook(phase, science, initialise, observer, protocol, case, applied):
    import numpy as np
    from loop_observer import InitialConditionHook, successful_return

    class JunctionInputs(InitialConditionHook):
        def __init__(self):
            super().__init__(phase, science, initialise, observer)
            self.loop = None
            self.completed = self.entries = self.exits = 0
            self.record = dict(
                clock="completed_updates_times_dt",
                events=case["junction_changes"],
                steps=[],
                native_methods_replaced=False,
            )
            applied["junction_inputs"] = self.record

        def apply(self):
            events, dt = case["junction_changes"], phase.p.dt
            indices = [round(e["time_s"] / dt) for e in events]
            u.need(
                indices[0] == 0
                and all(a < b for a, b in zip(indices, indices[1:], strict=False))
                and all(
                    abs(e["time_s"] - i * dt) <= 8 * np.finfo(float).eps * max(dt, e["time_s"])
                    for e, i in zip(events, indices, strict=True)
                ),
                "Junction inputs must lie on completed native steps",
            )
            index = max(i for i, value in enumerate(indices) if value <= self.completed)
            fraction = events[index]["fraction"]
            u.need(0 <= fraction <= 1, "Invalid junction fraction")
            phase.sim.gj_block = np.asarray(applied["dynamic_junction"]["base_block"]) * fraction
            self.record["steps"].append(
                dict(
                    index=self.completed,
                    before_elapsed_s=self.completed * dt,
                    event_index=index,
                    block=phase.sim.gj_block.tolist(),
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
                    u.need(self.completed == phase.p.init_tsteps, "Incomplete junction clock")
                    self.loop = None
            elif name == "update_V" and event == "return" and self.loop is not None:
                self.completed += 1
                if self.completed < phase.p.init_tsteps:
                    self.apply()

        def __exit__(self, kind, error, traceback):
            result = super().__exit__(kind, error, traceback)
            if kind is None:
                u.need(
                    self.entries == self.exits == 1
                    and self.loop is None
                    and len(self.record["steps"]) == phase.p.init_tsteps,
                    "Incomplete junction input lifecycle",
                )
            return result

    return JunctionInputs()


if __name__ == "__main__":
    native.main(adapter=sys.modules[__name__])
