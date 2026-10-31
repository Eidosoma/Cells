"""Unrun source proposals using qualified original/control artifacts only."""

import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

from cells.processes import stable_seed_partition_advance as first
from cells.processes import stable_seed_partition_advance_refinement as common
from validation.geometry import (
    stable_seed_partition_advance_refinement_declarations as declarations,
)

CASES = (
    "uniform-two-species",
    "unequal-clefts-readback-defects",
    "two-cell-four-species",
    "four-cell-reordered-gradient",
)
BUDGET_REFUSALS = (
    ("two-cell-four-species", "dt-quarter"),
    ("four-cell-reordered-gradient", "base"),
    ("four-cell-reordered-gradient", "dt-half"),
    ("four-cell-reordered-gradient", "dt-quarter"),
)


def request_from_qualified_index(case, *, budget_control=None):
    """Read completed evidence; never generate physical inputs or fixtures."""
    index = json.loads(
        Path(os.environ["CELLS_STABLE_SEED_PARTITION_REFINEMENT_INITIAL_INDEX"]).read_text()
    )
    assert index["kind"] == "separately_qualified_clock_resource_initials@1"
    row = index["cases"][case]
    role = "comparison" if budget_control is None else "original_budget_refusal_control"
    acceptance = (
        row["comparison_acceptance"]
        if budget_control is None
        else row["budget_acceptances"][budget_control]
    )
    authority = common.Authority(
        Path(index["manifest"]).read_text(),
        Path(index["source_review"]).read_text(),
        Path(index["numerical_qualification"]).read_text(),
        acceptance,
    )
    common.gate(authority)
    from cells.core import finite_ecm_polygon_preparation as physical
    from cells.processes import finite_ecm_polygon_geometry as finite
    from cells.processes import stable_seed_explicit_ecm_partition as constructor
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    ids = declarations.comparison_ids(case) if budget_control is None else (budget_control,)
    arms = []
    for control_id in ids:
        entry = row["arms"][control_id]
        incoming = Path(entry["input"]).read_text()
        report = Path(entry["report"]).read_text()
        raw = json.loads(incoming)
        assert raw["case_id"] == case and raw["numerical_control_id"] == control_id
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
        preparation = initial.Preparation(
            p["request_identity"],
            physical.Preparation(**p["physical_preparation"]),
            constructor.freeze(p["conversions"]),
            constructor.freeze(p["initial_snapshot"]),
            constructor.freeze(p["provenance"]),
            p["identity"],
        )
        arms.append(common.Arm(control_id, request, preparation, incoming, report))
    return common.bind(case, arms, authority, role=role)


def persist(path, value):
    with path.open("x") as stream:
        json.dump(first.plain(value), stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def retained_attempt(request, directory, *, observer=None):
    persist(directory / "original-common-request.json", request)
    try:
        result = common.advance(request, observer=observer)
    except BaseException as error:
        persist(
            directory / "candidate-refusal.json",
            dict(
                type=type(error).__name__,
                reason=str(error),
                code=getattr(error, "code", None),
                stage=getattr(error, "stage", None),
                original=getattr(error, "original", None),
                partial=getattr(error, "partial", None),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    persist(directory / "candidate-complete.json", result)
    return result


def test_original_callers_and_storage_refusals_are_retained_as_controls():
    data = declarations.document()
    assert data["original_callers_document"]["shared"]["execution"]["dt"] == 1e-6
    assert data["original_callers_document"]["shared"]["execution"]["max_trace_bytes"] == 1048576
    assert data["scope"]["physical_cases"] == 4 and data["scope"]["new_physical_cases"] == 0
    assert data["resource_control"]["max_trace_bytes"] == 4194304
    assert {
        (row["case_id"], row["numerical_control_id"])
        for row in data["original_budget_refusal_controls"]
    } == set(BUDGET_REFUSALS)
    for case in CASES:
        ids = declarations.comparison_ids(case)
        assert len(ids) == 3
        assert len({declarations.arm(name).get("max_trace_bytes", 1048576) for name in ids}) == 1
        assert all(declarations.clock_labels(name)[-1] == 1e-6 for name in ids)


def test_pending_successor_qualification_blocks_science(monkeypatch):
    monkeypatch.setattr(common, "INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256", None)
    authority = common.Authority("{}", "{}", "{}", {})
    with pytest.raises(first.AdvanceRejected) as caught:
        common.bind(CASES[0], [], authority)
    assert caught.value.code == "initial_clock_successor_numerical_qualification_pending"
    assert caught.value.stage == "successor_qualification"
    assert caught.value.partial["numerical_execution_permitted"] is False


@pytest.mark.parametrize("case", CASES)
def test_complete_common_endpoint_matches_existing_Cells_driver(case, tmp_path):
    request = request_from_qualified_index(case)
    import numpy as np

    from cells.core import surface_tissue_spec as schema
    from cells.core.runner import run

    result = retained_attempt(request, tmp_path)
    for control_id in declarations.comparison_ids(case):
        arm = result.arm_records[control_id]
        try:
            ordinary = run(schema.parse(arm["definition"]))
        except BaseException as error:
            persist(
                tmp_path / (control_id + "-ordinary-refusal.json"),
                dict(
                    type=type(error).__name__,
                    reason=str(error),
                    attributes=vars(error),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        persist(
            tmp_path / (control_id + "-ordinary.json"),
            dict(
                times=ordinary.times.tolist(),
                history=first.array_record(ordinary.history, np),
                final=first.checkpoint_record(ordinary.final, np),
            ),
        )
        assert list(ordinary.times) == list(arm["times"])
        assert ordinary.final.time == arm["checkpoint"]["time_s"] == 1e-6
        for name, record in arm["history"].items():
            decoded = np.frombuffer(
                bytes.fromhex(record["data_hex"]), dtype=record["dtype"]
            ).reshape(record["shape"])
            np.testing.assert_array_equal(decoded, np.asarray(getattr(ordinary.history, name)))
        assert len(arm["completed_steps"]) == len(arm["times"]) - 1
        assert arm["definition"]["execution"]["max_trace_bytes"] in (1048576, 4194304)
    assert result.provenance["old_budget_refusals_reclassified"] is False
    assert result.provenance["new_physical_cases"] == 0


@pytest.mark.parametrize("case", CASES)
def test_independent_common_endpoint_and_original_refinement_budgets(case, tmp_path):
    request = request_from_qualified_index(case)
    result = retained_attempt(request, tmp_path)
    source = tmp_path / "input.json"
    target = tmp_path / "output.json"
    persist(source, dict(request=request, candidate=result))
    process = None
    with (tmp_path / "reference.stdout.log").open("x") as log:
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.geometry.stable_seed_partition_advance_refinement_reference",
                    "--input",
                    str(source),
                    "--output",
                    str(target),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            persist(
                tmp_path / "started.json",
                dict(
                    pid=process.pid,
                    parent_pid=os.getpid(),
                    input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    actual_nested_child=True,
                    separate_replay=False,
                ),
            )
            process.wait(timeout=480)
        except BaseException:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            raise
        finally:
            log.flush()
            os.fsync(log.fileno())
    persist(tmp_path / "process.json", dict(pid=process.pid, returncode=process.returncode))
    report = json.loads(target.read_text())
    assert report["runtime_origin"]["pid"] == process.pid
    assert report["runtime_origin"]["parent_pid"] == os.getpid()
    assert (
        report["runtime_origin"]["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert report["runtime_origin"]["production_modules_loaded"] == []
    assert (
        report["runtime_origin"]["file_errors"] == {}
        and report["runtime_origin"]["mapped_file_errors"] == []
    )
    assert not report.get("runtime_capture_failed", False) and not report.get(
        "failure_capture_failed", False
    )
    assert (
        process.returncode == 0
        and report["status"] == "complete"
        and report["baseline_passed"] is True
    )
    assert report["baseline"]["refinement_error_limit"] == 0.2
    assert report["baseline"]["fourth_order_claimed"] is False


@pytest.mark.parametrize(("case", "control_id"), BUDGET_REFUSALS)
def test_original_1MiB_storage_refusals_are_not_reclassified(case, control_id, tmp_path):
    request = request_from_qualified_index(case, budget_control=control_id)
    with pytest.raises(first.AdvanceRejected) as caught:
        retained_attempt(request, tmp_path)
    persist(
        tmp_path / "original-budget-refusal.json",
        dict(
            code=caught.value.code,
            stage=caught.value.stage,
            original=caught.value.original,
            partial=caught.value.partial,
        ),
    )
    assert caught.value.code == "existing_Cells_trace_storage_budget_refusal"
    assert caught.value.stage == "existing_Cells_clock_and_storage_admission"
    arm = caught.value.partial["arms"][control_id]
    assert arm["existing_Cells_clock_storage_refusal"]["type"] == "ConfigError"
    assert (
        arm["existing_Cells_clock_storage_refusal"]["reason"]
        == "Estimated trace working storage exceeds max_trace_bytes"
    )
    assert arm["existing_Cells_clock_storage_refusal"]["declared_max_trace_bytes"] == 1048576
    assert caught.value.partial["common_endpoint_accepted"] is False


def test_later_step_failure_retains_every_completed_prefix_and_return(tmp_path):
    request = request_from_qualified_index(CASES[0])

    def fail(name, value):
        if name == "dt-quarter/step-2-trial-0-rhs-return":
            raise RuntimeError("injected later-step completed RHS failure")

    with pytest.raises(first.AdvanceRejected) as caught:
        retained_attempt(request, tmp_path, observer=fail)
    persist(
        tmp_path / "later-step-refusal.json",
        dict(
            code=caught.value.code,
            stage=caught.value.stage,
            original=caught.value.original,
            partial=caught.value.partial,
        ),
    )
    arm = caught.value.partial["arms"]["dt-quarter"]
    assert len(arm["completed_prefix_checkpoints"]) == 3
    assert arm["completed_prefix_checkpoints"][-1]["time_s"] == 5e-7
    raw = arm["completed_cells_step_attempts"][2]["raw"]
    assert "trial-0-field-return" in raw and "trial-0-rhs-return" in raw
    assert caught.value.partial["common_endpoint_accepted"] is False
    assert any(
        row["type"] == "RuntimeError"
        and row["reason"] == "injected later-step completed RHS failure"
        for row in caught.value.original["causes"]
    )
