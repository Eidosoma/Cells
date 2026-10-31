# ruff: noqa: E501
"""Generate private INIT mechanics glue from the frozen common composition."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02/source")


class Unwrap(ast.NodeTransformer):
    def visit_Attribute(self, node):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in ("binding", "parent")
            and node.attr == "events"
        ):
            return node.value
        return self.generic_visit(node)


def main():
    tree = ast.parse(
        (PARENT / "src/cells/processes/betse_normal_ecm_event_mechanics.py").read_text()
    )
    original = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "mechanics_input"
    )
    incoming = Unwrap().visit(copy.deepcopy(original))
    binder = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "bind")
    # All owner/measure/map/constant/dt/zero-flow checks, without the SIM/event binder.
    start = next(
        i
        for i, n in enumerate(binder.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "mb"
    )
    check = ast.parse("def bind(raw, eb):\n    pass").body[0]
    check.body = [
        ast.parse('policy = raw["mechanics_definition"]["policy"]').body[0]
    ] + copy.deepcopy(binder.body[start:-1])
    check.body.append(ast.parse("return mb").body[0])
    header = '''"""Common mechanics validation and actual post-network input, before commit.

Only the event-wrapper nesting is removed. Constitutive arithmetic stays in the
existing ordinary steady/osmotic mechanics component and its unchanged budgets.
"""

import numpy as np

from cells.processes import betse_mechanics_join as mechanics

'''
    path = ROOT / "src/cells/processes/betse_normal_ecm_init_phase_mechanics.py"
    with path.open("x") as stream:
        stream.write(
            header
            + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in (check, incoming))
            + "\n"
        )


if __name__ == "__main__":
    main()
