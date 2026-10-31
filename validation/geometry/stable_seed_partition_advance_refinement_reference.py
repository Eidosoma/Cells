"""Fresh-process independent common-endpoint/control verifier; execution pending."""

import argparse
import hashlib
import importlib.abc
import json
import os
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

INITIAL_SUCCESSOR_MANIFEST_SHA256 = (
    "61679336deda03709b6425f6dc571222a1ffdb6a3e92af01b2378bd3270c115f"
)
INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256 = (
    "84440f74eff19c7a96a275afb81f99ccc0eecc241d484c4cb3c9a13735f1f614"
)
INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256 = (
    "5aad4bce5c8f90020b0bc09786a6e7d4aad11cc71d25b2f1109556f572c788cc"
)
DRAFT_ONLY = False
DENIED = {"cells", "betse", "jax", "jaxlib", "PIL", "torch"}
LAW = "cells_partition_original_endpoint_clock_resource_controls@1"


class NoProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Independent common-endpoint verifier denies " + fullname)


if any(name.split(".")[0] in DENIED for name in sys.modules):
    raise RuntimeError("Independent common-endpoint verifier requires a fresh process")
sys.meta_path.insert(0, NoProduction())

from validation.geometry import (  # noqa: E402 - fresh-process denial is installed first
    stable_seed_partition_advance_refinement_declarations as declarations,
)
from validation.geometry import (  # noqa: E402 - helper imports follow the same guard
    stable_seed_partition_advance_refinement_initial_worker as metadata,
)


class ComparisonRejected(ValueError):
    code = "common_endpoint_contract"
    stage = "independent_common_endpoint_comparison"


def need(value, reason):
    if not value:
        raise ComparisonRejected(reason)


def gate(payload):
    if (
        DRAFT_ONLY
        or INITIAL_SUCCESSOR_MANIFEST_SHA256 is None
        or INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256 is None
        or INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256 is None
    ):
        raise ValueError("Separately qualified initial clock/resource successor is pending")
    authority = payload["request"]["authority"]
    need(
        hashlib.sha256(authority["manifest_json"].encode()).hexdigest()
        == INITIAL_SUCCESSOR_MANIFEST_SHA256,
        "exact initial successor manifest",
    )
    need(
        hashlib.sha256(authority["source_review_json"].encode()).hexdigest()
        == INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256,
        "exact initial successor source review",
    )
    need(
        hashlib.sha256(authority["numerical_qualification_json"].encode()).hexdigest()
        == INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256,
        "exact initial successor qualification",
    )


def authenticate(payload, partial):
    gate(payload)
    request = payload["request"]
    need(request["role"] == "comparison", "original budget refusals never become comparison passes")
    case = request["case_id"]
    arms = request["arms"]
    ids = declarations.comparison_ids(case)
    need(tuple(row["control_id"] for row in arms) == ids, "complete explicit comparison profile")
    need(
        request["identity"]
        == metadata.digest([LAW, case, arms, request["authority"], request["role"]]),
        "complete common-endpoint request seal",
    )
    manifest = metadata.parse(request["authority"]["manifest_json"])
    definitions = {}
    inputs = []
    partial["initial_arm_authentication"] = inputs
    for arm in arms:
        incoming = metadata.parse(arm["input_json"])
        report = metadata.parse(arm["report_json"])
        record = dict(
            control_id=arm["control_id"],
            original_input=incoming,
            original_report=report,
            partial={},
        )
        inputs.append(record)
        initial_request, _, _ = metadata.authenticate(incoming, record["partial"])
        need(
            incoming["case_id"] == case and incoming["numerical_control_id"] == arm["control_id"],
            "individual clock/control identity",
        )
        need(
            metadata.digest(initial_request) == metadata.digest(arm["initial_request"])
            and metadata.digest(incoming["preparation"])
            == metadata.digest(arm["initial_preparation"]),
            "complete original independently checked initial preparation",
        )
        need(
            report["status"] == "complete"
            and report["baseline_passed"] is True
            and report["candidate_passed"] is True
            and report["control_detected"] is False
            and report["controls"] == []
            and not report.get("runtime_capture_failed", False)
            and not report.get("failure_capture_failed", False)
            and report["baseline"]["full_node_physics_and_RHS_verified"] is True,
            "each clock has its own complete initial positive check",
        )
        runtime = report["runtime_origin"]
        rel = "validation/geometry/stable_seed_partition_advance_refinement_initial_worker.py"
        need(
            runtime["source_sha256"] == manifest["file_sha256"]["source/" + rel]
            and runtime["input_sha256"] == hashlib.sha256(arm["input_json"].encode()).hexdigest()
            and runtime["production_imports_denied"] is True
            and runtime["production_modules_loaded"] == []
            and runtime["file_errors"] == {}
            and runtime["mapped_file_errors"] == [],
            "actual independent initial control-worker origin",
        )
        definitions[arm["control_id"]] = metadata.parse(
            arm["initial_preparation"]["physical_preparation"]["definition_json"]
        )
    declarations.same_physical_definition(definitions, ids)
    return request, definitions


def compare(candidate, request, target, definitions, partial):
    import numpy as np

    from validation.geometry import stable_seed_partition_advance_refinement_dynamics as dynamics
    from validation.geometry import (
        stable_seed_partition_physiology_bridge_initial_reference as codec,
    )

    need(
        type(candidate) is dict
        and set(candidate)
        == {"request_identity", "case_id", "arm_records", "provenance", "identity"},
        "complete common-endpoint result",
    )
    need(
        candidate["request_identity"] == request["identity"]
        and candidate["case_id"] == request["case_id"],
        "same authenticated case/request",
    )
    need(
        candidate["identity"]
        == metadata.digest(
            [
                LAW,
                candidate["request_identity"],
                candidate["case_id"],
                candidate["arm_records"],
                candidate["provenance"],
            ]
        ),
        "complete result seal",
    )
    expected_provenance = dict(
        kind="cells.common_original_endpoint_clock_control_candidate@1",
        law=LAW,
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
    need(
        metadata.digest(candidate["provenance"]) == metadata.digest(expected_provenance),
        "complete scope/physics/storage provenance",
    )
    ids = declarations.comparison_ids(request["case_id"])
    need(set(candidate["arm_records"]) == set(ids), "complete three-arm result")
    context = target["binding"]
    errors, charge_errors, reports = [], [], []
    partial["completed_arm_comparisons"] = reports

    def decoded(record, name, shape):
        value = codec.decode(record, label=name)
        need(value.dtype.str == "<f8" and value.shape == shape, name + ": exact float64 axes")
        return value

    def check_field_rhs(state, time, field_record, rhs_record, label):
        raw_state = dynamics.flatten(context, state)
        expected = dynamics.field_snapshot(context, raw_state, time, partial)
        # Same-point field/RHS budgets remain the original qualified stage budgets.
        rows = []
        try:
            codec.compare_arrays(field_record, expected["field"], label="field", rows=rows)
        except codec.SnapshotRejected as error:
            raise ComparisonRejected(label + ": complete independent field/RHS") from error
        need(set(rhs_record) == set(expected["rhs"]), "complete twelve-field same-point RHS")
        for name, target_rhs in expected["rhs"].items():
            actual_rhs = codec.decode(rhs_record[name], label=label + "/RHS/" + name)
            need(
                actual_rhs.dtype.str == np.asarray(target_rhs).dtype.str
                and actual_rhs.shape == np.asarray(target_rhs).shape,
                label + ": complete RHS dtype/axes",
            )
            atol = 3e-23 if name.endswith("_C") else 3e-12
            need(
                np.all(np.abs(actual_rhs - target_rhs) <= atol + 3e-10 * np.abs(target_rhs)),
                label + ": original unit-specific same-point RHS budget",
            )
            rows.append(dict(field=label + "/RHS/" + name, complete_field_verified=True))
        values = {
            name: (
                {
                    key: codec.decode(value, label=label + "/rates/" + key)
                    for key, value in item.items()
                }
                if name == "rates"
                else codec.decode(item, label=label + "/" + name)
            )
            for name, item in field_record.items()
        }
        raw = dynamics.stage(context, raw_state, time)
        try:
            dynamics.electrical.check(
                raw, SimpleNamespace(**dict(values, rates=SimpleNamespace(**values["rates"])))
            )
        except AssertionError as error:
            raise ComparisonRejected(
                label + ": scalar charge/current/material/energy checks"
            ) from error
        charge = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
        bound = 3e-25 + 2e-12 * np.maximum(
            np.abs(charge), np.abs(values["capacitor_node_charge_C"])
        )
        norm = np.max(np.abs(values["charge_residual_C"]) / bound)
        need(
            np.isclose(values["charge_normalized"], norm, rtol=3e-10, atol=1e-14),
            label + ": exact charge-normalized readback link",
        )
        scale = max(
            float(np.max(np.abs(values["rates"][key + "_current_A"]), initial=0.0))
            for key in ("face", "junction")
        )
        norm = np.max(np.abs(values["component_current_residual_A"]), initial=0.0) / (
            1e-23 + 2e-12 * scale
        )
        need(
            np.isclose(values["current_normalized"], norm, rtol=3e-10, atol=1e-14),
            label + ": exact current-normalized readback link",
        )
        return rows

    for arm in request["arms"]:
        control_id = arm["control_id"]
        result = candidate["arm_records"][control_id]
        need(
            set(result)
            == {
                "control_id",
                "initial_request_identity",
                "initial_preparation_identity",
                "definition",
                "times",
                "history",
                "checkpoint",
                "boundary_fields_RHS",
                "checkpoints",
                "completed_steps",
                "complete_common_endpoint",
                "qualified_initial_input_sha256",
                "qualified_initial_report_sha256",
            },
            "complete arm fields",
        )
        need(
            result["control_id"] == control_id and result["complete_common_endpoint"] is True,
            "complete original endpoint per arm",
        )
        need(
            metadata.digest(result["definition"]) == metadata.digest(definitions[control_id]),
            "unchanged admitted per-arm definition",
        )
        need(
            result["initial_request_identity"] == arm["initial_request"]["identity"]
            and result["initial_preparation_identity"] == arm["initial_preparation"]["identity"]
            and result["qualified_initial_input_sha256"]
            == hashlib.sha256(arm["input_json"].encode()).hexdigest()
            and result["qualified_initial_report_sha256"]
            == hashlib.sha256(arm["report_json"].encode()).hexdigest(),
            "each result bound to its own qualified initial input",
        )
        times = declarations.clock_labels(control_id)
        need(
            result["times"] == times and result["checkpoint"]["time_s"] == 1e-6,
            "exact original grid and common endpoint",
        )
        history = result["history"]
        need(set(history) == set(context["shapes"]), "complete twelve-field history")
        arrays = {
            key: decoded(history[key], control_id + "/" + key, (len(times), *shape))
            for key, shape in context["shapes"].items()
        }
        amount_error, charge_error = 0.0, 0.0
        checks = []
        record = dict(
            control_id=control_id,
            times=times,
            checks=checks,
            amount_energy_max_error=None,
            electrode_charge_max_error_C=None,
        )
        reports.append(record)
        for i, time in enumerate(times):
            target_state = target["states"][time]
            for name, values in arrays.items():
                actual = values[i]
                expected = target_state[name]
                atol = 3e-25 if name.endswith("_C") else 2e-11
                need(
                    np.all(np.abs(actual - expected) <= atol + 3e-9 * np.abs(expected)),
                    control_id + "/" + name + ": original independent trajectory budget",
                )
                if i == len(times) - 1:
                    error = float(np.max(np.abs(actual - expected), initial=0))
                    if name.endswith("_C"):
                        charge_error = max(charge_error, error)
                    else:
                        amount_error = max(amount_error, error)
        need(
            len(result["checkpoints"]) == len(times)
            and len(result["completed_steps"]) == len(times) - 1
            and len(result["boundary_fields_RHS"]) == len(times) - 1,
            "every accepted prefix and step retained",
        )
        need(
            metadata.digest(result["checkpoint"]) == metadata.digest(result["checkpoints"][-1]),
            "complete final/prefix checkpoint link",
        )
        for i, checkpoint in enumerate(result["checkpoints"]):
            need(
                checkpoint["time_s"] == times[i]
                and checkpoint["step_index"] == i
                and checkpoint["event_index"] == 0,
                "complete checkpoint clock identity",
            )
            need(
                metadata.digest(checkpoint["layout"])
                == metadata.digest(arm["initial_preparation"]["initial_snapshot"]["layout"]),
                "unchanged complete layout",
            )
            need(set(checkpoint["state"]) == set(arrays), "complete checkpoint state")
            for key, shape in context["shapes"].items():
                need(
                    np.array_equal(decoded(checkpoint["state"][key], key, shape), arrays[key][i]),
                    "checkpoint/history readback:" + key,
                )
        for i, step in enumerate(result["completed_steps"]):
            need(
                step["index"] == i
                and step["left_s"] == times[i]
                and step["right_s"] == times[i + 1]
                and step["actual_step_s"] == times[i + 1] - times[i]
                and step["accepted"] is True,
                "every actual Cells interval retained",
            )
            kernel = step["raw"]["cells_checked_kernel_return"]
            accepted = codec.decode(kernel["accepted_domain"], label="Cells checked status")
            need(
                accepted.dtype.kind == "b" and accepted.shape == () and bool(accepted),
                "Cells stage domain accepted",
            )
            trials = kernel["trials"]
            need(
                len(trials) == 5
                and [row["role"] for row in trials]
                == ["k1", "k2", "k3", "k4", "unmasked_endpoint"],
                "complete unmasked trial roster",
            )
            need(
                metadata.digest(step["raw"]["cells_trial_roster"]) == metadata.digest(trials),
                "completed trial roster retained without truncation",
            )
            coefficients = (0.0, 0.5, 0.5, 1.0)
            slopes = []
            for j, row in enumerate(trials):
                fields = {
                    "index",
                    "role",
                    "state",
                    "control",
                    "control_domain_return",
                    "rhs_evaluated",
                }
                if j < 4:
                    fields |= {"field", "rhs"}
                need(set(row) == fields and row["index"] == j, "complete Cells trial fields")
                need(set(row["state"]) == set(context["shapes"]), "complete trial state inventory")
                need(
                    metadata.digest(row["control"])
                    == metadata.digest(arm["initial_preparation"]["initial_snapshot"]["control"]),
                    "unchanged explicitly held control in every trial",
                )
                status = codec.decode(row["control_domain_return"], label="control-aware domain")
                need(
                    status.dtype.kind == "b" and status.shape == () and bool(status),
                    "actual control-aware guard passed",
                )
            need(trials[-1]["rhs_evaluated"] is False, "endpoint guard is not a cached RHS")
            for j, row in enumerate(trials[:4]):
                need(row["rhs_evaluated"] is True, "complete existing Cells trial RHS")
                state = {
                    key: decoded(row["state"][key], key, shape)
                    for key, shape in context["shapes"].items()
                }
                checks.extend(
                    check_field_rhs(
                        state,
                        times[i] + coefficients[j] * (times[i + 1] - times[i]),
                        row["field"],
                        row["rhs"],
                        control_id + "/trial" + str(i) + "/" + str(j),
                    )
                )
                slopes.append(
                    {
                        key: decoded(row["rhs"][key], key, shape)
                        for key, shape in context["shapes"].items()
                    }
                )
            # Independently link the supplied trial records to the existing RK4 arithmetic.
            h = times[i + 1] - times[i]
            for name in arrays:
                start = arrays[name][i]
                expected_trials = (
                    start,
                    start + 0.5 * h * slopes[0][name],
                    start + 0.5 * h * slopes[1][name],
                    start + h * slopes[2][name],
                )
                for j, expected in enumerate(expected_trials):
                    actual = codec.decode(trials[j]["state"][name], label="RK4 trial link")
                    need(np.array_equal(actual, expected), "complete supplied RK4 trial arithmetic")
                endpoint = start + (h / 6.0) * (
                    slopes[0][name] + 2 * slopes[1][name] + 2 * slopes[2][name] + slopes[3][name]
                )
                need(
                    np.array_equal(endpoint, arrays[name][i + 1]),
                    "complete supplied RK4 endpoint arithmetic",
                )
                need(
                    np.array_equal(
                        codec.decode(trials[-1]["state"][name], label="unmasked endpoint"),
                        arrays[name][i + 1],
                    ),
                    "unmasked endpoint/state link",
                )
                need(
                    np.array_equal(
                        codec.decode(kernel["returned_state"][name], label="Cells kernel return"),
                        arrays[name][i + 1],
                    ),
                    "complete Cells returned state link",
                )
            boundary = result["boundary_fields_RHS"][i]
            need(boundary["time_s"] == times[i + 1], "endpoint readout at accepted boundary")
            state = {key: arrays[key][i + 1] for key in arrays}
            checks.extend(
                check_field_rhs(
                    state,
                    times[i + 1],
                    boundary["field"],
                    boundary["rhs"],
                    control_id + "/endpoint" + str(i),
                )
            )
        endpoint_phi = codec.decode(
            result["boundary_fields_RHS"][-1]["field"]["potential_V"], label="common endpoint field"
        )
        need(
            np.all(np.abs(endpoint_phi - target["samples"][1e-6]["field"]["potential_V"]) <= 2e-8),
            "original independent trajectory endpoint voltage budget",
        )
        record["amount_energy_max_error"] = amount_error
        record["electrode_charge_max_error_C"] = charge_error
        errors.append(amount_error)
        charge_errors.append(charge_error)
    need(errors[-1] <= max(errors[0] * 0.2, 3e-13), "original amount/energy refinement criterion")
    need(
        charge_errors[-1] <= max(charge_errors[0] * 0.2, 3e-27),
        "original electrode-charge refinement criterion",
    )
    return dict(
        passed=True,
        arms=reports,
        amount_energy_errors=errors,
        electrode_charge_errors_C=charge_errors,
        refinement_error_limit=0.2,
        amount_energy_floor=3e-13,
        electrode_charge_floor_C=3e-27,
        roundoff_limited_amount_energy=errors[0] <= 3e-13,
        roundoff_limited_charge=charge_errors[0] <= 3e-27,
        fourth_order_claimed=False,
        physical_cases=1,
        numerical_controls=2,
        resource_controls_are_not_cases=True,
    )


def evaluate(payload):
    partial = dict(stage="initial_successor_qualification", original_payload=payload)
    try:
        request, definitions = authenticate(payload, partial)
        from validation.geometry import (
            stable_seed_partition_advance_refinement_dynamics as dynamics,
        )

        ids = declarations.comparison_ids(request["case_id"])
        sample_times = sorted({time for arm in ids for time in declarations.clock_labels(arm)})
        partial["stage"] = "independent_common_endpoint"
        target = dynamics.integrate_common_endpoint(definitions[ids[0]], sample_times, partial)
        partial["completed_independent_target"] = target
        baseline = compare(payload["candidate"], request, target, definitions, partial)
        partial["baseline_verification"] = baseline
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=True,
            control_detected=False,
            controls=[],
            baseline=baseline,
            reference=target,
            raw_partial=partial,
        )
    except ComparisonRejected as error:
        return dict(
            status="baseline_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            type=type(error).__name__,
            code=error.code,
            stage=error.stage,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            type=type(error).__name__,
            reason=str(error),
            traceback=traceback.format_exc(),
            raw_partial=partial,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(metadata.parse(args.input.read_text()))
    try:
        runtime = metadata.runtime_inventory(args.input)
        runtime["source"] = str(Path(__file__).resolve())
        runtime["source_sha256"] = metadata.sha(__file__)
        runtime["files"][runtime["source"]] = runtime["source_sha256"]
        report["runtime_origin"] = runtime
        if (
            runtime["file_errors"]
            or runtime["mapped_file_errors"]
            or runtime["production_modules_loaded"]
        ):
            report["runtime_capture_failed"] = True
    except Exception as error:
        report["runtime_capture_failed"] = True
        report["runtime_capture_failure"] = dict(type=type(error).__name__, reason=str(error))
    errors = []
    captured = metadata.safe(report, errors=errors)
    if errors:
        captured["failure_capture_failed"] = True
        captured["failure_capture_errors"] = errors
        captured["baseline_passed"] = captured["candidate_passed"] = False
    with args.output.open("x") as stream:
        json.dump(captured, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not captured["baseline_passed"] or captured.get("runtime_capture_failed", False) or errors:
        raise SystemExit(2 if captured["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
