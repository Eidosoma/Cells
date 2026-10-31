"""Inventory saved evidence without following pytest's temporary aliases.

The earlier live-recording audit also records pytest links separately from file
hashes. Here callers must name each eligible temporary directory explicitly;
only pytest's sibling numbered-directory aliases are admitted there. Scientific
artifacts, source trees and every other location retain a no-symlink policy.
"""

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _relative(name):
    path = PurePosixPath(name)
    _require(
        type(name) is str
        and bool(name)
        and not path.is_absolute()
        and str(path) == name
        and ".." not in path.parts
        and "\\" not in name,
        "Noncanonical temporary directory",
    )
    return path


def inventory(directory, *, pytest_tmp_roots=(), max_entries=50000, max_path_bytes=1024):
    """Return hashes of real files and distinct records of permitted aliases.

    This is a read-only snapshot, not a verdict about a computation. No link is
    followed during traversal, no artifact is removed, and target files occur
    only once under their real names.
    """
    root = Path(directory).absolute()
    _require(root.is_dir() and not root.is_symlink(), "Require a real artifact directory")
    _require(type(max_entries) is int and max_entries > 0, "Invalid entry bound")
    _require(type(max_path_bytes) is int and max_path_bytes > 0, "Invalid path bound")
    allowed = {str(_relative(name)) for name in pytest_tmp_roots}
    _require(all(name.startswith("tmp/") for name in allowed), "Only declared tmp directories")
    for name in allowed:
        parent = root
        for part in PurePosixPath(name).parts:
            parent = parent / part
            _require(
                parent.is_dir() and not parent.is_symlink(), "Linked/missing temporary directory"
            )

    files, links, entries = {}, {}, 0

    def walk_error(error):
        raise error

    for base, directories, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in sorted(directories + names):
            path = Path(base) / name
            relative = str(path.relative_to(root))
            entries += 1
            _require(entries <= max_entries, "Artifact entry bound")
            _require(len(relative.encode()) <= max_path_bytes, "Artifact path bound")
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                _require(
                    str(path.parent.relative_to(root)) in allowed and name.endswith("current"),
                    "Undeclared artifact link: " + relative,
                )
                text = os.readlink(path)
                raw_target = Path(text)
                target = raw_target if raw_target.is_absolute() else path.parent / raw_target
                prefix = name[: -len("current")]
                suffix = target.name[len(prefix) :] if target.name.startswith(prefix) else ""
                _require(
                    ".." not in target.parts
                    and target.parent == path.parent
                    and bool(prefix)
                    and suffix.isascii()
                    and suffix.isdecimal()
                    and target.is_dir()
                    and not target.is_symlink(),
                    "Require a real sibling pytest numbered directory: " + relative,
                )
                links[relative] = dict(
                    target=text,
                    target_relative=str(target.relative_to(root)),
                    target_text_sha256=hashlib.sha256(os.fsencode(text)).hexdigest(),
                )
            elif stat.S_ISREG(mode):
                with path.open("rb") as stream:
                    files[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
            else:
                _require(stat.S_ISDIR(mode), "Nonregular artifact: " + relative)

    return dict(
        files_sha256=dict(sorted(files.items())),
        pytest_tmp_links=dict(sorted(links.items())),
        entries=entries,
        allowed_pytest_tmp_roots=sorted(allowed),
        links_followed=False,
    )
