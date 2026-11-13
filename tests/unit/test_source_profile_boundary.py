"""D149: the source profile's numerical conventions stay confined to emt_mirna_pair@1.

`cells.processes.source_electrochemistry` reproduces four implementation choices of the
reference simulator for bitwise continuity of the recorded replication runs. D149 admits
them only through `cells.models.source_pair`. This test fails if any other module in the
checkout imports it, or if the pair's spec stops pinning its parameter set.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = "cells.processes.source_electrochemistry"
ALLOWED = {"src/cells/models/source_pair.py"}


def _importers():
    found = set()
    for top in ("src", "validation", "scripts", "tests"):
        for path in (ROOT / top).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "src/cells/processes/source_electrochemistry.py":
                continue
            tree = ast.parse(path.read_text(), filename=rel)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                else:
                    continue
                if any(n == MODULE or n.startswith(MODULE + ".") for n in names):
                    found.add(rel)
    return found


def test_only_the_pair_model_imports_the_source_profile():
    assert _importers() == ALLOWED


def test_the_pair_spec_pins_its_parameter_set():
    from cells.core import source_pair_spec

    assert source_pair_spec.PARAMETER_SET == "emt-mirna-pair-scaled-simple"
    text = (ROOT / "src/cells/core/source_pair_spec.py").read_text()
    assert 'p["parameter_set"] != PARAMETER_SET' in text
