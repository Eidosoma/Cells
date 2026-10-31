"""Exclusive literal pre-mesh source writer; never executes scientific AST."""

import ast
import copy
from pathlib import Path

root = Path("/home/robert/Cells")
source = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
tree = ast.parse((source / "science/tissue/tishandler.py").read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
cut = copy.deepcopy(
    next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_cut_cells")
)
stop = next(
    i
    for i, n in enumerate(cut.body)
    if isinstance(n, ast.Assign) and "cells.mesh.cut_mesh" in ast.unparse(n)
)
cut.body = cut.body[:stop]
cut.name = "deletion_prefix"
flat_tree = ast.parse((source / "science/math/toolbox.py").read_text())
flat = copy.deepcopy(
    next(n for n in flat_tree.body if isinstance(n, ast.FunctionDef) and n.name == "flatten")
)


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
        return self.generic_visit(node)


cut = Clean().visit(cut)
flat = Clean().visit(flat)
header = '''# ruff: noqa: B007, B905
"""Literal native deletion prefix; stops before the first DEC mesh mutation.

No geometry regeneration, solver continuation or complete native-cut claim.
"""
import copy
from types import SimpleNamespace
import numpy as np

logs=SimpleNamespace(log_info=lambda *_:None)
'''
text = (
    header
    + ast.unparse(ast.fix_missing_locations(ast.Module(body=[flat], type_ignores=[])))
    + "\n\ntb=SimpleNamespace(flatten=flatten)\n\n"
    + ast.unparse(ast.fix_missing_locations(ast.Module(body=[cut], type_ignores=[])))
    + "\n"
)
with (root / "src/cells/processes/betse_native_cut_lifecycle_source.py").open("x") as stream:
    stream.write(text)
