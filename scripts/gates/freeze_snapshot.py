"""Freeze an execution snapshot of a checkout for a gate, with the checkout's own
validation/source_snapshot.freeze: the Git revision, the dirty patch and the exact bytes.

Two scopes:
- full (the default): every file Git tracks except visualizer/, which the tier runner does not
  collect, so the tree-scanning guards see the whole tree. This supersedes
  /mnt/workspaces/Cells/core-boundary-checks-20261117/tools/snap_full.py and its identical copy
  in d198-retire-20261117/tools/. Both are kept byte for byte, since recorded runs cite them.
- guards: src/cells, validation, tests and pyproject.toml, the guards' usual scope (FR's landing
  set freezes this one). This supersedes
  /mnt/workspaces/Cells/inventory-coupling-m4-20261114-01/freeze.py, also kept.

Usage: python freeze_snapshot.py CHECKOUT DESTINATION [--scope full|guards] [--require-clean]
Prints one JSON line: revision, files, patch_sha256 and whether the selection is clean. With
--require-clean, exits 1 when it is not.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCOPES = {"full": None, "guards": ("src/cells", "validation", "tests", "pyproject.toml")}


def selected(checkout, scope):
    """The tracked files the scope selects, sorted, present and not caches."""
    paths = SCOPES[scope]
    pathspec = ("--", *paths) if paths else ()
    listed = subprocess.run(
        ["git", "-C", str(checkout), "ls-files", "--cached", "-z", *pathspec],
        capture_output=True, check=True, timeout=120).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    if scope == "full":
        names = [n for n in names if not n.startswith("visualizer/")]
    return [n for n in names if (checkout / n).is_file() and "__pycache__" not in n]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("checkout")
    p.add_argument("destination")
    p.add_argument("--scope", choices=sorted(SCOPES), default="full")
    p.add_argument("--require-clean", action="store_true")
    a = p.parse_args(argv)
    checkout = Path(a.checkout).resolve()
    sys.path.insert(0, str(checkout))  # The checkout's own snapshot tool.
    from validation.source_snapshot import freeze

    names = selected(checkout, a.scope)
    value = freeze(checkout, Path(a.destination), {n: n for n in names})
    clean = value["patch_sha256"] == hashlib.sha256(b"").hexdigest()
    print(json.dumps(dict(destination=a.destination, scope=a.scope, revision=value["git_revision"],
                          files=len(names), patch_sha256=value["patch_sha256"], clean=clean)))
    return 0 if clean or not a.require_clean else 1


if __name__ == "__main__":
    sys.exit(main())
