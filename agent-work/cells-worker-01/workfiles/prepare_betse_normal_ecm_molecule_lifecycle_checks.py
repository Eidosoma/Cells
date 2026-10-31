"""Copy established capture/comparison plumbing as source, never import tests."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-molecule-transport-prepared-20261031-01/source"
)
PREFIX = "betse_normal_ecm_molecule_lifecycle"


def main():
    old = ast.parse((PARENT / "tests/unit/test_betse_normal_ecm_molecule_transport.py").read_text())
    keep = {"root", "archive", "references", "isolated", "check"}
    helpers = "\n\n".join(
        ast.unparse(n) for n in old.body if isinstance(n, ast.FunctionDef) and n.name in keep
    )
    helpers = (
        helpers.replace("normal-ecm-molecule-transport", "normal-ecm-molecule-lifecycle")
        .replace("betse_normal_ecm_molecule_transport_reference", PREFIX + "_reference")
        .replace("betse_normal_ecm_molecule_transport_native", PREFIX + "_native")
    )
    target = ROOT / "tests/unit" / ("test_" + PREFIX + "_capture.py")
    target.parent.mkdir(parents=True, exist_ok=True)
    header = '''"""Frozen capture plumbing for the held molecule lifecycle suite."""
import json
import os
import subprocess
import sys
from pathlib import Path
from cells.processes import betse_normal_ion_join as ions
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_grn_join_native as archives
'''
    text = header + "\n" + helpers + "\n"
    compile(text, str(target), "exec")
    with target.open("x") as stream:
        stream.write(text)
    print(target)


if __name__ == "__main__":
    main()
