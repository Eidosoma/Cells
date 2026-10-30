"""Independent carried physical trajectories with rational native event labels.

Only raw definitions, named owners and initial fields enter this oracle. Both
the component blocker buffer and all physical fields are carried across calls;
no production endpoints or calendar implementation are used as starting states.
"""

from copy import deepcopy

from validation.perturbations import global_controls_reference as setters
from validation.perturbations import physiology_calendar_reference as clocks
from validation.tissue import physiology_block_step_reference as intervals


def integrate(
    raw,
    fields,
    binding_record,
    current_diffusion_m2_s,
    block_binding,
    block_state,
    calendar,
    *,
    start_call=0,
    stop_call=None,
    refinement=1,
):
    count, dt = calendar["step_count"], calendar["dt_s"]
    stop = count if stop_call is None else stop_call
    if (
        type(start_call) is not int
        or type(stop) is not int
        or not 0 <= start_call < stop <= count
        or calendar["phase"] not in ("INIT", "SIM")
    ):
        raise ValueError("Require complete bounded independent native calls")
    points = intervals.grid(raw)
    model = raw["model"].get("ionic", raw["model"])
    oracle = intervals.physical.ORACLES[raw["model"]["id"]]
    current, carried = deepcopy(fields), deepcopy(block_state)
    calls = []
    for index in range(start_call, stop):
        label = clocks.event_label(calendar, index)
        start, end = index * dt, (index + 1) * dt
        if start not in points or end not in points or not start < end:
            raise ValueError("Independent native call must span exact physical boundaries")
        source = setters.evaluate(
            block_binding["program"],
            dict(temperature_K=model["temperature_K"], boundary_voltage_V=[0.0] * 4, **carried),
            label,
            model["temperature_K"],
            events_enabled=calendar["phase"] == "SIM",
        )
        carried = {key: source[key] for key in carried}
        rows = []
        for offset in range(points.index(start), points.index(end)):
            result = intervals.integrate(
                raw,
                current,
                binding_record,
                current_diffusion_m2_s,
                block_binding,
                carried,
                start_time_s=points[offset],
                end_time_s=points[offset + 1],
                events_enabled=False,
                refinement=refinement,
            )
            current = oracle.unpack(result["context"], result["state"])
            rows.append(result)
        calls.append(
            dict(
                call_index=index,
                event_label_s=label,
                start_time_s=start,
                end_time_s=end,
                declared_duration_s=dt,
                block_state=deepcopy(carried),
                setter_state=source,
                context=rows[-1]["context"],
                state=rows[-1]["state"],
                endpoint_potential_V=rows[-1]["endpoint_potential_V"],
                endpoint_rate=rows[-1]["endpoint_rate"],
                physical_subintervals=len(rows),
                evaluations=sum(row["evaluations"] for row in rows),
                intervals=rows,
            )
        )
    return calls
