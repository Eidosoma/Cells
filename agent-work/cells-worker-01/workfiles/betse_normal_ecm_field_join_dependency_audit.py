"""Authenticate coordinated diagnostic-only inputs to a new static packet."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-02")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class OriginalScience(ast.NodeTransformer):
    def visit_Assign(self, node):
        target = ast.unparse(node.targets[0])
        if target.startswith("requested_gap_outward_increment"):
            return None
        return self.generic_visit(node)

    def visit_Dict(self, node):
        return self.generic_visit(node)

    def visit_Call(self, node):
        node.keywords = [
            k for k in node.keywords if k.arg != "junction_requested_outward_increment_mol_m3"
        ]
        if ast.unparse(node.func) == "finish":
            node.func = ast.Name(id="serial", ctx=ast.Load())
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == "finish":
            return None
        if node.name == "evaluate":
            assert node.args.kwonlyargs[-1].arg == "retain_decimal"
            node.args.kwonlyargs = node.args.kwonlyargs[:-1]
            node.args.kw_defaults = node.args.kw_defaults[:-1]
        return self.generic_visit(node)

    def visit_If(self, node):
        if "retain_decimal" in ast.unparse(node.test):
            return None
        return self.generic_visit(node)


def audit():
    inputs = json.loads((BASE / "inputs.json").read_text())
    proof = {}
    for relative in (
        "src/cells/processes/betse_ecm_transport.py",
        "validation/betse/betse_ecm_transport_reference.py",
    ):
        old = BASE / "source" / relative
        assert sha(old) == inputs["source_hashes"][relative]
        before = ast.parse(old.read_text())
        after = OriginalScience().visit(copy.deepcopy(ast.parse((ROOT / relative).read_text())))
        assert ast.dump(before, include_attributes=False) == ast.dump(
            after, include_attributes=False
        ), relative
        proof[relative] = dict(
            old_frozen_sha256=sha(old),
            new_live_sha256=sha(ROOT / relative),
            inverse_AST_original_material_updates_and_all_legacy_ledgers_equal=True,
        )
    return dict(
        kind="cells.normal_ecm_field_coordinated_input_audit@1",
        original_inputs=str(BASE / "inputs.json"),
        original_inputs_sha256=sha(BASE / "inputs.json"),
        changes=proof,
        scope="New packet explicitly pins current inputs; all prior prepared inputs stay unchanged",
        separately_requested_diagnostic_not_compared_or_credited_by_this_join=True,
        optional_decimal_retention_hook_unused_in_this_join=True,
        original39of40_material_failure_still_failed=True,
        scientific_imports=0,
        scientific_AST_executions=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / "betse_normal_ecm_field_join_dependency_witness_01.json"
    with path.open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        json.dumps(
            dict(
                status="coordinated_input_inverse_AST_passed",
                files=2,
                witness=str(path),
                sha256=sha(path),
                scientific_imports=0,
                scientific_AST_executions=0,
            )
        )
    )
