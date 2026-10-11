"""Independent reconstruction of prescribed native controls; no Cells imports."""

import numpy as np

from validation.betse.spatial_active import reference


def step_rows(row):
    events = row["case"]["interventions"]
    record = row["fixture"]["interventions"]
    assert record["events"] == events and record["clock"] == "completed_updates_times_dt"
    assert record["native_methods_replaced"] is False and len(record["steps"]) == row["steps"]
    active = row["fixture"]["active"]
    owners = row["geometry"]["mem_to_cells"]
    rows = []
    for step, captured in enumerate(record["steps"]):
        eligible = [i for i, e in enumerate(events) if round(e["time_s"] / row["dt_s"]) <= step]
        event_index = eligible[-1]
        event = events[event_index]
        assert captured["index"] == step and captured["event_index"] == event_index
        assert captured["before_elapsed_s"] == step * row["dt_s"]
        pump, channel = [], []
        for patch, owner in enumerate(owners):
            selected = event["target_cells"] == "all" or owner in event["target_cells"]
            pump.append(
                active["pump_availability"][patch] * (event["pump_fraction"] if selected else 1)
            )
            channel.append(
                active["channel_permeability_m_s"] * (event["channel_fraction"] if selected else 1)
            )
        np.testing.assert_array_equal(captured["pump_available"], pump)
        np.testing.assert_array_equal(captured["channel_permeability_m_s"], channel)
        rows.append(
            row
            | {
                "fixture": row["fixture"]
                | {
                    "active": active
                    | {"pump_availability": pump, "channel_permeability_m_s": channel}
                }
            }
        )
    return rows


def native_check(row, trace, protocol):
    return reference.native_check(row, trace, protocol, step_rows=step_rows(row))
