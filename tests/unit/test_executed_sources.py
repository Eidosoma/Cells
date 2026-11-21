"""validation/executed_sources.py: a run from a checkout names what Git does not track (D259).

Host only, in a scratch Git repository, with no world compiled. Each claim with a planted error it
must catch (D187):
- an untracked module the process imported is found, its full content is in checkout()'s diff, the
  status lists it, and refuse_untracked raises; once committed, none is found and nothing is
  refused (planted: the old fallback, `git diff HEAD` with `--untracked-files=no`, is empty);
- pytest's collected test files are the harness, not a source;
- a frozen snapshot's root (SNAPSHOT.json) and a tree outside Git report none.

Cost: about 1 s (a few git calls). Reason: the helper's claims are its git calls.
"""

import importlib
import subprocess
import sys

import pytest

from validation import executed_sources


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout  # fmt: skip


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "check@example.invalid")
    git(root, "config", "user.name", "check")
    (root / "tracked.py").write_text("X = 1\n")
    git(root, "add", "tracked.py")
    git(root, "commit", "-q", "-m", "base")
    return root


def load(root, name, text, relative=None):
    """Write a module under root and import it, as a run would."""
    path = root / (relative or f"{name}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    sys.path.insert(0, str(path.parent))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.remove(str(path.parent))


def test_an_untracked_executed_source_is_found_recorded_and_refused(repo):
    name = "d259_untracked_driver_helper"
    try:
        load(repo, name, "VALUE = 'the untracked executed source'\n")
        assert executed_sources.untracked(repo) == [f"{name}.py"]
        record = executed_sources.checkout(repo)
        assert "the untracked executed source" in record["diff"]
        assert f"?? {name}.py" in record["status"]
        assert record["untracked_executed"] == [f"{name}.py"]
        with pytest.raises(executed_sources.UntrackedSources, match=name):
            executed_sources.refuse_untracked(repo, "the check")
        # Planted: the old fallback records nothing of it.
        assert git(repo, "diff", "HEAD") == ""
        assert git(repo, "status", "--porcelain", "--untracked-files=no") == ""
        git(repo, "add", f"{name}.py")
        git(repo, "commit", "-q", "-m", "tracked now")
        assert executed_sources.untracked(repo) == []
        executed_sources.refuse_untracked(repo, "the check")  # tracked: nothing to refuse
    finally:
        sys.modules.pop(name, None)


def test_the_harness_a_snapshot_and_a_tree_outside_git_report_none(repo, tmp_path):
    name = "test_d259_harness_module"
    try:
        load(repo, name, "Y = 2\n", relative=f"tests/unit/{name}.py")
        assert executed_sources.untracked(repo) == []  # pytest's collected file, not a source
    finally:
        sys.modules.pop(name, None)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "SNAPSHOT.json").write_text("{}")
    other = tmp_path / "outside"
    other.mkdir()
    for root in (snapshot, other):
        assert executed_sources.untracked(root) == []
        assert executed_sources.checkout(root) == dict(status="", diff="", untracked_executed=[])
        executed_sources.refuse_untracked(root)
