"""Unevaluated run contracts on the unchanged reviewed molecule54 specimens."""

import copy

from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation.betse import betse_normal_ecm_molecule_lifecycle_fixtures as leaf

CASES = (
    "continuous",
    "window_1_then_3",
    "window_2_then_3",
    "window_each_call",
    "empty_prefix_then_all",
    "fractional_sampling",
    "no_samples",
    "general_only",
    "GRN_only",
    "both_disabled",
    "zero_capacity",
    "null_transporters",
    "empty_transporters",
    "ordered_transporters",
    "reverse_transporters",
    "one_INIT_call",
    "zero_INIT_calls",
    "mixed_INIT_inactive",
    "all_INIT_inactive",
    "default_INIT_active",
    "different_SIM_dt",
    "CaATP_disabled_retains_rate",
    "NaK_disabled_resets_on_call",
    "publication_off",
)
RAW_CASES = (
    "first_general_negative",
    "first_GRN_negative",
    "warm_missing_max_rate_0",
    "warm_missing_max_rate_1",
)
OBSERVER_CASES = ("before_call", "accepted_call", "headless_observation", "phase_after_call")
PREFIX_CASES = ("paused_INIT", "capped_INIT", "failed_INIT")
DEPENDENCIES = (
    "foreign_component_binding",
    "changed_time_profile",
    "wrong_phase",
    "native_persistence",
    "native_display",
    "invalid_stop_policy",
    "foreign_entry",
    "entry_advanced",
    "entry_paused",
    "entry_receipt_changed",
    "changed_binding",
    "changed_run",
    "changed_journal",
    "rebased_source_label",
    "changed_observation",
    "missing_owner_cache",
    "changed_transporter_cache",
    "foreign_previous_phase",
    "changed_completed_INIT",
    "boolean_stop",
    "stop_before_cursor",
    "stop_past_cap",
    "terminal_step",
    "failed_resume",
)


def selected(case):
    if case not in (*CASES, *RAW_CASES, *OBSERVER_CASES, *PREFIX_CASES, *DEPENDENCIES):
        raise ValueError("Unknown separately declared headless molecule run specimen")
    return (
        case
        if case in (*leaf.CASES, *leaf.RAW_INIT_CASES, *leaf.RAW_SIM_CASES, *leaf.PREFIX_REFUSALS)
        else "both_enabled"
    )


def init_inputs(case):
    raw = leaf.init_fixture(selected(case))
    if case == "fractional_sampling":
        raw["time_profile"]["init_sampling_s"] = 2.5 * raw["time_profile"]["init_dt_s"]
    elif case == "no_samples":
        raw["time_profile"]["init_sampling_s"] = 8.0 * raw["time_profile"]["init_dt_s"]
    return raw


def sim_inputs(case, completed):
    raw = leaf.fixture(selected(case), completed)
    if case in ("fractional_sampling", "no_samples"):
        profile = raw["sim_phase"]["time_profile"]
        profile["sim_sampling_s"] = (2.5 if case == "fractional_sampling" else 3.0) * profile[
            "sim_dt_s"
        ]
    return raw


def declaration(case, component_binding):
    return dict(
        kind=run.INPUT_KIND,
        case_id=case,
        run_id="molecule-headless-" + case + "-" + run.composition.kind(component_binding),
        component_binding_identity=component_binding.identity,
        time_profile=copy.deepcopy(run.ions.data(run.composition.profile(component_binding))),
        entry_mode="supplied_molecule54_phase_entry",
        observation_mode="headless_only_native_display_refused",
        stop_policy="accepted_call_boundaries_only",
        persistence="none",
    )


def stops(case, count):
    return (
        {
            "window_1_then_3": (1, 3),
            "window_2_then_3": (2, 3),
            "window_each_call": (1, 2, 3),
            "empty_prefix_then_all": (0, 3),
        }.get(case, (count,))
        if count == 3
        else (count,)
    )
