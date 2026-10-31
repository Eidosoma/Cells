"""Check only the failure-capture AST delta against immutable ECM01."""

import ast
import copy
import hashlib
from pathlib import Path

ROOT = Path("/home/robert/Cells")
FROZEN = Path("/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-01/source")


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def audit():
    paths = ("src/cells/processes/betse_ecm_grn_join.py", "tests/unit/test_betse_ecm_grn_join.py")
    old, new = (ast.parse((base / paths[0]).read_text()) for base in (FROZEN, ROOT))
    oldf, newf = functions(old), functions(new)
    inverse = copy.deepcopy(new)
    inverse.body = [n for n in inverse.body if getattr(n, "name", None) != "_failure_snapshot"]
    for name in ("initialize", "advance"):
        target = next(n for n in functions(inverse)[name].body if isinstance(n, ast.Try))
        before = next(n for n in oldf[name].body if isinstance(n, ast.Try))
        target.handlers = copy.deepcopy(before.handlers)
        after = next(n for n in newf[name].body if isinstance(n, ast.Try))
        assert all(
            not (isinstance(n, ast.Call) and ast.unparse(n.func) == "source.cache")
            for handler in after.handlers
            for n in ast.walk(handler)
        )
        raised = [
            n for handler in after.handlers for n in ast.walk(handler) if isinstance(n, ast.Raise)
        ]
        assert len(raised) == 1 and ast.unparse(raised[0].cause) == "error"
    assert dump(inverse) == dump(old)
    helper = newf["_failure_snapshot"]
    guard = next(
        n
        for n in helper.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "owner is not None and core is not None"
    )
    guarded = next(n for n in guard.body if isinstance(n, ast.Try))
    assert any(
        isinstance(n, ast.Call) and ast.unparse(n.func) == "source.cache" for n in ast.walk(guarded)
    )
    assert ast.unparse(guarded.handlers[0].type) == "Exception"
    assert "complete_owner_cache_claimed=False" in ast.unparse(helper)
    assert "cache=None" in ast.unparse(helper) and "supplied_cache=supplied_cache" in ast.unparse(
        helper
    )
    old, new = (ast.parse((base / paths[1]).read_text()) for base in (FROZEN, ROOT))
    inverse = copy.deepcopy(new)
    before = functions(old)["test_ecm_grn_dependencies"]
    for i, node in enumerate(inverse.body):
        if getattr(node, "name", None) == "test_ecm_grn_dependencies":
            inverse.body[i] = copy.deepcopy(before)
    assert dump(inverse) == dump(old)
    dependency = functions(new)["test_ecm_grn_dependencies"]
    branch = next(
        n
        for n in dependency.body
        if isinstance(n, ast.If) and "missing_cache" in ast.unparse(n.test)
    )
    archive_index = next(
        i
        for i, n in enumerate(branch.body)
        if isinstance(n, ast.Expr) and "malformed-parent-before-call" in ast.unparse(n)
    )
    call_index = next(
        i
        for i, n in enumerate(branch.body)
        if isinstance(n, ast.With) and "joined.advance" in ast.unparse(n)
    )
    assert archive_index < call_index
    for path in (
        "src/cells/processes/betse_ecm_grn_source.py",
        "validation/betse/betse_ecm_grn_fixtures.py",
        "validation/betse/betse_ecm_grn_native.py",
        "validation/betse/betse_ecm_grn_native_network.py",
        "validation/betse/betse_ecm_grn_reference.py",
    ):
        assert (ROOT / path).read_bytes() == (FROZEN / path).read_bytes(), path
    return dict(
        join_inverse_AST_exact=True,
        all_other_test_AST_exact=True,
        five_other_scientific_Python_files_byte_exact=True,
        original_exception_explicit_raise_from=True,
        cache_capture_guarded_by_actual_owner_core_and_try=True,
        no_valid_cache_claim_for_absent_owner=True,
        supplied_malformed_parent_archived_before_invocation=True,
        final_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        scientific_execution=False,
    )


if __name__ == "__main__":
    print(audit())
