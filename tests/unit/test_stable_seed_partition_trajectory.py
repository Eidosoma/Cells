"""Uncollected trajectory proposals; qualified inputs must be supplied separately.

These tests create no geometry or initial physiology fixture. Long qualification
must use the existing detached guarded runner; no automatic jobs are installed.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

from cells.processes import stable_seed_partition_advance as first
from cells.processes import stable_seed_partition_trajectory as trajectory
from validation.geometry import stable_seed_partition_trajectory_authority as authority_gate
from validation.geometry import stable_seed_partition_trajectory_declarations as declarations
from validation.geometry import stable_seed_partition_trajectory_records as records

CASES = (
    "uniform-two-species",
    "unequal-clefts-readback-defects",
    "two-cell-four-species",
    "four-cell-reordered-gradient",
)
CLOCKS = ("base", "dt-half", "dt-quarter")
REFUSALS = tuple(clock + "-refusal-" + cap for cap in ("1MiB", "4MiB") for clock in CLOCKS)
CORRUPTIONS = ("shape", "dtype", "owner", "clock", "event", "definition", "state_checksum")


def index_path():
    return Path(os.environ["CELLS_STABLE_SEED_PARTITION_TRAJECTORY_INITIAL_INDEX"])


def request(case, *, refusal_id=None):
    return trajectory.from_index(
        authority_gate.parse(index_path().read_text()), case, refusal_id=refusal_id
    )


def persist(path, value):
    return records.write(path, first.plain(value))


def child(module, payload, directory):
    """A child of a separately guarded/detached qualification job; retain all exits."""
    source = directory.with_name(directory.name + "-input.json")
    persist(source, payload)
    with directory.with_name(directory.name + ".stdout.log").open("xb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                module,
                "--input",
                str(source),
                "--directory",
                str(directory),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        persist(
            directory.with_name(directory.name + "-started.json"),
            dict(
                pid=process.pid,
                parent_pid=os.getpid(),
                input_sha256=records.sha(source),
                actual_nested_child=True,
            ),
        )
        # This is inside a durable external job, not an assistant-side watcher.
        # The external existing guard owns memory, aggregate and reserve limits.
        process.wait()
        log.flush()
        os.fsync(log.fileno())
    persist(
        directory.with_name(directory.name + "-exit.json"),
        dict(pid=process.pid, returncode=process.returncode),
    )
    return process


def segment(
    case, control_id, directory, *, stop_step=None, restart_directory=None, refusal_id=None
):
    payload = dict(index=str(index_path().resolve()), case_id=case, control_id=control_id)
    if stop_step is not None:
        payload["stop_step"] = stop_step
    if restart_directory is not None:
        payload["restart_directory"] = str(restart_directory)
    if refusal_id is not None:
        payload["refusal_id"] = refusal_id
    return child("validation.geometry.stable_seed_partition_trajectory_worker", payload, directory)


def test_unfrozen_pending_receipts_block_all_science(monkeypatch):
    monkeypatch.setattr(trajectory, "DRAFT_ONLY", False)
    monkeypatch.setattr(authority_gate, "DRAFT_ONLY", False)
    monkeypatch.setattr(authority_gate, "INITIAL18_NUMERICAL_QUALIFICATION_SHA256", None)
    with pytest.raises(authority_gate.PrerequisitePending) as caught:
        trajectory.gate({})
    assert caught.value.code == "trajectory_prerequisite_pending"
    assert caught.value.detail["numerical_execution_permitted"] is False
    assert caught.value.detail["freeze_permitted"] is False
    assert "initial18_qualification_json" in caught.value.detail["pending"]


def test_time_scales_clocks_and_new_initial_roster_are_explicit():
    data = declarations.document()
    assert data["frozen"] is False and data["qualification_inherited"] is False
    assert data["fresh_initial_case_arm_bindings"] == 18 and data["new_physical_cases"] == 0
    assert data["guards"] == dict(worker_GiB=1, aggregate_GiB=2, host_reserve_GiB=8)
    for case, coarse, cap, estimate in zip(
        CASES,
        (20, 960, 497, 342),
        (1048576, 1048576, 4194304, 8388608),
        (944832, 944832, 2580672, 5798592),
        strict=True,
    ):
        row = declarations.case(case)
        assert row["coarse_steps"] == coarse
        assert row["end_time_s"] == coarse * 1e-6
        assert row["fastest_planning_scale"]["tau_s"] <= row["end_time_s"]
        assert row["fresh_initial_qualification_required_for_every_arm"] is True
        for clock, multiple in zip(CLOCKS, (1, 2, 4), strict=True):
            arm = declarations.selected(case, clock)
            assert (
                arm["max_trace_bytes"] == cap and arm["source_predicted_window_bytes"] == estimate
            )
            assert arm["actual_steps"] == coarse * multiple
            labels = declarations.clock_labels(case, clock)
            assert (
                len(labels) == coarse * multiple + 1
                and labels[0] == 0.0
                and labels[-1] == row["end_time_s"]
            )


@pytest.mark.parametrize("case", CASES)
def test_bounded_driver_matches_existing_checked_window_driver(case, tmp_path):
    req = request(case)
    # This comparison uses the ordinary bounded API. The original whole-history
    # admission and old storage refusal evidence remain unchanged.
    import numpy as np

    from cells.core import surface_tissue_spec as schema
    from cells.core.windows import WindowPolicy, iter_windows

    arm = req.arms[0]
    candidate = tmp_path / "candidate"
    trajectory.run_segment(req, arm.control_id, candidate)
    stream = (
        (name, value) for name, value in records.entries(candidate) if name == "accepted_boundary"
    )
    _, first_boundary = next(stream)
    assert first_boundary["checkpoint"]["step_index"] == 0
    ordinary = records.Journal(tmp_path / "ordinary")
    try:
        for window in iter_windows(
            schema.parse(arm.initial_preparation.physical_preparation.definition),
            WindowPolicy(1, "full"),
        ):
            value = first.checkpoint_record(window.final, np)
            ordinary.append(
                "complete_checked_window",
                dict(
                    times=window.times.tolist(),
                    history=first.array_record(window.history, np),
                    final=value,
                    diagnostics=window.diagnostics,
                ),
            )
            _, actual = next(stream)
            assert first.digest(value) == first.digest(actual["checkpoint"])
        assert next(stream, None) is None
        ordinary.complete(dict(matched_all_boundaries=True))
    except BaseException as error:
        ordinary.fail(
            dict(type=type(error).__name__, reason=str(error), traceback=traceback.format_exc())
        )
        raise


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("control_id", CLOCKS)
def test_fresh_process_exact_restart_carries_all_owners_and_raw_stages(case, control_id, tmp_path):
    req = request(case)
    count = declarations.selected(case, control_id)["actual_steps"]
    full, prefix, suffix = (tmp_path / name for name in ("full", "prefix", "suffix"))
    assert segment(case, control_id, full).returncode == 0
    assert segment(case, control_id, prefix, stop_step=count // 2).returncode == 0
    assert (
        segment(case, control_id, suffix, restart_directory=prefix / "checkpoint").returncode == 0
    )
    comparison = tmp_path / "restart-comparison"
    process = child(
        "validation.geometry.stable_seed_partition_trajectory_restart",
        dict(
            request=req,
            control_id=control_id,
            uninterrupted_directory=str(full),
            segment_directories=[str(prefix), str(suffix)],
        ),
        comparison,
    )
    assert process.returncode == 0
    result = authority_gate.parse((comparison / "complete.json").read_text())["result"]
    assert result["exact_restart_equal"] is True and result["fresh_processes"] == 3
    assert result["state_layout_control_field_RHS_and_stages_byte_exact"] is True
    assert result["independent_accuracy_credit"] is False


@pytest.mark.parametrize("split", (1, 19))
def test_restart_at_first_and_penultimate_original_boundaries(split, tmp_path):
    case, control_id = CASES[0], "base"
    req = request(case)
    full, prefix, suffix = (tmp_path / name for name in ("full", "prefix", "suffix"))
    assert segment(case, control_id, full).returncode == 0
    assert segment(case, control_id, prefix, stop_step=split).returncode == 0
    assert (
        segment(case, control_id, suffix, restart_directory=prefix / "checkpoint").returncode == 0
    )
    assert (
        child(
            "validation.geometry.stable_seed_partition_trajectory_restart",
            dict(
                request=req,
                control_id=control_id,
                uninterrupted_directory=str(full),
                segment_directories=[str(prefix), str(suffix)],
            ),
            tmp_path / "restart",
        ).returncode
        == 0
    )


@pytest.mark.parametrize("case", CASES)
def test_independent_full_horizon_accuracy_and_common_endpoint_refinement(case, tmp_path):
    req = request(case)
    directories = {}
    for control_id in CLOCKS:
        directory = tmp_path / control_id
        assert segment(case, control_id, directory).returncode == 0
        directories[control_id] = str(directory)
    output = tmp_path / "independent"
    process = child(
        "validation.geometry.stable_seed_partition_trajectory_reference",
        dict(request=req, arm_directories=directories),
        output,
    )
    assert process.returncode == 0
    result = authority_gate.parse((output / "complete.json").read_text())["result"]
    assert result["passed"] is True
    assert result["refinement_error_limit"] == 0.2
    assert result["amount_energy_floor"] == 3e-13 and result["electrode_charge_floor_C"] == 3e-27
    assert result["fourth_order_claimed"] is False
    assert result["restart_equality_supplies_accuracy_credit"] is False
    assert result["endpoint_s"] == declarations.case(case)["end_time_s"]


@pytest.mark.parametrize("control_id", REFUSALS)
def test_original_window_storage_controls_keep_all_three_clocks(control_id, tmp_path):
    case = CASES[3]
    request(case, refusal_id=control_id)
    directory = tmp_path / "refusal"
    process = segment(case, control_id, directory, refusal_id=control_id)
    assert process.returncode != 0 and not (directory / "complete.json").exists()
    report = authority_gate.parse((directory / "failure.json").read_text())
    failure = report["failure"]
    assert failure["type"] == "ConfigError"
    assert failure["stage"] == "existing_full_clock_and_window_storage_admission"
    assert failure["reason"] == "Estimated window working storage exceeds max_trace_bytes"
    assert report["completed"] is False
    retained = []
    with (directory / "index.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line)
            assert records.sha(directory / row["file"]) == row["sha256"]
            retained.append(row["name"])
    assert "admitted_definition" in retained and "step_start" not in retained


def test_later_attempt_failure_retains_every_accepted_prefix_and_unmasked_return(
    monkeypatch, tmp_path
):
    req = request(CASES[0])
    original = first._cells_trial
    attempts = 0

    def fail_after_trial(*args, **kwargs):
        nonlocal attempts
        value = original(*args, **kwargs)
        attempts += 1
        if attempts == 3:
            raise RuntimeError("injected failure after complete unmasked third-step return")
        return value

    monkeypatch.setattr(first, "_cells_trial", fail_after_trial)
    directory = tmp_path / "failed-prefix"
    with pytest.raises(RuntimeError, match="complete unmasked third-step return"):
        trajectory.run_segment(req, "base", directory)
    assert not (directory / "complete.json").exists()
    report = json.loads((directory / "failure.json").read_text())
    assert report["failure"]["last_attempted_global_step"] == 2
    names = []
    chunks = []
    for line in (directory / "index.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert records.sha(directory / row["file"]) == row["sha256"]
        names.append(row["name"])
        if row["name"] == "step_raw/2/cells_checked_kernel_return":
            chunks.append(json.loads((directory / row["file"]).read_text()))
    assert names.count("accepted_boundary") == 3 and names.count("completed_step") == 2
    assert len(chunks) == 1 and len(chunks[0]["trials"]) == 5
    assert [row["role"] for row in chunks[0]["trials"]] == [
        "k1",
        "k2",
        "k3",
        "k4",
        "unmasked_endpoint",
    ]


def corrupt_snapshot(source, target, kind):
    """Reseal selected defects so the ordinary loader reaches the intended check."""
    import numpy as np

    from cells.core.specs import digest, parse_spec

    shutil.copytree(source, target)
    manifest = json.loads((target / "manifest.json").read_text())
    if kind in {"shape", "dtype", "owner"}:
        with np.load(target / "state.npz", allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        if kind == "shape":
            arrays["amount_increment"] = arrays["amount_increment"][:, :0]
        elif kind == "dtype":
            arrays["amount_increment"] = arrays["amount_increment"].astype(np.float32)
        else:
            arrays["volume"] = arrays["volume"].copy()
            arrays["volume"][0] *= 2
        np.savez(target / "state.npz", **arrays)
        manifest["state_sha256"] = records.sha(target / "state.npz")
    elif kind == "clock":
        manifest["clock"]["time"] += 2.5e-7
    elif kind == "event":
        manifest["clock"]["event_index"] += 1
    elif kind == "definition":
        manifest["spec"]["experiment"]["end_time"] *= 2
        manifest["spec"]["execution"]["max_steps"] *= 2
        manifest["spec_sha256"] = parse_spec(manifest["spec"]).fingerprint
    elif kind == "state_checksum":
        data = bytearray((target / "state.npz").read_bytes())
        data[-1] ^= 1
        (target / "state.npz").write_bytes(data)
    else:
        raise ValueError(kind)
    manifest.pop("manifest_sha256")
    manifest["manifest_sha256"] = digest(manifest)
    (target / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


@pytest.mark.parametrize("kind", CORRUPTIONS)
def test_checkpoint_owner_clock_dtype_shape_and_definition_defects_refuse(kind, tmp_path):
    case, control_id = CASES[0], "base"
    request(case)
    prefix = tmp_path / "prefix"
    assert segment(case, control_id, prefix, stop_step=1).returncode == 0
    corrupt = tmp_path / "corrupt"
    corrupt_snapshot(prefix / "checkpoint", corrupt, kind)
    output = tmp_path / "restore-refusal"
    process = segment(case, control_id, output, restart_directory=corrupt)
    assert process.returncode != 0 and not (output / "complete.json").exists()
    report = json.loads((output / "failure.json").read_text())["failure"]
    expected = {
        "shape": "Checkpoint amount_increment has incompatible shape or precision",
        "dtype": "Checkpoint amount_increment has incompatible shape or precision",
        "owner": "Checkpoint layout volume does not match the model definition",
        "clock": "Checkpoint time does not match its accepted integration boundary",
        "event": "Checkpoint event position is inconsistent with its schedule",
        "state_checksum": "Checkpoint state checksum mismatch",
    }
    if kind == "definition":
        assert report["code"] == "restart_requires_identical_full_horizon_spec"
    else:
        assert report["type"] == "ConfigError"
        assert report["reason"] == expected[kind]
    persist(
        tmp_path / "defect-evidence.json",
        dict(
            kind=kind,
            source_checkpoint_sha256=hashlib.sha256(
                (prefix / "checkpoint" / "manifest.json").read_bytes()
            ).hexdigest(),
            original_failed_input_preserved=True,
        ),
    )
