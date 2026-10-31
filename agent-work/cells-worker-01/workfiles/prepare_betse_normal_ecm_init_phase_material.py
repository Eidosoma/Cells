# ruff: noqa: E501
"""Prepare an INIT post-network splice without evaluating scientific source AST."""

import ast
import builtins
import copy
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")
SOURCE = PARENT / "src/cells/processes/betse_normal_ecm_calcium_join.py"
OUT = ROOT / "src/cells/processes/betse_normal_ecm_init_phase_material.py"


def prepare():
    tree = ast.parse(SOURCE.read_text())
    original = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_material_step"
    )
    proposed = copy.deepcopy(original)
    proposed.name = "step_init"
    proposed.args.kwonlyargs.append(ast.arg(arg="on_post_network"))
    proposed.args.kw_defaults.append(None)
    block = next(
        n
        for n in ast.walk(proposed)
        if isinstance(n, ast.With)
        and any(
            isinstance(s, ast.If) and ast.unparse(s.test) == "on_network is not None"
            for s in n.body
        )
    )
    index = (
        next(
            i
            for i, n in enumerate(block.body)
            if isinstance(n, ast.If) and ast.unparse(n.test) == "on_network is not None"
        )
        + 1
    )
    inserted = ast.parse("""
on_post_network([cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening])
observe("INIT_post_network")
""").body
    block.body[index:index] = inserted
    inverse = copy.deepcopy(proposed)
    inverse.name = original.name
    inverse.args.kwonlyargs.pop()
    inverse.args.kw_defaults.pop()
    mapped = next(
        n
        for n in ast.walk(inverse)
        if isinstance(n, ast.With)
        and any(
            isinstance(s, ast.If) and ast.unparse(s.test) == "on_network is not None"
            for s in n.body
        )
    )
    del mapped.body[index : index + 2]
    assert ast.dump(inverse, include_attributes=False) == ast.dump(
        original, include_attributes=False
    )
    code = ast.unparse(ast.fix_missing_locations(proposed))
    table = symtable.symtable(code, str(OUT), "exec")
    known = set(dir(builtins)) | {"__name__", "__file__", proposed.name}

    def global_names(scope):
        result = {
            s.get_name()
            for s in scope.get_symbols()
            if s.is_global() and s.is_referenced() and s.get_name() not in known
        }
        for child in scope.get_children():
            result |= global_names(child)
        return result

    aliases = global_names(table)
    header = '''"""Exact common CaATP material body with one INIT post-network mechanics hook.

The hook precedes deferred primary commit and adds no event/protein-noise path.
Shared arithmetic, guards, diagnostics and numeric budgets are unchanged.
"""

from cells.processes import betse_normal_ecm_calcium_join as base

'''
    for name in sorted(aliases):
        header += name + " = base." + name + "\n"
    with OUT.open("x") as stream:
        stream.write(header + "\n\n" + code + "\n")
    compile(OUT.read_text(), str(OUT), "exec")
    print(str(OUT))


if __name__ == "__main__":
    prepare()
