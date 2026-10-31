# ruff: noqa: E501
"""Prepare private reference bodies with an exact INIT active-guard inverse."""

import ast
import builtins
import copy
import json
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")


def function(path, name):
    tree = ast.parse(path.read_text())
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def main():
    catalog = PARENT / "validation/betse/betse_normal_ecm_catalog_join_reference.py"
    events = PARENT / "validation/betse/betse_normal_ecm_event_join_reference.py"
    original = function(events, "channel_sequence")
    channel = copy.deepcopy(original)
    loop = next(
        n
        for n in ast.walk(channel)
        if isinstance(n, ast.For)
        and ast.unparse(n.target) == "row"
        and "inputs['catalog']['populations']" in ast.unparse(n.iter)
    )
    loop.body.insert(
        0, ast.parse('if row.get("init active", True) is False:\n    continue').body[0]
    )
    inverse = copy.deepcopy(channel)
    found = next(
        n
        for n in ast.walk(inverse)
        if isinstance(n, ast.For)
        and ast.unparse(n.target) == "row"
        and "inputs['catalog']['populations']" in ast.unparse(n.iter)
    )
    found.body.pop(0)
    assert ast.dump(inverse, include_attributes=False) == ast.dump(
        original, include_attributes=False
    )
    model = function(catalog, "material_model")
    nodes = [channel, model]
    known = set(dir(builtins)) | {"channel_sequence", "material_model", "__file__", "__name__"}

    def names(scope):
        result = {
            s.get_name()
            for s in scope.get_symbols()
            if s.is_global() and s.is_referenced() and s.get_name() not in known
        }
        for child in scope.get_children():
            result |= names(child)
        return result

    header = '''"""Unchanged common material equations and INIT-filtered common channel equations.

No shared reference namespace is mutated. The single active-guard insertion has
an exact inverse AST; constitutive equations and numerical budgets are retained.
"""

from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_event_join_reference as events

'''
    for node, module in ((channel, "events"), (model, "catalog")):
        text = ast.unparse(ast.fix_missing_locations(node))
        for name in sorted(names(symtable.symtable(text, "<private INIT reference>", "exec"))):
            line = name + " = " + module + "." + name + "\n"
            if name + " = " not in header:
                header += line
    path = ROOT / "validation/betse/betse_normal_ecm_init_phase_reference_models.py"
    with path.open("x") as stream:
        stream.write(
            header
            + "\n\n"
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes)
            + "\n"
        )
    main_node = function(
        PARENT / "validation/betse/betse_normal_ecm_event_mechanics_reference.py", "main"
    )
    cli = (
        ROOT / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_reference_cli.txt"
    )
    with cli.open("x") as stream:
        stream.write(
            ast.unparse(ast.fix_missing_locations(main_node))
            + '\n\nif __name__ == "__main__":\n    main()\n'
        )
    with (
        ROOT
        / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_reference_generation_01.json"
    ).open("x") as stream:
        json.dump(
            dict(
                kind="cells.init_reference_generation@1",
                scientific_execution=False,
                channel_inverse_exact=True,
                material_function_AST_exact=True,
                main_function_AST_exact=True,
            ),
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
