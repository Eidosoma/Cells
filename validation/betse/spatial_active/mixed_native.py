"""One boundary-input hook for pump, channel and junction availability.

The existing hook owns native initialization, profiling, completed-step timing
and restoration. Only its prescribed-input callback is extended; native BETSE
methods and the read-only observer are unchanged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

junction = u.private("mixed_junction_native", Path(__file__).with_name("junction_native.py"))
intervention = u.private(
    "mixed_intervention_native", Path(__file__).with_name("intervention_native.py")
)
configuration, fixture = junction.configuration, junction.fixture
snapshot, Observer = junction.snapshot, junction.Observer


def hook(phase, science, initialise, observer, protocol, case, applied):
    import numpy as np

    u.need(
        case["junction_changes"]
        == [
            dict(time_s=e["time_s"], fraction=e["junction_fraction"]) for e in case["interventions"]
        ],
        "Mixed control schedules disagree",
    )
    scheduled = intervention.hook(phase, science, initialise, observer, protocol, case, applied)
    apply_active = scheduled.apply
    record = dict(
        clock="completed_updates_times_dt",
        events=case["junction_changes"],
        steps=[],
        native_methods_replaced=False,
    )
    applied["junction_inputs"] = record

    def apply():
        apply_active()
        active = scheduled.record["steps"][-1]
        fraction = case["interventions"][active["event_index"]]["junction_fraction"]
        u.need(0 <= fraction <= 1, "Invalid junction fraction")
        phase.sim.gj_block = np.asarray(applied["dynamic_junction"]["base_block"]) * fraction
        record["steps"].append(
            dict(
                index=active["index"],
                before_elapsed_s=active["before_elapsed_s"],
                event_index=active["event_index"],
                block=phase.sim.gj_block.tolist(),
            )
        )

    scheduled.apply = apply
    return scheduled


if __name__ == "__main__":
    junction.native.main(adapter=sys.modules[__name__])
