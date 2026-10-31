"""Source provenance controls; no scientific modules or numerical cases."""

import json
import os
import stat
import subprocess

import pytest

from validation import source_snapshot as snapshot


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "tracked.py").write_text("initial = 1\n")
    (repo / ".gitignore").write_text("ignored.py\n")
    snapshot.git(repo, "add", ".")
    snapshot.git(
        repo,
        "-c",
        "user.name=Snapshot Test",
        "-c",
        "user.email=test@invalid",
        "commit",
        "-qm",
        "fixture",
    )
    return repo


def test_preserves_dirty_staged_and_untracked_bytes(checkout, tmp_path):
    (checkout / "tracked.py").write_text("staged = 2\n")
    snapshot.git(checkout, "add", "tracked.py")
    (checkout / "tracked.py").write_text("working = 3\n")
    (checkout / "new.py").write_text("new = 4\n")
    out = tmp_path / "out"
    row = snapshot.freeze(checkout, out, {"source.py": "tracked.py", "new.py": "new.py"})
    assert (out / "source.py").read_bytes() == (checkout / "tracked.py").read_bytes()
    assert (out / "new.py").read_bytes() == (checkout / "new.py").read_bytes()
    assert row["git_revision"] == snapshot.git(checkout, "rev-parse", "HEAD").decode().strip()
    assert "MM tracked.py" in row["selected_status_porcelain_v1_z"]
    assert "?? new.py" in row["selected_status_porcelain_v1_z"]
    assert b"working = 3" in (out / "checkout.patch").read_bytes()
    assert row["files"]["source.py"]["sha256"] == snapshot.digest(out / "source.py")
    assert not row["scientific_acceptance"]


@pytest.mark.parametrize("name", ["../escape.py", "/absolute.py", "a/../escape.py", ".git/config"])
def test_refuses_path_escape(checkout, tmp_path, name):
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="canonical"):
        snapshot.freeze(checkout, out, {name: "tracked.py"})
    assert not out.exists()


def test_refuses_linked_ancestor(checkout, tmp_path):
    (checkout / "link").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "foreign.py").write_text("foreign = True\n")
    # Git itself cannot select a file below a symlink; the source validator
    # independently rejects the linked ancestor as well.
    with pytest.raises(ValueError, match="Linked source"):
        snapshot.regular_file(checkout, "link/foreign.py")


def test_refuses_ignored_source_and_retains_failure(checkout, tmp_path):
    (checkout / "ignored.py").write_text("ignored = True\n")
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="absent from Git or ignored"):
        snapshot.freeze(checkout, out, {"ignored.py": "ignored.py"})
    assert json.loads((out / "FAILURE.json").read_text())["status"] == "incomplete"
    assert not (out / "SNAPSHOT.json").exists()


def test_refuses_concurrent_change_and_preserves_partial_copy(checkout, tmp_path, monkeypatch):
    original = snapshot.git_state
    calls = []

    def state(repo, files):
        calls.append(True)
        if len(calls) == 2:
            (checkout / "tracked.py").write_text("changed = True\n")
        return original(repo, files)

    monkeypatch.setattr(snapshot, "git_state", state)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="changed during snapshot"):
        snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    assert (out / "tracked.py").read_text() == "initial = 1\n"
    assert (out / "FAILURE.json").exists()
    assert not (out / "SNAPSHOT.json").exists()


def test_refuses_overwrite_and_checkout_destination(checkout, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep").write_text("prior evidence")
    with pytest.raises(FileExistsError):
        snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    assert (out / "keep").read_text() == "prior evidence"
    with pytest.raises(ValueError, match="outside the editable checkout"):
        snapshot.freeze(checkout, checkout / "snapshot", {"tracked.py": "tracked.py"})


def test_snapshot_sealed_and_verifier_detects_mutation(checkout, tmp_path):
    out = tmp_path / "out"
    row = snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    assert snapshot.verify(out, manifest_sha256=snapshot.digest(out / "SNAPSHOT.json")) == row
    assert snapshot.assert_checkout_unchanged(out) == row
    for path in (out, *out.rglob("*")):
        assert stat.S_IMODE(path.stat().st_mode) & 0o222 == 0
    (out / "tracked.py").chmod(0o644)
    (out / "tracked.py").write_text("tampered = True\n")
    with pytest.raises(ValueError, match="Changed snapshot payload"):
        snapshot.verify(out)


@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink"])
def test_invalid_source_never_completes(checkout, tmp_path, kind):
    name = "other.py"
    if kind == "symlink":
        (checkout / name).symlink_to(checkout / "tracked.py")
    elif kind == "hardlink":
        os.link(checkout / "tracked.py", checkout / name)
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        snapshot.freeze(checkout, out, {name: name})
    assert (out / "FAILURE.json").is_file()
    assert not (out / "SNAPSHOT.json").exists()


def test_ignored_tracked_file_is_also_refused(checkout, tmp_path):
    (checkout / ".gitignore").write_text("ignored.py\ntracked.py\n")
    with pytest.raises(ValueError, match="ignored"):
        snapshot.freeze(checkout, tmp_path / "out", {"tracked.py": "tracked.py"})


def test_untracked_drift_after_final_git_read_refuses(checkout, tmp_path, monkeypatch):
    (checkout / "new.py").write_text("before = True\n")
    original = snapshot.git_state
    calls = []

    def state(repo, files):
        calls.append(True)
        if len(calls) == 2:
            (checkout / "new.py").write_text("after = True\n")
        return original(repo, files)

    monkeypatch.setattr(snapshot, "git_state", state)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="Source changed during snapshot"):
        snapshot.freeze(checkout, out, {"new.py": "new.py"})
    assert not (out / "SNAPSHOT.json").exists()


def test_later_checkout_drift_does_not_rewrite_snapshot(checkout, tmp_path):
    out = tmp_path / "out"
    snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    (checkout / "tracked.py").write_text("later = True\n")
    assert snapshot.verify(out)["status"] == "complete"
    with pytest.raises(ValueError, match="changed during snapshot"):
        snapshot.assert_checkout_unchanged(out)
    assert (out / "tracked.py").read_text() == "initial = 1\n"


def test_finalization_failure_never_leaves_complete_manifest(checkout, tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("synthetic final verifier failure")

    monkeypatch.setattr(snapshot, "verify", broken)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="synthetic final verifier failure"):
        snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    assert not (out / "SNAPSHOT.json").exists()
    assert (out / "INCOMPLETE_SNAPSHOT.json").exists()
    assert json.loads((out / "FAILURE.json").read_text())["status"] == "incomplete"


def test_extra_payload_and_unfinished_snapshot_refuse(checkout, tmp_path):
    unfinished = tmp_path / "unfinished"
    unfinished.mkdir()
    with pytest.raises(ValueError, match="Incomplete"):
        snapshot.verify(unfinished)
    out = tmp_path / "out"
    snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    out.chmod(0o755)
    (out / "extra.py").write_text("extra = True\n")
    (out / "extra.py").chmod(0o444)
    out.chmod(0o555)
    with pytest.raises(ValueError, match="extra checkout snapshot"):
        snapshot.verify(out)


def test_unrelated_worktree_edits_are_not_selected(checkout, tmp_path):
    (checkout / "unrelated.py").write_text("unrelated = True\n")
    out = tmp_path / "out"
    row = snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
    assert row["selected_status_porcelain_v1_z"] == ""
    assert set(row["files"]) == {"tracked.py"}


def test_check_ignore_accepts_literal_bracket_and_newline_path(checkout, tmp_path):
    name = "literal[1]\nsource.py"
    (checkout / name).write_text("literal_source = True\n")
    (checkout / "literal1\nsource.py").write_text("different_source = True\n")
    out = tmp_path / "out"
    row = snapshot.freeze(checkout, out, {"source.py": name})
    assert (out / "source.py").read_bytes() == (checkout / name).read_bytes()
    assert row["files"]["source.py"]["checkout_path"] == name
    assert snapshot.verify(out) == row


@pytest.mark.parametrize("exit_code", [0, 1, 128])
def test_check_ignore_command_specific_options_and_exit_status(
    checkout, tmp_path, monkeypatch, exit_code
):
    original = snapshot.subprocess.run
    ignored_calls = []

    def run(arguments, **kwargs):
        if "check-ignore" in arguments:
            ignored_calls.append(arguments)
            assert "--literal-pathspecs" not in arguments
            assert arguments[-4:] == ["check-ignore", "--no-index", "-z", "--stdin"]
            assert kwargs["input"] == b"tracked.py\0"
            return subprocess.CompletedProcess(
                arguments,
                exit_code,
                b"tracked.py\0" if exit_code == 0 else b"",
                b"synthetic Git failure" if exit_code == 128 else b"",
            )
        if any(command in arguments for command in ("ls-files", "status", "diff")):
            assert "--literal-pathspecs" in arguments
        return original(arguments, **kwargs)

    monkeypatch.setattr(snapshot.subprocess, "run", run)
    out = tmp_path / "out"
    if exit_code == 1:
        assert snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})["status"] == "complete"
    else:
        error_type = ValueError if exit_code == 0 else subprocess.CalledProcessError
        with pytest.raises(error_type) as caught:
            snapshot.freeze(checkout, out, {"tracked.py": "tracked.py"})
        failure = json.loads((out / "FAILURE.json").read_text())
        assert failure["status"] == "incomplete" and not (out / "SNAPSHOT.json").exists()
        if exit_code == 128:
            assert caught.value.returncode == 128
            assert caught.value.stderr == b"synthetic Git failure"
            assert failure["stderr"] == "synthetic Git failure"
    assert ignored_calls
