"""Resume must reject changed evidence and never promote interrupted captures."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("trajectory_resume_test", HERE / "resume.py")
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)


@pytest.fixture
def witness():
    folder = os.environ.get("CELLS_JUNCTION_TRAJECTORY_RESUME_WITNESS")
    if not folder:
        pytest.skip("A terminal interrupted native panel is required")
    prior = Path(folder)
    return prior, resume.u.read(prior / "protocol.json")


def test_interrupted_panel_retains_complete_rows_only(witness, tmp_path):
    prior, protocol = witness
    # Partial native resume still requires the original scientific sources.
    original = resume.u.read(prior / "registration.json")["sources_sha256"]
    receipt = resume.describe(prior, protocol, original, resume.u.runtime())
    assert len(receipt["rows"]) == 19
    assert len(receipt["missing_rows"]) == 29
    assert receipt["discarded_partial_rows"] == ["network_equal/step-0/bare"]
    assert set(receipt["rows"]).isdisjoint(receipt["missing_rows"])
    assert set(receipt["rows"]) | set(receipt["missing_rows"]) == set(resume.identities(protocol))
    assert 1200 < receipt["estimated_native_seconds"] < 1800
    assert receipt["native_timeout_seconds"] >= 2 * receipt["estimated_native_seconds"]
    assert receipt["reuse_is_numerical_acceptance"] is False
    resume.u.write(tmp_path / "resume-receipt.json", receipt)
    name = "single_mixed/step-0/observed"
    destination = tmp_path / "copied-native"
    expected = receipt["rows"][name]["files_sha256"]
    resume.copy_row(prior / "native" / name, destination, expected)
    assert resume.u.inventory(destination) == expected


@pytest.mark.parametrize(
    "name",
    [
        "src/cells/core/runner.py",
        "validation/betse/junction_trajectory/native.py",
        "validation/betse/junction_trajectory/reference.py",
        "validation/betse/junction_trajectory/check.py",
        "validation/betse/junction_trajectory/protocol.json",
        "validation/betse/fresh_rerun/prepare.py",
    ],
)
def test_scientific_change_blocks_resume(name):
    previous = {name: "old", "validation/betse/junction_transport/run.py": "old-controller"}
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(previous, previous | {name: "new"})
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(previous, {"validation/betse/junction_transport/run.py": "old"})


def test_control_change_allowed_but_added_physics_is_not():
    previous = {"src/cells/core/runner.py": "physics"}
    current = previous | {"validation/betse/junction_trajectory/resume.py": "controller"}
    assert resume.compatible_sources(previous, current)
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(previous, current | {"src/cells/new_law.py": "new-physics"})


@pytest.mark.parametrize(
    "corruption,match",
    [
        ("trace", "trace changed"),
        ("preparation", "preparation changed"),
        ("failure", "failure artifact"),
        ("pickle", "capture files"),
        ("clock", "identity/clock"),
        ("mode", "identity/clock"),
        ("lifecycle", "native lifecycle"),
        ("linked", "Linked evidence"),
    ],
)
def test_reject_corrupted_terminal_capture(witness, tmp_path, corruption, match):
    prior, protocol = witness
    name = "single_mixed/step-0/observed"
    path = tmp_path / "row"
    shutil.copytree(prior / "native" / name, path)
    if corruption in ("trace", "preparation"):
        item = path / ("trace.npz" if corruption == "trace" else "preparation.json")
        with item.open("ab") as handle:
            handle.write(b"changed")
    elif corruption == "failure":
        resume.u.write(path / "failure.json", {"status": "failed"})
    elif corruption == "pickle":
        (path / "INITS/init_1.betse.gz").unlink()
    elif corruption == "linked":
        (path / "native.yaml").unlink()
        (path / "native.yaml").symlink_to(prior / "native" / name / "native.yaml")
    else:
        row = resume.u.read(path / "result.json")
        if corruption == "clock":
            row["steps"] -= 1
        elif corruption == "mode":
            row["mode"] = "bare"
        else:
            row["hook_restored"] = False
        (path / "result.json").write_text(json.dumps(row))
    with pytest.raises(ValueError, match=match):
        resume.complete_row(path, resume.identities(protocol)[name], protocol)


def test_copy_rejects_change_since_registration(witness, tmp_path):
    prior, _ = witness
    source = tmp_path / "changed-source"
    shutil.copytree(prior / "native/single_mixed/step-0/bare", source)
    registered = resume.u.inventory(source)
    (source / "native.yaml").write_text("changed after registration")
    destination = tmp_path / "destination"
    with pytest.raises(ValueError, match="changed before copy"):
        resume.copy_row(source, destination, registered)
    assert not destination.exists()


def test_active_parent_is_not_resumed(witness, monkeypatch):
    prior, protocol = witness
    monkeypatch.setattr(resume.os, "kill", lambda pid, signal: None)
    with pytest.raises(ValueError, match="still present"):
        resume.describe(prior, protocol, resume.u.sources(), resume.u.runtime())


def test_other_panel_cli_rejects_resume_without_creating_output(tmp_path):
    destination = tmp_path / "output"
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            str(HERE.parent / "junction_transport/run.py"),
            "launch",
            str(destination),
            "--resume-from",
            str(tmp_path / "parent"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert child.returncode != 0
    assert "Resume is trajectory-only" in child.stderr
    assert not destination.exists()


@pytest.fixture
def completed_native():
    folder = os.environ.get("CELLS_JUNCTION_TRAJECTORY_COMPLETED_NATIVE")
    if not folder:
        pytest.skip("A complete saved native trajectory panel is required")
    prior = Path(folder)
    return prior, resume.u.read(prior / "protocol.json")


def test_comparison_copies_complete_panel_without_new_native_runs(completed_native, tmp_path):
    prior, protocol = completed_native
    registration = {
        "protocol": protocol,
        "sources_sha256": resume.u.sources(),
        "runtime": resume.u.runtime(),
    }
    receipt = resume.describe(
        prior,
        protocol,
        registration["sources_sha256"],
        registration["runtime"],
        comparison_only=True,
    )
    assert len(receipt["rows"]) == 48 and not receipt["missing_rows"]
    assert receipt["native_timeout_seconds"] == receipt["estimated_native_seconds"] == 0
    assert receipt["comparison_only"] and not receipt["reuse_is_numerical_acceptance"]
    assert "validation/betse/junction_trajectory/check.py" in receipt["comparison_source_changes"]
    registration["resume"] = receipt
    resume.stage_complete(tmp_path / "native", registration)
    assert resume.u.inventory(tmp_path / "native") == resume.u.inventory(prior / "native")
    resume.u.write(tmp_path / "comparison-registration.json", registration)


def test_comparison_rejects_incomplete_panel(witness):
    prior, protocol = witness
    with pytest.raises(ValueError, match="requires a complete native panel"):
        resume.describe(
            prior, protocol, resume.u.sources(), resume.u.runtime(), comparison_only=True
        )


@pytest.mark.parametrize(
    "name",
    [
        "src/cells/core/runner.py",
        "validation/betse/junction_trajectory/native.py",
        "validation/betse/junction_trajectory/reference.py",
        "validation/betse/junction_trajectory/protocol.json",
    ],
)
def test_comparison_changes_cannot_change_physics_reference_or_tolerances(name):
    original = {name: "old"}
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(original, {name: "changed"}, comparison_only=True)


def test_comparison_records_checker_change_without_allowing_partial_resume():
    name = "validation/betse/junction_trajectory/check.py"
    before, after = {name: "old"}, {name: "new"}
    assert resume.compatible_sources(before, after, comparison_only=True) == {
        name: {"previous": "old", "current": "new"}
    }
    with pytest.raises(ValueError, match="scientific source changed"):
        resume.compatible_sources(before, after)


def test_comparison_staging_rejects_changed_registration(completed_native, tmp_path):
    prior, protocol = completed_native
    registration = {
        "protocol": protocol,
        "sources_sha256": resume.u.sources(),
        "runtime": resume.u.runtime(),
    }
    receipt = resume.describe(
        prior,
        protocol,
        registration["sources_sha256"],
        registration["runtime"],
        comparison_only=True,
    )
    receipt["parent_files_sha256"]["native/panel.json"] = "changed"
    registration["resume"] = receipt
    with pytest.raises(ValueError, match="Registered comparison evidence changed"):
        resume.stage_complete(tmp_path / "native", registration)
    assert not (tmp_path / "native").exists()
