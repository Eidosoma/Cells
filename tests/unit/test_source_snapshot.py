"""Source provenance controls; no scientific modules or numerical cases."""

import json
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
