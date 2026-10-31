"""Unfrozen, bounded full-horizon continuation using the existing checked kernel.

New full-horizon initial bindings and accepted upstream receipts are mandatory.
This module changes no runner, model, kernel, checkpoint or conservation law.
"""

import hashlib
import os
import sys
import traceback
from dataclasses import dataclass, replace
from pathlib import Path

from cells.processes import stable_seed_partition_advance as first
from validation.geometry import stable_seed_partition_trajectory_authority as authority_gate
from validation.geometry import stable_seed_partition_trajectory_declarations as declarations
from validation.geometry import stable_seed_partition_trajectory_records as records

LAW_ID = "cells_partition_full_horizon_checked_trajectory_exact_restart@1"
DRAFT_ONLY = True
FIRST_ADVANCE_SOURCE_SHA256 = "2a92b3f55ee0a3c7b4374dcd5da4f48aa8234e3ad947712fdc7fc4d53c3d580c"
BOUNDARY_SOURCE_PINS = {
    "src/cells/io.py": "e44d65d5677da3752700f83adda27893c774e26d738dda1b6b31e8a2112a43f9",
    "src/cells/core/windows.py": "628068a7c1ab073cb54fe979f96e8db3e15be13eb7eeaba362b4cb16c2c09094",
    "src/cells/core/resources.py": (
        "410ff57effc1fe24f3004e6ea42374e88bc21503ea7ed177c5c4c8b008bf7954"
    ),
    "src/cells/core/specs.py": "193d7f814d422099c2ea0c661a58d08142fb07c43de6bad3eb59c3b2f132eb09",
}


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
    authority: object
    role: str
    identity: str


def require(value, reason, *, stage="trajectory_binding"):
    first._require(value, reason, stage=stage)


def gate(authority):
    if DRAFT_ONLY:
        error = authority_gate.PrerequisitePending("Trajectory is an unfrozen source proposal")
        error.detail = dict(numerical_execution_permitted=False, freeze_permitted=False)
        raise error
    accepted = authority_gate.require(authority, phase="trajectory")
    require(
        records.sha(first.__file__) == FIRST_ADVANCE_SOURCE_SHA256,
        "preserved_checked_kernel_capture_source",
    )
    first._pins()
    root = Path(__file__).resolve().parents[3]
    for rel, pin in BOUNDARY_SOURCE_PINS.items():
        require(
            records.sha(root / rel) == pin, "unchanged_existing_window_checkpoint_source:" + rel
        )
    return accepted


def _qualified_arm(case_id, arm, authority, accepted):
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    require(type(arm) is Arm, "complete_fresh_trajectory_arm")
    request, prepared = arm.initial_request, arm.initial_preparation
    require(
        type(request) is initial.Request and type(prepared) is initial.Preparation,
        "complete_initial_owner_types",
    )
    rebuilt = initial.bind(
        request.constructor_request,
        request.constructor_candidate,
        request.geometry_evidence,
        request.declaration,
    )
    require(
        first.digest(rebuilt) == first.digest(request)
        and prepared.request_identity == request.identity
        and prepared.identity == initial.digest(initial.preparation_record(prepared)),
        "complete_new_initial_seals",
    )
    expected = declarations.declaration(
        case_id,
        request.constructor_candidate.partition_binding.geometry,
        document_sha256=declarations.ORIGINAL_CALLERS_SHA256,
        numerical_control_id=arm.control_id,
    )
    require(
        first.digest(request.declaration) == first.digest(expected),
        "new_full_horizon_contract_declared_at_time_zero",
    )
    payload, report = first._json(arm.input_json), first._json(arm.report_json)
    require(
        set(payload)
        == {
            "case_id",
            "numerical_control_id",
            "parent_initial_source_review_json",
            "request",
            "preparation",
            "trajectory_authority",
            "root_geometry_candidate_json",
        },
        "complete_new_initial_worker_input",
    )
    require(
        payload["case_id"] == case_id
        and payload["numerical_control_id"] == arm.control_id
        and first.digest(payload["request"]) == first.digest(request)
        and first.digest(payload["preparation"]) == first.digest(prepared)
        and payload["trajectory_authority"] == authority_gate.initial_phase(authority),
        "exact_new_initial_input_binding",
    )
    require(
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
        "fresh_complete_initial_physics_and_accounting",
    )
    runtime = report["runtime_origin"]
    manifest = accepted["trajectory_initial_manifest_json"]
    entry = "validation/geometry/stable_seed_partition_trajectory_initial_worker.py"
    require(
        runtime["source_sha256"] == manifest["file_sha256"]["source/" + entry]
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
        "actual_fresh_independent_initial_worker",
    )
    root = Path(runtime["source"]).parents[2]
    for rel in (
        entry,
        "validation/geometry/stable_seed_partition_trajectory_declarations.py",
        "validation/geometry/stable_seed_partition_trajectory_authority.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_declarations.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_initial_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_field_reference.py",
        "validation/geometry/stable_seed_partition_physiology_bridge_scalar_reference.py",
        "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    ):
        require(
            runtime["files"].get(str(root / rel)) == manifest["file_sha256"]["source/" + rel],
            "complete_initial_runtime_closure:" + rel,
        )
    definition = prepared.physical_preparation.definition
    binding = dict(
        case_id=case_id,
        numerical_control_id=arm.control_id,
        input_sha256=hashlib.sha256(arm.input_json.encode()).hexdigest(),
        report_sha256=hashlib.sha256(arm.report_json.encode()).hexdigest(),
        initial_request_identity=request.identity,
        initial_preparation_identity=prepared.identity,
        definition_sha256=first.digest(definition),
    )
    qualification = accepted["trajectory_initial_qualification_json"]
    require(
        qualification["kind"] == "cells.partition_trajectory_initial_qualification@1"
        and qualification["status"] == "accepted"
        and qualification["qualification_inherited"] is False,
        "new_trajectory_initials_have_their_own_accepted_qualification",
    )
    bindings = qualification["accepted_bindings"]
    expected_roster = {
        (row["case_id"], a["id"]) for row in declarations.document()["cases"] for a in row["arms"]
    }
    require(
        len(bindings) == len(expected_roster) == 18
        and {(r["case_id"], r["numerical_control_id"]) for r in bindings} == expected_roster,
        "all_eighteen_new_initial_bindings_separately_qualified",
    )
    require(binding in bindings, "this_exact_full_horizon_initial_was_accepted")
    return binding


def request_record(value):
    return [LAW_ID, value.case_id, value.arms, value.authority, value.role]


def bind(case_id, arms, authority, *, role="comparison"):
    accepted = gate(authority)
    require(role in {"comparison", "declared_window_refusal_control"}, "explicit_trajectory_role")
    ids = tuple(arm.control_id for arm in arms)
    if role == "comparison":
        require(ids == declarations.comparison_ids(case_id), "all_three_common_endpoint_clocks")
    else:
        require(
            len(ids) == 1
            and declarations.selected(case_id, ids[0])["source_predicted_window_admission"]
            is False,
            "explicit_original_storage_refusal_control",
        )
    for arm in arms:
        _qualified_arm(case_id, arm, authority, accepted)
    if role == "comparison":
        declarations.same_physical_definition(
            case_id,
            {a.control_id: a.initial_preparation.physical_preparation.definition for a in arms},
        )
    value = Request(case_id, tuple(arms), first.freeze(authority), role, "")
    return replace(value, identity=first.digest(request_record(value)))


def from_index(index, case_id, *, refusal_id=None):
    """Restore qualified immutable inputs only; never construct a new fixture."""
    authority = {name: Path(path).read_text() for name, path in index["authority"].items()}
    gate(authority)
    from cells.core import finite_ecm_polygon_preparation as physical
    from cells.processes import finite_ecm_polygon_geometry as finite
    from cells.processes import stable_seed_explicit_ecm_partition as constructor
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    require(
        index["kind"] == "cells.partition_trajectory_qualified_initial_index@1",
        "own_qualified_initial_index",
    )
    ids = declarations.comparison_ids(case_id) if refusal_id is None else (refusal_id,)
    arms = []
    for control_id in ids:
        row = index["cases"][case_id]["arms"][control_id]
        incoming, report = Path(row["input"]).read_text(), Path(row["report"]).read_text()
        raw = first._json(incoming)
        r, p = raw["request"], raw["preparation"]
        c = r["constructor_candidate"]
        constructor_request = constructor.Request(
            constructor.freeze(r["constructor_request"]["declaration"]),
            r["constructor_request"]["identity"],
        )
        candidate = constructor.Candidate(
            c["request_identity"],
            finite.Request(**c["partition_request"]),
            finite.Binding(**c["partition_binding"]),
            constructor.freeze(c["construction"]),
            constructor.freeze(c["owner_maps"]),
            constructor.freeze(c["conservation"]),
            constructor.freeze(c["provenance"]),
            c["identity"],
        )
        g = r["geometry_evidence"]
        evidence = initial.GeometryEvidence(
            g["source_review_json"],
            g["prepared_manifest_json"],
            g["input_json"],
            g["report_json"],
            constructor.freeze(g["caller_acceptance"]),
        )
        request = initial.Request(
            constructor_request,
            candidate,
            evidence,
            constructor.freeze(r["declaration"]),
            r["identity"],
        )
        prepared = initial.Preparation(
            p["request_identity"],
            physical.Preparation(**p["physical_preparation"]),
            constructor.freeze(p["conversions"]),
            constructor.freeze(p["initial_snapshot"]),
            constructor.freeze(p["provenance"]),
            p["identity"],
        )
        arms.append(Arm(control_id, request, prepared, incoming, report))
    return bind(
        case_id,
        arms,
        authority,
        role="comparison" if refusal_id is None else "declared_window_refusal_control",
    )


def _boundary(checkpoint, spec, model, np, retain):
    from cells.core.schedule import control_values

    table = control_values(spec, np.asarray([checkpoint.time], dtype=np.float64))
    held = type(table)(*(value[0] for value in table))
    retain(
        "boundary_input",
        dict(
            checkpoint=first.checkpoint_record(checkpoint, np), control=first.array_record(held, np)
        ),
    )
    field = model.field_values(checkpoint.state, held, checkpoint.layout)
    result = dict(
        checkpoint=first.checkpoint_record(checkpoint, np),
        control=first.array_record(held, np),
        field=first.array_record(field, np),
    )
    retain("boundary_field_return", result)
    rhs = model.derivative_from_field(field, checkpoint.layout)
    result["rhs"] = first.array_record(rhs, np)
    retain("boundary_RHS_return", result["rhs"])
    return result, bool(field.converged) and bool(field.rates.valid)


def _binding(request, arm, spec, checkpoint, np):
    return dict(
        kind="cells.partition_trajectory_portable_checkpoint_binding@1",
        request_identity=request.identity,
        case_id=request.case_id,
        control_id=arm.control_id,
        definition_sha256=first.digest(spec.to_dict()),
        initial_request_identity=arm.initial_request.identity,
        initial_preparation_identity=arm.initial_preparation.identity,
        qualified_initial_input_sha256=hashlib.sha256(arm.input_json.encode()).hexdigest(),
        qualified_initial_report_sha256=hashlib.sha256(arm.report_json.encode()).hexdigest(),
        checkpoint=first.checkpoint_record(checkpoint, np),
        full_contract_from_time_zero=True,
        horizon_or_budget_changed_on_restart=False,
    )


def run_segment(request, control_id, directory, *, stop_step=None, restart_directory=None):
    """Persist one bounded segment; never retry, rebase, repair or infer a clock."""
    journal = records.Journal(directory)
    stage, current_step = "metadata_prerequisites", None
    try:
        journal.append("request", first.plain(request))
        journal.append(
            "origin",
            dict(
                pid=os.getpid(),
                parent_pid=os.getppid(),
                executable=sys.executable,
                source=str(Path(__file__).resolve()),
                source_sha256=records.sha(__file__),
            ),
        )
        accepted = gate(first.plain(request.authority))
        rebuilt = bind(
            request.case_id, request.arms, first.plain(request.authority), role=request.role
        )
        require(
            type(request) is Request and first.digest(rebuilt) == first.digest(request),
            "sealed_complete_trajectory_request",
        )
        arm = next(a for a in request.arms if a.control_id == control_id)
        binding = _qualified_arm(request.case_id, arm, first.plain(request.authority), accepted)
        journal.append("qualified_initial_binding", binding)

        # No model/array/solver import is reachable before all receipt checks.
        import jax
        import numpy as np

        from cells.core import surface_tissue_spec as schema
        from cells.core.devices import execution_device
        from cells.core.runner import validate_checkpoint
        from cells.core.schedule import control_values, event_index
        from cells.core.state import Checkpoint
        from cells.core.windows import WindowPolicy, plan_windows
        from cells.io import load_snapshot, write_snapshot
        from cells.models import surface_tissue as model

        definition = arm.initial_preparation.physical_preparation.definition
        journal.append("admitted_definition", first.plain(definition))
        spec = schema.parse(definition)
        stage = "existing_full_clock_and_window_storage_admission"
        checkpoint = None
        if restart_directory is not None:
            saved_path = Path(restart_directory)
            portable = load_snapshot(saved_path)
            checkpoint = portable.checkpoint
            journal.append(
                "loaded_portable_spec_and_checkpoint",
                dict(
                    spec=portable.spec.to_dict(), checkpoint=first.checkpoint_record(checkpoint, np)
                ),
            )
            require(
                first.digest(portable.spec.to_dict()) == first.digest(spec.to_dict()),
                "restart_requires_identical_full_horizon_spec",
            )
            saved = first._json((saved_path / "trajectory_binding.json").read_text())
            checksum = saved.pop("sha256")
            require(
                records.digest(saved) == checksum, "complete_trajectory_checkpoint_binding_checksum"
            )
            require(
                first.digest(saved) == first.digest(_binding(request, arm, spec, checkpoint, np)),
                "restart_carries_every_owner_bit_and_global_clock",
            )
        plan = plan_windows(spec, WindowPolicy(window_steps=1, recording="full"), checkpoint)
        labels = declarations.clock_labels(request.case_id, control_id)
        require(
            len(plan.grid) == len(labels)
            and all(plan.grid[i] == value for i, value in enumerate(labels)),
            "unchanged_actual_global_EventGrid_labels",
        )
        journal.append(
            "existing_window_admission",
            dict(
                start_step=plan.start_step,
                estimated_working_bytes=plan.estimated_working_bytes,
                policy=plan.policy.to_dict(),
                full_end_time_s=spec.experiment.end_time,
                full_max_steps=spec.execution.max_steps,
                declared_max_trace_bytes=spec.execution.max_trace_bytes,
                total_global_steps=len(plan.grid) - 1,
            ),
        )
        device = execution_device("cpu")
        if checkpoint is None:
            state, layout = model.initial_values(spec)
            state, layout = jax.device_put((state, layout), device)
            checkpoint = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
            table = control_values(spec, np.asarray([0.0], dtype=np.float64))
            held = type(table)(*(value[0] for value in table))
            for name, value in (("state", state), ("layout", layout), ("control", held)):
                record = first.array_record(value, np)
                journal.append("initial_" + name, record)
                require(
                    first.digest(record)
                    == first.digest(arm.initial_preparation.initial_snapshot[name]),
                    "exact_qualified_initial_carry:" + name,
                )
        validate_checkpoint(spec, checkpoint, times=plan.grid)
        start = checkpoint.step_index
        stop = len(plan.grid) - 1 if stop_step is None else stop_step
        require(
            type(stop) is int and start <= stop < len(plan.grid), "declared_global_segment_stop"
        )
        boundary, valid = _boundary(checkpoint, spec, model, np, journal.append)
        journal.append("raw_boundary", boundary)
        require(valid, "full_boundary_field_domain")
        journal.append("accepted_boundary", boundary)
        for index in range(start, stop):
            current_step, stage = index, "existing_checked_RK4_step"
            left, right = plan.grid[index], plan.grid[index + 1]
            step = dict(
                index=index,
                left_s=left,
                right_s=right,
                actual_step_s=right - left,
                accepted=False,
                raw={},
            )
            journal.append("step_start", {k: v for k, v in step.items() if k != "raw"})

            def capture(name, value, index=index, step=step):
                value = first.plain(value)
                journal.append("step_raw/" + str(index) + "/" + name, value)
                step["raw"][name] = value

            table = control_values(spec, np.asarray([left, right], dtype=np.float64))
            held, following = (type(table)(*(value[i] for value in table)) for i in (0, 1))
            require(
                all(np.array_equal(a, b) for a, b in zip(held, following, strict=True)),
                "original_controls_held_on_every_interval",
            )
            held = jax.device_put(held, device)
            proposed, _ = first._cells_trial(
                checkpoint.state,
                held,
                checkpoint.layout,
                jax.device_put(np.asarray(right - left, dtype=np.float64), device),
                model,
                jax,
                np,
                capture,
            )
            # Every row is checked against immutable initial ledgers. Adjacent
            # rows additionally preserve the existing dissipation monotonicity.
            pair = model.STATE_TYPE(
                *(
                    np.stack((np.asarray(a), np.asarray(b)))
                    for a, b in zip(checkpoint.state, proposed, strict=True)
                )
            )
            capture("raw_two_boundary_state", first.array_record(pair, np))
            balances = model.balances(
                model.STATE_TYPE(*(np.asarray(v) for v in proposed)),
                model.LAYOUT_TYPE(*(np.asarray(v) for v in checkpoint.layout)),
            )
            capture("raw_integrated_balances", first.array_record(balances, np))
            capture("existing_integrated_checks", model.check_values(pair, spec))
            next_checkpoint = Checkpoint(
                proposed,
                checkpoint.layout,
                float(right),
                index + 1,
                event_index(spec, float(right)),
            )
            boundary, valid = _boundary(next_checkpoint, spec, model, np, journal.append)
            journal.append("raw_boundary", boundary)
            require(valid, "full_endpoint_field_domain")
            validate_checkpoint(spec, next_checkpoint, times=plan.grid)
            require(
                first.digest(boundary["checkpoint"]["layout"])
                == first.digest(arm.initial_preparation.initial_snapshot["layout"]),
                "all_original_layout_owners_carried",
            )
            step["accepted"] = True
            journal.append("completed_step", step)
            journal.append("accepted_boundary", boundary)
            checkpoint = next_checkpoint
            # Only one step, two states and one complete field are retained live.
            del proposed, pair, balances, step, boundary, table, held, following, capture
        require(request.role == "comparison", "declared_storage_refusal_did_not_occur")
        stage = "portable_checkpoint_publication"
        saved_path = Path(directory) / "checkpoint"
        write_snapshot(saved_path, spec, checkpoint)
        binding = _binding(request, arm, spec, checkpoint, np)
        records.write(
            saved_path / "trajectory_binding.json", dict(binding, sha256=records.digest(binding))
        )
        result = dict(
            case_id=request.case_id,
            control_id=control_id,
            request_identity=request.identity,
            start_step=start,
            stop_step=stop,
            final_time_s=checkpoint.time,
            global_final_step=len(plan.grid) - 1,
            horizon_complete=stop == len(plan.grid) - 1,
            checkpoint_directory=str(saved_path.resolve()),
            exact_restart_qualified=False,
            independent_accuracy_qualified=False,
            physics_or_tolerances_changed=False,
        )
        journal.complete(result)
        return result
    except BaseException as error:
        failure = dict(
            type=type(error).__name__,
            reason=str(error),
            stage=getattr(error, "stage", stage),
            code=getattr(error, "code", None),
            detail=first.plain(getattr(error, "detail", None)),
            original=first.plain(getattr(error, "original", None)),
            partial=first.plain(getattr(error, "partial", None)),
            last_attempted_global_step=current_step,
            traceback=traceback.format_exc(),
        )
        try:
            journal.fail(failure)
        except BaseException as capture_error:
            raise first.AdvanceRejected(
                "durable_failure_capture_failed",
                stage=stage,
                original=dict(
                    failure=failure,
                    capture_type=type(capture_error).__name__,
                    capture_reason=str(capture_error),
                ),
            ) from error
        raise
