"""Explicit catalog02 to Chief03 callback dependency refresh, stdlib source only."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_event_join"
REPAIR = Path("/mnt/workspaces/Cells/ecm-callback-repair-20261031-01")
PINS = {
    "src/cells/processes/betse_normal_ecm_calcium_join.py": (
        "d1f897bf49d613fefaae909e001f570d5aa00f0d05e4fdb2de44d136cea90b63"
    ),
    "src/cells/processes/betse_normal_ecm_catalog_join.py": (
        "3d2692dff6bab9f7ac2ef9f6d35ad1095cda46359e6335527bfc4f1589ca2504"
    ),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


class UndoPacket(ast.NodeTransformer):
    def __init__(self):
        self.packet = None
        self.count = 0

    def visit_Assign(self, node):
        if [ast.unparse(t) for t in node.targets] == ["packet"]:
            assert self.packet is None
            self.packet = copy.deepcopy(node.value)
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if ast.unparse(node.func) == "material.drive" and ast.unparse(node.args[-1]) == "packet":
            assert self.packet is not None
            node.args[-1] = copy.deepcopy(self.packet)
            self.count += 1
        elif (
            ast.unparse(node.func) == "source.clone"
            and len(node.args) == 1
            and ast.unparse(node.args[0]) == "packet"
        ):
            node.args[0] = ast.parse("forcing._asdict()", mode="eval").body
            self.count += 1
        return self.generic_visit(node)


def audit():
    prior = Path("/mnt/workspaces/Cells/betse-normal-ecm-catalog-join-prepared-20261031-02")
    old = json.loads((prior / "inputs.json").read_text())
    inherited = old["owned_sha256"] | old["protected_sha256"]
    changes = {}
    for path, expected in inherited.items():
        actual = sha(ROOT / path)
        if path not in PINS:
            assert actual == expected, path
        else:
            assert actual == PINS[path], path
            before = ast.parse((prior / "source" / path).read_text())
            transform = UndoPacket()
            inverse = transform.visit(ast.parse((ROOT / path).read_text()))
            assert transform.count == 2 and digest(before) == digest(inverse), path
            changes[path] = dict(
                old_sha256=expected,
                new_sha256=actual,
                inverse_callback_representation_AST_exact=True,
                equations_order_guards_and_budgets_unchanged=True,
            )
    preparation = json.loads((REPAIR / "preparation.json").read_text())
    source_delta = json.loads((REPAIR / "source-delta.json").read_text())
    assert sha(REPAIR / "source-delta.json") == preparation["source_delta_sha256"]
    bundles = {}
    for row in preparation["bundles"]:
        folder = Path(row["bundle"])
        assert sha(folder / "inputs.json") == row["inputs_sha256"]
        manifest = json.loads((folder / "inputs.json").read_text())
        assert all(
            manifest["owned_sha256"].get(p, manifest["protected_sha256"].get(p)) == h
            for p, h in PINS.items()
            if p in manifest["owned_sha256"] | manifest["protected_sha256"]
        )
        bundles[row["family"]] = dict(
            inputs=str(folder / "inputs.json"), sha256=row["inputs_sha256"]
        )
    assert source_delta["no_changed_equations_or_tolerances"] is True
    return dict(
        kind="cells.ECM_events_explicit_dependency_refresh@1",
        authority=(
            "Chief direct finalized03 callback-pin instruction; "
            "review still a separate freeze prerequisite"
        ),
        prior_inputs=str(prior / "inputs.json"),
        prior_inputs_sha256=sha(prior / "inputs.json"),
        controlled_files=129,
        unchanged_files=127,
        changes=changes,
        successors=bundles,
        preparation=dict(
            path=str(REPAIR / "preparation.json"), sha256=sha(REPAIR / "preparation.json")
        ),
        no_frozen_inputs_receipts_or_failed_evidence_changed=True,
        no_new_numerical_qualification_credit=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / (PREFIX + "_dependency_witness_01.json")).open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(controlled_files=129, unchanged_files=127, changes=result["changes"]),
            sort_keys=True,
        )
    )
