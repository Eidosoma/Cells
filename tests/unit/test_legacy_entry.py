"""The older families' one entry point (D188 R1): nothing in src/cells outside cells/legacy/ names
the legacy package, except core/legacy_entry.py's constant LEGACY, which legacy() imports.

The scan reads every module's syntax tree: imports in every form (absolute, `from cells import
legacy`, relative), importlib and __import__ calls, attribute chains from `cells`, and every string
literal that is not a docstring. Each form is planted once and must be caught.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cells"
PACKAGE = "cells.legacy"
ENTRY = "core/legacy_entry.py"


def _names_legacy(dotted):
    return dotted == PACKAGE or dotted.startswith(PACKAGE + ".")


def _module_of(relative):
    parts = list(Path(relative).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["cells", *parts])


def _docstrings(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def findings(source, relative):
    """[(line, what)] of every reference to the legacy package in one module of src/cells."""
    tree = ast.parse(source)
    module = _module_of(relative)
    package = module if relative.endswith("__init__.py") else module.rpartition(".")[0]
    skip = _docstrings(tree)
    allowed = None
    if relative == ENTRY:  # The one constant: LEGACY = "cells.legacy.registration".
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and [getattr(t, "id", None) for t in node.targets] == ["LEGACY"]
                and isinstance(node.value, ast.Constant)
            ):
                allowed = id(node.value)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, f"import {a.name}") for a in node.names if _names_legacy(a.name)]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - node.level + 1]
                base = ".".join([*parts, base] if base else parts)
            targets = [base] + [f"{base}.{a.name}" for a in node.names]
            if any(_names_legacy(t) for t in targets):
                out.append((node.lineno, f"from {'.' * node.level}{node.module or ''} import"))
        elif isinstance(node, ast.Attribute) and node.attr == "legacy":
            value = node.value
            if isinstance(value, ast.Name) and value.id == "cells":
                out.append((node.lineno, "cells.legacy attribute"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in skip or id(node) == allowed:
                continue
            if PACKAGE in node.value:
                out.append((node.lineno, f"string {node.value[:60]!r}"))
    return out


def scan(root):
    """{relative path: findings} over a tree shaped like src/cells, outside its legacy/ folder."""
    out = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("legacy/"):
            continue
        found = findings(path.read_text(), relative)
        if found:
            out[relative] = found
    return out


def test_nothing_outside_legacy_names_it():
    assert scan(SRC) == {}


def test_the_entry_imports_the_one_constant():
    from cells.core import legacy_entry
    from cells.legacy import registration

    assert legacy_entry.LEGACY == registration.__name__
    assert legacy_entry.legacy() is registration
    assert legacy_entry.legacy() is legacy_entry.legacy()


@pytest.mark.parametrize(
    "relative, source",
    [
        ("core/specs.py", "import cells.legacy\n"),
        ("core/specs.py", "import cells.legacy.registration as r\n"),
        ("core/specs.py", "from cells.legacy import registration\n"),
        ("core/specs.py", "from cells.legacy.registration import model_for\n"),
        ("core/specs.py", "from cells import legacy\n"),
        ("models/registry.py", "def f():\n    from cells.legacy import registration\n"),
        ("__main__.py", "from .legacy import registration\n"),
        ("core/schedule.py", "from ..legacy.registration import control_values\n"),
        ("ensemble/cli.py", "from .. import legacy\n"),
        ("core/specs.py", "import importlib\nm = importlib.import_module('cells.legacy.x')\n"),
        ("core/specs.py", "m = __import__('cells.legacy.registration')\n"),
        ("core/specs.py", "import sys\nm = sys.modules['cells.legacy.registration']\n"),
        ("core/specs.py", "import cells\nm = cells.legacy.registration\n"),
        ("core/specs.py", "NAME = 'cells.legacy' + '.registration'\n"),
        (ENTRY, 'LEGACY = "cells.legacy.registration"\nOTHER = "cells.legacy.registration"\n'),
    ],
)
def test_each_planted_reference_is_caught(relative, source):
    assert findings(source, relative)


def test_the_allowed_forms_are_not_flagged():
    entry = (SRC / ENTRY).read_text()
    assert findings(entry, ENTRY) == []
    assert findings('"""Mentions cells.legacy in prose."""\nx = 1\n', "core/specs.py") == []
    assert findings('LEGACY = "cells.legacy.registration"\n', "core/specs.py")  # Not the entry.


def test_a_planted_module_in_a_copied_tree_is_caught(tmp_path):
    for relative in ("core/specs.py", ENTRY, "legacy/registration.py"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((SRC / relative).read_text())
    assert scan(tmp_path) == {}
    planted = tmp_path / "core/specs.py"  # One path, which a source move rewrites (D188).
    planted.write_text(planted.read_text() + "\nfrom cells.legacy.registration import parse\n")
    assert list(scan(tmp_path)) == ["core/specs.py"]
