"""Bounded source and actual-control probes, without running either simulator."""

import copy
import math

import contact as c
import intervention_design as d
import pytest


@pytest.fixture(scope="module")
def plan():
    return c.read(d.PLAN)


@pytest.fixture(scope="module")
def native():
    return d.run_probe("native")


def test_prior_closeout_and_sources_are_unchanged():
    assert len(d.authenticate()["implementation_files_sha256"]) == 352


def test_design_is_not_a_registration_or_trajectory(plan):
    d.validate_plan(plan)
    assert len(plan["gates"]) == 3
    assert plan["trajectory_run"] is plan["trajectory_qualified"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("status",), "registered"),
        (("trajectory_run",), True),
        (("trajectory_qualified",), True),
        (("relax_prior_tolerances",), True),
        (("duration_s",), 0.01),
        (("candidate_pulse", "transition_s"), 0),
        (("candidate_pulse", "transition_s"), -1),
        (("candidate_pulse", "on_s"), 0.0008),
        (("candidate_pulse", "additive_multiplier"), -2),
        (("candidate_pulse", "additive_multiplier"), float("nan")),
        (("candidate_pulse", "exact_zero_interval"), True),
        (("clock", "rewrite_native_clock"), True),
        (("clock", "scale_fields"), ["change start", "change finish"]),
        (("drive_comparison", "separate_forcing_and_solver_refinement"), False),
        (("drive_comparison", "cells_step_subdivisions_per_native_interval"), [1, 1, 1]),
        (("drive_comparison", "controls_derived_from_native_trajectory_output"), True),
        (("source_control_probe_atol",), 1),
        (("criteria_source",), "missing.json"),
    ],
)
def test_design_rejects_overclaims_and_invalid_controls(plan, path, value):
    altered = copy.deepcopy(plan)
    target = altered
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        d.validate_plan(altered)


def test_native_dispatch_is_sim_only_and_precedes_flux():
    source = (c.SOURCE / "betse/science/sim.py").read_text()
    result = d.native_phase_contract(source)
    assert result["events_in_init"] is False and result["events_in_sim"] is True
    assert result["event_line"] < result["first_flux_line"] < result["update_line"]


@pytest.mark.parametrize(
    "old,new",
    [
        ("if phase.kind is SimPhaseKind.SIM:", "if phase.kind is SimPhaseKind.INIT:"),
        (
            "phase.dyna.fire_events(phase=phase, t=t)",
            "phase.dyna.fire_events(phase=phase, t=t+p.dt)",
        ),
        (
            "np.linspace(0, phase_time_len, phase_time_step_count)",
            "np.arange(phase_time_step_count) * phase.p.dt",
        ),
    ],
)
def test_source_contract_rejects_phase_or_clock_changes(old, new):
    source = (c.SOURCE / "betse/science/sim.py").read_text()
    assert old in source
    with pytest.raises(ValueError):
        d.native_phase_contract(source.replace(old, new))


@pytest.mark.parametrize("dt,count", [(0.000025, 40), (0.0000125, 80), (0.00000625, 160)])
def test_clock_conversion_scales_all_three_time_parameters(plan, dt, count):
    actual, scale, mapped = d.clock_parameters(plan, dt)
    assert actual == count and scale == count / (count - 1)
    q = plan["candidate_pulse"]
    assert mapped == [scale * q[k] for k in ("on_s", "off_s", "transition_s")]
    assert (count - 1) * dt < plan["duration_s"]
    assert math.isclose(scale * (count - 1) * dt, plan["duration_s"], abs_tol=1e-18)


@pytest.mark.parametrize("dt", [0, -1, True, float("inf"), 0.001, 0.000015])
def test_clock_conversion_rejects_noncorresponding_steps(plan, dt):
    with pytest.raises(ValueError):
        d.clock_parameters(plan, dt)


def test_actual_native_pulse_matches_independent_elapsed_clock_controls(plan, native):
    assert native["engine"] == "pinned_betse_toolbox_pulse_only"
    assert native["integration_calls"] == 0 and native["warnings"] == []
    assert native["plan_sha256"] == c.sha(d.PLAN)
    assert sum(row["steps"] for row in native["rows"]) == 280
    for row in native["rows"]:
        assert row["maximum_control_error"] <= plan["source_control_probe_atol"]
        assert len(row["applied_availability"]) == row["steps"]
        assert row["unscaled_maximum_control_difference"] > 1e-3


def test_smooth_suppression_does_not_claim_exact_blocking_or_unchanged_initial_drive(plan, native):
    q = plan["candidate_pulse"]
    midpoint = (q["on_s"] + q["off_s"]) / 2
    assert 0 < d.decimal_availability(midpoint, q) < 1e-8
    assert native["midpoint_availability_decimal"] > 0
    # A logistic pulse has tails before/after its named transition centres.
    assert 0 < d.decimal_availability(0, q) < 1
    assert 0 < d.decimal_availability(plan["duration_s"], q) < 1
    assert d.decimal_availability(q["on_s"], q) == pytest.approx(0.5, abs=2e-14)


def test_zero_amplitude_is_a_true_no_op_at_the_control_level(plan):
    q = plan["candidate_pulse"] | {"additive_multiplier": 0}
    assert all(d.decimal_availability(t, q) == 1 for t in (0, 0.0003, 0.0005, 0.0007, 0.001))


def test_existing_cells_control_is_right_continuous_and_splits_off_grid_events():
    result = d.run_probe("cells")
    assert result["integration_calls"] == 0
    assert result["availability"] == [1, 1, 0, 0, 0, 1, 1]
    assert len(result["event_split_grid_s"]) - 1 == 12
    assert result["plan_sha256"] == c.sha(d.PLAN)


def test_subdivisions_really_refine_within_each_held_input_interval(plan):
    # Coarse nominal Cells steps above the forcing interval would be split into
    # the same grid. The proposed h, h/2, h/4 instead produce distinct grids.
    for dt in plan["native_steps_s"]:
        count, _, _ = d.clock_parameters(plan, dt)
        for factor in plan["drive_comparison"]["cells_step_subdivisions_per_native_interval"]:
            fine = dt / factor
            assert all(k * dt == (factor * k) * fine for k in range(count))
        assert len({count * f for f in (1, 2, 4)}) == 3
