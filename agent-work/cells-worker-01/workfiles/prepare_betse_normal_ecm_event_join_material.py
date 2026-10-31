# ruff: noqa: E501 -- explicit inverse AST hook string.
"""Isolate post-event material input and post-GRN noise hook; AST/text only."""

import ast
import builtins
import copy
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
SOURCE = ROOT / "src/cells/processes/betse_normal_ecm_calcium_join.py"
DEST = ROOT / "src/cells/processes/betse_normal_ecm_event_join_material.py"


def build():
    tree = ast.parse(SOURCE.read_text())
    original = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_material_step"
    )
    step = copy.deepcopy(original)
    step.name = "step_after_events"
    step.args.kwonlyargs.append(ast.arg(arg="on_noise"))
    step.args.kw_defaults.append(None)
    removed = []

    class Scope(ast.NodeTransformer):
        def visit_Expr(self, node):
            if ast.unparse(node) in ("fm.fill(0)", "fg.fill(0)"):
                removed.append(copy.deepcopy(node))
                return None
            if ast.unparse(node) == "observe('ecm_grn_dispatch')":
                return node
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if ast.unparse(node.targets[0]) == "(fx_all, fy_all)":
                removed.append(copy.deepcopy(node))
                return None
            return self.generic_visit(node)

        def visit_If(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.test) == "on_network is not None":
                return [
                    node,
                    *ast.parse(
                        'on_noise([cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening])\nobserve("protein_noise")'
                    ).body,
                ]
            return node

    step = Scope().visit(step)
    assert len(removed) == 3
    # Reconstruct inverse exactly, proving only these orchestration boundaries changed.
    inverse = copy.deepcopy(step)
    inverse.name = original.name
    inverse.args = copy.deepcopy(original.args)

    class Inverse(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "on_noise":
                return None
            if ast.unparse(node) == "observe('protein_noise')":
                return None
            if ast.unparse(node) == "observe('initial')":
                return [node, *copy.deepcopy(removed)]
            return self.generic_visit(node)

    inverse = Inverse().visit(inverse)
    assert ast.dump(inverse, include_attributes=False) == ast.dump(
        original, include_attributes=False
    )
    text = ast.unparse(step)
    table = symtable.symtable(text, "<event material static symbols>", "exec").get_children()[0]
    globals_ = {s.get_name() for s in table.get_symbols() if s.is_global() and s.is_referenced()}

    # Include referenced globals inside observer closure as well.
    def collect(scope):
        result = {s.get_name() for s in scope.get_symbols() if s.is_global() and s.is_referenced()}
        for child in scope.get_children():
            result |= collect(child)
        return result

    globals_ |= collect(table)
    aliases = sorted(globals_ - set(dir(builtins)) - {"np", "replace"})
    header = '''"""Owned material subcall after actual pre-step flux reset/events.

Only reset ownership and the post-GRN noise callback differ from the existing
CaATP material adapter. All lower math/guards/budgets are unchanged. Inputs use
legitimate material bindings lowered from actual live event coefficients.
"""
from dataclasses import replace
import numpy as np
from cells.processes import betse_normal_ecm_calcium_join as base
'''
    header += "\n".join(name + " = base." + name for name in aliases) + "\n\n"
    return header + text + "\n", removed


if __name__ == "__main__":
    text, removed = build()
    with DEST.open("x") as stream:
        stream.write(text)
    print("Wrote post-event material adapter; inverse AST exact; no scientific import/execution")
