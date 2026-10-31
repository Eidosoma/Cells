"""Source/AST-only audit of isolated initial clock/resource declarations."""

import ast
import copy
import hashlib
import json
from pathlib import Path

WORK = Path("/mnt/workspaces/Cells")
PARENT = WORK / "stable-seed-partition-physiology-bridge-prepared-20261031-01"
PARENT_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
REVIEW = WORK / "stable-seed-partition-physiology-bridge-preflight-20261031-01/REVIEW.json"
REVIEW_SHA256 = "e055f0ff664553e6c6fdf02fc777beb31e6206b3f99fead6835d088f8dd63249"
FIRST = WORK / "stable-seed-partition-advance-draft-20261031-01"
FIRST_SHA256 = "c4736118b594104d50e99c3c270dd8969e4fd5cd17604788f6da3c48c6cfdfd4"
FINITE = WORK / "finite-ecm-polygon-prepared-20261031-01"
FINITE_SHA256 = "232f5762460fd03d8990a65648e7f264dccb4b8f6ee5e2514f431d127041bc9f"
PREFIX = "validation/geometry/stable_seed_partition_advance_refinement_"
OLD = "validation/geometry/stable_seed_partition_physiology_bridge_"
WORKER, DECLARATIONS, CALLERS = (
    PREFIX + s for s in ("initial_worker.py", "declarations.py", "callers.json")
)
DENIED = {"cells", "betse", "jax", "jaxlib", "PIL", "torch"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def tree(path):
    return ast.parse(Path(path).read_bytes())


def dump(node):
    return ast.dump(node, include_attributes=False)


def assigned(module, name):
    return next(
        n.value
        for n in module.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    )


def literal(module, name):
    return ast.literal_eval(assigned(module, name))


def function(module, name):
    return next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name)


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def site(rel, node):
    return dict(
        source=rel,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(dump(node).encode()).hexdigest(),
    )


def preserved(project):
    assert sha(PARENT / "manifest.json") == PARENT_SHA256
    files = read(PARENT / "manifest.json")["file_sha256"]
    assert len(files) == 503
    for rel, pin in files.items():
        assert sha(PARENT / rel) == pin, rel
    plan = read(
        PARENT
        / "source/agent-work/cells-specialist/stable_seed_partition_physiology_bridge_plan.json"
    )
    original = plan["owned_source_sha256"]
    assert len(original) == 12
    for rel, pin in original.items():
        assert sha(project / rel) == pin, rel
    assert sha(REVIEW) == REVIEW_SHA256
    review = read(REVIEW)
    assert review["blockers"] == [] and review["packet"]["manifest_sha256"] == PARENT_SHA256
    assert sha(FIRST / "receipt.json") == FIRST_SHA256
    first = read(FIRST / "receipt.json")["source_sha256"]
    assert len(first) == 6
    for rel, pin in first.items():
        assert sha(FIRST / "original-source-capture" / rel) == pin == sha(project / rel), rel
    return dict(
        parent_manifest_sha256=PARENT_SHA256,
        parent_verified_files=503,
        original_live_owned_files_unchanged=12,
        initial_source_review_sha256=REVIEW_SHA256,
        first_advance_receipt_sha256=FIRST_SHA256,
        first_advance_source_files_unchanged=6,
    )


def helper_pins(module):
    value = assigned(module, "HELPER_PINS")
    result = {}
    for key, pin in zip(value.keys, value.values, strict=True):
        if isinstance(key, ast.Constant):
            rel = ast.literal_eval(key)
        else:
            assert isinstance(key, ast.BinOp) and isinstance(key.op, ast.Add)
            assert ast.unparse(key.left) == "PREFIX"
            rel = literal(module, "PREFIX") + ast.literal_eval(key.right)
        result[rel] = ast.literal_eval(pin)
    return result


def worker_ancestry(project):
    before = tree(PARENT / "source" / (OLD + "reference.py"))
    after = tree(project / WORKER)
    assert literal(after, "PARENT_INITIAL_REVIEW_SHA256") == REVIEW_SHA256
    assert literal(after, "PARENT_INITIAL_MANIFEST_SHA256") == PARENT_SHA256
    assert literal(after, "REFINEMENT_CALLERS_SHA256") == sha(project / CALLERS)
    old_pins, new_pins = helper_pins(before), helper_pins(after)
    assert new_pins.pop(DECLARATIONS) == sha(project / DECLARATIONS)
    assert new_pins == old_pins
    for rel, pin in helper_pins(after).items():
        assert sha(project / rel) == pin, rel
    changed = {"source_pins", "authenticate", "evaluate"}
    unchanged = {}
    for name in [n.name for n in before.body if isinstance(n, ast.FunctionDef)]:
        if name not in changed:
            assert dump(function(before, name)) == dump(function(after, name)), name
            unchanged[name] = site(WORKER, function(after, name))
    normalized = copy.deepcopy(after)
    normalized.body[0] = before.body[0]
    additions = {
        "PARENT_INITIAL_REVIEW_SHA256",
        "PARENT_INITIAL_MANIFEST_SHA256",
        "REFINEMENT_CALLERS_SHA256",
    }
    normalized.body = [
        n
        for n in normalized.body
        if not (
            isinstance(n, ast.FunctionDef)
            and n.name == "parent_initial_review"
            or isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id in additions for t in n.targets)
        )
    ]
    for node in normalized.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "HELPER_PINS" for t in node.targets
        ):
            node.value = assigned(before, "HELPER_PINS")
    source = function(normalized, "source_pins")
    assert len(source.body) == len(function(before, "source_pins").body) + 1
    addition = source.body.pop(-2)
    assert "REFINEMENT_CALLERS_SHA256" in ast.unparse(addition)
    auth = function(normalized, "authenticate")
    assert "numerical_control_id" in ast.unparse(auth.body[0])
    assert "parent_initial_source_review_json" in ast.unparse(auth.body[0])
    auth.body[0] = function(before, "authenticate").body[0]
    additions = [
        n
        for n in auth.body
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "parent_initial_review"
    ]
    assert len(additions) == 1 and additions[0].lineno < calls(auth, "source_pins")[0].lineno
    auth.body.remove(additions[0])
    imports = [
        n
        for n in ast.walk(auth)
        if isinstance(n, ast.ImportFrom) and n.module == "validation.geometry"
    ]
    successor = [
        n
        for n in imports
        if any(a.name == "stable_seed_partition_advance_refinement_declarations" for a in n.names)
    ]
    assert len(successor) == 1
    successor[0].names = [
        ast.alias(
            name="stable_seed_partition_physiology_bridge_declarations", asname="declarations"
        )
    ]
    declared = calls(auth, "declarations.declaration")
    assert len(declared) == 1
    extra = [k for k in declared[0].keywords if k.arg == "numerical_control_id"]
    assert len(extra) == 1 and ast.unparse(extra[0].value) == "payload['numerical_control_id']"
    declared[0].keywords.remove(extra[0])
    evaluated = function(normalized, "evaluate")
    for name in ("case_id", "numerical_control_id"):
        additions = [k for n in calls(evaluated, "dict") for k in n.keywords if k.arg == name]
        assert len(additions) == 3
        for n in calls(evaluated, "dict"):
            for k in list(n.keywords):
                if k.arg == name:
                    assert ast.unparse(k.value) == "payload.get('" + name + "')"
                    n.keywords.remove(k)
    assert dump(normalized) == dump(before), (
        "Worker equation/control/capture logic changed outside declared metadata scope"
    )
    return dict(
        parent_reference_sha256=sha(PARENT / "source" / (OLD + "reference.py")),
        successor_sha256=sha(project / WORKER),
        whole_module_normalized_AST_equal=True,
        unchanged_functions=unchanged,
        original_helper_pins_unchanged=old_pins,
        allowed_changes=[
            "exact parent source review binding",
            "clock/resource caller helper and JSON pins",
            "explicit per-arm authentication",
            "case/control report metadata",
        ],
    )


def import_closure(project):
    pending, closure = [WORKER], {}
    while pending:
        rel = pending.pop()
        if rel in closure:
            continue
        imports, local = [], set()
        for node in ast.walk(tree(project / rel)):
            if isinstance(node, ast.Import):
                modules = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                modules = [node.module + "." + n.name for n in node.names]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] not in DENIED, module
                imports.append(module)
                parts = module.split(".")
                for end in range(len(parts), 0, -1):
                    path = "/".join(parts[:end]) + ".py"
                    if (project / path).is_file():
                        assert path.startswith("validation/geometry/"), path
                        local.add(path)
                        break
        closure[rel] = dict(sha256=sha(project / rel), imports=sorted(imports), local=sorted(local))
        pending.extend(local)
    assert len(closure) == 9
    return closure


def caller_scope(project):
    data = read(project / CALLERS)
    old_path = project / (OLD + "callers.json")
    original = read(old_path)
    assert (
        sha(old_path)
        == data["original_callers_document_sha256"]
        == "4be058c5f6211a9a489c709ee95f371d3dd7bf0ba03c8834e789c0be3554c09f"
    )
    assert json.dumps(
        data["original_callers_document"], sort_keys=True, allow_nan=False
    ) == json.dumps(original, sort_keys=True, allow_nan=False)
    assert data["parent_initial_manifest_sha256"] == PARENT_SHA256
    assert data["parent_initial_source_review_sha256"] == REVIEW_SHA256
    assert data["clock_metadata_equivalence_shortcut"] is False
    assert data["initial_qualification_required_for_each_arm"] is True
    assert original["shared"]["experiment"] == dict(
        end_time=1e-6, observation_times=[0], junction_controls=[]
    )
    assert original["shared"]["execution"]["dt"] == 1e-6
    assert original["shared"]["execution"]["max_trace_bytes"] == 1048576
    ids = [row["id"] for row in original["cases"]]
    assert ids == data["scope"]["case_ids"] and len(ids) == 4
    arms = [data["original_arm"], *data["numerical_controls"], *data["resource_numerical_controls"]]
    assert len(arms) == 6 and len({a["id"] for a in arms}) == 6
    bindings, storage, refusals = [], [], []
    for case in original["cases"]:
        x, s = case["capacities"], len(case["species"])
        columns = (48 * s + 96) * (
            (x["capacity"] + x["extracellular_capacity"])
            + (x["membrane_capacity"] + x["face_capacity"])
        ) + 96 * (x["capacity"] + x["extracellular_capacity"]) ** 2
        for arm in arms:
            if case["id"] not in arm.get("applies_to_case_ids", ids):
                continue
            steps = arm["max_steps"]
            assert steps in (1, 2, 4) and arm["dt_s"] == 1e-6 / steps and arm["end_time_s"] == 1e-6
            times = [i * arm["dt_s"] for i in range(steps)] + [arm["end_time_s"]]
            assert times[0] == 0 and all(a < b for a, b in zip(times, times[1:], strict=False))
            cap = arm.get("max_trace_bytes", 1048576)
            required = 8 * (columns * (steps + 1 + 1) + 4 * (steps + 1))
            binding = dict(
                case_id=case["id"],
                numerical_control_id=arm["id"],
                nominal_dt_s=arm["dt_s"],
                max_steps=steps,
                end_time_s=1e-6,
                labels_s=times,
                actual_step_hex=[(b - a).hex() for a, b in zip(times, times[1:], strict=False)],
                observation_count=1,
                required_trace_bytes=required,
                declared_max_trace_bytes=cap,
                source_predicted_storage_admission=required <= cap,
            )
            bindings.append(binding)
            if "max_trace_bytes" in arm:
                assert cap == 4194304 and required <= cap
                storage.append(binding)
            elif required > cap:
                refusals.append(
                    dict(
                        case_id=case["id"],
                        numerical_control_id=arm["id"],
                        required_trace_bytes=required,
                        declared_max_trace_bytes=cap,
                        expected_refusal="Estimated trace working storage exceeds max_trace_bytes",
                    )
                )
    assert refusals == data["original_budget_refusal_controls"] and len(refusals) == 4
    assert len(bindings) == 18 and len(storage) == 6
    comparisons = []
    for case_id in ids:
        expected = ["base", "dt-half", "dt-quarter"]
        if case_id in ids[2:]:
            expected = [name + "-trace-4MiB" for name in expected]
        assert data["comparison_arm_ids"][case_id] == expected
        selected = [
            next(
                b for b in bindings if b["case_id"] == case_id and b["numerical_control_id"] == name
            )
            for name in expected
        ]
        assert len({b["declared_max_trace_bytes"] for b in selected}) == 1
        assert all(b["source_predicted_storage_admission"] for b in selected)
        comparisons.extend(selected)
    helper = tree(project / DECLARATIONS)
    assert literal(helper, "PARENT_CALLERS_SHA256") == sha(old_path)
    base = function(helper, "declaration")
    assert len(calls(base, "original.declaration")) == 1
    assert any(
        isinstance(n, ast.If)
        and ast.unparse(n.test) == "numerical_control_id == 'base'"
        and isinstance(n.body[0], ast.Return)
        and ast.unparse(n.body[0].value) == "base"
        for n in base.body
    )
    changed_targets = [
        ast.unparse(t)
        for n in ast.walk(base)
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Subscript) and ast.unparse(t).startswith("changed[")
    ]
    assert set(changed_targets) == {
        "changed['execution']['dt']",
        "changed['execution']['max_steps']",
        "changed['execution']['max_trace_bytes']",
        "changed['provenance']['resource_control']",
    }
    guard = data["resource_control"]
    assert (
        guard["process_guard_GiB"],
        guard["aggregate_guard_GiB"],
        guard["host_reserve_GiB"],
    ) == (1, 2, 8)
    return dict(
        physical_cases=4,
        new_physical_cases=0,
        original_callers_unchanged=True,
        numerical_clock_control_bindings=8,
        added_storage_bindings=6,
        total_initial_case_arm_bindings=18,
        common_endpoint_comparison_arms=12,
        bindings=bindings,
        comparison_bindings=comparisons,
        original_budget_refusal_controls=refusals,
        budget_refusals_observed=False,
        resource_sufficiency_measured=False,
        observation_times_unchanged=[0.0],
        clock_metadata_equivalence_shortcut=False,
        guards=dict(worker_GiB=1, aggregate_GiB=2, host_reserve_GiB=8),
    )


def clock_dependencies(project):
    assert sha(FINITE / "manifest.json") == FINITE_SHA256
    finite = read(FINITE / "manifest.json")["file_sha256"]
    parent = read(PARENT / "manifest.json")["file_sha256"]
    roster = {
        "src/cells/core/grid.py": ["__init__", "__getitem__", "require_refinement_model"],
        "src/cells/core/runner.py": [
            "timeline",
            "_trace_budget",
            "integration_steps",
            "validate_checkpoint",
            "_checked_eager_rollout",
        ],
        "src/cells/core/resources.py": ["trace_bytes"],
        "src/cells/core/surface_tissue_spec.py": ["parse", "to_dict"],
        "src/cells/core/schedule.py": ["event_index", "control_values"],
        "src/cells/core/specs.py": [],
        "src/cells/core/state.py": ["initialise"],
        "src/cells/models/surface_tissue.py": [
            "working_size",
            "check_steps",
            "initial_values",
            "rhs",
            "control_domain_valid",
            "check_values",
        ],
        "src/cells/numerics/fixed_step.py": ["rk4_checked_step"],
        "src/cells/processes/stable_seed_partition_physiology_bridge.py": [
            "_declaration",
            "_materialize",
            "_initial_snapshot",
            "prepare",
        ],
        "src/cells/core/finite_ecm_polygon_preparation.py": ["prepare"],
    }
    origins, sites = {}, {}
    for rel, names in roster.items():
        bundle, files = (PARENT, parent) if "source/" + rel in parent else (FINITE, finite)
        pin = files["source/" + rel]
        assert sha(bundle / "source" / rel) == pin == sha(project / rel), rel
        module = tree(project / rel)
        origins[rel] = dict(bundle=str(bundle), sha256=pin)
        sites[rel] = {name: site(rel, function(module, name)) for name in names}
        origins[rel]["clock_attribute_mentions"] = sorted(
            {
                n.lineno
                for n in ast.walk(module)
                if isinstance(n, ast.Attribute)
                and n.attr
                in {
                    "dt",
                    "end_time",
                    "max_steps",
                    "max_trace_bytes",
                    "observation_times",
                    "step_index",
                    "event_index",
                }
            }
        )
    resource_path = PARENT / "source/resource_guard.py"
    return dict(
        source_origins=origins,
        function_sites=sites,
        grid="Exact float i*dt labels plus original end; each width is adjacent-label subtraction",
        event_splitting="No events after time zero; separate dt declarations, no refinement_times",
        controls=(
            "Original time-zero availability held on each interval; "
            "endpoint uses right-continuous readout"
        ),
        admission=(
            "Schema initial admission is distinct from unchanged "
            "runner.timeline trace/step admission"
        ),
        observations=(
            "Original [0.0] retained; independent comparison samples "
            "are not experiment observations"
        ),
        physical_state=(
            "Fresh initial derive/field/RHS/accounting required separately for all 18 bindings"
        ),
        storage_formula=(
            "8*(working_columns*(steps+1+observation_count)+4*(steps+1)); observation_count=1"
        ),
        resource_guard_sha256=sha(resource_path),
        resource_guard_implementation_changed=False,
        launcher_and_finalizer_prepared=False,
        resource_sufficiency_measured=False,
    )


def audit(project):
    project = Path(project)
    return dict(
        kind="cells.partition_initial_clock_resource_successor_source_audit@1",
        source_only=True,
        source_freeze_permitted=True,
        preserved=preserved(project),
        worker_ancestry=worker_ancestry(project),
        independent_initial_import_closure=import_closure(project),
        caller_scope=caller_scope(project),
        clock_dependencies=clock_dependencies(project),
        numerical_launch_authorized=False,
        numerical_qualification_inherited=False,
        source_review_pending=True,
        tests_and_collection_executed=0,
        fixture_or_scientific_evaluations=0,
        jobs=0,
        GPU_activity=0,
        PROGRESS_edited=False,
    )
