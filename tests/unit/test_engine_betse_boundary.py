"""BETSE stays an external reference: guard the engine/BETSE boundary.

See AGENTS.md ("BETSE's role"). The frozen `betse_native_*` and `betse_normal_*`
tooling that re-hosted or transcribed BETSE was removed from the tree (recoverable
from tag native-betse-frozen-2026-11-08); it must not return, and no module under
src may load the BETSE package or source tree.
"""

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
FROZEN = re.compile(r"(^|\.)betse_(native|normal)_")
# Law/schema IDs such as "betse_x@1" or "cells.betse_y@2" (any case) are BETSE-specific names.
BETSE_ID = re.compile(r"betse[^\s\"']*@\d+", re.IGNORECASE)


def _modules():
    modules = {}
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).with_suffix("")
        parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
        modules[".".join(parts)] = path
    return modules


def _loads_betse(path):
    """Imports, module-path strings ("betse.science.sim") or the BETSE source tree."""
    text = path.read_text(encoding="utf-8")
    if "betse-v1.5.0" in text:
        return True
    for node in ast.walk(ast.parse(text)):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or ""]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names = [node.value]
        if any(re.match(r"^betse(\.[A-Za-z_]\w*)*$", item) for item in names):
            return True
    return False


def test_no_frozen_betse_tooling_modules():
    frozen = sorted(name for name in _modules() if FROZEN.search(name))
    assert not frozen, frozen


def test_live_modules_do_not_load_betse():
    loaders = sorted(name for name, path in _modules().items() if _loads_betse(path))
    assert not loaders, loaders


def test_no_betse_in_module_names():
    named = sorted(name for name in _modules() if "betse" in name.lower())
    assert not named, named


def test_no_betse_in_law_or_schema_ids():
    """String literals shaped like IDs; docstrings (plain citations) stay allowed."""
    found = []
    for name, path in _modules().items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and BETSE_ID.search(node.value)
            ):
                found.append((name, node.value[:60]))
    assert not found, found


def test_no_betse_in_src_data_file_names():
    files = sorted(
        str(p.relative_to(SRC)) for p in SRC.rglob("*") if p.is_file() and "betse" in p.name.lower()
    )
    files = [f for f in files if "__pycache__" not in f]
    assert not files, files
