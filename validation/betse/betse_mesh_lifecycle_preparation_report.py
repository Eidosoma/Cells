"""Observed lifecycle coverage from one saved typed actual record at a time."""

from pathlib import Path

from validation.betse import betse_initial_mesh_preparation_replay as transport
from validation.betse import betse_mesh_lifecycle_preparation_replay as replay

np, wire = transport.np, transport.wire
METHODS = (
    "after_clip_lifecycle",
    "init_mesh",
    "laplacian_smoothing",
    "refine_mesh",
    "create_core_operators",
    "create_aux_operators",
    "mesh_quality_calc",
)


def field(tree, name):
    assert tree["type"] == "dict"
    values = [v for k, v in tree["values"] if k == dict(type="str", value=name)]
    assert len(values) == 1
    return values[0]


def operator_signatures(payload):
    cache = field(payload["tree"], "cache")
    assert cache["type"] == "dict"
    return {
        key["value"]: wire.signature(value)
        for key, value in cache["values"]
        if key["type"] == "str" and key["value"].startswith("delta_")
    }


def inspect_record(path):
    path = Path(path)
    actual = replay.read(path)
    helper = actual.get("classification") == "isolated_manufactured_lifecycle_helper"
    main = actual.get("mode") == "actual_before_native_lifecycle"
    role = (
        "raw_helper"
        if helper and actual["failure_type"]
        else "helper"
        if helper
        else "mesh"
        if main
        else "ancillary"
    )
    counts = {
        name: 0
        for name in (
            "lifecycle_markers",
            "rebuilds_entered",
            "rebuilds_returned",
            "rebuilds_failed",
            "iterations_started",
            "iterations_completed",
            "converged_iterations",
            "inner_coordinate_copies",
            "all_coordinate_copies",
            "x_coordinate_updates",
            "y_coordinate_updates",
            "pinv_inputs",
            "pinv_outputs",
            "pinv_failures",
            "dot_inputs",
            "dot_outputs",
            "dot_failures",
            "source_row_deletions",
            "removed_point_occurrences",
            "partial_local_snapshots",
            "rebuilds_with_inherited_operators",
            "rebuilds_returning_same_inherited_operators",
        )
    }
    calls = {name: 0 for name in METHODS}
    returns = {name: 0 for name in METHODS}
    labels, rebuilds = {}, {}
    active = helper
    parameters = None
    state = actual.get("state")
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        for event in actual["events"]:
            kind, method = event["kind"], event["method"]
            if kind == "lifecycle_continuation_start":
                active = True
                counts["lifecycle_markers"] += 1
            if not active:
                continue
            if kind == "method_enter" and method in calls:
                calls[method] += 1
            elif kind == "method_return" and method in returns:
                returns[method] += 1
            key = {
                "lifecycle_rebuild_enter": "rebuilds_entered",
                "lifecycle_rebuild_return": "rebuilds_returned",
                "lifecycle_rebuild_failure": "rebuilds_failed",
                "refinement_iteration_start": "iterations_started",
                "refinement_iteration_end": "iterations_completed",
                "pinv_input": "pinv_inputs",
                "pinv_output": "pinv_outputs",
                "pinv_failure": "pinv_failures",
                "dot_input": "dot_inputs",
                "dot_output": "dot_outputs",
                "dot_failure": "dot_failures",
                "source_row_deletion": "source_row_deletions",
                "lifecycle_partial_locals": "partial_local_snapshots",
            }.get(kind)
            if key:
                counts[key] += 1
            if kind not in {
                "lifecycle_continuation_start",
                "refinement_iteration_end",
                "coordinate_update_after",
                "source_row_deletion",
                "lifecycle_rebuild_enter",
                "lifecycle_rebuild_return",
                "lifecycle_rebuild_failure",
                "pinv_input",
                "pinv_output",
                "pinv_failure",
                "dot_input",
                "dot_output",
                "dot_failure",
            }:
                continue
            payload = transport.load_cache(event["payload"], archive, owned=True)

            def value(name, cache=payload):
                return wire.plain(field(cache["tree"], name), cache["columns"])

            if kind == "lifecycle_continuation_start":
                parameters = value("parameters")
            elif kind == "refinement_iteration_end":
                counts["converged_iterations"] += int(value("termination") == "converged")
            elif kind == "coordinate_update_after":
                policy, axis = value("policy"), value("axis")
                key = (
                    "inner_coordinate_copies"
                    if policy == "inner"
                    else "all_coordinate_copies"
                    if policy == "all"
                    else "x_coordinate_updates"
                    if axis == 0
                    else "y_coordinate_updates"
                )
                counts[key] += 1
            elif kind == "source_row_deletion":
                counts["removed_point_occurrences"] += len(value("removed_ids"))
            elif kind.startswith(("pinv_", "dot_")):
                label = kind + ":" + value("label")
                labels[label] = labels.get(label, 0) + 1
            else:
                epoch = value("epoch")
                operators = operator_signatures(payload)
                if kind == "lifecycle_rebuild_enter":
                    rebuilds[epoch] = operators
                    counts["rebuilds_with_inherited_operators"] += int(bool(operators))
                else:
                    previous = rebuilds.pop(epoch)
                    counts["rebuilds_returning_same_inherited_operators"] += int(
                        kind == "lifecycle_rebuild_return"
                        and bool(previous)
                        and previous == operators
                    )
    termination = state["termination"] if state is not None else None
    branch = dict(
        smoothing_none_skipped=parameters is not None
        and parameters["smoothing"] is None
        and calls["laplacian_smoothing"] == 0,
        zero_smoothing_ran=parameters is not None
        and parameters["smoothing"] == 0
        and calls["laplacian_smoothing"] > 0,
        nonzero_smoothing_ran=parameters is not None
        and parameters["smoothing"] not in (None, 0)
        and calls["laplacian_smoothing"] > 0,
        zero_step_refinement_returned=parameters is not None
        and parameters["refinement"]
        and parameters["max_steps"] == 0
        and returns["refine_mesh"] > 0,
        convergence_branch_observed=counts["converged_iterations"] > 0,
        bounded_steps_exhausted=parameters is not None
        and parameters["refinement"]
        and parameters["max_steps"] > 0
        and counts["iterations_completed"] == parameters["max_steps"]
        and counts["converged_iterations"] == 0
        and returns["refine_mesh"] > 0,
        all_points_refinement_observed=counts["all_coordinate_copies"] > 0,
        inner_points_refinement_observed=counts["inner_coordinate_copies"] > 0,
        auxiliary_operator_construction_observed=calls["create_aux_operators"] > 0,
    )
    return dict(
        case=path.stem.removesuffix("-actual"),
        role=role,
        origin=actual.get("request", {}).get("origin", "manufactured_helper" if helper else None),
        source_status=state["status"]
        if state is not None
        else "source_failed"
        if actual["failure_type"]
        else "source_completed",
        failure_type=state["failure_type"] if state is not None else actual["failure_type"],
        counts=counts,
        method_calls=calls,
        method_returns=returns,
        numeric_call_labels=labels,
        observed_branches=branch,
        termination=termination,
        incomplete_rebuild_epochs=sorted(rebuilds),
        whole_pipeline_scope=role == "mesh",
        manufactured_helper_is_whole_pipeline=False,
        only_observed_branches_receive_scope_credit=True,
        topology_qualified=False,
        physical_geometry_admitted=False,
        upstream_initial_qualification="19/22 accuracy qualification open",
    )
