"""Common-endpoint source audit; no module, fixture or test execution."""

import ast
import copy
import hashlib
import json
import runpy
from pathlib import Path

PREFIX = "validation/geometry/stable_seed_partition_advance_refinement_"
CORE = "src/cells/processes/stable_seed_partition_advance_refinement.py"
FIRST_CORE = "src/cells/processes/stable_seed_partition_advance.py"
REFERENCE = PREFIX + "reference.py"
DYNAMICS = PREFIX + "dynamics.py"
TEST = "tests/unit/test_stable_seed_partition_advance_refinement.py"
FINITE = Path("/mnt/workspaces/Cells/finite-ecm-polygon-prepared-20261031-01")
ORIGINAL = "validation/tissue/surface_dynamics_reference.py"
ORIGINAL_SHA256 = "b55ff84dcf83f282f9dd6d695cf73510b1cdb99d863d42e7c16ef9d8ca5d0fcd"
PROTOCOL = "validation/tissue/surface_dynamics_protocol.json"
PROTOCOL_SHA256 = "2f708a1a8e05716357d62ce1e354a1ac5dcbdac4e2f7aae256486e28a8f565c0"
FIRST_SHA256 = "2a92b3f55ee0a3c7b4374dcd5da4f48aa8234e3ad947712fdc7fc4d53c3d580c"
INITIAL_SUCCESSOR = Path(
    "/mnt/workspaces/Cells/stable-seed-partition-advance-initial-successor-prepared-20261031-01"
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return ast.parse(Path(path).read_bytes())


def dump(node):
    return ast.dump(node, include_attributes=False)


def function(module, name):
    return next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name)


def literal(module, name):
    return ast.literal_eval(
        next(
            n.value
            for n in module.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
    )


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def call_line(node, name):
    return min(n.lineno for n in calls(node, name))


def retention_line(node, name, callee="capture"):
    return next(
        n.lineno
        for n in calls(node, callee)
        if isinstance(n.args[0], ast.Constant) and n.args[0].value == name
    )


def site(rel, node):
    return dict(
        source=rel,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(dump(node).encode()).hexdigest(),
    )


def dynamics_ancestry(project):
    assert sha(FINITE / "source" / ORIGINAL) == ORIGINAL_SHA256 == sha(project / ORIGINAL)
    assert sha(FINITE / "source" / PROTOCOL) == PROTOCOL_SHA256 == sha(project / PROTOCOL)
    before, after = tree(project / ORIGINAL), tree(project / DYNAMICS)
    unchanged = {}
    for name in ("bind", "initial", "unpack", "flatten", "stage"):
        assert dump(function(before, name)) == dump(function(after, name)), name
        unchanged[name] = site(DYNAMICS, function(after, name))
    evaluated = copy.deepcopy(function(after, "evaluate"))
    original = function(before, "evaluate")
    assert [a.arg for a in evaluated.args.args] == ["c", "state", "time", "partial"]
    assert [a.arg for a in evaluated.args.kwonlyargs] == ["evaluation_time_s"]
    evaluated.args = copy.deepcopy(original.args)
    retained = []
    body = []
    for n in evaluated.body:
        if isinstance(n, ast.Assign):
            target = ast.unparse(n.targets[0])
            if target == "event" or target.startswith("event[") or target == "partial['stage']":
                retained.append(site(DYNAMICS, n))
                continue
            if target == "flat":
                assert ast.unparse(n.value) == "flatten(c, result)"
                continue
        if (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and ast.unparse(n.value.func) == "partial['rhs_trials'].append"
        ):
            retained.append(site(DYNAMICS, n))
            continue
        body.append(n)
    evaluated.body = body
    solved = calls(evaluated, "electrical.solve")
    assert len(solved) == 1 and ast.unparse(solved[0].args[1]) == "event['root']"
    solved[0].args.pop()
    assert ast.unparse(evaluated.body[-1]) == "return (flat, phi, proof)"
    evaluated.body[-1] = copy.deepcopy(original.body[-1])
    assert dump(evaluated) == dump(original), (
        "Independent RHS equations changed outside capture arguments"
    )
    assert len(retained) == 10
    integration = function(after, "integrate_common_endpoint")
    old_solve = calls(before, "solve_ivp")
    new_solve = calls(integration, "solve_ivp")
    assert len(old_solve) == len(new_solve) == 1
    old_kw = {k.arg: ast.unparse(k.value) for k in old_solve[0].keywords}
    new_kw = {k.arg: ast.unparse(k.value) for k in new_solve[0].keywords}
    assert {k: v for k, v in new_kw.items() if k != "atol"} == {
        k: v for k, v in old_kw.items() if k != "atol"
    }
    assert new_kw["atol"] == old_kw["atol"] == "atols"
    atols = [
        n.value
        for n in ast.walk(integration)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "atols" for t in n.targets)
    ]
    old_atols = [
        n.value
        for n in ast.walk(before)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "atols" for t in n.targets)
    ]
    assert len(atols) == len(old_atols) == 1
    normalized_atols = copy.deepcopy(atols[0])
    for n in ast.walk(normalized_atols):
        if isinstance(n, ast.Name) and n.id == "context":
            n.id = "c"
        if isinstance(n, ast.Name) and n.id == "key":
            n.id = "k"
    assert dump(normalized_atols) == dump(old_atols[0])
    returned = next(
        n.lineno
        for n in ast.walk(integration)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "segment['returned']"
    )
    dense = next(
        n.lineno
        for n in ast.walk(integration)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "segment['dense_output']"
    )
    gate = next(
        n.lineno
        for n in ast.walk(integration)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "not sol.success"
    )
    assert returned < dense < gate
    field = function(after, "field_snapshot")
    values = next(
        n.value
        for n in field.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "values" for t in n.targets)
    )
    assert len(values.keywords) == 21
    imports = [n.module for n in ast.walk(after) if isinstance(n, ast.ImportFrom)]
    assert imports == ["scipy.integrate", "validation.geometry", "validation.geometry"]
    return dict(
        parent_sha256=ORIGINAL_SHA256,
        parent_protocol_sha256=PROTOCOL_SHA256,
        five_unchanged_functions=unchanged,
        RHS_normalized_AST_unchanged=True,
        capture_additions=retained,
        DOP853_keywords_unchanged=new_kw,
        unit_specific_reference_atol_AST_unchanged=True,
        complete_solver_return_and_dense_interpolants_retained_before_success_gate=True,
        field_snapshot=site(DYNAMICS, field),
        full_field_count=21,
        new_field_assembly_requires_independent_source_review=True,
    )


def production_scope(project):
    core, first = tree(project / CORE), tree(project / FIRST_CORE)
    assert sha(project / FIRST_CORE) == FIRST_SHA256 == literal(core, "FIRST_ADVANCE_SOURCE_SHA256")
    assert literal(core, "DRAFT_ONLY") is False
    manifest_pin = literal(core, "INITIAL_SUCCESSOR_MANIFEST_SHA256")
    if manifest_pin is not None:
        assert sha(INITIAL_SUCCESSOR / "manifest.json") == manifest_pin
        files = json.loads((INITIAL_SUCCESSOR / "manifest.json").read_text())["file_sha256"]
        for rel in (CORE, REFERENCE, DYNAMICS, TEST, PREFIX + "audit.py"):
            assert "source/" + rel not in files, "Initial packet must exclude advancing source"
    for name in (
        "INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256",
        "INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256",
    ):
        assert literal(core, name) == ACCEPTED_INITIAL_RECEIPTS[name]
    gate = function(core, "gate")
    assert isinstance(gate.body[0], ast.If) and isinstance(gate.body[0].body[0], ast.Raise)
    bind, advance, execute = (function(core, name) for name in ("bind", "advance", "_execute_arm"))
    assert call_line(bind, "gate") < call_line(bind, "_qualified_arm")
    assert call_line(advance, "gate") < call_line(advance, "_execute_arm")
    assert len(calls(execute, "first._cells_trial")) == 1
    assert (
        call_line(execute, "timeline")
        < call_line(execute, "model.initial_values")
        < call_line(execute, "first._cells_trial")
    )
    assert (
        call_line(execute, "model.balances")
        < retention_line(execute, "raw_integrated_balances")
        < call_line(execute, "model.check_values")
    )
    assert (
        call_line(execute, "model.check_values")
        < call_line(execute, "model.field_values")
        < call_line(execute, "model.derivative_from_field")
    )
    assert len(calls(execute, "validate_checkpoint")) == 2
    for forbidden in (
        "initial.prepare",
        "initial._initial_snapshot",
        "initial._initial_accounting",
        "solve_ivp",
        "rk4_step",
        "array_rk4_step",
        "np.clip",
        "retry",
        "subdivide",
    ):
        assert not calls(core, forbidden), forbidden
    operation = function(first, "_cells_trial")
    assert len(calls(operation, "rk4_checked_step")) == 1
    assert retention_line(operation, "cells_checked_kernel_return", "retain") < max(
        n.lineno for n in calls(operation, "_require")
    )
    assert "completed_prefix_checkpoints" in ast.unparse(execute)
    assert "completed_boundary_fields_RHS" in ast.unparse(execute)
    assert "completed_cells_step_attempts" in ast.unparse(execute)
    assert "traceback.format_exc()" in ast.unparse(advance) and "cause.__cause__" in ast.unparse(
        advance
    )
    return dict(
        core_sha256=sha(project / CORE),
        original_first_core_sha256=FIRST_SHA256,
        unchanged_existing_Cells_trial_callback=site(FIRST_CORE, operation),
        source_sites={
            name: site(CORE, function(core, name))
            for name in ("gate", "bind", "_qualified_arm", "_execute_arm", "advance")
        },
        unchanged_timeline_storage_admission_before_all_steps=True,
        complete_history_uses_existing_integrated_checks=True,
        original_layout_and_all_twelve_state_ledgers_carried=True,
        complete_prefix_and_unmasked_failure_evidence_retained=True,
        no_field_cache_or_initial_accounting_after_advancement=True,
        new_physical_law=False,
        numerical_tolerances_changed=False,
    )


def reference_scope(project):
    module = tree(project / REFERENCE)
    assert literal(module, "DRAFT_ONLY") is False
    assert literal(module, "INITIAL_SUCCESSOR_MANIFEST_SHA256") == literal(
        tree(project / CORE), "INITIAL_SUCCESSOR_MANIFEST_SHA256"
    )
    for name in (
        "INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256",
        "INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256",
    ):
        assert literal(module, name) == ACCEPTED_INITIAL_RECEIPTS[name]
    auth, evaluate = function(module, "authenticate"), function(module, "evaluate")
    assert call_line(auth, "gate") < call_line(auth, "metadata.authenticate")
    imports = [n.lineno for n in ast.walk(evaluate) if isinstance(n, ast.ImportFrom)]
    assert call_line(evaluate, "authenticate") < min(imports)
    compare = function(module, "compare")
    assert len(calls(compare, "codec.compare_arrays")) == 1
    assert len(calls(compare, "dynamics.electrical.check")) == 1
    assert len(calls(evaluate, "dynamics.integrate_common_endpoint")) == 1
    text = ast.unparse(compare)
    for clause in (
        "3e-23 if name.endswith('_C') else 3e-12",
        "3e-25 if name.endswith('_C') else 2e-11",
        "errors[-1] <= max(errors[0] * 0.2, 3e-13)",
        "charge_errors[-1] <= max(charge_errors[0] * 0.2, 3e-27)",
    ):
        assert clause in text, clause
    assert len(calls(compare, "np.array_equal")) >= 5
    return dict(
        reference_sha256=sha(project / REFERENCE),
        actual_independent_fresh_process_required=True,
        production_and_JAX_imports_denied=True,
        complete_field_RHS_and_trial_links=True,
        every_clock_has_separate_positive_initial_worker_evidence=True,
        source_review_and_numerical_qualification_receipts_pending=True,
        exact_rtol=3e-9,
        amount_energy_atol=2e-11,
        charge_atol_C=3e-25,
        endpoint_voltage_atol_V=2e-8,
        same_point_RHS_rtol=3e-10,
        same_point_RHS_amount_energy_atol=3e-12,
        same_point_RHS_charge_atol_A=3e-23,
        refinement_error_limit=0.2,
        amount_energy_floor=3e-13,
        charge_floor_C=3e-27,
        fourth_order_claimed=False,
        all_failures_and_raw_reference_trials_retained=True,
    )


def test_roster(project):
    module = tree(project / TEST)
    cases, refusals = literal(module, "CASES"), literal(module, "BUDGET_REFUSALS")
    assert len(cases) == len(refusals) == 4
    functions = [
        n for n in module.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(functions) == 6
    ids, children = [], []
    for node in functions:
        base = TEST + "::" + node.name
        if node.name in {
            "test_complete_common_endpoint_matches_existing_Cells_driver",
            "test_independent_common_endpoint_and_original_refinement_budgets",
        }:
            expanded = [base + "[" + case + "]" for case in cases]
        elif node.name == "test_original_1MiB_storage_refusals_are_not_reclassified":
            expanded = [base + "[" + case + "-" + control + "]" for case, control in refusals]
        else:
            expanded = [base]
        ids.extend(expanded)
        if node.name == "test_independent_common_endpoint_and_original_refinement_budgets":
            assert len(calls(node, "subprocess.Popen")) == 1
            children.extend(expanded)
    assert len(ids) == len(set(ids)) == 15 and len(children) == 4
    helper = function(module, "request_from_qualified_index")
    assert call_line(helper, "common.gate") < min(
        n.lineno for n in ast.walk(helper) if isinstance(n, ast.ImportFrom)
    )
    assert not calls(module, "initial.prepare")
    return dict(
        functions=6,
        pytest_trees=15,
        exact_source_predicted_ids=ids,
        nested_independent_reference_children=4,
        nested_child_parent_ids=children,
        independent_reference_replay=False,
        new_scientific_cases=0,
        collected=False,
        executed=0,
        initial_qualified_index_required=True,
        launcher_finalizer_and_measured_resource_sufficiency_pending=True,
    )


def audit(project):
    project = Path(project)
    initial = runpy.run_path(str(project / (PREFIX + "initial_audit.py")))["audit"](project)
    return dict(
        kind="cells.partition_common_endpoint_refinement_source_audit@1",
        source_only=True,
        initial_successor_source_audit=initial,
        production=production_scope(project),
        independent_dynamics=dynamics_ancestry(project),
        independent_comparison=reference_scope(project),
        prospective_tests=test_roster(project),
        numerical_execution_permitted=False,
        numerical_launch_authorized=False,
        new_physical_cases=0,
        science_imports=0,
        model_or_reference_evaluations=0,
        fixtures=0,
        tests=0,
        collection=0,
        jobs=0,
        polls=0,
        GPU_activity=0,
        PROGRESS_edited=False,
    )


ACCEPTED_INITIAL_RECEIPTS = {
    "INITIAL_SUCCESSOR_SOURCE_REVIEW_SHA256": (
        "84440f74eff19c7a96a275afb81f99ccc0eecc241d484c4cb3c9a13735f1f614"
    ),
    "INITIAL_SUCCESSOR_NUMERICAL_QUALIFICATION_SHA256": (
        "5aad4bce5c8f90020b0bc09786a6e7d4aad11cc71d25b2f1109556f572c788cc"
    ),
}
