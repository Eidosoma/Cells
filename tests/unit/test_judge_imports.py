"""The registered judges' drivers find every engine name they read.

A registered judge reruns exactly as registered only if every name it imports still exists:
the names it imports from cells and validation modules, and the attributes it reads from
the modules it imports. On 13 November, G2-Q1's Q2 failed on the current tree because it
reads cell_replacement.CHARGE_PER_FMOL, which the thin module had not exported since
92a4eeb. Read from each driver's source (ast); nothing is run.
"""

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JUDGES = (
    "validation/tissue/cell_replacement_judge.py",  # G2-Q1
    "validation/tissue/cell_replacement_qualification.py",  # G2-Q1's definitions
    "validation/tissue/pump_water_qualification.py",  # W1
    "validation/tissue/pump_water_kcc_qualification.py",  # W2
    "validation/tissue/injection_rm1.py",  # Rm1
)
OURS = ("cells", "validation")


def unresolved(path):
    """Imported names and module attributes the driver reads that do not exist."""
    tree = ast.parse((ROOT / path).read_text())
    aliases, missing = {}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                aliases[name.asname or name.name.split(".")[0]] = name.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(OURS):
            module = importlib.import_module(node.module)
            for name in node.names:
                if not hasattr(module, name.name):
                    try:
                        importlib.import_module(f"{node.module}.{name.name}")
                    except ImportError:
                        missing.append(f"from {node.module} import {name.name}")
                aliases.setdefault(name.asname or name.name, f"{node.module}.{name.name}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = aliases.get(node.value.id, "")
            if not target.startswith(OURS):
                continue
            try:
                module = importlib.import_module(target)
            except ImportError:
                continue  # The alias names a class or function, not a module.
            if not hasattr(module, node.attr):
                missing.append(f"{target}.{node.attr}")
    return sorted(set(missing))


@pytest.mark.parametrize("path", JUDGES)
def test_every_name_a_registered_judge_reads_exists(path):
    assert unresolved(path) == []


def test_the_check_finds_a_missing_name(tmp_path, monkeypatch):
    from cells.models import cell_replacement

    monkeypatch.delattr(cell_replacement, "CHARGE_PER_FMOL")
    assert unresolved(JUDGES[0]) == ["cells.models.cell_replacement.CHARGE_PER_FMOL"]
