"""Held new event programs on unchanged molecule54 source specimens."""

import copy

from cells.processes import betse_normal_ecm_molecule_events as joined
from validation.betse import betse_normal_ecm_molecule_lifecycle_fixtures as source
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

CASES = (
    "no_events",
    "combined",
    "salt_order",
    "temperature",
    "GJ_override",
    "NaK_shape",
    "membrane_four",
    "ecmJ",
    "periodic",
    "sweep",
    "voltage_same_edge",
    "pressure_setter",
    "profile_duplicate",
    "general_only",
    "GRN_only",
    "both_disabled",
    "null_transporters",
    "empty_transporters",
    "ordered_transporters",
    "reverse_transporters",
    "publication_off",
    "different_SIM_dt",
    "CaATP_disabled_retains_rate",
    "NaK_disabled_resets_on_call",
)
RAW_CASES = ("zero_global_pulse_width", "negative_Dm_source_return", "late_negative_temperature")
OBSERVER_CASES = (
    "entry_before",
    "entry_after",
    "before_call",
    "before_events",
    "after_global",
    "after_events",
    "after_molecules",
    "after_call",
)
DEPENDENCIES = (
    "foreign_source_binding",
    "foreign_source_entry",
    "advanced_source_entry",
    "wrong_scope",
    "cut_requested",
    "foreign_profile",
    "changed_configured_environment",
    "unsupported_callback",
    "changed_binding",
    "changed_clock",
    "changed_event_trace",
    "changed_event_store",
    "changed_entry_receipt",
    "changed_entry_material",
    "missing_owner_cache",
    "changed_transporter_flux",
    "missing_event_store",
    "boolean_stop",
    "stop_before_cursor",
    "stop_past_cap",
    "failed_resume",
    "native_storage_claim",
)


def selected(case):
    if case not in (*CASES, *RAW_CASES, *OBSERVER_CASES, *DEPENDENCIES):
        raise ValueError("Unknown held event specimen")
    return case if case in source.CASES else "both_enabled"


def declaration(case, binding, entry):
    original = entry.phase_binding.setup_receipt["event_finalization"]["source_fields"]["owner"]
    owner = copy.deepcopy(joined.ions.data(original))
    owner["provenance"] = "Supplied finalized events on actual SIM geometry/profile owners"
    dt = entry.phase_binding.calendar.dt_s
    on, off, width = (0.5 * dt, 2.0 * dt, 0.7 * dt)
    glob = dict.fromkeys(owner["global_options"], 0)
    sched = dict.fromkeys(owner["scheduled_options"], 0)
    callbacks = {}
    program = {
        "zero_global_pulse_width": "temperature",
        "negative_Dm_source_return": "membrane_four",
        "late_negative_temperature": "temperature",
    }.get(case, case)
    combined = case not in (
        "no_events",
        "salt_order",
        "temperature",
        "GJ_override",
        "NaK_shape",
        "membrane_four",
        "ecmJ",
        "periodic",
        "sweep",
        "voltage_same_edge",
        "pressure_setter",
        "profile_duplicate",
        *RAW_CASES,
    )
    if combined or program == "salt_order":
        for key, amp in (("K_env", 0.02), ("Cl_env", 0.015), ("Na_env", 0.01)):
            glob[key] = [on, off, width, amp]
    if combined or program == "temperature":
        glob["T_change"] = [
            on,
            off,
            0.0 if case == "zero_global_pulse_width" else width,
            -2.0 if case == "late_negative_temperature" else 0.01,
        ]
    if combined or program == "GJ_override":
        glob["gj_block"] = [on, off, width, 100]
    if combined or program == "NaK_shape":
        glob["NaKATP_block"] = [on, off, width]
    targets = ["region0", "region0", "all"] if case == "profile_duplicate" else ["all"]
    if combined or program in ("membrane_four", "periodic", "sweep", "profile_duplicate"):
        function = "periodic" if case == "periodic" else "f_sweep" if case == "sweep" else "None"
        for key, suffix in (
            ("Na_mem", "Namem"),
            ("K_mem", "Kmem"),
            ("Cl_mem", "Clmem"),
            ("Ca_mem", "Camem"),
        ):
            sched[key] = [
                on,
                off,
                width,
                -2.0 if case == "negative_Dm_source_return" else 0.15,
                targets,
                function,
            ]
            dynamic = (
                dict(
                    kind="periodic",
                    frequency=2500.0,
                    phase=0.2,
                    provenance="Unchanged source42 periodic parameters",
                )
                if function == "periodic"
                else dict(
                    kind="sweep",
                    start=500.0,
                    slope=10000000.0,
                    provenance="Unchanged source42 sweep parameters",
                )
                if function == "f_sweep"
                else dict(kind="constant")
            )
            callbacks[suffix] = dict(
                source_function=function,
                source_scalar=1,
                dynamic=dynamic,
                provenance="Explicit supplied scalar-one source callback",
            )
    if combined or program == "pressure_setter":
        sched["pressure"] = [on, off, width, 1e-06, ["region0"], "None"]
        callbacks["P"] = dict(
            source_function="None",
            source_scalar=1,
            dynamic=dict(kind="constant"),
            provenance="Original pressure setter; active mechanics remains disabled",
        )
    if combined or program == "ecmJ":
        sched["ecmJ"] = [on, off, width, targets, 0.2]
    owner["voltage"] = (
        dict(
            start_time_step=on,
            stop_time_step=off,
            time_step_rate=width,
            peak_voltage=0.003,
            positive_voltage_boundary="R",
            negative_voltage_boundary="R" if case == "voltage_same_edge" else "L",
        )
        if combined or program == "voltage_same_edge"
        else None
    )
    owner.update(global_options=glob, scheduled_options=sched, callbacks=callbacks)
    owner["handler_fields"] = finalize_fields(
        glob, sched, owner, len(owner["owners"]["membrane_ids"])
    )
    return dict(
        kind=joined.INPUT_KIND,
        case_id=case,
        provenance="Held SIM events with actual source INIT/SIM association",
        source_binding_identity=binding.identity,
        source_entry_identity=entry.identity,
        scope=copy.deepcopy(joined.SCOPE),
        event_owner=owner,
    )
