"""Freeze selected checkout files, with Git provenance and concurrent-change refusal.

No source is restored from an earlier run. Failed copies remain as evidence and
never receive a complete manifest. This is source provenance, not qualification.
"""

import hashlib
import json
import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MAX_FILE_BYTES = 64 * 2**20
MAX_SNAPSHOT_BYTES = 512 * 2**20
RESERVED = {"SNAPSHOT.json", "FAILURE.json", "checkout.patch"}


def relative_path(name):
    path = Path(name)
    if (
        type(name) is not str
        or not name
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != name
        or path.parts[0] == ".git"
        or name == "."
    ):
        raise ValueError("Require a canonical checkout-relative file name")
    return path


def regular_file(root, name):
    path = root / relative_path(name)
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("Linked source is not a checkout snapshot: " + name)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Missing regular checkout source: " + name)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Checkout source exceeds the file limit: " + name)
    return path


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(repository, *args):
    return subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    ).stdout


def git_state(repository, sources):
    return {
        "revision": git(repository, "rev-parse", "HEAD").decode().strip(),
        "status": git(
            repository, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *sources
        ),
        "index": git(repository, "ls-files", "--stage", "-z", "--", *sources),
        "patch": git(
            repository, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--", *sources
        ),
    }


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def freeze(repository, destination, files):
    """Copy ``{snapshot_path: checkout_path}`` into an exclusive new directory.

    Selected tracked and nonignored untracked files are allowed. Exact bytes,
    modes, staged state and the patch from HEAD are retained. Unrelated edits
    in a shared checkout need not block a snapshot of this selected scope.
    """
    repository = Path(repository).resolve(strict=True)
    destination = Path(destination).absolute()
    if not isinstance(files, dict) or not files:
        raise ValueError("An explicit nonempty source mapping is required")
    for target, source in files.items():
        relative_path(target)
        relative_path(source)
        if Path(target).parts[0] in RESERVED:
            raise ValueError("Reserved snapshot metadata name")
    if destination.resolve().is_relative_to(repository):
        raise ValueError("Execution snapshots belong outside the editable checkout")
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("Linked snapshot destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    try:
        sources = sorted(set(files.values()))
        available = {
            os.fsdecode(p)
            for p in git(
                repository,
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                *sources,
            ).split(b"\0")
            if p
        }
        if not set(sources) <= available:
            raise ValueError("Selected source is absent from Git or ignored")
        before = git_state(repository, sources)
        original, modes, total = {}, {}, 0
        for name in sources:
            path = regular_file(repository, name)
            total += path.stat().st_size
            if total > MAX_SNAPSHOT_BYTES:
                raise ValueError("Selected checkout exceeds the snapshot limit")
            original[name] = digest(path)
            modes[name] = stat.S_IMODE(path.stat().st_mode)
        for target, name in sorted(files.items()):
            source = regular_file(repository, name)
            path = destination / target
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as incoming, path.open("xb") as outgoing:
                copied = 0
                while block := incoming.read(1024 * 1024):
                    copied += len(block)
                    if copied > MAX_FILE_BYTES:
                        raise ValueError("Source grew beyond the file limit")
                    outgoing.write(block)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            path.chmod(modes[name])
            if digest(path) != original[name]:
                raise ValueError("Source changed while copying: " + name)
        for name in sources:
            path = regular_file(repository, name)
            if digest(path) != original[name] or stat.S_IMODE(path.stat().st_mode) != modes[name]:
                raise ValueError("Source changed during snapshot: " + name)
        if git_state(repository, sources) != before:
            raise ValueError("Git revision or selected checkout state changed during snapshot")
        with (destination / "checkout.patch").open("xb") as stream:
            stream.write(before["patch"])
            stream.flush()
            os.fsync(stream.fileno())
        result = {
            "kind": "cells.checkout_source_snapshot@1",
            "status": "complete",
            "utc": datetime.now(timezone.utc).isoformat(),
            "repository": str(repository),
            "git_revision": before["revision"],
            "selected_status_porcelain_v1_z": before["status"].decode("utf-8", "surrogateescape"),
            "selected_index_stage_z": before["index"].decode("utf-8", "surrogateescape"),
            "patch_sha256": digest(destination / "checkout.patch"),
            "files": {
                target: {"checkout_path": name, "sha256": original[name], "mode": modes[name]}
                for target, name in sorted(files.items())
            },
            "scientific_acceptance": False,
            "source_policy": "One-way checkout copy; immutable after creation; no historical overlay.",
        }
        write_json(destination / "SNAPSHOT.json", result)
        return result
    except BaseException as error:
        write_json(
            destination / "FAILURE.json",
            {"status": "incomplete", "type": type(error).__name__, "message": str(error)},
        )
        raise
