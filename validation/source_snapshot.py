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
RESERVED = {
    "SNAPSHOT.json",
    "SNAPSHOT.json.pending",
    "INCOMPLETE_SNAPSHOT.json",
    "FAILURE.json",
    "checkout.patch",
}


def relative_path(name):
    if type(name) is not str or not name:
        raise ValueError("Require a canonical checkout-relative file name")
    path = Path(name)
    if (
        path.is_absolute()
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
    if path.stat().st_nlink != 1:
        raise ValueError("Linked source is not a checkout snapshot: " + name)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Checkout source exceeds the file limit: " + name)
    return path


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(repository, *args):
    return subprocess.run(
        ["git", "--no-optional-locks", "--literal-pathspecs", "-C", str(repository), *args],
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


def _selected(repository, sources):
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
    ignored = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "check-ignore",
            "--no-index",
            "-z",
            "--stdin",
        ],
        input=b"\0".join(os.fsencode(p) for p in sources) + b"\0",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if ignored.returncode not in (0, 1):
        raise subprocess.CalledProcessError(
            ignored.returncode, ignored.args, ignored.stdout, ignored.stderr
        )
    if not set(sources) <= available or ignored.stdout:
        raise ValueError("Selected source is absent from Git or ignored")
    if git(repository, "ls-files", "--unmerged", "-z", "--", *sources):
        raise ValueError("Selected source has unresolved Git index stages")


def _stat(value):
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "size": value.st_size,
        "mode": stat.S_IMODE(value.st_mode),
        "mtime_ns": value.st_mtime_ns,
        "ctime_ns": value.st_ctime_ns,
        "links": value.st_nlink,
    }


def _observe(repository, name):
    path = regular_file(repository, name)
    before = _stat(path.stat())
    value = digest(path)
    if _stat(regular_file(repository, name).stat()) != before:
        raise ValueError("Source changed during snapshot hashing: " + name)
    return dict(sha256=value, observation=before)


def verify(destination, *, manifest_sha256=None):
    """Verify a complete, immutable snapshot without consulting live checkout bytes."""
    destination = Path(destination).absolute()
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("Linked snapshot destination")
    manifest = destination / "SNAPSHOT.json"
    if (destination / "FAILURE.json").exists() or not manifest.is_file():
        raise ValueError("Incomplete checkout snapshot")
    if manifest_sha256 is not None and digest(manifest) != manifest_sha256:
        raise ValueError("Changed checkout snapshot manifest")
    if manifest.stat().st_size > 16 * 2**20:
        raise ValueError("Snapshot manifest exceeds metadata limit")
    value = json.loads(manifest.read_text())
    if (
        value.get("kind") != "cells.checkout_source_snapshot@1"
        or value.get("status") != "complete"
        or value.get("immutable") is not True
        or type(value.get("files")) is not dict
        or not value["files"]
    ):
        raise ValueError("Incomplete checkout snapshot declaration")
    expected, total = {"SNAPSHOT.json", "checkout.patch"}, 0
    for name, row in value["files"].items():
        relative_path(name)
        relative_path(row["checkout_path"])
        if Path(name).parts[0] in RESERVED:
            raise ValueError("Reserved snapshot metadata name")
        path = regular_file(destination, name)
        total += path.stat().st_size
        if (
            digest(path) != row["sha256"]
            or path.stat().st_size != row["observation"]["size"]
            or stat.S_IMODE(path.stat().st_mode) != row["snapshot_mode"]
            or row["snapshot_mode"] & 0o222
            or total > MAX_SNAPSHOT_BYTES
        ):
            raise ValueError("Changed snapshot payload: " + name)
        expected.add(name)
    paths = [destination, *destination.rglob("*")]
    if any(p.is_symlink() or stat.S_IMODE(p.stat().st_mode) & 0o222 for p in paths):
        raise ValueError("Snapshot is linked or writable")
    if {str(p.relative_to(destination)) for p in paths if p.is_file()} != expected:
        raise ValueError("Incomplete or extra checkout snapshot files")
    regular_file(destination, "SNAPSHOT.json")
    regular_file(destination, "checkout.patch")
    if digest(destination / "checkout.patch") != value["patch_sha256"]:
        raise ValueError("Changed checkout patch")
    return value


def assert_checkout_unchanged(destination):
    """Refuse source/index/revision drift while a caller assembles derived metadata."""
    value = verify(destination)
    repository = Path(value["repository"])
    sources = sorted({row["checkout_path"] for row in value["files"].values()})
    _selected(repository, sources)
    state = git_state(repository, sources)
    if (
        state["revision"] != value["git_revision"]
        or state["status"].decode("utf-8", "surrogateescape")
        != value["selected_status_porcelain_v1_z"]
        or state["index"].decode("utf-8", "surrogateescape") != value["selected_index_stage_z"]
        or hashlib.sha256(state["patch"]).hexdigest() != value["patch_sha256"]
    ):
        raise ValueError("Git revision or selected checkout state changed during snapshot")
    for row in value["files"].values():
        if _observe(repository, row["checkout_path"]) != {
            "sha256": row["sha256"],
            "observation": row["observation"],
        }:
            raise ValueError("Source changed during snapshot: " + row["checkout_path"])
    return value


def freeze(repository, destination, files):
    """Copy ``{snapshot_path: checkout_path}`` into an exclusive new directory.

    Selected tracked and nonignored untracked files are allowed. Exact bytes,
    modes, staged state and the patch from HEAD are retained. Unrelated edits
    in a shared checkout need not block a snapshot of this selected scope.
    """
    repository = Path(repository).absolute()
    if any(p.is_symlink() for p in (repository, *repository.parents)):
        raise ValueError("Linked source checkout")
    repository = repository.resolve(strict=True)
    if Path(git(repository, "rev-parse", "--show-toplevel").decode().strip()) != repository:
        raise ValueError("Require the Git checkout root")
    destination = Path(destination).absolute()
    if not isinstance(files, dict) or not files:
        raise ValueError("An explicit nonempty source mapping is required")
    targets = set(files)
    for target, source in files.items():
        relative_path(target)
        relative_path(source)
        if Path(target).parts[0] in RESERVED:
            raise ValueError("Reserved snapshot metadata name")
        # A target that is another target's parent directory overlaps it. Checking
        # each target's own parents is linear; the pairwise scan took minutes.
        if any(str(parent) in targets for parent in Path(target).parents):
            raise ValueError("Overlapping snapshot file paths")
    if destination.resolve().is_relative_to(repository):
        raise ValueError("Execution snapshots belong outside the editable checkout")
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError("Linked snapshot destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    try:
        sources = sorted(set(files.values()))
        _selected(repository, sources)
        before = git_state(repository, sources)
        original, total = {}, 0
        for name in sources:
            original[name] = _observe(repository, name)
        if (
            sum(original[name]["observation"]["size"] for name in files.values())
            > MAX_SNAPSHOT_BYTES
        ):
            raise ValueError("Selected checkout exceeds the snapshot limit")
        for target, name in sorted(files.items()):
            source = regular_file(repository, name)
            path = destination / target
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as incoming, path.open("xb") as outgoing:
                if _stat(os.fstat(incoming.fileno())) != original[name]["observation"]:
                    raise ValueError("Source changed before copying: " + name)
                copied = 0
                while block := incoming.read(1024 * 1024):
                    copied += len(block)
                    if copied > MAX_FILE_BYTES:
                        raise ValueError("Source grew beyond the file limit")
                    outgoing.write(block)
                outgoing.flush()
                os.fsync(outgoing.fileno())
                if _stat(os.fstat(incoming.fileno())) != original[name]["observation"]:
                    raise ValueError("Source changed while copying: " + name)
            total += copied
            path.chmod(original[name]["observation"]["mode"] & ~0o222)
            if digest(path) != original[name]["sha256"] or total > MAX_SNAPSHOT_BYTES:
                raise ValueError("Source changed while copying: " + name)
        _selected(repository, sources)
        if git_state(repository, sources) != before:
            raise ValueError("Git revision or selected checkout state changed during snapshot")
        for name in sources:
            if _observe(repository, name) != original[name]:
                raise ValueError("Source changed during snapshot: " + name)
        with (destination / "checkout.patch").open("xb") as stream:
            stream.write(before["patch"])
            stream.flush()
            os.fsync(stream.fileno())
        (destination / "checkout.patch").chmod(0o444)
        result = {
            "kind": "cells.checkout_source_snapshot@1",
            "status": "complete",
            "immutable": True,
            "utc": datetime.now(timezone.utc).isoformat(),
            "repository": str(repository),
            "git_revision": before["revision"],
            "selected_status_porcelain_v1_z": before["status"].decode("utf-8", "surrogateescape"),
            "selected_index_stage_z": before["index"].decode("utf-8", "surrogateescape"),
            "patch_sha256": digest(destination / "checkout.patch"),
            "files": {
                target: {
                    "checkout_path": name,
                    "sha256": original[name]["sha256"],
                    "mode": original[name]["observation"]["mode"],
                    "snapshot_mode": original[name]["observation"]["mode"] & ~0o222,
                    "observation": original[name]["observation"],
                }
                for target, name in sorted(files.items())
            },
            "scientific_acceptance": False,
            "source_policy": (
                "One-way checkout copy; immutable after creation; no historical overlay."
            ),
        }
        pending = destination / "SNAPSHOT.json.pending"
        write_json(pending, result)
        pending.chmod(0o444)
        for path in sorted(destination.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir():
                path.chmod(0o555)
        pending.rename(destination / "SNAPSHOT.json")
        destination.chmod(0o555)
        verify(destination)
        return result
    except BaseException as error:
        try:
            destination.chmod(0o755)
            for name in ("SNAPSHOT.json", "SNAPSHOT.json.pending"):
                path = destination / name
                if path.exists():
                    path.rename(destination / "INCOMPLETE_SNAPSHOT.json")
            write_json(
                destination / "FAILURE.json",
                {
                    "status": "incomplete",
                    "type": type(error).__name__,
                    "message": str(error),
                    "command": getattr(error, "cmd", None),
                    "stderr": (
                        error.stderr.decode("utf-8", "backslashreplace")
                        if isinstance(getattr(error, "stderr", None), bytes)
                        else None
                    ),
                },
            )
            (destination / "FAILURE.json").chmod(0o444)
            destination.chmod(0o555)
        except Exception as capture_error:
            error.add_note("Snapshot failure receipt could not be sealed: " + repr(capture_error))
        raise
