"""Unfrozen trajectory source/metadata audit; no fixture, model or test execution."""

import argparse
import ast
import copy
import hashlib
import importlib.abc
import json
import sys
from pathlib import Path

PREFIX = "validation/geometry/stable_seed_partition_trajectory_"
CORE = "src/cells/processes/stable_seed_partition_trajectory.py"
TEST = "tests/unit/test_stable_seed_partition_trajectory.py"
PARENT = "validation/geometry/stable_seed_partition_advance_refinement_"
WORK = Path("/mnt/workspaces/Cells")
INITIAL18 = WORK / "stable-seed-partition-advance-initial-successor-prepared-20261031-01"
INITIAL18_SHA256 = "61679336deda03709b6425f6dc571222a1ffdb6a3e92af01b2378bd3270c115f"
INITIAL = WORK / "stable-seed-partition-physiology-bridge-prepared-20261031-01"
INITIAL_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
FIRST = WORK / "stable-seed-partition-advance-draft-20261031-01"
FIRST_SHA256 = "c4736118b594104d50e99c3c270dd8969e4fd5cd17604788f6da3c48c6cfdfd4"
REFINEMENT = WORK / "stable-seed-partition-advance-refinement-draft-20261031-01"
REFINEMENT_SHA256 = "adc1dd3422bc76297248ed92b5aff7e005ef6f2adbe8ff52046c52d6161e9a3e"
OWN_PY = (
    CORE,
    TEST,
    *(
        PREFIX + suffix
        for suffix in (
            "authority.py",
            "declarations.py",
            "records.py",
            "initial_worker.py",
            "worker.py",
            "dynamics.py",
            "reference.py",
            "restart.py",
            "audit.py",
        )
    ),
)
DENIED = {"cells", "betse", "jax", "jaxlib", "numpy", "scipy", "PIL", "torch", "pytest"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def tree(path):
    return ast.parse(Path(path).read_bytes())


def dump(node):
    return ast.dump(node, include_attributes=False)


def function(module, name):
    return next(
        node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == name
    )


def literal(module, name):
    def value(node):
        if isinstance(node, ast.Name):
            return literal(module, node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return value(node.left) + value(node.right)
        if isinstance(node, ast.Dict):
            return {value(k): value(v) for k, v in zip(node.keys, node.values, strict=True)}
        return ast.literal_eval(node)

    return value(
        next(
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
    )


def calls(node, name):
    return [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call) and ast.unparse(item.func) == name
    ]


def first_call(node, name):
    return min(item.lineno for item in calls(node, name))


def site(rel, node):
    return dict(
        source=rel,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(dump(node).encode()).hexdigest(),
    )


def preserved(project):
    counts = {}
    for packet, pin in ((INITIAL, INITIAL_SHA256), (INITIAL18, INITIAL18_SHA256)):
        assert sha(packet / "manifest.json") == pin
        files = read(packet / "manifest.json")["file_sha256"]
        for rel, expected in files.items():
            assert sha(packet / rel) == expected, rel
        counts[str(packet)] = len(files)
    assert counts[str(INITIAL)] == 503 and counts[str(INITIAL18)] == 530
    parent_files = read(INITIAL18 / "manifest.json")["file_sha256"]
    worker = PARENT + "initial_worker.py"
    assert sha(project / worker) == parent_files["source/" + worker]
    assert sha(FIRST / "receipt.json") == FIRST_SHA256
    old = read(FIRST / "receipt.json")["source_sha256"]
    for rel, pin in old.items():
        assert sha(project / rel) == pin == sha(FIRST / "original-source-capture" / rel), rel
    old_pins = literal(
        tree(project / "src/cells/processes/stable_seed_partition_advance.py"), "SOURCE_PINS"
    )
    for rel, pin in old_pins.items():
        assert sha(project / rel) == pin, rel
    boundary_pins = literal(tree(project / CORE), "BOUNDARY_SOURCE_PINS")
    for rel, pin in boundary_pins.items():
        assert sha(project / rel) == pin, rel
    assert sha(REFINEMENT / "receipt.json") == REFINEMENT_SHA256
    proposal = read(REFINEMENT / "receipt.json")
    # The draft receipt's exact old sources are held separately from its initial capsule.
    for rel, pin in proposal["source_sha256"].items():
        assert sha(project / rel) == pin, rel
    return dict(
        preserved_initial_packets=counts,
        original_first_advance_files=len(old),
        preserved_existing_physics_pins=len(old_pins),
        existing_window_checkpoint_source_pins=boundary_pins,
        refinement_draft_files=len(proposal["source_sha256"]),
        old_sources_changed=False,
    )


def initial_ancestry(project):
    before, after = (
        tree(project / (PARENT + "initial_worker.py")),
        tree(project / (PREFIX + "initial_worker.py")),
    )
    unchanged = {}
    for name in (
        "canonical",
        "encoded",
        "digest",
        "json_digest",
        "parse",
        "keys",
        "parent_initial_review",
        "production_pin_metadata",
        "materialization_contract",
        "physical_provenance",
        "verify",
        "evaluate",
        "safe",
        "runtime_inventory",
        "main",
    ):
        assert dump(function(before, name)) == dump(function(after, name)), name
        unchanged[name] = site(PREFIX + "initial_worker.py", function(after, name))
    assert literal(after, "DRAFT_ONLY") is True
    pins = literal(after, "HELPER_PINS")
    for rel, pin in pins.items():
        assert sha(project / rel) == pin, rel
    assert literal(after, "TRAJECTORY_CALLERS_SHA256") == sha(project / (PREFIX + "callers.json"))
    authentic = function(after, "authenticate")
    assert (
        first_call(authentic, "gate")
        < first_call(authentic, "source_pins")
        < first_call(authentic, "declarations.declaration")
    )
    assert first_call(function(after, "gate"), "trajectory_authority.require") < min(
        n.lineno for n in ast.walk(function(after, "gate")) if isinstance(n, ast.If)
    )
    assert "exact_Root_accepted_geometry_candidate_bytes" in ast.unparse(authentic)
    assert "exact_Root_accepted_geometry_report" in ast.unparse(authentic)
    assert "exact_Root_accepted_geometry_reference_input" in ast.unparse(authentic)
    return dict(
        unchanged_functions=unchanged,
        new_initial_worker_fresh_bindings_required=True,
        changed_scope="metadata_and_full_horizon_caller_binding_only",
        physics_equations_changed=False,
    )


def dynamics_ancestry(project):
    before, after = (
        tree(project / (PARENT + "dynamics.py")),
        tree(project / (PREFIX + "dynamics.py")),
    )
    unchanged = {}
    for name in ("bind", "initial", "unpack", "flatten", "stage", "evaluate", "field_snapshot"):
        assert dump(function(before, name)) == dump(function(after, name)), name
        unchanged[name] = site(PREFIX + "dynamics.py", function(after, name))
    solve = calls(function(after, "integrate_trajectory"), "solve_ivp")
    assert len(solve) == 1
    keywords = {item.arg: ast.unparse(item.value) for item in solve[0].keywords}
    assert keywords == dict(
        method="'DOP853'", rtol="2e-11", atol="atols", max_step="0.0001", dense_output="True"
    )
    old_atol = next(
        n.value
        for n in ast.walk(function(before, "integrate_common_endpoint"))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "atols" for t in n.targets)
    )
    new_atol = next(
        n.value
        for n in ast.walk(function(after, "integrate_trajectory"))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "atols" for t in n.targets)
    )
    assert dump(old_atol) == dump(new_atol)
    before_check = function(tree(project / (PARENT + "reference.py")), "check_field_rhs")
    after_check = copy.deepcopy(
        function(tree(project / (PREFIX + "reference.py")), "check_field_rhs")
    )
    assert [arg.arg for arg in after_check.args.args] == [
        arg.arg for arg in before_check.args.args
    ] + ["context", "partial", "np", "codec", "dynamics"]
    after_check.args = copy.deepcopy(before_check.args)
    assert dump(before_check) == dump(after_check)
    return dict(
        seven_unchanged_numerical_functions=unchanged,
        original_DOP853_keywords=keywords,
        original_unit_specific_atol_AST_unchanged=True,
        same_point_field_RHS_checker_AST_unchanged_except_explicit_context_arguments=True,
        raw_RHS_trials_streamed_without_truncation=True,
        reference_starts_at_true_epoch_zero=True,
    )


def driver_scope(project):
    core = tree(project / CORE)
    assert literal(core, "DRAFT_ONLY") is True
    run = function(core, "run_segment")
    auth = function(tree(project / (PREFIX + "authority.py")), "require")
    assert literal(tree(project / (PREFIX + "authority.py")), "DRAFT_ONLY") is True
    for name in (
        "INITIAL18_NUMERICAL_QUALIFICATION_SHA256",
        "FIRST_ADVANCE_SOURCE_REVIEW_SHA256",
        "FIRST_ADVANCE_NUMERICAL_QUALIFICATION_SHA256",
        "TRAJECTORY_INITIAL_MANIFEST_SHA256",
        "TRAJECTORY_INITIAL_SOURCE_REVIEW_SHA256",
        "TRAJECTORY_INITIAL_NUMERICAL_QUALIFICATION_SHA256",
        "TRAJECTORY_SOURCE_REVIEW_SHA256",
    ):
        assert literal(tree(project / (PREFIX + "authority.py")), name) is None
    scientific = [n for n in ast.walk(run) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert first_call(run, "gate") < min(n.lineno for n in scientific)
    assert first_call(run, "plan_windows") < first_call(run, "first._cells_trial")
    assert len(calls(run, "first._cells_trial")) == 1
    assert len(calls(run, "model.check_values")) == 1
    assert first_call(run, "model.balances") < first_call(run, "model.check_values")
    forbidden = {"branch_checkpoint", "timeline", "initial.prepare", "model.rhs", "model.rk4"}
    assert not any(calls(run, name) for name in forbidden)
    assert "state.layout" not in ast.unparse(run)
    assert "horizon_or_budget_changed_on_restart=False" in ast.unparse(function(core, "_binding"))
    boundary = function(core, "_boundary")
    retained = calls(boundary, "retain")
    assert len(retained) == 3
    assert (
        first_call(boundary, "model.field_values")
        < retained[1].lineno
        < first_call(boundary, "model.derivative_from_field")
    )
    # Scientific observation and advancement are gated in both child entry paths.
    worker = tree(project / (PREFIX + "worker.py"))
    assert literal(worker, "DRAFT_ONLY") is True
    launch = function(worker, "launch")
    assert first_call(launch, "authority_gate.require") < min(
        n.lineno for n in ast.walk(launch) if isinstance(n, ast.ImportFrom)
    )
    reference = tree(project / (PREFIX + "reference.py"))
    assert literal(reference, "DRAFT_ONLY") is True
    evaluate = function(reference, "evaluate")
    assert first_call(evaluate, "authenticate") < min(
        n.lineno for n in ast.walk(evaluate) if isinstance(n, (ast.Import, ast.ImportFrom))
    )
    restart = tree(project / (PREFIX + "restart.py"))
    assert literal(restart, "DRAFT_ONLY") is True
    assert not any(
        isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("cells")
        for n in ast.walk(restart)
    )
    assert "independent_accuracy_credit=False" in ast.unparse(restart)
    return dict(
        checked_kernel=site(CORE, function(core, "run_segment")),
        metadata_gate=site(PREFIX + "authority.py", auth),
        all_execution_gates_closed=True,
        uses_existing_public_window_storage_admission=True,
        uses_existing_portable_checkpoint_IO=True,
        new_full_contract_required_from_time_zero=True,
        exact_restart_is_not_accuracy=True,
        raw_boundary_retained_before_RHS_or_validity_gate=True,
        no_clock_rebase_budget_extension_retry_or_new_physics=True,
    )


def tests(project):
    module = tree(project / TEST)
    functions = [
        n for n in module.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    multiplicities = {
        "test_unfrozen_pending_receipts_block_all_science": 1,
        "test_time_scales_clocks_and_new_initial_roster_are_explicit": 1,
        "test_bounded_driver_matches_existing_checked_window_driver": 4,
        "test_fresh_process_exact_restart_carries_all_owners_and_raw_stages": 12,
        "test_restart_at_first_and_penultimate_original_boundaries": 2,
        "test_independent_full_horizon_accuracy_and_common_endpoint_refinement": 4,
        "test_original_window_storage_controls_keep_all_three_clocks": 6,
        "test_later_attempt_failure_retains_every_accepted_prefix_and_unmasked_return": 1,
        "test_checkpoint_owner_clock_dtype_shape_and_definition_defects_refuse": 7,
    }
    assert {n.name for n in functions} == set(multiplicities)
    assert literal(module, "CASES") == (
        "uniform-two-species",
        "unequal-clefts-readback-defects",
        "two-cell-four-species",
        "four-cell-reordered-gradient",
    )
    assert literal(module, "CLOCKS") == ("base", "dt-half", "dt-quarter")
    assert len(literal(module, "CORRUPTIONS")) == 7
    child = function(module, "child")
    assert len(calls(child, "subprocess.Popen")) == 1
    assert not calls(child, "process.kill")
    assert not any(
        "fixtures" in ast.unparse(n)
        for n in ast.walk(module)
        if isinstance(n, (ast.Import, ast.ImportFrom))
    )
    return dict(
        proposed_trees=sum(multiplicities.values()),
        proposed_nested_children=92,
        trees=[
            dict(name=n.name, instances=multiplicities[n.name], site=site(TEST, n))
            for n in functions
        ],
        execution_status="all_unrun_and_uncollected",
        fixture_generation=False,
    )


def audit(project):
    # This small import executes literal declarations only, under a science deny guard.
    from validation.geometry import stable_seed_partition_trajectory_declarations as declarations

    before = preserved(project)
    planned = declarations.planning_document()
    saved = declarations.document()
    assert planned == saved
    assert saved["frozen"] is False and saved["numerical_launch_authorized"] is False
    assert sum(len(row["arms"]) for row in saved["cases"]) == 18
    summary = []
    for row in saved["cases"]:
        for arm in row["arms"]:
            labels = declarations.clock_labels(row["case_id"], arm["id"])
            assert labels[-1] == row["end_time_s"] and len(labels) == arm["actual_steps"] + 1
        summary.append(
            {
                key: row[key]
                for key in ("case_id", "end_time_s", "coarse_steps", "fastest_planning_scale")
            }
            | dict(
                window_bytes=row["arms"][0]["source_predicted_window_bytes"],
                max_trace_bytes=row["arms"][0]["max_trace_bytes"],
            )
        )
    physics = initial_ancestry(project)
    dynamics = dynamics_ancestry(project)
    driver = driver_scope(project)
    proposed = tests(project)
    compiled = []
    for rel in OWN_PY:
        compile((project / rel).read_bytes(), str(project / rel), "exec")
        compiled.append(rel)
    loaded = sorted(name for name in sys.modules if name.split(".")[0] in DENIED)
    assert loaded == []
    return dict(
        kind="cells.partition_trajectory_unfrozen_source_metadata_audit@1",
        frozen=False,
        verdict="static_checks_passed_science_unrun_prerequisites_pending",
        preserved=before,
        source_value_time_scale_metadata_only=summary,
        initial_ancestry=physics,
        independent_dynamics_ancestry=dynamics,
        driver_scope=driver,
        proposed_tests=proposed,
        owned_source_sha256={rel: sha(project / rel) for rel in OWN_PY},
        compile_only=compiled,
        geometry_acceptance_sha256=declarations.GEOMETRY_ACCEPTANCE_SHA256,
        callers_sha256=sha(declarations.document_path()),
        scientific_modules_loaded=loaded,
        fixture_model_solver_evaluations=0,
        tests_run=0,
        tests_collected=0,
        jobs_launched=0,
        freeze_permitted=False,
        numerical_execution_permitted=False,
    )


class NoScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Source-only trajectory audit denies " + fullname)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.meta_path.insert(0, NoScience())
    root = Path(__file__).resolve().parents[2]
    result = audit(root)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "verdict",
                    "frozen",
                    "fixture_model_solver_evaluations",
                    "tests_run",
                    "tests_collected",
                    "jobs_launched",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
