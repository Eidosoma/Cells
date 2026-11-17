"""The detached assembly worker's source (D188 R5): the copy it runs from, and the source identity
its registration records, hold the whole cells package.

A detached `cells assembly-cell` or `assembly-cluster` run copies the package into its output's
source/ folder and launches its worker module from that copy, and the worker refuses unless its
own source identity equals the registration's. Both take their root from the package
(`cells.__file__`), not from their own module's depth: move 1 puts the assembly engines in
src/cells/legacy/, where `Path(__file__).parents[1]` names src/cells/legacy, so the copy would hold
only that part and the worker could not import its own module. That root is planted once and must
be caught.
"""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import cells
from cells.assembly_cell import cli
from cells.io import source_hashes

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = {
    "assembly-cell": ROOT / "configs/assembly_regulated_cell.json",
    "assembly-cluster": ROOT / "configs/assembly_regulated_cluster.json",
}
# configure_caches() sets these in os.environ; setting them through monkeypatch restores them.
CACHES = (
    "TMPDIR",
    "XDG_CACHE_HOME",
    "CUDA_CACHE_PATH",
    "JAX_COMPILATION_CACHE_DIR",
    "XLA_PYTHON_CLIENT_PREALLOCATE",
    "PYTHONDONTWRITEBYTECODE",
)


def launch(tmp_path, monkeypatch, command):
    """A detached run launched with its process start stubbed: the output folder and the module
    the worker would run."""
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", str(tmp_path))  # The CLI writes only under the root.
    for name in CACHES:
        monkeypatch.setenv(name, os.environ.get(name, ""))
    launched = []

    def popen(argv, **options):
        launched.append(argv)
        return SimpleNamespace(pid=0)

    monkeypatch.setattr(cli.subprocess, "Popen", popen)
    output = tmp_path / "run"
    argv = ["run", str(CONFIGS[command]), "--output", str(output), "--detach"]
    assert cli.main(argv, cluster=command == "assembly-cluster") == 0
    (worker,) = launched
    return output, worker[worker.index("-m") + 1]


def problems(output, module, package):
    """What the worker's source lacks: package files missing from the copy or copied with other
    bytes, the worker's module missing from it, and a registered identity other than the
    package's."""
    copy = output / "source" / "cells"
    out = []
    for name, sha in sorted(package.items()):
        if not (copy / name).is_file():
            out.append(f"missing from the copy: {name}")
        elif hashlib.sha256((copy / name).read_bytes()).hexdigest() != sha:
            out.append(f"copied with other bytes: {name}")
    if not copy.joinpath(*module.split(".")[1:], "__main__.py").is_file():
        out.append(f"the worker's module {module} is not in the copy")
    if json.loads((output / "registration.json").read_text())["sources_sha256"] != package:
        out.append("the registered source identity is not the package's")
    return out


@pytest.mark.parametrize("command", sorted(CONFIGS))
def test_detached_worker_source_holds_the_whole_package(tmp_path, monkeypatch, capsys, command):
    package = source_hashes()  # Every module of the package, by its path in it.
    output, module = launch(tmp_path, monkeypatch, command)
    assert problems(output, module, package) == []
    capsys.readouterr()


def test_planted_module_relative_root_is_caught(tmp_path, monkeypatch, capsys):
    """The planted root: src/cells/legacy, the folder a module-relative root names once move 1 has
    put the engines there, planted as the package's folder through cells.__file__. Code that
    ignores the package's root, as the module-relative one did, also fails here."""
    package = source_hashes()
    folder = Path(cells.__file__).resolve().parent
    monkeypatch.setattr(cells, "__file__", str(folder / "legacy" / "__init__.py"))
    output, module = launch(tmp_path, monkeypatch, "assembly-cell")
    found = problems(output, module, package)
    assert "copied with other bytes: __init__.py" in found  # legacy/__init__.py in its place.
    assert "missing from the copy: io.py" in found
    assert f"the worker's module {module} is not in the copy" in found
    assert "the registered source identity is not the package's" in found
    capsys.readouterr()
