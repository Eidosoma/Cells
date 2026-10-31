# ruff: noqa: E501
"""Copy only generic record plumbing, never scientific equations or execution."""

import ast
import copy
from pathlib import Path

root = Path("/home/robert/Cells")
p = root / "src/cells/processes/betse_native_cut_lifecycle.py"
tree = ast.parse(p.read_text())
node = copy.deepcopy(
    next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "snapshot")
)
header = '''"""Generic typed array/alias records for independent source capture; no Cells imports."""
import json
from collections.abc import Mapping
from dataclasses import fields,is_dataclass
from types import SimpleNamespace
import numpy as np

class _DataOwner:
    pass

'''
with (root / "validation/topology/betse_native_cut_lifecycle_records.py").open("x") as stream:
    stream.write(header + ast.unparse(ast.fix_missing_locations(node)) + "\n")
