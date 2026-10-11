"""Matched transient controls; reuse the existing model and numerical limits."""

import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "validation/betse/fresh_rerun"))
import common as u  # noqa: E402

u.module_path("pump_matched_pilot")
import pilot_context as context  # noqa: E402
from pilot_math import canonical  # noqa: E402, F401


def controls(arm, protocol):
    u.need(arm in protocol["arms"], "Unregistered recovery arm")
    block, release, end = (protocol[k] for k in ("block_time_s", "release_time_s", "duration_s"))
    u.need(0 < block < release < end, "Pump intervention clock")
    if arm == "baseline":
        return [(0.0, 1.0)]
    value = 1.0 if arm == "no_op" else 0.5 if arm == "half_release" else 0.0
    return [(0.0, 1.0), (block, value), (release, 0.0 if arm == "held_block" else 1.0)]


def plan(protocol):
    result = copy.deepcopy(u.plan())
    end, spacing = protocol["duration_s"], protocol["sample_dt_s"]
    times = [i * spacing for i in range(round(end / spacing))] + [end]
    u.need(
        protocol["block_time_s"] in times and protocol["release_time_s"] in times,
        "Observations must include both intervention boundaries",
    )
    result.update(duration_s=end, common_times_s=times, variants=protocol["arms"])
    result["reference"].update(
        sample_dt_s=spacing,
        max_rhs_calls_per_solve=protocol["reference_rhs_cap"],
        max_accepted_steps_per_solve=protocol["reference_accepted_step_cap"],
    )
    for setting, divisor in zip(
        result["reference"]["solves"], protocol["reference_step_divisors"], strict=True
    ):
        setting["max_step_s"] = end / divisor
    return result


def case(preparation, arm, protocol):
    result = copy.deepcopy(preparation["cases"]["pump_leak"])
    result.update(
        id=arm,
        end_time_s=protocol["duration_s"],
        controls=[dict(time_s=t, pump=value, leak=1.0) for t, value in controls(arm, protocol)],
    )
    return result


def definition(preparation, arm, protocol, dt, backend):
    selected = case(preparation, arm, protocol)
    raw = context.definition(selected, dt, times=plan(protocol)["common_times_s"])
    for membrane in raw["experiment"]["membrane_controls"]:
        membrane["pump"] = [dict(time=t, multiplier=value) for t, value in controls(arm, protocol)]
    raw["execution"].update(
        backend=backend,
        max_steps=protocol["resources"]["max_cells_steps"],
        max_trace_bytes=protocol["resources"]["max_trace_bytes"],
    )
    return raw


def preflight(preparation, protocol):
    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec

    rows = []
    for arm in protocol["arms"]:
        for dt in protocol["cells_steps_s"]:
            spec = parse_spec(definition(preparation, arm, protocol, dt, "cpu"))
            grid = timeline(spec)
            for name in ("block_time_s", "release_time_s"):
                u.need(protocol[name] in grid, "Recovery checkpoint is not an exact grid boundary")
            u.need(
                len(grid) - 1 <= spec.execution.max_steps
                and trace_bytes(spec, len(grid) - 1) <= spec.execution.max_trace_bytes,
                "Recovery grid exceeds registered working storage/steps",
            )
            rows.append(
                dict(
                    arm=arm,
                    dt_s=dt,
                    steps=len(grid) - 1,
                    trace_bytes=trace_bytes(spec, len(grid) - 1),
                )
            )
    return {"status": "recovery_grids_fit", "rows": rows}


def control_at(rows, time):
    u.need(math.isfinite(time) and time >= 0, "Invalid control time")
    selected = rows[0]
    for row in rows:
        if row["time_s"] > time:
            break
        selected = row
    return selected["pump"], selected["leak"]
