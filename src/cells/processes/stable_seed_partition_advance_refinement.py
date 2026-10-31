"""Source-only common-endpoint proposal over separately qualified clock arms."""

import hashlib
import traceback
from dataclasses import dataclass, replace
from pathlib import Path

from cells.processes import stable_seed_partition_advance as first
from validation.geometry import (
    stable_seed_partition_advance_refinement_declarations as declarations,
)

LAW_ID = "cells_partition_original_endpoint_clock_resource_controls@1"
INITIAL_SUCCESSOR_MANIFEST_SHA256 = (
    "61679336deda03709b6425f6dc571222a1ffdb6a3e92af01b2378bd3270c115f"
)
INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256 = (
    "84440f74eff19c7a96a275afb81f99ccc0eecc241d484c4cb3c9a13735f1f614"
)
INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256 = (
    "5aad4bce5c8f90020b0bc09786a6e7d4aad11cc71d25b2f1109556f572c788cc"
)
PARENT_INITIAL_REVIEW_SHA256 = "e055f0ff664553e6c6fdf02fc777beb31e6206b3f99fead6835d088f8dd63249"
FIRST_ADVANCE_SOURCE_SHA256 = "2a92b3f55ee0a3c7b4374dcd5da4f48aa8234e3ad947712fdc7fc4d53c3d580c"
DRAFT_ONLY = False


@dataclass(frozen=True)
class Authority:
    manifest_json: str
    source_review_json: str
    numerical_qualification_json: str
    caller_acceptance: object


@dataclass(frozen=True)
class Arm:
    control_id: str
    initial_request: object
    initial_preparation: object
    input_json: str
    report_json: str


@dataclass(frozen=True)
class Request:
    case_id: str
    arms: tuple
    authority: Authority
    role: str
    identity: str


@dataclass(frozen=True)
class Result:
    request_identity: str
    case_id: str
    arm_records: object
    provenance: object
    identity: str


def _require(value, code, *, stage):
    first._require(value, code, stage=stage)


def gate(authority):
    if DRAFT_ONLY or any(
        value is None
        for value in (
            INITIAL_SUCCESSOR_MANIFEST_SHA256,
            INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256,
            INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256,
        )
    ):
        raise first.AdvanceRejected(
            "initial_clock_successor_numerical_qualification_pending",
            stage="successor_qualification",
            original=first.plain(authority),
            partial=dict(numerical_execution_permitted=False, automatic_retry=False),
        )
    _require(
        type(authority) is Authority,
        "complete_clock_successor_authority",
        stage="successor_qualification",
    )
    for text, pin in (
        (authority.manifest_json, INITIAL_SUCCESSOR_MANIFEST_SHA256),
        (authority.source_review_json, INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256),
        (authority.numerical_qualification_json, INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256),
    ):
        _require(
            type(text) is str and hashlib.sha256(text.encode()).hexdigest() == pin,
            "changed_clock_successor_authority",
            stage="successor_qualification",
        )
        first._json(text)
    _require(
        hashlib.sha256(Path(first.__file__).read_bytes()).hexdigest()
        == FIRST_ADVANCE_SOURCE_SHA256,
        "changed_preserved_first_advance_source",
        stage="source_pins",
    )
    first._pins()


def _qualified_arm(case_id, arm, authority):
    _require(type(arm) is Arm, "complete_separately_qualified_arm", stage="arm_binding")
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    request, prepared = arm.initial_request, arm.initial_preparation
    _require(
        type(request) is initial.Request and type(prepared) is initial.Preparation,
        "complete_original_initial_types",
        stage="arm_binding",
    )
    rebuilt = initial.bind(
        request.constructor_request,
        request.constructor_candidate,
        request.geometry_evidence,
        request.declaration,
    )
    _require(
        first.digest(rebuilt) == first.digest(request)
        and prepared.request_identity == request.identity
        and prepared.identity == initial.digest(initial.preparation_record(prepared)),
        "complete_initial_arm_seal",
        stage="arm_binding",
    )
    geometry = request.constructor_candidate.partition_binding.geometry
    expected = declarations.declaration(
        case_id,
        geometry,
        document_sha256=declarations.PARENT_CALLERS_SHA256,
        numerical_control_id=arm.control_id,
    )
    _require(
        first.digest(request.declaration) == first.digest(expected),
        "exact_explicit_clock_resource_caller",
        stage="arm_binding",
    )
    payload, report = first._json(arm.input_json), first._json(arm.report_json)
    _require(
        set(payload)
        == {
            "case_id",
            "numerical_control_id",
            "parent_initial_source_review_json",
            "request",
            "preparation",
        }
        and payload["case_id"] == case_id
        and payload["numerical_control_id"] == arm.control_id
        and first.digest(payload["request"]) == first.digest(request)
        and first.digest(payload["preparation"]) == first.digest(prepared)
        and hashlib.sha256(payload["parent_initial_source_review_json"].encode()).hexdigest()
        == PARENT_INITIAL_REVIEW_SHA256,
        "complete_original_arm_worker_input",
        stage="arm_binding",
    )
    _require(
        report["status"] == "complete"
        and report["case_id"] == case_id
        and report["numerical_control_id"] == arm.control_id
        and report["baseline_passed"] is True
        and report["candidate_passed"] is True
        and report["control_detected"] is False
        and report["controls"] == []
        and not report.get("runtime_capture_failed", False)
        and not report.get("failure_capture_failed", False)
        and report["baseline"]["full_node_physics_and_RHS_verified"] is True
        and report["baseline"]["represented_concentration_defects_verified"] is True
        and report["baseline"]["accounting_passed"] is True,
        "complete_positive_initial_check_for_every_arm",
        stage="arm_binding",
    )
    runtime = report["runtime_origin"]
    manifest = first._json(authority.manifest_json)
    entry = "validation/geometry/stable_seed_partition_advance_refinement_initial_worker.py"
    expected_source = manifest["file_sha256"]["source/" + entry]
    _require(
        runtime["source_sha256"] == expected_source
        and runtime["input_sha256"] == hashlib.sha256(arm.input_json.encode()).hexdigest()
        and runtime["production_imports_denied"] is True
        and runtime["production_modules_loaded"] == []
        and runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
        and type(runtime["pid"]) is int
        and type(runtime["parent_pid"]) is int
        and runtime["pid"] > 0
        and runtime["parent_pid"] > 0
        and runtime["pid"] != runtime["parent_pid"],
        "complete_actual_initial_arm_worker_origin",
        stage="arm_binding",
    )
    worker_root = Path(runtime["source"]).parents[2]
    for rel in (
        entry,
        "validation/geometry/stable_seed_partition_advance_refinement_declarations.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_declarations.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_initial_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_field_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_scalar_reference.py",
        "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    ):
        _require(
            runtime["files"].get(str(worker_root / rel))
            == manifest["file_sha256"]["source/" + rel],
            "complete_initial_arm_runtime_closure:" + rel,
            stage="arm_binding",
        )
    return dict(
        control_id=arm.control_id,
        initial_request_identity=request.identity,
        initial_preparation_identity=prepared.identity,
        input_sha256=hashlib.sha256(arm.input_json.encode()).hexdigest(),
        report_sha256=hashlib.sha256(arm.report_json.encode()).hexdigest(),
    )


def request_record(value):
    return [LAW_ID, value.case_id, value.arms, value.authority, value.role]


def bind(case_id, arms, authority, *, role="comparison"):
    gate(authority)
    _require(
        role in {"comparison", "original_budget_refusal_control"},
        "explicit_control_role",
        stage="arm_binding",
    )
    expected_ids = declarations.comparison_ids(case_id)
    if role == "comparison":
        _require(
            tuple(arm.control_id for arm in arms) == expected_ids,
            "complete_common_storage_comparison_roster",
            stage="arm_binding",
        )
    else:
        allowed = {
            (row["case_id"], row["numerical_control_id"])
            for row in declarations.document()["original_budget_refusal_controls"]
        }
        _require(
            len(arms) == 1 and (case_id, arms[0].control_id) in allowed,
            "explicit_original_budget_refusal_roster",
            stage="arm_binding",
        )
    bindings = [_qualified_arm(case_id, arm, authority) for arm in arms]
    if role == "comparison":
        declarations.same_physical_definition(
            {
                arm.control_id: arm.initial_preparation.physical_preparation.definition
                for arm in arms
            },
            expected_ids,
        )
        _require(
            len({row["input_sha256"] for row in bindings}) == 3,
            "separate_initial_qualification_inputs_for_all_clocks",
            stage="arm_binding",
        )
    expected = dict(
        kind="caller_accepts_separately_qualified_clock_resource_arms@1",
        case_id=case_id,
        role=role,
        arms=bindings,
        initial_successor_manifest_sha256=INITIAL_SUCCESSOR_MANIFEST_SHA256,
        initial_successor_source_review_sha256=INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256,
        initial_successor_numerical_qualification_sha256=INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256,
        endpoint_s=1e-6,
        storage_contract_consistent_within_comparison=role == "comparison",
        clock_equivalence_shortcut=False,
        new_physical_cases=0,
    )
    _require(
        first.digest(authority.caller_acceptance) == first.digest(expected),
        "complete_explicit_common_endpoint_acceptance",
        stage="arm_binding",
    )
    value = Request(case_id, tuple(arms), authority, role, "")
    return replace(value, identity=first.digest(request_record(value)))


def _execute_arm(arm, partial, retain):
    import jax
    import numpy as np

    from cells.core import surface_tissue_spec as schema
    from cells.core.devices import execution_device
    from cells.core.runner import timeline, validate_checkpoint
    from cells.core.schedule import control_values, event_index
    from cells.core.specs import ConfigError
    from cells.core.state import Checkpoint
    from cells.models import surface_tissue as model
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    initial.physical._pins()
    definition = arm.initial_preparation.physical_preparation.definition
    retain("admitted_definition", definition)
    spec = schema.parse(definition)
    partial["stage"] = "existing_Cells_clock_and_storage_admission"
    # This includes the unchanged Cells trace_bytes admission. No budget bypass.
    try:
        times = timeline(spec)
    except ConfigError as error:
        partial["existing_Cells_clock_storage_refusal"] = dict(
            type=type(error).__name__,
            reason=str(error),
            declared_max_trace_bytes=definition["execution"]["max_trace_bytes"],
        )
        code = (
            "existing_Cells_trace_storage_budget_refusal"
            if str(error) == "Estimated trace working storage exceeds max_trace_bytes"
            else "existing_Cells_clock_storage_admission_failed"
        )
        raise first.AdvanceRejected(
            code,
            stage=partial["stage"],
            original=partial["existing_Cells_clock_storage_refusal"],
            partial=partial,
        ) from error
    retain("existing_Cells_clock_return", times.tolist())
    _require(
        times.tolist() == declarations.clock_labels(arm.control_id),
        "complete_declared_original_clock_labels",
        stage=partial["stage"],
    )
    state, layout = model.initial_values(spec)
    table = control_values(spec, times)
    initial_control = type(table)(*(value[0] for value in table))
    for name, value in (("state", state), ("layout", layout), ("control", initial_control)):
        record = first.array_record(value, np)
        retain("initial_" + name, record)
        _require(
            first.digest(record) == first.digest(arm.initial_preparation.initial_snapshot[name]),
            "exact_initial_quantities_units_and_layout:" + name,
            stage="initial_carry",
        )
    device = execution_device("cpu")
    state, layout = jax.device_put((state, layout), device)
    source = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    validate_checkpoint(spec, source, times=times)
    states, checkpoints, boundaries, steps = [state], [first.checkpoint_record(source, np)], [], []
    partial["completed_prefix_checkpoints"] = checkpoints
    partial["completed_boundary_fields_RHS"] = boundaries
    partial["completed_cells_step_attempts"] = steps
    for index, (left, right) in enumerate(zip(times, times[1:], strict=False)):
        partial["stage"] = "existing_Cells_checked_RK4_step_" + str(index)
        step = dict(
            index=index,
            left_s=float(left),
            right_s=float(right),
            actual_step_s=float(right - left),
            accepted=False,
            raw={},
        )
        steps.append(step)

        def capture(name, value, step=step):
            step["raw"][name] = first.plain(value)
            retain("step-" + str(step["index"]) + "-" + name, value)

        held = type(table)(*(value[index] for value in table))
        endpoint_control = type(table)(*(value[index + 1] for value in table))
        _require(
            all(np.array_equal(a, b) for a, b in zip(held, endpoint_control, strict=True)),
            "only_original_held_controls_per_interval",
            stage=partial["stage"],
        )
        held, endpoint_control = jax.device_put((held, endpoint_control), device)
        proposed, _ = first._cells_trial(
            state,
            held,
            layout,
            jax.device_put(np.asarray(right - left, dtype=np.float64), device),
            model,
            jax,
            np,
            capture,
        )
        history = model.STATE_TYPE(
            *(
                np.stack([np.asarray(value) for value in (*[s[i] for s in states], proposed[i])])
                for i in range(len(state))
            )
        )
        capture("complete_prefix_history", first.array_record(history, np))
        balances = model.balances(
            model.STATE_TYPE(*(np.asarray(v) for v in proposed)),
            model.LAYOUT_TYPE(*(np.asarray(v) for v in layout)),
        )
        capture("raw_integrated_balances", first.array_record(balances, np))
        checks = model.check_values(history, spec)
        capture("existing_integrated_history_checks", checks)
        field = model.field_values(proposed, endpoint_control, layout)
        capture("full_endpoint_field", first.array_record(field, np))
        rhs = model.derivative_from_field(field, layout)
        capture("full_endpoint_RHS", first.array_record(rhs, np))
        _require(
            bool(field.converged) and bool(field.rates.valid),
            "complete_endpoint_field_domain",
            stage=partial["stage"],
        )
        checkpoint = Checkpoint(
            proposed, source.layout, float(right), index + 1, event_index(spec, float(right))
        )
        validate_checkpoint(spec, checkpoint, times=times)
        record = first.checkpoint_record(checkpoint, np)
        _require(
            first.digest(record["layout"]) == first.digest(checkpoints[0]["layout"]),
            "original_layout_carried_without_rebase",
            stage=partial["stage"],
        )
        checkpoints.append(record)
        boundaries.append(
            dict(
                time_s=float(right),
                field=first.array_record(field, np),
                rhs=first.array_record(rhs, np),
            )
        )
        states.append(proposed)
        state = proposed
        step["accepted"] = True
        retain("completed_prefix_" + str(index + 1), record)
    _require(
        checkpoints[-1]["time_s"] == 1e-6, "unchanged_common_endpoint", stage="common_endpoint"
    )
    history = model.STATE_TYPE(
        *(np.stack([np.asarray(s[i]) for s in states]) for i in range(len(state)))
    )
    return dict(
        control_id=arm.control_id,
        initial_request_identity=arm.initial_request.identity,
        initial_preparation_identity=arm.initial_preparation.identity,
        definition=definition,
        times=times.tolist(),
        history=first.array_record(history, np),
        checkpoint=checkpoints[-1],
        boundary_fields_RHS=boundaries,
        checkpoints=checkpoints,
        completed_steps=steps,
        complete_common_endpoint=True,
        qualified_initial_input_sha256=hashlib.sha256(arm.input_json.encode()).hexdigest(),
        qualified_initial_report_sha256=hashlib.sha256(arm.report_json.encode()).hexdigest(),
    )


def result_record(value):
    return [LAW_ID, value.request_identity, value.case_id, value.arm_records, value.provenance]


def advance(request, *, observer=None):
    partial = dict(
        stage="successor_qualification",
        request=first.plain(request),
        common_endpoint_accepted=False,
        arms={},
    )

    def retain(name, value):
        partial[name] = first.plain(value)
        if observer is not None:
            observer(name, first.plain(value))

    try:
        _require(type(request) is Request, "exact_common_endpoint_request", stage=partial["stage"])
        gate(request.authority)
        rebuilt = bind(request.case_id, request.arms, request.authority, role=request.role)
        _require(
            first.digest(rebuilt) == first.digest(request),
            "changed_common_endpoint_request",
            stage="arm_binding",
        )
        results = {}
        for arm in request.arms:
            arm_partial = dict(stage="initial_carry", input=first.plain(arm))
            partial["arms"][arm.control_id] = arm_partial

            def capture(name, value, arm=arm, arm_partial=arm_partial):
                arm_partial[name] = first.plain(value)
                retain(arm.control_id + "/" + name, value)

            try:
                results[arm.control_id] = _execute_arm(arm, arm_partial, capture)
            except Exception as error:
                raise first.AdvanceRejected(
                    getattr(error, "code", "common_endpoint_arm_failed"),
                    stage=getattr(error, "stage", arm_partial["stage"]),
                    original=dict(type=type(error).__name__, reason=str(error)),
                    partial=arm_partial,
                ) from error
            retain("completed_arm/" + arm.control_id, results[arm.control_id])
        _require(
            request.role == "comparison",
            "expected_original_budget_refusal_did_not_occur",
            stage="resource_control",
        )
        provenance = dict(
            kind="cells.common_original_endpoint_clock_control_candidate@1",
            law=LAW_ID,
            existing_Cells_stepping_laws=True,
            endpoint_s=1e-6,
            independent_initial_qualification_for_each_arm=True,
            explicit_storage_profile=True,
            old_budget_refusals_reclassified=False,
            original_callers_changed=False,
            new_physical_law=False,
            new_physical_cases=0,
            numerical_comparison_and_refinement_qualification_required=True,
            numerical_tolerances_changed=False,
            process_guards_changed=False,
            retry_or_hidden_subdivision=False,
            native_BETSE_equivalence=False,
        )
        partial["common_endpoint_accepted"] = True
        value = Result(
            request.identity,
            request.case_id,
            first.freeze(results),
            first.freeze(provenance),
            "",
        )
        return replace(value, identity=first.digest(result_record(value)))
    except Exception as error:
        partial["common_endpoint_accepted"] = False
        causes = []
        cause = error
        while cause is not None:
            causes.append(
                dict(
                    type=type(cause).__name__,
                    reason=str(cause),
                    code=getattr(cause, "code", None),
                    stage=getattr(cause, "stage", None),
                    original=first.plain(getattr(cause, "original", None)),
                )
            )
            cause = cause.__cause__
        raise first.AdvanceRejected(
            getattr(error, "code", "common_endpoint_attempt_failed"),
            stage=getattr(error, "stage", partial["stage"]),
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                partial=first.plain(getattr(error, "partial", None)),
                causes=causes,
                traceback=traceback.format_exc(),
            ),
            partial=first.freeze(first.plain(partial)),
        ) from error
