"""Shared evidence utilities and paths for the bounded spatial composition panel."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "validation/betse/fresh_rerun"))
import common as u  # noqa: E402


def inputs(root):
    return u.read(root / "protocol.json"), u.read(root / "definitions.json")


def artifacts(directory, *, pytest_links=False):
    """Hash real evidence and record only pytest's direct numbered-directory aliases.

    Uses the separate file/link receipt convention from live_recording_audit;
    the ordinary strict inventory remains in force for every non-test phase.
    """
    u.need(directory.is_dir() and not directory.is_symlink(), "Artifact directory")
    if not pytest_links:
        return dict(files_sha256=u.inventory(directory), pytest_internal_links={})
    files, links = {}, {}
    for path in sorted(directory.rglob("*")):
        name = str(path.relative_to(directory))
        if path.is_symlink():
            link = os.readlink(path)
            target = path.parent / link
            prefix = path.name.removesuffix("current")
            suffix = target.name.removeprefix(prefix)
            u.need(
                path.parent == directory / "pytest"
                and path.name.endswith("current")
                and bool(prefix)
                and target.parent == path.parent
                and target.name.startswith(prefix)
                and suffix.isascii()
                and suffix.isdecimal()
                and not target.is_symlink()
                and target.is_dir(),
                "Unexpected pytest artifact link: " + name,
            )
            links[name] = link
        else:
            u.need(path.is_file() or path.is_dir(), "Nonregular artifact: " + name)
            if path.is_file():
                files[name] = u.sha(path)
    return dict(files_sha256=files, pytest_internal_links=links)


def check_artifacts(directory, receipt, *, pytest_links=False):
    actual = artifacts(directory, pytest_links=pytest_links)
    actual["files_sha256"].pop("completion.json", None)
    for key, values in actual.items():
        u.need(values == receipt[key], "Spatial phase artifact changed: " + key)
