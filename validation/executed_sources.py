"""Untracked executed sources: what a run from a checkout executed that its Git revision lacks
(D259, a review's finding on a restart receipt, and its class).

Run provenance is the Git revision, the dirty diff and the frozen snapshot (AGENTS.md). A run made
from a checkout, not from a frozen snapshot, names its revision and its dirty diff, but
`git diff HEAD` and `git status --untracked-files=no` both miss a file that Git does not track.
A run that executed one would then name a revision that lacks it, with an empty patch. This module
finds those files and gives a driver two remedies:
- record them, as validation/betse/betse_reference_run.py does: each one's full content, as a diff
  from /dev/null, joined to the tracked diff (checkout());
- refuse the run while there are any (refuse_untracked()), for a driver whose record holds no diff.

**Executed sources** are the files under the checkout that the running process has loaded: every
imported module's file, the script it runs among them. pytest's collected test files (test_*.py
under tests/, and conftest.py) are the harness, not a driver's source, so they are left out. A data
file that a driver reads is not an executed source here.

**Not a checkout.** A frozen execution snapshot (SNAPSHOT.json at its root,
validation/source_snapshot.py) holds a copy of every source it ran, so it has none to report. A
tree that is neither a snapshot nor a Git work tree has none either: its record already names no
revision.
"""

import subprocess
import sys
from pathlib import Path

SNAPSHOT = "SNAPSHOT.json"


class UntrackedSources(RuntimeError):
    """A run from a checkout executed a source that Git does not track."""


def _git(root, *args):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True,
        check=False,
        timeout=60,
    )


def _toplevel(root):
    """The Git work tree holding `root`, or None: a frozen snapshot, or not a work tree."""
    root = Path(root).resolve()
    if (root / SNAPSHOT).is_file():
        return None
    found = _git(root, "rev-parse", "--show-toplevel")
    if found.returncode != 0:
        return None
    return Path(found.stdout.decode().strip()).resolve()


def _harness(rel):
    """pytest's collected test files: a test module under tests/, or a conftest.py."""
    parts = Path(rel).parts
    name = parts[-1]
    return name == "conftest.py" or (
        parts[0] == "tests" and name.startswith("test_") and name.endswith(".py")
    )


def untracked(root):
    """The executed sources under `root`'s work tree that Git does not track, as paths relative to
    the work tree, sorted (module docstring)."""
    top = _toplevel(root)
    if top is None:
        return []
    listed = _git(top, "ls-files", "-z")
    if listed.returncode != 0:
        return []
    tracked = {p for p in listed.stdout.decode("utf-8", "surrogateescape").split("\0") if p}
    out = set()
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name:
            continue
        try:
            path = Path(name).resolve()
        except (OSError, RuntimeError):
            continue
        if "__pycache__" in path.parts or not path.is_file() or not path.is_relative_to(top):
            continue
        rel = path.relative_to(top).as_posix()
        if rel not in tracked and not _harness(rel):
            out.add(rel)
    return sorted(out)


def untracked_diff(root, paths):
    """Each untracked path's full content as a diff from /dev/null (git diff --no-index), joined."""
    top = _toplevel(root)
    if top is None:
        return ""
    return "".join(
        _git(top, "diff", "--binary", "--no-index", "--", "/dev/null", rel).stdout.decode(
            "utf-8", "surrogateescape"
        )
        for rel in paths
    )


def checkout(root):
    """{status, diff, untracked_executed} of a run from `root`'s checkout: the porcelain status with
    every untracked file, `git diff --binary HEAD` joined to the untracked executed sources' full
    contents, and their paths (betse_reference_run.py's form). Empty outside a work tree."""
    top = _toplevel(root)
    if top is None:
        return dict(status="", diff="", untracked_executed=[])
    status = _git(top, "status", "--porcelain=v1", "--untracked-files=all").stdout
    tracked = _git(top, "diff", "--binary", "--no-ext-diff", "HEAD").stdout
    paths = untracked(top)
    return dict(
        status=status.decode("utf-8", "surrogateescape"),
        diff=tracked.decode("utf-8", "surrogateescape") + untracked_diff(top, paths),
        untracked_executed=paths,
    )


def refuse_untracked(root, what="this run"):
    """Refuse a run from `root`'s checkout that executed an untracked source (module docstring)."""
    paths = untracked(root)
    if paths:
        raise UntrackedSources(
            f"{what} executed sources that Git does not track: {', '.join(paths)}. Its record "
            "would name a revision that lacks them, so commit them or run from a frozen snapshot "
            "(validation/source_snapshot.py)"
        )
