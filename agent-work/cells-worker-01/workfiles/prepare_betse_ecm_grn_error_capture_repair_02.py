# ruff: noqa: E501
"""Static narrow repair of failure capture; preserve frozen/failed01 evidence."""

import ast
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
FROZEN = Path("/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-01")
FAILED = Path("/mnt/workspaces/Cells/betse-ecm-grn-tests-20261031-01")
JOIN = "src/cells/processes/betse_ecm_grn_join.py"
TEST = "tests/unit/test_betse_ecm_grn_join.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


inputs = json.loads((FROZEN / "inputs.json").read_text())
for path, expected in inputs["owned_sha256"].items():
    assert sha(ROOT / path) == sha(FROZEN / "source" / path) == expected, path
old_join = (ROOT / JOIN).read_text()
old_test = (ROOT / TEST).read_text()
helper = """

def _failure_snapshot(ctx, supplied_cache):
    # Supplied input and the original exception chain remain authoritative.
    # Capture diagnostics independently: no missing/partial owner is promoted
    # to a valid complete cache, and a diagnostic failure cannot mask the cause.
    result = dict(cache=None, supplied_cache=supplied_cache, available_context=None,
                  capture_errors=[])
    if ctx is None:
        return result
    owner = getattr(ctx.sim, "grn", None)
    core = getattr(owner, "core", None)
    available = dict(owner_available=owner is not None, core_available=core is not None,
                     complete_owner_cache_claimed=False)
    result["available_context"] = available
    for label, capture in (
        ("material", lambda: source.material_values(ctx.sim)),
        ("wire", lambda: source.wire(owner, ctx.sim)),
        ("coefficient_fields", lambda: {name: source.clone(getattr(ctx.sim, name))
            for name in ("D_env_weight", "D_env_weight_base", "TJ_targets")
            if hasattr(ctx.sim, name)}),
    ):
        try:
            available[label] = capture()
        except Exception as capture_error:
            result["capture_errors"].append(dict(field=label,
                type=type(capture_error).__name__, message=str(capture_error)))
    if owner is not None and core is not None:
        try:
            result["cache"] = source.cache(ctx)
        except Exception as capture_error:
            result["capture_errors"].append(dict(field="cache",
                type=type(capture_error).__name__, message=str(capture_error)))
    return result

"""
join = old_join.replace("\ndef initialize(binding):", helper + "\ndef initialize(binding):", 1)
before = 'error, dict(stage="cold", cache=source.cache(ctx), material=parent)'
assert before in join
join = join.replace(
    before, 'error, dict(stage="cold", material=parent, **_failure_snapshot(ctx, None))', 1
)
before = "            cache=None if ctx is None else source.cache(ctx),"
assert before in join
join = join.replace(before, "            **_failure_snapshot(ctx, parent.network_cache),", 1)
old_tree, new_tree = ast.parse(old_join), ast.parse(join)
oldf, newf = functions(old_tree), functions(new_tree)
inverse = copy.deepcopy(new_tree)
inverse.body = [n for n in inverse.body if getattr(n, "name", None) != "_failure_snapshot"]
for name in ("initialize", "advance"):
    target = functions(inverse)[name]
    original = oldf[name]
    new_try = next(n for n in target.body if isinstance(n, ast.Try))
    old_try = next(n for n in original.body if isinstance(n, ast.Try))
    new_try.handlers = copy.deepcopy(old_try.handlers)
assert dump(inverse) == dump(old_tree)
(ROOT / JOIN).write_text(join)

test = old_test.replace(
    "        changed = joined._state(binding, parent.material, raw, parent.controls)\n",
    "        changed = joined._state(binding, parent.material, raw, parent.controls)\n"
    '        archive(tmp_path, dependency + "-malformed-parent-before-call",\n'
    "                dict(parent=changed, supplied_cache=raw, inputs=inputs))\n",
    1,
)
needle = "            joined.advance(binding, changed)\n"
assert needle in test
test = test.replace(
    needle,
    needle
    + """        archive(tmp_path, dependency + "-available-partial", dict(partial=caught.value.partial))
        if dependency in ("missing_cache", "missing_default"):
            partial = caught.value.partial
            assert partial["cache"] is None
            assert partial["available_context"]["owner_available"] is False
            assert partial["available_context"]["core_available"] is False
            assert partial["available_context"]["complete_owner_cache_claimed"] is False
            assert not partial["capture_errors"]
            old.exact_nested(partial["supplied_cache"], raw)
            assert partial["available_context"]["wire"]["owner_fields"] == {}
""",
    1,
)
old_tree, new_tree = ast.parse(old_test), ast.parse(test)
inverse = copy.deepcopy(new_tree)
original = functions(old_tree)["test_ecm_grn_dependencies"]
for i, node in enumerate(inverse.body):
    if getattr(node, "name", None) == "test_ecm_grn_dependencies":
        inverse.body[i] = copy.deepcopy(original)
assert dump(inverse) == dump(old_tree)
(ROOT / TEST).write_text(test)

xml = ET.parse(FAILED / "run-dependencies/tests.xml").getroot()
cases = list(xml.iter("testcase"))
failed = [n for n in cases if n.find("failure") is not None or n.find("error") is not None]
assert len(cases) == 8 and len(failed) == 2
assert {n.attrib["name"] for n in failed} == {
    "test_ecm_grn_dependencies[missing_cache]",
    "test_ecm_grn_dependencies[missing_default]",
}
saved = {
    str(path): sha(path)
    for path in (
        FROZEN / "inputs.json",
        WORK / "betse_ecm_grn_static_receipt_01.json",
        FAILED / "failure.json",
        FAILED / "run-dependencies/failure.json",
        FAILED / "run-dependencies/tests.xml",
    )
}
witness = dict(
    kind="cells.ecm_grn_error_capture_repair_02@1",
    scope="Error capture only; no scientific law, native comparator, fixture/case/ID or tolerance change",
    initial_round=dict(
        output=str(FAILED),
        passed=6,
        failed=2,
        unrun=17,
        accepted=False,
        completed_positive_histories=0,
        independent_reference_forms_credited=0,
    ),
    original_failure="source.restore rejects missing_cache/default before ctx.sim.grn exists; old advance exception handler calls source.cache(ctx) and masks ValueError with AttributeError",
    repair="Cache capture guarded by actual owner/core presence; separately labelled available context and malformed supplied input retained. Every diagnostic call is guarded; original exception cause chain remains. Test archives malformed parent/input before invocation.",
    original_exception_chain_preserved=True,
    complete_owner_cache_not_fabricated=True,
    raw_inputs_durable_before_failing_call=True,
    join_whole_AST_equal_after_reverting_only_exception_handlers_and_removing_new_helper=True,
    all_other_test_module_AST_equal=True,
    existing_fixture_case_IDs_budgets_unchanged=True,
    five_other_scientific_Python_files_byte_exact=True,
    saved_failed_and_frozen01_sha256=saved,
    changed_before={JOIN: inputs["owned_sha256"][JOIN], TEST: inputs["owned_sha256"][TEST]},
    scientific_imports=0,
    scientific_AST_executions=0,
    numerical_runs=0,
    pytest_collection_runs=0,
    automatic_retry=False,
)
path = WORK / "betse_ecm_grn_error_capture_witness_02.json"
assert not path.exists()
write(path, witness)
qpath = WORK / "betse_ecm_grn_workqueue.json"
q = json.loads(qpath.read_text())
q["error_capture_repair_02"] = dict(
    witness=str(path),
    sha256=sha(path),
    **{
        key: witness[key]
        for key in (
            "scope",
            "initial_round",
            "original_exception_chain_preserved",
            "complete_owner_cache_not_fabricated",
            "raw_inputs_durable_before_failing_call",
        )
    },
)
for label, path in (
    ("failed_ecm01_inputs", FROZEN / "inputs.json"),
    ("failed_ecm01_static_receipt", WORK / "betse_ecm_grn_static_receipt_01.json"),
    ("failed_ecm01_round", FAILED / "failure.json"),
    ("failed_ecm01_dependencies", FAILED / "run-dependencies/failure.json"),
    ("failed_ecm01_junit", FAILED / "run-dependencies/tests.xml"),
    ("ecm_error_capture_witness02", WORK / "betse_ecm_grn_error_capture_witness_02.json"),
):
    q["binding_evidence"][label] = dict(path=str(path), sha256=sha(path))
q["workfiles"] += [
    "agent-work/cells-worker-01/workfiles/" + name
    for name in (
        "prepare_betse_ecm_grn_error_capture_repair_02.py",
        "betse_ecm_grn_error_capture_witness_02.json",
    )
]
q["status"] = "error_capture_repair02_requires_static_audit_no_retry"
write(qpath, q)
protocol_path = ROOT / "validation/betse/betse_ecm_grn_protocol.json"
protocol = json.loads(protocol_path.read_text())
protocol["error_capture_repair_02"] = q["error_capture_repair_02"]
protocol["binding_evidence"] = q["binding_evidence"]
write(protocol_path, protocol)
mapping_path = ROOT / "validation/betse/betse_ecm_grn_source_map.json"
mapping = json.loads(mapping_path.read_text())
mapping["error_capture_repair_02"] = q["error_capture_repair_02"]
write(mapping_path, mapping)
print(
    json.dumps(
        dict(
            repair="ECM error capture02",
            passed_before=6,
            failed_before=2,
            unrun=17,
            inverse_AST_exact=True,
            scientific_execution=False,
        )
    )
)
