"""Unfrozen byte-exact restart comparison, with no numerical-accuracy credit."""

import argparse
from pathlib import Path

from validation.geometry import stable_seed_partition_trajectory_authority as authority_gate
from validation.geometry import stable_seed_partition_trajectory_declarations as declarations
from validation.geometry import stable_seed_partition_trajectory_records as records

DRAFT_ONLY = True


def evidence(directory, journal, origin, request, definition):
    """Yield complete boundary and step records in original global order."""
    origins = requests = definitions = 0
    for name, value in records.entries(directory):
        if name == "origin":
            if value["pid"] != origin["pid"] or value["parent_pid"] != origin["parent_pid"]:
                raise ValueError("Actual segment and child runtime process identities differ")
            if origin["files"].get(value["source"]) != value["source_sha256"]:
                raise ValueError("Actual runtime did not load the recorded trajectory driver bytes")
            origins += 1
        elif name == "request":
            if records.encoded(value) != records.encoded(request):
                raise ValueError("Actual segment did not use the complete same initial request")
            requests += 1
        elif name == "admitted_definition":
            if records.encoded(value) != records.encoded(definition):
                raise ValueError(
                    "Actual restart segments must share the new full-horizon definition"
                )
            definitions += 1
        if name in {"accepted_boundary", "completed_step"}:
            journal.append(
                "compared_source_record",
                dict(directory=str(directory), name=name, sha256=records.digest(value)),
            )
            yield name, value
    if origins != 1 or requests != 1 or definitions != 1:
        raise ValueError("One complete request, full definition and actual origin per segment")


def runtime(directory):
    found = []
    for name, value in records.entries(Path(directory).with_name(Path(directory).name + "-worker")):
        if name == "actual_runtime":
            found.append(value)
    if len(found) != 1:
        raise ValueError("One complete actual runtime per segment process required")
    origin = found[0]
    wrapper = authority_gate.parse(
        Path(directory)
        .with_name(Path(directory).name + "-worker")
        .joinpath("complete.json")
        .read_text()
    )["result"]
    segment = authority_gate.parse(Path(directory).joinpath("complete.json").read_text())["result"]
    if records.encoded(wrapper["segment"]) != records.encoded(segment):
        raise ValueError("Actual child completion must bind the exact segment completion")
    if (
        type(origin["pid"]) is not int
        or type(origin["parent_pid"]) is not int
        or origin["pid"] <= 0
        or origin["parent_pid"] <= 0
        or origin["pid"] == origin["parent_pid"]
        or origin["file_errors"]
        or origin["mapped_file_errors"]
    ):
        raise ValueError("Complete actual fresh-process origin required")
    return origin


def compare(payload, directory):
    journal = records.Journal(directory)
    try:
        journal.append("original_restart_comparison", payload)
        if DRAFT_ONLY:
            raise authority_gate.PrerequisitePending(
                "Exact trajectory restart comparison is unfrozen"
            )
        authority_gate.require(payload["request"]["authority"], phase="trajectory")
        request = payload["request"]
        if request["role"] != "comparison":
            raise ValueError("Storage refusal controls supply no exact restart qualification")
        arm = next(row for row in request["arms"] if row["control_id"] == payload["control_id"])
        definition = authority_gate.parse(
            arm["initial_preparation"]["physical_preparation"]["definition_json"]
        )
        declared = declarations.selected(request["case_id"], payload["control_id"])
        labels = declarations.clock_labels(request["case_id"], payload["control_id"])
        full = Path(payload["uninterrupted_directory"])
        segments = [Path(path) for path in payload["segment_directories"]]
        if (
            len(segments) != 2
            or len({str(full.resolve()), *(str(path.resolve()) for path in segments)}) != 3
        ):
            raise ValueError("One uninterrupted and two distinct saved/restored segments required")
        origins = [runtime(path) for path in (full, *segments)]
        if len({origin["pid"] for origin in origins}) != 3:
            raise ValueError(
                "Uninterrupted, prefix and restored suffix require distinct actual processes"
            )
        if len({origin["source_sha256"] for origin in origins}) != 1:
            raise ValueError("Restart processes use the same unchanged worker source")
        expected = None
        expected_manifest = None
        for path in (full, *segments):
            manifest = authority_gate.parse((path / "complete.json").read_text())
            result = manifest["result"]
            if result["global_final_step"] != declared["actual_steps"]:
                raise ValueError("Every segment retains the entire declared global clock contract")
            if (
                result["request_identity"] != payload["request"]["identity"]
                or result["control_id"] != payload["control_id"]
                or result["case_id"] != payload["request"]["case_id"]
            ):
                raise ValueError("Every complete segment carries the same new full-horizon request")
            if path == full:
                if (
                    result["start_step"] != 0
                    or result["horizon_complete"] is not True
                    or result["stop_step"] != declared["actual_steps"]
                    or result["final_time_s"] != declared["end_time_s"]
                ):
                    raise ValueError(
                        "The uninterrupted comparison covers the entire declared horizon"
                    )
                expected_manifest = result
            elif path == segments[0]:
                if result["start_step"] != 0 or result["horizon_complete"] is not False:
                    raise ValueError(
                        "The saved prefix stops at a declared interior global boundary"
                    )
                expected = result["stop_step"]
            elif (
                result["start_step"] != expected
                or result["stop_step"] != expected_manifest["stop_step"]
                or result["horizon_complete"] is not True
            ):
                raise ValueError(
                    "The restored suffix continues the same global clock to full horizon"
                )
        uninterrupted = evidence(full, journal, origins[0], payload["request"], definition)
        previous_boundary = None
        boundary_count = step_count = 0
        for part, path in enumerate(segments):
            first_boundary = True
            for name, value in evidence(
                path, journal, origins[part + 1], payload["request"], definition
            ):
                if name == "accepted_boundary" and first_boundary:
                    first_boundary = False
                    if part:
                        if previous_boundary is None or records.encoded(value) != records.encoded(
                            previous_boundary
                        ):
                            raise ValueError(
                                "Saved state/layout/control/field/RHS bytes differ after restore"
                            )
                        continue
                expected_record = next(uninterrupted, None)
                if (
                    expected_record is None
                    or expected_record[0] != name
                    or records.encoded(expected_record[1]) != records.encoded(value)
                ):
                    raise ValueError(
                        "Restart state, owners, clock, raw checked stages, "
                        "field or RHS differ bit for bit"
                    )
                if name == "accepted_boundary":
                    checkpoint = value["checkpoint"]
                    if (
                        checkpoint["step_index"] != boundary_count
                        or checkpoint["time_s"] != labels[boundary_count]
                        or checkpoint["event_index"] != 0
                        or records.encoded(checkpoint["layout"])
                        != records.encoded(arm["initial_preparation"]["initial_snapshot"]["layout"])
                    ):
                        raise ValueError(
                            "Every restored boundary keeps its global clock and original owners"
                        )
                    previous_boundary = value
                    boundary_count += 1
                else:
                    step_count += 1
            if first_boundary:
                raise ValueError("A complete segment retains its initial boundary")
        if (
            next(uninterrupted, None) is not None
            or step_count != expected_manifest["global_final_step"]
            or boundary_count != step_count + 1
        ):
            raise ValueError(
                "Restart comparison must consume every original global step and boundary"
            )
        journal.append("actual_segment_origins", origins)
        result = dict(
            exact_restart_equal=True,
            control_id=payload["control_id"],
            boundaries=boundary_count,
            checked_steps=step_count,
            split_global_step=expected,
            fresh_processes=3,
            state_layout_control_field_RHS_and_stages_byte_exact=True,
            independent_accuracy_credit=False,
            horizon_budget_or_owners_changed=False,
        )
        journal.complete(result)
        return result
    except BaseException as error:
        import traceback

        journal.fail(
            dict(
                type=type(error).__name__,
                reason=str(error),
                traceback=traceback.format_exc(),
                code=getattr(error, "code", None),
                exact_restart_equal=False,
                independent_accuracy_credit=False,
            )
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    compare(authority_gate.parse(args.input.read_text()), args.directory)


if __name__ == "__main__":
    main()
