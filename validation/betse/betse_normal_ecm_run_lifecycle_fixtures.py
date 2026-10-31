"""Deferred supplied-entry lifecycle recipes; no native initialization implied."""

import copy
import math

from validation.betse import betse_normal_ecm_event_mechanics_fixtures as composition

CASES = (
    "continuous",
    "window_1_then_3",
    "window_2_then_3",
    "window_each_call",
    "empty_prefix_then_all",
    "fractional_sampling",
    "no_samples",
    "temperature_events",
    "moving_protein_noise",
    "pressure_control",
    "mechanics_disabled",
    "zero_noise_level",
)
RAW_CASES = (
    "events_zero_width",
    "network_refuses",
    "late_negative_temperature",
    "mechanics_overflow",
)
OBSERVER_FAILURES = ("before_call", "accepted_call", "headless_observation")
DEPENDENCIES = (
    "INIT_execution",
    "profile_count",
    "profile_dt",
    "profile_stride",
    "nonprogress_stride",
    "partial_component",
    "native_load",
    "native_persistence",
    "native_display",
    "missing_entry",
    "foreign_entry",
    "entry_already_advanced",
    "receipt_mismatch",
    "entry_field_missing",
    "entry_cache_missing",
    "changed_binding",
    "changed_state",
    "changed_journal",
    "rebased_label",
    "stop_before_cursor",
    "boolean_stop",
    "terminal_step",
)
CLOCK_CASES = (
    "INIT_count_zero",
    "INIT_count_one",
    "SIM_count_three",
    "fractional_sample_stride",
    "duration_truncation",
    "no_samples",
)


def time_profile(dt, stride):
    return dict(
        phase="SIM",
        init_total_s=2 * dt,
        init_dt_s=dt,
        init_sampling_s=dt,
        sim_total_s=3 * dt,
        sim_dt_s=dt,
        sim_sampling_s=stride * dt,
        provenance=(
            "Supplied ordinary time settings; original int(total/dt), phase dt and sampling/dt"
        ),
    )


def wrapped(inputs, case):
    calendar = inputs["event_inputs"]["calendar"]
    return dict(
        kind="cells.normal_ecm_headless_run_inputs@1",
        case_id=case,
        run_id="declared-headless-" + case,
        composition_inputs=inputs,
        time_profile=time_profile(calendar["dt_s"], calendar["sample_stride"]),
        entry_mode="supplied_component_cold_bootstrap_subset",
        observation_mode="headless_only_native_display_refused",
        stop_policy="accepted_call_boundaries_only",
        persistence="none",
    )


def fixture(case="continuous"):
    if case not in CASES:
        raise ValueError("Choose a declared headless lifecycle contract")
    source_case = {
        "temperature_events": "temperature",
        "moving_protein_noise": "moving_P_noise",
        "pressure_control": "pressure_only",
        "mechanics_disabled": "mechanics_disabled",
        "zero_noise_level": "noise_zero_level",
    }.get(case, "combined")
    inputs = composition.fixture(source_case)
    if case in ("fractional_sampling", "no_samples"):
        inputs["event_inputs"]["calendar"]["sample_stride"] = (
            2.5 if case == "fractional_sampling" else 3.0
        )
    return wrapped(inputs, case)


def stops(case):
    return {
        "window_1_then_3": (1, 3),
        "window_2_then_3": (2, 3),
        "window_each_call": (1, 2, 3),
        "empty_prefix_then_all": (0, 3),
    }.get(case, (3,))


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared phase raw refusal")
    source = {
        "events_zero_width": "zero_global_pulse_width",
        "network_refuses": "GRN_refuses_before_noise",
        "late_negative_temperature": "late_negative_temperature",
        "mechanics_overflow": "mechanics_overflow_before_commit",
    }[case]
    return wrapped(composition.raw_fixture(source), case)


def clock_fixture(case):
    if case not in CLOCK_CASES:
        raise ValueError("Choose a declared clock-only source probe")
    raw = time_profile(1e-4, 1.0)
    if case.startswith("INIT_"):
        raw["phase"] = "INIT"
        raw["init_total_s"] = 0.0 if case == "INIT_count_zero" else raw["init_dt_s"]
    elif case == "fractional_sample_stride":
        raw["sim_sampling_s"] = 2.5 * raw["sim_dt_s"]
    elif case == "duration_truncation":
        raw["sim_total_s"] = math.nextafter(raw["sim_total_s"], 0.0)
    elif case == "no_samples":
        raw["sim_sampling_s"] = 3 * raw["sim_dt_s"]
    return copy.deepcopy(raw)
