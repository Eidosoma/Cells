# ruff: noqa: C408
"""Metadata relationships for frozen molecule57; no scientific equations."""

import copy
import json
import math

if __package__:
    from .betse_normal_ecm_molecule_events_execution_contract import require
else:
    from betse_normal_ecm_molecule_events_execution_contract import require
if __package__:
    from .betse_normal_ecm_molecule_events_execution_lifecycle import (
        FIELD_FIELDS,
        MATERIAL_FIELDS,
        PHASE_FIELDS,
        ROLES,
        array,
        cursor,
        json_exact,
        numeric_values,
        phase_owner_cache,
        sim_parent,
    )
else:
    from betse_normal_ecm_molecule_events_execution_lifecycle import (
        FIELD_FIELDS,
        MATERIAL_FIELDS,
        PHASE_FIELDS,
        ROLES,
        array,
        cursor,
        json_exact,
        numeric_values,
        phase_owner_cache,
        sim_parent,
    )
EVENT_STORES = (
    "T",
    "c_env_bound",
    "gj_block",
    "NaKATP_block",
    "rho_channel",
    "bound_V",
    "Dm_base",
    "Dm_scheduled",
    "Dm_cells",
    "D_env_base",
    "D_env",
    "D_env_weight_base",
    "D_env_weight",
    "D_free",
    "P_base",
    "P_mod",
    "P_cells",
)
SCOPE = dict(
    phase="SIM",
    solver="FULL",
    geometry_cutting=False,
    flow=False,
    active_mechanics=False,
    dynamic_noise=False,
    dynamic_gate_expansion=False,
    physical_initializer=False,
    native_storage=False,
)
STAGES = ("_fire_events_global", "_fire_events_tissue", "makeAllChanges")
STATE_FIELDS = set(PHASE_FIELDS) | {
    "runtime_material_binding",
    "runtime_definition",
    "entry_receipt",
}


def event_trace(a, trace, label, *, complete=True):
    require(
        set(trace) >= {"before", "after", "stages", "source_time_s", "source_completed"},
        "Complete original event trace required",
    )
    require(
        trace["source_time_s"] == label and trace["source_completed"] is complete,
        "Event label/completion differs",
    )
    names = [row["stage"] for row in trace["stages"]]
    require(
        names == list(STAGES)
        if complete
        else names == list(STAGES)[: len(names)] and len(names) < 3,
        "Original global/tissue/makeAllChanges order differs",
    )
    for value in [trace["before"], trace["after"], *[row["state"] for row in trace["stages"]]]:
        require(set(value) == set(EVENT_STORES), "Every actual event store required")
    if trace["stages"]:
        a.exact(trace["stages"][-1]["state"], trace["after"])
    return trace


def source_partial(a, partial, prior):
    require(
        set(partial)
        == {
            "stage",
            "reached_stage",
            "call_index",
            "parent",
            "available",
            "inner_partial",
            "root_cause",
            "owner_buffers",
            "supplied_owner_cache",
            "available_event_stores",
            "missing_event_stores",
        },
        "Complete actual source partial schema required",
    )
    require(
        partial["call_index"] == cursor(prior)
        and isinstance(partial["available"], dict)
        and (set(partial["root_cause"]) == {"type", "message"})
        and partial["root_cause"]["type"],
        "Source partial call/cause differs",
    )
    a.exact(partial["parent"], prior)
    a.exact(partial["supplied_owner_cache"], prior["network"]["network_cache"])
    buffers = partial["owner_buffers"]
    if buffers is not None:
        require(
            set(buffers)
            == {
                "capture_errors",
                "source_order",
                "material",
                "owners",
                "traces",
                "partial_wires",
                "simulator_arrays",
            }
            and (not buffers["capture_errors"]),
            "Complete actual failure owner-buffer capture required",
        )
    present, missing = (partial["available_event_stores"], partial["missing_event_stores"])
    require(
        isinstance(present, dict)
        and isinstance(missing, list)
        and (len(missing) == len(set(missing)))
        and (not set(present) & set(missing))
        and (set(present) | set(missing) == set(EVENT_STORES)),
        "Full available/missing event-store partition required",
    )
    return partial


def binding(a, value):
    require(
        set(value) == {"source_binding", "source_entry", "raw", "identity"},
        "Complete owned event binding required",
    )
    entry = value["source_entry"]
    sim_parent(a, value["source_binding"], entry)
    require(
        cursor(entry) == 0 and entry["active"]["status"] == "ready",
        "Actual fresh retained SIM entry required",
    )
    raw = value["raw"]
    require(
        raw["source_binding_identity"] == value["source_binding"]["identity"]
        and raw["source_entry_identity"] == entry["identity"],
        "Original source INIT/SIM association differs",
    )
    require(
        set(raw["scope"]) == set(SCOPE)
        and all(
            (type(raw["scope"][k]) is type(v) and raw["scope"][k] == v for k, v in SCOPE.items())
        ),
        "Unqualified event scope expansion",
    )
    base = entry["phase_binding"]
    require(
        base["calendar"]["phase"] == "SIM"
        and base["calendar"]["step_count"] == base["call_limit"] == 3,
        "Original bounded N3 SIM calendar required",
    )
    owner = base["setup_receipt"]["event_finalization"]["source_fields"]["owner"]
    for key in (
        "configured_environment",
        "tissue_default",
        "owners",
        "tissue_target_inds",
        "cell_target_inds",
        "env_target_inds",
    ):
        a.exact(raw["event_owner"][key], owner[key])
    return base


def entry_receipt(a, declared, receipt):
    require(
        set(receipt)
        == {
            "kind",
            "source_entry_identity",
            "before",
            "after",
            "source_control_initializations",
            "native_physical_initializer_called",
            "source_owner_cold_or_reinitialize_called",
        },
        "Complete actual entry receipt required",
    )
    require(
        receipt["kind"] == "cells.actual_SIM_event_control_entry@1"
        and receipt["source_entry_identity"] == declared["source_entry"]["identity"],
        "Entry source owner differs",
    )
    require(
        type(receipt["source_control_initializations"]) is int
        and receipt["source_control_initializations"] == 1
        and (
            receipt["native_physical_initializer_called"]
            is receipt["source_owner_cold_or_reinitialize_called"]
            is False
        ),
        "Only the two supplied entry control branches are admitted",
    )
    original = declared["source_entry"]["active"]
    before, after = (receipt["before"], receipt["after"])
    a.exact(before["owners"], original["network"]["network_cache"])
    a.exact(before["controls"], original["network"]["controls"])
    require(
        before["mode"] == "entry_controls"
        and before["source_phase"] == "SIM"
        and (before["legacy_run_sim"] is True),
        "Actual SIM entry-control input required",
    )
    a.exact(before["global_options"], declared["raw"]["event_owner"]["global_options"])
    m = len(
        declared["source_entry"]["phase_binding"]["material_binding"]["geometry_binding"][
            "current_binding"
        ]["membrane_ids"]
    )
    require(before["membranes"] == m, "Complete membrane axis differs")
    wanted = copy.deepcopy(original["network"]["network_cache"])
    for key in ("gj_block", "NaKATP_block"):
        control = after["controls"][key]
        if before["global_options"][key] != 0:
            require(
                array(control)
                and control["dtype"] == "<f8"
                and (control["shape"] == [m])
                and all((v == 1 for v in a.values(control))),
                "Original enabled entry control vector differs",
            )
        else:
            require(
                type(control) is int and control == 1,
                "Original disabled entry control must retain scalar shape",
            )
        wanted["shared"][key] = control
    a.exact(after["owners"], wanted)
    return receipt


def state(a, declared, parent, *, clock_forms=None):
    require(set(parent) == STATE_FIELDS, "Complete owned event State schema required")
    base = binding(a, declared)
    original = declared["source_entry"]["active"]
    index = cursor(parent)
    dt = base["calendar"]["dt_s"]
    require(
        type(index) is int
        and 0 <= index <= 3
        and (parent["binding_identity"] == declared["identity"]),
        "Actual owned event cursor/binding differs",
    )
    net, field = (parent["network"], parent["field"])
    require(
        set(net) == {"binding_identity", "material", "network_cache", "controls", "identity"}
        and set(net["material"]) == {"binding_identity", "step_index", "values", "identity"},
        "Complete network/material records required",
    )
    require(
        net["binding_identity"] == declared["identity"]
        and net["material"]["step_index"] == parent["mechanics"]["step_index"] == index,
        "Material/network/mechanics source epoch differs",
    )
    require(
        set(net["material"]["values"]) == set(MATERIAL_FIELDS)
        and all((array(v) and v["dtype"] == "<f8" for v in net["material"]["values"].values())),
        "Complete typed ordinary material buffers required",
    )
    require(
        set(field) == set(FIELD_FIELDS)
        and field["binding_identity"]
        == (original["field"]["binding_identity"] if index == 0 else declared["identity"]),
        "Complete preceding full field ownership differs",
    )
    require(
        set(parent["clock"]) == {"source_times_s", "call_index", "material_dt_sum_s"}
        and parent["clock"]["material_dt_sum_s"] == index * dt,
        "Original clock/dt cursor differs",
    )
    a.exact(parent["clock"]["source_times_s"], original["clock"]["source_times_s"])
    labels = list(numeric_values(a, parent["clock"]["source_times_s"]))
    require(len(labels) == 3, "Original SIM source labels required")
    require(
        parent["mechanics"]["sampled_steps"] == [],
        "Native storage/display mechanics credit forbidden",
    )
    entry_receipt(a, declared, parent["entry_receipt"])
    require(
        set(parent["stores"]) == set(original["stores"]) | set(EVENT_STORES),
        "Every setup/event store required",
    )
    for key in set(original["stores"]) - set(EVENT_STORES) - {"div_u_osmo"}:
        a.exact(parent["stores"][key], original["stores"][key])
    phase_owner_cache(a, base, parent)
    cache = net["network_cache"]
    a.exact(cache["enabled"], original["network"]["network_cache"]["enabled"])
    for key in set(cache["shared"]) & set(EVENT_STORES):
        a.exact(cache["shared"][key], parent["stores"][key])
    runtime = parent["runtime_material_binding"]
    require(
        set(runtime) == {"definition_json", "geometry_binding", "kernel", "identity"},
        "Complete legally lowered material binding required",
    )
    a.exact(runtime["geometry_binding"], base["material_binding"]["geometry_binding"])
    require(
        net["material"]["binding_identity"] == runtime["identity"],
        "Actual material binding association differs",
    )
    definition = parent["runtime_definition"]
    wanted = copy.deepcopy(base["inputs"]["definition"])
    wanted["ions"]["membrane_diffusion_m2_s"] = parent["stores"]["Dm_cells"]
    wanted["ions"]["environment_diffusion_m2_s"] = parent["stores"]["D_env"]
    a.exact(definition, wanted)
    require(
        isinstance(runtime["definition_json"], str)
        and len(runtime["definition_json"]) <= 64 * 2**20,
        "Bounded original serialized material definition required",
    )
    json_exact(a, definition, json.loads(runtime["definition_json"]))
    for key in set(base["material_binding"]["kernel"]) - {
        "membrane_diffusion_m2_s",
        "environment_diffusion_m2_s",
    }:
        a.exact(runtime["kernel"][key], base["material_binding"]["kernel"][key])
    for key, present in (
        (
            "rate_cache",
            base["setup_receipt"].get("entry_CaATP_present", False)
            or (index > 0 and base["calcium"]["alpha_Ca"] > 0),
        ),
        ("nak_rate", base["setup_receipt"].get("entry_NaK_present", False) or index > 0),
    ):
        saved = parent[key]
        require(
            set(saved) == {"present", "value"}
            and saved["present"] is bool(present)
            and ((saved["value"] is not None) is bool(present)),
            "Actual producer rate-cache presence differs",
        )
        if present:
            require(
                array(saved["value"])
                and saved["value"]["dtype"] == "<f8"
                and (
                    saved["value"]["shape"]
                    == [
                        len(
                            base["material_binding"]["geometry_binding"]["current_binding"][
                                "membrane_ids"
                            ]
                        )
                    ]
                )
                and all((math.isfinite(v) for v in a.values(saved["value"]))),
                "Complete finite original rate buffer required",
            )
    if index == 0:
        for key in ("rate_cache", "nak_rate", "field", "mechanics"):
            a.exact(parent[key], original[key])
        a.exact(net["material"], original["network"]["material"])
        a.exact(cache, parent["entry_receipt"]["after"]["owners"])
    require(len(parent["history"]) == index, "Complete accepted event journal required")
    for j, row in enumerate(parent["history"]):
        require(
            row["call_index"] == j
            and row["source_label_s"] == labels[j]
            and (row["dt_s"] == dt)
            and (row["material_dt_sum_s"] == (j + 1) * dt),
            "Original event receipt clock differs",
        )
        require(
            type(row["sample_eligible"]) is bool
            and row["source_phase"] == "SIM"
            and (row["legacy_run_sim"] is True)
            and all(
                (
                    type(row[k]) is int
                    for k in (
                        "event_fire_calls",
                        "pre_event_flux_reset_calls",
                        "protein_noise_calls",
                    )
                )
            )
            and (row["event_fire_calls"] == row["pre_event_flux_reset_calls"] == 1)
            and (row["protein_noise_calls"] == 0),
            "Exactly one reset/event call and no protein noise required",
        )
        event_trace(a, row["event_trace"], labels[j])
    if index:
        require(
            parent["history"][-1]["after_network_identity"] == net["identity"]
            and parent["history"][-1]["after_field_identity"] == field["identity"],
            "Reached network/field receipt association differs",
        )
    samples = [j for j, row in enumerate(parent["history"]) if row["sample_eligible"]]
    require(
        [r["call_index"] for r in parent["observations"]] == samples,
        "Original headless sample ownership differs",
    )
    for observation, j in zip(parent["observations"], samples, strict=True):
        require(
            set(observation)
            == {
                "call_index",
                "source_label_s",
                "elapsed_end_s",
                "network",
                "field",
                "mechanics",
                "native_storage_called",
                "display_completed",
            }
            and observation["native_storage_called"] is observation["display_completed"] is False,
            "Complete headless observation scope required",
        )
        require(
            observation["source_label_s"] == labels[j]
            and observation["elapsed_end_s"] == (j + 1) * dt
            and (observation["network"]["material"]["step_index"] == j + 1),
            "Headless original call epoch differs",
        )
        require(
            observation["network"]["identity"] == parent["history"][j]["after_network_identity"]
            and observation["field"]["identity"] == parent["history"][j]["after_field_identity"],
            "Complete reached observation owner differs",
        )
    require(
        parent["status"]
        in ({"exhausted", "failed"} if index == 3 else {"ready", "paused", "failed"}),
        "Source prefix/status differs",
    )
    if clock_forms:
        for form in clock_forms:
            json_exact(
                a,
                parent["clock"],
                dict(form["clock"], call_index=index, material_dt_sum_s=index * dt),
            )
            require(
                samples == [j for j in form["sample_indices"] if j < index],
                "Independent original sampling recurrence differs",
            )
    return parent


def transition(a, declared, prior, current, detail):
    require(cursor(current) == cursor(prior) + 1, "Actual accepted call prefix differs")
    a.exact(current["history"][:-1], prior["history"])
    a.exact(current["entry_receipt"], prior["entry_receipt"])
    a.exact(current["observations"][: len(prior["observations"])], prior["observations"])
    require(
        current["history"][-1]["incoming_identity"] == prior["identity"],
        "Accepted call lost actual caller",
    )
    a.exact(current["history"][-1], detail["receipt"])
    a.exact(current["field"], detail["field"])
    a.exact(current["mechanics"], detail["mechanics_trial"]["candidate"])
    a.exact(detail["events"], current["history"][-1]["event_trace"])
    a.exact(detail["before_events"]["material_before"], prior["network"]["material"]["values"])
    a.exact(detail["before_events"]["clock"], prior["clock"])
    a.exact(detail["before_events"]["before"], detail["events"]["before"])
    if current["history"][-1]["sample_eligible"]:
        for key in ("network", "field", "mechanics"):
            a.exact(current["observations"][-1][key], current[key])


def native_event(a, incoming, trace, reset, native, *, complete=True):
    require(
        native["mode"] == "events"
        and native["status"] == ("source_completed" if complete else "source_refused")
        and (not native["capture_errors"])
        and (native["native_whole_initializer"] is False),
        "Complete associated local native event outcome required",
    )
    a.exact(trace, native["events"])
    a.exact(reset, native["reset_return"])
    a.exact(incoming["before"], trace["before"])
    event_trace(a, trace, incoming["source_time_s"], complete=complete)


def native_owner(a, parent, detail, native):
    require(
        native["status"] == "source_completed" and (not native["capture_errors"]),
        "Complete actual local owner native return required",
    )
    a.exact(detail["before_commit"]["values_before"], native["returned"]["material"])
    a.exact(detail["network"]["shared_after"], native["returned"]["shared"])
    a.exact(detail["network"]["shared_after"], parent["network"]["network_cache"]["shared"])
    for role in ROLES:
        saved = parent["network"]["network_cache"]["handlers"][role]
        a.exact(None if saved is None else saved["cache"], native["returned"]["handlers"][role])
    a.exact(detail["network"]["source_order"], native["order"])
    enabled = [role for role in ROLES if parent["network"]["network_cache"]["enabled"][role]]
    require(
        [r["role"] for r in detail["network"]["source_order"] if r["stage"] == "before_dispatch"]
        == enabled,
        "General-before-GRN actual source order differs",
    )
