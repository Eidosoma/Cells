"""Unfrozen independent trajectory accuracy worker; exact replay is separate."""

import argparse
import hashlib
import importlib.abc
import os
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

DRAFT_ONLY = True
DENIED = {"cells", "betse", "jax", "jaxlib", "PIL", "torch"}
LAW = "cells_partition_full_horizon_checked_trajectory_exact_restart@1"


class NoProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Independent trajectory worker denies " + fullname)


if any(name.split(".")[0] in DENIED for name in sys.modules):
    raise RuntimeError("Independent trajectory accuracy requires a fresh nonproduction process")
sys.meta_path.insert(0, NoProduction())

from validation.geometry import (  # noqa: E402 - denial is installed first
    stable_seed_partition_trajectory_authority as authority_gate,  # noqa: E402
)
from validation.geometry import (  # noqa: E402 - metadata follows the denial guard
    stable_seed_partition_trajectory_declarations as declarations,  # noqa: E402
)
from validation.geometry import (  # noqa: E402 - no production imports
    stable_seed_partition_trajectory_initial_worker as metadata,  # noqa: E402
)
from validation.geometry import stable_seed_partition_trajectory_records as records  # noqa: E402


class ComparisonRejected(ValueError):
    code = "partition_trajectory_independent_contract"
    stage = "independent_full_horizon_accuracy"


def need(value, reason):
    if not value:
        raise ComparisonRejected(reason)


def integrated_accounting(context, state, field, previous, initial_field, np):
    """Independent incidence sums and stable free-energy changes on original owners."""
    import math

    p = context["layout"]
    local = state["amount_increment"].copy()
    outside = state["extracellular_amount_increment"].copy() - state["reservoir_supplied"]
    for k, (cell, bath) in enumerate(zip(p["membrane_cell"], p["membrane_outside"], strict=True)):
        local[:, cell] += state["membrane_transferred"][:, k]
        outside[:, bath] -= state["membrane_transferred"][:, k]
    for kind, amount, target in (
        ("junction", state["junction_transferred"], local),
        ("face", state["face_transferred"], outside),
    ):
        for k, (sender, receiver) in enumerate(
            zip(p[kind + "_sender"], p[kind + "_receiver"], strict=True)
        ):
            target[:, sender] += amount[:, k]
            target[:, receiver] -= amount[:, k]
    total = (
        state["amount_increment"].sum(axis=1)
        + state["extracellular_amount_increment"].sum(axis=1)
        - state["reservoir_supplied"].sum(axis=1)
    )
    chemical_terms = []
    for key, anchor, volume in (
        ("amount_increment", context["ai"], context["vi"]),
        ("extracellular_amount_increment", context["ao"], context["vo"]),
    ):
        for i in range(anchor.shape[0]):
            for j in range(anchor.shape[1]):
                a, delta, v = float(anchor[i, j]), float(state[key][i, j]), float(volume[j])
                need(a > 0 and a + delta > 0, "Positive physical inventories throughout trajectory")
                chemical_terms.append(
                    delta * (math.log(a / v) - 1) + (a + delta) * math.log1p(delta / a)
                )
    chemical = (
        1e-3
        * context["raw"]["model"]["temperature_K"]
        * float(context["gas_constant"])
        * math.fsum(chemical_terms)
    )
    volt = field["rates"]["membrane_voltage_V"]
    initial_volt = initial_field["rates"]["membrane_voltage_V"]
    electric = 0.5e12 * math.fsum(
        float(cap) * float(v - v0) * float(v + v0)
        for cap, v, v0 in zip(p["membrane_capacitance"], volt, initial_volt, strict=True)
    )
    dissipated = math.fsum(
        float(value)
        for kind in ("membrane", "junction", "face")
        for value in state[kind + "_dissipated_energy_pJ"]
    )
    work = sum(float(np.sum(state[key])) for key in ("reservoir_work_pJ", "electrode_work_pJ"))
    charges = np.r_[context["qi"], context["qo"]] + float(context["faraday"]) * 1e-15 * np.sum(
        np.asarray(p["valence"])
        * np.c_[state["amount_increment"], state["extracellular_amount_increment"]],
        axis=0,
    )
    charge = field["capacitor_node_charge_C"] - charges
    # Original callers have finite sealed baths and no imposed source work.
    zero_source_keys = (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    )
    source_checks = {
        key: float(np.max(np.abs(state[key]), initial=0.0)) for key in zero_source_keys
    }
    material_tol = np.asarray(context["raw"]["execution"]["material_balance_atol_fmol"])
    if material_tol.ndim == 0:
        material_tol = np.full(local.shape[0], material_tol)
    need(
        np.all(np.abs(local) <= material_tol[:, None])
        and np.all(np.abs(outside) <= material_tol[:, None])
        and np.all(np.abs(total) <= material_tol),
        "Original local and global material ledger budgets",
    )
    need(
        np.all(np.abs(charge) <= 3e-25 + 2e-12 * np.abs(charges)),
        "Original integrated node charge budget",
    )
    need(
        source_checks["reservoir_supplied"] <= float(np.min(material_tol))
        and source_checks["electrode_charge_transferred_C"] <= 3e-25
        and source_checks["reservoir_work_pJ"] <= 3e-12
        and source_checks["electrode_work_pJ"] <= 3e-12,
        "Complete sealed finite-ECM charge and work ledgers",
    )
    need(
        abs(chemical + electric + dissipated - work) <= 2e-8,
        "Original integrated stored energy, heat and work budget",
    )
    for kind in ("membrane", "junction", "face"):
        key = kind + "_dissipated_energy_pJ"
        need(np.min(state[key], initial=0.0) >= -1e-12, "Original nonnegative dissipation budget")
        if previous is not None:
            need(
                np.min(state[key] - previous[key], initial=0.0) >= -1e-12,
                "Original adjacent dissipation budget",
            )
    return dict(
        local=local,
        outside=outside,
        total=total,
        charge=charge,
        source_checks=source_checks,
        chemical_change_pJ=chemical,
        capacitor_change_pJ=electric,
        dissipated_pJ=dissipated,
        work_pJ=work,
        energy_balance_pJ=chemical + electric + dissipated - work,
    )


def check_step(step, previous, times, arm, context, partial, journal, np, codec, dynamics):
    i = step["index"]
    need(
        step["accepted"] is True
        and step["left_s"] == times[i]
        and step["right_s"] == times[i + 1]
        and step["actual_step_s"] == times[i + 1] - times[i],
        "Every actual adjacent global interval retained",
    )
    need(previous["checkpoint"]["step_index"] == i, "Step starts at the preceding accepted state")
    kernel = step["raw"]["cells_checked_kernel_return"]
    accepted = codec.decode(kernel["accepted_domain"], label="Cells checked domain status")
    need(
        accepted.dtype.kind == "b" and accepted.shape == () and bool(accepted),
        "Existing checked RK4 accepted",
    )
    trials = kernel["trials"]
    need(
        len(trials) == 5
        and [row["role"] for row in trials] == ["k1", "k2", "k3", "k4", "unmasked_endpoint"],
        "Full unmasked trial roster",
    )
    need(
        metadata.digest(step["raw"]["cells_trial_roster"]) == metadata.digest(trials),
        "Untruncated raw trial roster",
    )
    slopes = []
    for j, row in enumerate(trials):
        fields = {"index", "role", "state", "control", "control_domain_return", "rhs_evaluated"}
        if j < 4:
            fields |= {"field", "rhs"}
        need(
            set(row) == fields
            and row["index"] == j
            and set(row["state"]) == set(context["shapes"]),
            "Complete twelve-field trial and role",
        )
        need(
            metadata.digest(row["control"])
            == metadata.digest(arm["initial_preparation"]["initial_snapshot"]["control"]),
            "Only original declared held controls",
        )
        domain = codec.decode(row["control_domain_return"], label="Control-aware domain status")
        need(
            domain.dtype.kind == "b" and domain.shape == () and bool(domain),
            "Actual control-aware guard passed",
        )
        need(row["rhs_evaluated"] is (j < 4), "Endpoint guard cannot substitute a cached RHS")
        if j < 4:
            state = {key: codec.decode(value, label=key) for key, value in row["state"].items()}
            field_checks = check_field_rhs(
                state,
                times[i] + (0.0, 0.5, 0.5, 1.0)[j] * (times[i + 1] - times[i]),
                row["field"],
                row["rhs"],
                arm["control_id"] + "/trial/" + str(i) + "/" + str(j),
                context,
                partial,
                np,
                codec,
                dynamics,
            )
            journal.append(
                "same_point_trial_field_RHS_checks",
                dict(global_step=i, trial=j, checks=field_checks),
            )
            slopes.append(
                {key: codec.decode(value, label=key) for key, value in row["rhs"].items()}
            )
    endpoint = {}
    h = times[i + 1] - times[i]
    for key, shape in context["shapes"].items():
        start = codec.decode(previous["checkpoint"]["state"][key], label="Accepted start/" + key)
        need(
            start.shape == shape and start.dtype.str == "<f8",
            "Full original state axes and precision",
        )
        targets = (
            start,
            start + 0.5 * h * slopes[0][key],
            start + 0.5 * h * slopes[1][key],
            start + h * slopes[2][key],
        )
        for j, target in enumerate(targets):
            need(
                np.array_equal(codec.decode(trials[j]["state"][key], label=key), target),
                "Original supplied RK4 trial arithmetic",
            )
        expected = start + (h / 6.0) * (
            slopes[0][key] + 2 * slopes[1][key] + 2 * slopes[2][key] + slopes[3][key]
        )
        endpoint[key] = codec.decode(kernel["returned_state"][key], label=key)
        need(
            np.array_equal(endpoint[key], expected)
            and np.array_equal(codec.decode(trials[-1]["state"][key], label=key), expected),
            "Original unmasked RK4 endpoint arithmetic",
        )
        pair = codec.decode(
            step["raw"]["raw_two_boundary_state"][key], label="Two-boundary accounting input"
        )
        need(
            pair.shape == (2, *shape)
            and np.array_equal(pair[0], start)
            and np.array_equal(pair[1], expected),
            "Every adjacent accounting input retained",
        )
    return endpoint


def compare_arm(directory, request, arm, definition, target, journal, partial, np, codec, dynamics):
    from validation.geometry import stable_seed_partition_trajectory_restart as restart_check

    case_id, control_id = request["case_id"], arm["control_id"]
    times = declarations.clock_labels(case_id, control_id)
    need(
        len(times) <= target["max_declared_samples"], "Bounded declared full-horizon sample roster"
    )
    context = target["binding"]
    actual_origin = restart_check.runtime(directory)
    journal.append("actual_candidate_process_origin", actual_origin)
    context["gas_constant"], context["faraday"] = dynamics.R, dynamics.F
    expected_layout = arm["initial_preparation"]["initial_snapshot"]["layout"]
    previous, previous_state, pending, raw_boundary = None, None, None, None
    step_raw = {}
    boundaries, steps, source_pid = 0, 0, None
    errors = dict(amount_energy=0.0, electrode_charge_C=0.0, endpoint_voltage_V=None)
    initial_field = dynamics.field_snapshot(
        context, target["independent_initial_state"], 0.0, partial
    )["field"]
    for name, value in records.entries(directory):
        if name == "request":
            need(
                metadata.digest(value) == metadata.digest(request),
                "Exact candidate request in durable journal",
            )
        elif name == "origin":
            need(
                type(value["pid"]) is int and value["pid"] > 0 and value["pid"] != os.getpid(),
                "Candidate and accuracy worker are separate processes",
            )
            need(
                value["pid"] == actual_origin["pid"]
                and value["parent_pid"] == actual_origin["parent_pid"]
                and actual_origin["files"].get(value["source"]) == value["source_sha256"],
                "Candidate journal binds the actual child and loaded driver bytes",
            )
            source_pid = value["pid"]
        elif name == "admitted_definition":
            need(
                metadata.digest(value) == metadata.digest(definition),
                "Unchanged full-horizon admitted definition",
            )
        elif name == "step_start":
            need(
                pending is None and not step_raw and value["index"] == steps,
                "Step attempts have exact original order",
            )
        elif name.startswith("step_raw/"):
            _, index, key = name.split("/", 2)
            need(
                int(index) == steps and key not in step_raw,
                "Every raw step result occurs exactly once",
            )
            step_raw[key] = value
        elif name == "completed_step":
            need(
                previous is not None
                and pending is None
                and metadata.digest(step_raw) == metadata.digest(value["raw"]),
                "All completed-step raw evidence links to durable writes",
            )
            pending = check_step(
                value, previous, times, arm, context, partial, journal, np, codec, dynamics
            )
            steps += 1
            step_raw = {}
        elif name == "raw_boundary":
            raw_boundary = value
        elif name == "accepted_boundary":
            need(
                raw_boundary is not None
                and metadata.digest(raw_boundary) == metadata.digest(value),
                "Every accepted boundary retains its raw return",
            )
            checkpoint = value["checkpoint"]
            need(
                checkpoint["step_index"] == boundaries
                and checkpoint["time_s"] == times[boundaries]
                and checkpoint["event_index"] == 0
                and metadata.digest(checkpoint["layout"]) == metadata.digest(expected_layout),
                "Complete global clock, event and original owner identity",
            )
            need(
                set(checkpoint["state"]) == set(context["shapes"]),
                "Complete twelve-state checkpoint",
            )
            state = {
                key: codec.decode(value, label=key) for key, value in checkpoint["state"].items()
            }
            for key, shape in context["shapes"].items():
                need(
                    state[key].shape == shape and state[key].dtype.str == "<f8",
                    "Complete state precision and axes",
                )
            if boundaries == 0:
                need(
                    metadata.digest(checkpoint["state"])
                    == metadata.digest(arm["initial_preparation"]["initial_snapshot"]["state"]),
                    "True independently qualified original initial state",
                )
            else:
                need(
                    pending is not None
                    and all(np.array_equal(state[key], pending[key]) for key in state),
                    "Accepted endpoint links to actual checked step",
                )
            time = times[boundaries]
            target_state = dynamics.unpack(context, target["solution"].sol(time))
            differences = {}
            for key, actual in state.items():
                expected = target_state[key]
                need(
                    np.all(
                        np.abs(actual - expected)
                        <= (3e-25 if key.endswith("_C") else 2e-11) + 3e-9 * np.abs(expected)
                    ),
                    "Original unit-specific independent trajectory accuracy",
                )
                differences[key] = float(np.max(np.abs(actual - expected), initial=0.0))
                if boundaries == len(times) - 1:
                    which = "electrode_charge_C" if key.endswith("_C") else "amount_energy"
                    errors[which] = max(errors[which], differences[key])
            checks = check_field_rhs(
                state,
                time,
                value["field"],
                value["rhs"],
                control_id + "/boundary/" + str(boundaries),
                context,
                partial,
                np,
                codec,
                dynamics,
            )
            expected_point = dynamics.field_snapshot(
                context, dynamics.flatten(context, state), time, partial
            )
            accounting = integrated_accounting(
                context, state, expected_point["field"], previous_state, initial_field, np
            )
            journal.append(
                "complete_boundary_accuracy",
                dict(
                    control_id=control_id,
                    global_step=boundaries,
                    time_s=time,
                    independent_target_state=target_state,
                    full_state_errors=differences,
                    field_RHS_checks=checks,
                    integrated_accounting=accounting,
                ),
            )
            target["spool"].flush()
            if boundaries == len(times) - 1:
                endpoint_target = dynamics.field_snapshot(
                    context, target["solution"].sol(time), time, partial
                )
                phi = codec.decode(
                    value["field"]["potential_V"], label="Full trajectory endpoint potential"
                )
                errors["endpoint_voltage_V"] = float(
                    np.max(np.abs(phi - endpoint_target["field"]["potential_V"]), initial=0.0)
                )
                need(
                    errors["endpoint_voltage_V"] <= 2e-8,
                    "Original independent endpoint voltage budget",
                )
            previous, previous_state, pending, raw_boundary = value, state, None, None
            boundaries += 1
    need(
        source_pid is not None
        and boundaries == len(times)
        and steps == len(times) - 1
        and pending is None
        and not step_raw,
        "Complete uninterrupted original-prefix inventory to full horizon",
    )
    return dict(
        control_id=control_id,
        source_pid=source_pid,
        boundaries=boundaries,
        steps=steps,
        errors=errors,
    )


def evaluate(payload, directory):
    journal = records.Journal(directory)
    partial = {}
    target = None
    try:
        journal.append("original_input", payload)
        request, definitions = authenticate(payload, journal)
        # Scientific imports are below all source, geometry and numerical receipts.
        import numpy as np

        from validation.geometry import (
            stable_seed_partition_physiology_bridge_initial_reference as codec,
        )
        from validation.geometry import stable_seed_partition_trajectory_dynamics as dynamics

        plan = declarations.case(request["case_id"])
        ids = declarations.comparison_ids(request["case_id"])
        target = dynamics.integrate_trajectory(definitions[ids[0]], plan, journal, partial)
        reports = []
        for arm in request["arms"]:
            reports.append(
                compare_arm(
                    payload["arm_directories"][arm["control_id"]],
                    request,
                    arm,
                    definitions[arm["control_id"]],
                    target,
                    journal,
                    partial,
                    np,
                    codec,
                    dynamics,
                )
            )
            journal.append("completed_arm_accuracy", reports[-1])
        errors = [row["errors"]["amount_energy"] for row in reports]
        charges = [row["errors"]["electrode_charge_C"] for row in reports]
        need(
            errors[-1] <= max(errors[0] * 0.2, 3e-13),
            "Original amount and energy refinement criterion",
        )
        need(
            charges[-1] <= max(charges[0] * 0.2, 3e-27),
            "Original electrode-charge refinement criterion",
        )
        target["spool"].flush()
        result = dict(
            passed=True,
            case_id=request["case_id"],
            arms=reports,
            amount_energy_errors=errors,
            electrode_charge_errors_C=charges,
            refinement_error_limit=0.2,
            amount_energy_floor=3e-13,
            electrode_charge_floor_C=3e-27,
            roundoff_limited_amount_energy=errors[0] <= 3e-13,
            roundoff_limited_charge=charges[0] <= 3e-27,
            fourth_order_claimed=False,
            restart_equality_supplies_accuracy_credit=False,
            original_initial_epoch_s=0.0,
            endpoint_s=plan["end_time_s"],
            new_physical_cases=0,
        )
        journal.append("runtime", runtime_identity(payload))
        journal.complete(result)
        return result
    except BaseException as error:
        if target is not None:
            target["spool"].flush()
        # The mutable trial is already spooled by integrate_trajectory on failures.
        # No history or scientific partial is summarized away.
        captured = {key: value for key, value in partial.items() if key != "rhs_trials"}
        journal.fail(
            dict(
                type=type(error).__name__,
                reason=str(error),
                code=getattr(error, "code", None),
                stage=getattr(error, "stage", partial.get("stage")),
                partial=captured,
                traceback=traceback.format_exc(),
                candidate_passed=False,
                control_detected=False,
            )
        )
        raise


def runtime_identity(payload):
    # Reuse the actual proc-map/module inventory, replacing its worker entry.
    runtime = metadata.runtime_inventory(Path(payload["input_path"]))
    runtime["source"], runtime["source_sha256"] = (
        str(Path(__file__).resolve()),
        records.sha(__file__),
    )
    runtime["files"][runtime["source"]] = runtime["source_sha256"]
    need(
        runtime["file_errors"] == {}
        and runtime["mapped_file_errors"] == []
        and runtime["production_modules_loaded"] == [],
        "Complete actual independent runtime closure",
    )
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    payload = metadata.parse(args.input.read_text())
    payload["input_path"] = str(args.input.resolve())
    evaluate(payload, args.directory)


def authenticate(payload, journal):
    if DRAFT_ONLY:
        raise authority_gate.PrerequisitePending("Independent trajectory comparison is unfrozen")
    request = payload["request"]
    accepted = authority_gate.require(request["authority"], phase="trajectory")
    need(request["role"] == "comparison", "Refusal controls never supply accuracy credit")
    case_id, arms = request["case_id"], request["arms"]
    ids = declarations.comparison_ids(case_id)
    need(
        tuple(row["control_id"] for row in arms) == ids,
        "Three separately initialized full-horizon clocks",
    )
    need(
        request["identity"]
        == metadata.digest([LAW, case_id, arms, request["authority"], request["role"]]),
        "Complete request seal",
    )
    need(
        set(payload["arm_directories"]) == set(ids), "Complete positive trajectory artifact roster"
    )
    qualified = accepted["trajectory_initial_qualification_json"]
    need(
        qualified["kind"] == "cells.partition_trajectory_initial_qualification@1"
        and qualified["status"] == "accepted"
        and qualified["qualification_inherited"] is False,
        "New initial qualification is separately accepted",
    )
    all_bindings = qualified["accepted_bindings"]
    expected_roster = {
        (row["case_id"], arm["id"])
        for row in declarations.document()["cases"]
        for arm in row["arms"]
    }
    need(
        len(all_bindings) == len(expected_roster) == 18
        and {(r["case_id"], r["numerical_control_id"]) for r in all_bindings} == expected_roster,
        "Every new full-horizon initial is separately qualified",
    )
    definitions = {}
    for arm in arms:
        incoming, report = metadata.parse(arm["input_json"]), metadata.parse(arm["report_json"])
        raw_authentication = {}
        journal.append("original_initial_arm", dict(arm=arm, incoming=incoming, report=report))
        try:
            original, _, _ = metadata.authenticate(incoming, raw_authentication)
        finally:
            journal.append("initial_metadata_authentication", raw_authentication)
        need(
            incoming["case_id"] == case_id
            and incoming["numerical_control_id"] == arm["control_id"]
            and incoming["trajectory_authority"]
            == authority_gate.initial_phase(request["authority"]),
            "Exact new initial authority and arm",
        )
        need(
            metadata.digest(original) == metadata.digest(arm["initial_request"])
            and metadata.digest(incoming["preparation"])
            == metadata.digest(arm["initial_preparation"]),
            "Complete original initial input",
        )
        need(
            report["status"] == "complete"
            and report["case_id"] == case_id
            and report["numerical_control_id"] == arm["control_id"]
            and report["baseline_passed"] is True
            and report["candidate_passed"] is True
            and report["control_detected"] is False
            and report["controls"] == []
            and not report.get("runtime_capture_failed", False)
            and not report.get("failure_capture_failed", False)
            and report["baseline"]["full_node_physics_and_RHS_verified"] is True
            and report["baseline"]["represented_concentration_defects_verified"] is True
            and report["baseline"]["accounting_passed"] is True,
            "Fresh complete positive initial report",
        )
        runtime = report["runtime_origin"]
        manifest = accepted["trajectory_initial_manifest_json"]
        entry = "validation/geometry/stable_seed_partition_trajectory_initial_worker.py"
        need(
            runtime["source_sha256"] == manifest["file_sha256"]["source/" + entry]
            and runtime["input_sha256"] == hashlib.sha256(arm["input_json"].encode()).hexdigest()
            and runtime["production_imports_denied"] is True
            and runtime["production_modules_loaded"] == []
            and runtime["file_errors"] == {}
            and runtime["mapped_file_errors"] == []
            and type(runtime["pid"]) is int
            and type(runtime["parent_pid"]) is int
            and runtime["pid"] > 0
            and runtime["parent_pid"] > 0
            and runtime["pid"] != runtime["parent_pid"],
            "Actual fresh independent initial runtime",
        )
        worker_root = Path(runtime["source"]).parents[2]
        for rel in (
            entry,
            "validation/geometry/stable_seed_partition_trajectory_authority.py",
            "validation/geometry/stable_seed_partition_trajectory_declarations.py",
            "validation/geometry/stable_seed_partition_physiology_bridge_declarations.py",
            "validation/geometry/stable_seed_partition_physiology_bridge_initial_reference.py",
            "validation/geometry/stable_seed_partition_physiology_bridge_field_reference.py",
            "validation/geometry/stable_seed_partition_physiology_bridge_scalar_reference.py",
            "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py",
            "validation/geometry/conservative_polygon_geometry_reference.py",
            "validation/geometry/stable_geometry_primitives_reference.py",
        ):
            need(
                runtime["files"].get(str(worker_root / rel))
                == manifest["file_sha256"]["source/" + rel],
                "Complete initial worker source closure: " + rel,
            )
        definition = metadata.parse(
            arm["initial_preparation"]["physical_preparation"]["definition_json"]
        )
        binding = dict(
            case_id=case_id,
            numerical_control_id=arm["control_id"],
            input_sha256=hashlib.sha256(arm["input_json"].encode()).hexdigest(),
            report_sha256=hashlib.sha256(arm["report_json"].encode()).hexdigest(),
            initial_request_identity=arm["initial_request"]["identity"],
            initial_preparation_identity=arm["initial_preparation"]["identity"],
            definition_sha256=metadata.digest(definition),
        )
        need(binding in all_bindings, "This exact new initial and full definition were accepted")
        definitions[arm["control_id"]] = definition
    declarations.same_physical_definition(case_id, definitions)
    return request, definitions


def check_field_rhs(
    state, time, field_record, rhs_record, label, context, partial, np, codec, dynamics
):
    raw_state = dynamics.flatten(context, state)
    expected = dynamics.field_snapshot(context, raw_state, time, partial)
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
        name: {
            key: codec.decode(value, label=label + "/rates/" + key) for key, value in item.items()
        }
        if name == "rates"
        else codec.decode(item, label=label + "/" + name)
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
    bound = 3e-25 + 2e-12 * np.maximum(np.abs(charge), np.abs(values["capacitor_node_charge_C"]))
    norm = np.max(np.abs(values["charge_residual_C"]) / bound)
    need(
        np.isclose(values["charge_normalized"], norm, rtol=3e-10, atol=1e-14),
        label + ": exact charge-normalized readback link",
    )
    scale = max(
        (
            float(np.max(np.abs(values["rates"][key + "_current_A"]), initial=0.0))
            for key in ("face", "junction")
        )
    )
    norm = np.max(np.abs(values["component_current_residual_A"]), initial=0.0) / (
        1e-23 + 2e-12 * scale
    )
    need(
        np.isclose(values["current_normalized"], norm, rtol=3e-10, atol=1e-14),
        label + ": exact current-normalized readback link",
    )
    return rows


if __name__ == "__main__":
    main()
