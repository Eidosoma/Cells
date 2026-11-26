"""The matched-arm export driver builds the 16 definitions and every one is admitted to planning.

validation/tissue/matched_arm_export.py. No time stepping and no full export: the four arms at the
four steps are built from the generator (regulated_availability_references), parsed, checked for the
nominal clock (no off-nominal step) and planned into windows (host side only), and their structure
is compared with the generator's declaration: the arms differ only in the production pulse factor
and the coupling switch, the steps only in dt and the record times, and the record times are the
engine's grid values (a decimal 0.35 is not an accepted integration boundary).
"""

import json

import pytest

from cells.definitions.specs import parse_spec
from cells.execution.grid import EventGrid
from cells.execution.windows import WindowPolicy, plan_windows
from validation.tissue import matched_arm_export as me


@pytest.fixture(scope="module")
def built():
    return {key: json.loads(data) for key, data in me.build_definitions().items()}


def test_there_are_16_definitions_and_each_is_planned(built):
    assert sorted(built) == sorted((a, dt) for a in me.ARMS for dt in me.DTS)
    assert len(built) == 16
    for (arm, dt), raw in built.items():
        spec = parse_spec(raw)
        grid = EventGrid(spec)
        assert len(grid) == round(me.END / dt) + 1 and not grid.extras, (arm, dt)
        assert plan_windows(spec, WindowPolicy(me.WINDOW, "full")).window_count >= 1


def test_the_arms_differ_only_in_the_pulse_and_the_coupling_switch(built):
    base = built["regulated_no_pulse", me.FINEST]
    assert [o["law"] for o in base["model"]["operators"]] == [
        "cells.operator.scheduled_species_turnover@1",
        "cells.operator.species_regulated_availability@1",
    ]
    assert base["model"]["id"] == "cells.model.resolved_pump_composite@1"

    def production(raw):
        controls = raw["experiment"]["turnover_controls"]
        (route,) = [c for c in controls if c["route_id"] == "production_X_c0"]
        return [(s["time"], s["rate"]) for s in route["schedule"]]

    def switch(raw):
        (control,) = raw["experiment"]["coupling_controls"]
        return [(s["time"], s["enabled"]) for s in control["schedule"]]

    for dt in me.DTS:
        quiet = production(built["regulated_no_pulse", dt])
        assert quiet == [(0.0, 0.01), (0.2, 0.01), (0.5, 0.01)]
        for arm, (factor, enabled) in me.ARMS.items():
            raw = built[arm, dt]
            assert production(raw) == [(0.0, 0.01), (0.2, 0.01 * factor), (0.5, 0.01)]
            assert switch(raw) == [(0.0, enabled)]
    for dt in me.DTS:  # Everything else is shared by the arms of a step, apart from the start.
        for arm in ("regulated_pulse", "disabled_pulse"):
            a, b = (
                built[arm, dt],
                built[
                    "regulated_no_pulse" if arm == "regulated_pulse" else "disabled_no_pulse", dt
                ],
            )
            a["experiment"]["turnover_controls"] = b["experiment"]["turnover_controls"]
            assert a == b


def test_the_record_times_are_the_engines_grid_values(built):
    for (_, dt), raw in built.items():
        times = raw["experiment"]["observation_times"]
        assert len(times) == 21 and times[0] == 0.0 and times[-1] == me.END
        assert times == me.record_times(dt)
        assert all(t == round(t / dt) * dt for t in times)  # An accepted integration boundary.
        assert raw["execution"]["dt"] == dt and raw["experiment"]["end_time"] == me.END


def test_the_pairs_share_their_start_and_the_switch_changes_it(built):
    def charge(raw):
        return raw["model"]["cells"][0]["initial_charge_C"]

    for dt in me.DTS:
        assert charge(built["regulated_pulse", dt]) == charge(built["regulated_no_pulse", dt])
        assert charge(built["disabled_pulse", dt]) == charge(built["disabled_no_pulse", dt])
        assert charge(built["regulated_pulse", dt]) != charge(built["disabled_pulse", dt])
    assert charge(built["regulated_pulse", 1e-3]) == charge(built["regulated_pulse", me.FINEST])


def test_the_restart_checkpoints_are_before_at_and_after_each_production_event():
    dt = me.FINEST
    assert [s * dt for s in me.RESTART_STEPS] == [0.199875, 0.2, 0.200125, 0.499875, 0.5, 0.500125]
