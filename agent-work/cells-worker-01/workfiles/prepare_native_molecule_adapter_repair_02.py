# ruff: noqa: E501 -- review metadata preserves exact descriptive strings.
"""Bind the narrow adapter correction and its static before/after evidence."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD = Path("/mnt/workspaces/Cells/betse-normal-molecule-prepared-20261030-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return ast.parse(Path(path).read_text())


def dump(node):
    return ast.dump(node, include_attributes=False)


queue_path = WORK / "betse_normal_molecule_join_workqueue.json"
queue = json.loads(queue_path.read_text())
source = "src/cells/processes/betse_normal_molecule_source.py"
fixture = "validation/betse/betse_normal_molecule_join_fixtures.py"
source_tree = tree(ROOT / source)
inverse = copy.deepcopy(source_tree)
parameters = next(
    node
    for node in inverse.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "PARAMETERS" for target in node.targets)
)
parameters.value.elts = [
    node for node in parameters.value.elts if ast.literal_eval(node) != "ignore_ECM_pump"
]
validate = next(
    node for node in inverse.body if isinstance(node, ast.FunctionDef) and node.name == "validate"
)


class RemoveGuard(ast.NodeTransformer):
    def visit_If(self, node):
        if ast.unparse(node.test) == "params['ignore_ECM_pump'] is not True":
            assert len(node.body) == 1 and isinstance(node.body[0], ast.Raise)
            return None
        return self.generic_visit(node)


RemoveGuard().visit(validate)
assert dump(inverse) == dump(tree(OLD / "source" / source))
fixture_tree = tree(ROOT / fixture)
inverse_fixture = copy.deepcopy(fixture_tree)
removed = 0
for node in ast.walk(inverse_fixture):
    if isinstance(node, ast.Call):
        matches = [kw for kw in node.keywords if kw.arg == "ignore_ECM_pump"]
        if matches:
            assert len(matches) == 1 and ast.literal_eval(matches[0].value) is True
            node.keywords = [kw for kw in node.keywords if kw.arg != "ignore_ECM_pump"]
            removed += 1
assert removed == 1 and dump(inverse_fixture) == dump(tree(OLD / "source" / fixture))
unchanged = {
    relative: sha(ROOT / relative)
    for relative in queue["owned"]
    if relative
    not in {
        source,
        fixture,
        "validation/betse/betse_normal_molecule_join_protocol.json",
        "validation/betse/betse_normal_molecule_join_source_map.json",
    }
}
assert len(unchanged) == 6
for relative, expected in unchanged.items():
    assert expected == queue["owned_sha256"][relative] == sha(OLD / "source" / relative), relative
for relative, expected in queue["protected_sha256"].items():
    assert sha(ROOT / relative) == expected, relative
witnesses = {}
for name, filename in (
    (
        "molecule_adapter_before_witness",
        "betse_normal_molecule_adapter_attributes_before_02_complete.json",
    ),
    ("molecule_adapter_after_witness", "betse_normal_molecule_adapter_attributes_after_02.json"),
):
    path = WORK / filename
    witnesses[name] = dict(path=str(path), sha256=sha(path))
evidence = dict(queue["binding_evidence"])
evidence.update(witnesses)
evidence["prior_molecule_failed_static_inputs"] = dict(
    path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")
)
correction = dict(
    authority="Chief requested a narrow adapter repair after first Root molecule qualification; no numerical retry by worker",
    failure_report="Chief directly reported CPU3 first qualification:4 dependency passes,2 raw failures,15 unrun; AttributeError ignore_ECM_pump before intended instability check",
    preserved_failed_run="/mnt/workspaces/Cells/betse-normal-molecule-tests-20261030-01",
    original_static_inputs=evidence["prior_molecule_failed_static_inputs"],
    field="ignore_ECM_pump",
    value=True,
    literal_source="betse/science/chemistry/networks.py:385; transport eager read5688",
    bridge="Both production _molecules and native attach already setattr every supplied parameter; complete validated parameters/fixture now include the source True value",
    before_after=witnesses,
    inverse_AST_proof="Remove one PARAMETERS member and one validation guard from source, and one fixture keyword: all remaining AST exactly equals frozen01",
    unchanged_scientific_files=unchanged,
    unchanged_native_capture_code=True,
    scientific_bodies_unchanged=22,
    unchanged_outer_helpers=5,
    protected_files_unchanged=215,
    budgets_and_reference_unchanged=True,
    numerical_runs=0,
    physical_failure_credit=False,
    required_reachable_attributes=42,
    missing_after={"production": {}, "native": {}},
)
for relative in (
    "validation/betse/betse_normal_molecule_join_protocol.json",
    "validation/betse/betse_normal_molecule_join_source_map.json",
):
    path = ROOT / relative
    data = json.loads(path.read_text())
    data["adapter_field_repair_02"] = correction
    if relative.endswith("protocol.json"):
        data["binding_evidence"] = evidence
        data["owned_state"]["static_fields"] += (
            "; native initialization ignore_ECM_pump=True is explicit, validated and passed through both actual parameter hydration loops"
        )
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
queue.update(
    binding_evidence=evidence,
    status="adapter_02_repaired_ready_for_static_audit_no_retry",
    adapter_field_repair_02=correction,
)
queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(
    json.dumps(
        dict(
            status=queue["status"],
            changed_scientific_files=4,
            unchanged_scientific_files=6,
            unchanged_native_capture_files=3,
            protected_files=215,
            numerical_runs=0,
        )
    )
)
