"""Prove only the two requested preflight evidence captures differ from02."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
FROZEN = Path("/mnt/workspaces/Cells/betse-ecm-charged-grn-prepared-20261031-02")
TEST = "tests/unit/test_betse_ecm_charged_grn_join.py"


def audit():
    before = ast.parse((FROZEN / "source" / TEST).read_text())
    after = ast.parse((ROOT / TEST).read_text())

    class Inverse(ast.NodeTransformer):
        def visit_Expr(self, node):
            if (
                isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "archive"
                and any(
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and n.value
                    in ("-cold-parent-before-later-calls", "-unexpected-successful-cold-parent")
                    for n in ast.walk(node)
                )
            ):
                return None
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if any(isinstance(n, ast.Name) and n.id == "unexpected_parent" for n in node.targets):
                assert ast.unparse(node.value) == "joined.initialize(binding)"
                return ast.Expr(value=node.value)
            return self.generic_visit(node)

    assert ast.dump(Inverse().visit(copy.deepcopy(after)), include_attributes=False) == ast.dump(
        before, include_attributes=False
    )
    funcs = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
    for name, target in (
        ("test_ecm_charged_grn_history", "parent"),
        ("test_ecm_charged_grn_partial_failure", "unexpected_parent"),
    ):
        attempt = next(n for n in funcs[name].body if isinstance(n, ast.Try))
        index = next(
            i
            for i, n in enumerate(attempt.body)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)
        )
        following = attempt.body[index + 1]
        assert isinstance(following, ast.Expr) and ast.unparse(following.value.func) == "archive"
        assert {"parent", "inputs", "binding"} <= {
            n.arg for n in ast.walk(following) if isinstance(n, ast.keyword)
        }
    inputs = json.loads((FROZEN / "inputs.json").read_text())
    exact = []
    for path, expected in inputs["owned_sha256"].items():
        if path != TEST and path.endswith(".py"):
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
            exact.append(path)
    return dict(
        kind="cells.ecm_charged_capture03_pending_review@1",
        source_test_sha256=hashlib.sha256((ROOT / TEST).read_bytes()).hexdigest(),
        full_test_AST_inverse_exact=True,
        immediate_cold_parent_and_unexpected_success_archives=True,
        other_six_scientific_Python_files_byte_exact=exact,
        physics_cases_budgets_unchanged=True,
        frozen02_preserved=True,
        not_a_numerical_failure=True,
        sole_hold_was_two_capture_sites=True,
        scientific_execution=False,
    )


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
