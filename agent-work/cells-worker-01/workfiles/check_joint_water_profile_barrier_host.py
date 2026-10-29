"""Check source/route/selection contracts without importing numerical models."""

import ast
import hashlib
import importlib.util
import itertools
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent

# These filters partition AST declarations only. Execution always uses full node IDs.
GROUPS = (
    ("first", "complete_parent or (full_stage and joint and False)", 4, "01"),
    ("guard", "strong_background", 2, "02"),
    ("water-stage-baseline", "full_stage and water_owner and False and not joint", 8, "03"),
    ("water-stage-changed", "full_stage and water_owner and True", 9, "04"),
    ("repair-stage-baseline", "full_stage and repair_owner and False and not joint", 8, "05"),
    ("repair-stage-changed", "full_stage and repair_owner and True", 9, "06"),
    (
        "water-physics",
        "water_owner and not full_stage and not complete_parent and not strong_background "
        "and not mismatched and not corruption and not cannot_be_hidden",
        15,
        "07",
    ),
    ("water-refusals", "water_owner and (mismatched or corruption or cannot_be_hidden)", 31, "08"),
    (
        "repair-physics",
        "repair_owner and not full_stage and not complete_parent and not strong_background "
        "and not mismatched and not corruption and not cannot_be_hidden",
        15,
        "09",
    ),
    (
        "repair-refusals",
        "repair_owner and (mismatched or corruption or cannot_be_hidden)",
        31,
        "10",
    ),
    ("oracle-source", "independent_equation_source", 1, "11"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        stream.write(encoded)
        pending = Path(stream.name)
    pending.replace(path)


def merge_execution(existing, current):
    """A host refresh cannot reset numerical credit or change an active plan."""
    if not existing:
        return current
    before = {group["group"]: group for group in existing["validation_groups"]}
    after = {group["group"]: group for group in current["validation_groups"]}
    launched = any(group["status"] != "not_launched" for group in before.values())
    if launched:
        if (
            existing["product_sha256"] != current["product_sha256"]
            or existing.get("qualification_source_sha256") != current["qualification_source_sha256"]
            or before.keys() != after.keys()
        ):
            raise ValueError("Cannot refresh changed sources or group inventory after a launch")
        for name, group in after.items():
            for key in (
                "planning_filter",
                "expected_tests",
                "output",
                "command",
                "declared_test_ids",
                "nodes_file_sha256",
            ):
                if before[name][key] != group[key]:
                    raise ValueError("Cannot alter a launched qualification plan: " + name)
    for name, group in after.items():
        previous = {key: value for key, value in before.get(name, {}).items() if key != "selection"}
        after[name] = previous | group | {"status": previous.get("status", "not_launched")}
    result = existing | current
    result["validation_groups"] = list(after.values())
    result["passed_numerical_checks"] = existing.get("passed_numerical_checks", 0)
    result["status"] = existing["status"]
    return result


def keyword_match(node, label):
    if isinstance(node, ast.Expression):
        return keyword_match(node.body, label)
    if isinstance(node, ast.Name):
        return node.id.casefold() in label.casefold()
    if isinstance(node, ast.Constant) and type(node.value) is bool:
        return str(node.value).casefold() in label.casefold()
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not keyword_match(node.operand, label)
    if isinstance(node, ast.BoolOp):
        values = [keyword_match(child, label) for child in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    raise TypeError(ast.dump(node))


def declared_cases():
    fixture = ast.parse(
        (ROOT / "validation/transport/active_profile_barrier_interventions_fixtures.py").read_text()
    )
    case_values = next(
        ast.literal_eval(node.value)
        for node in fixture.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets)
    )
    tree = ast.parse((ROOT / "tests/unit/test_joint_water_profile_barriers.py").read_text())
    node_ids, categories = [], {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        groups = []
        for decorator in reversed(node.decorator_list):
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "parametrize"
            ):
                value = decorator.args[1]
                if isinstance(value, ast.Name) and value.id == "FAMILIES":
                    group = ["water_owner", "repair_owner"]
                elif isinstance(value, ast.Attribute) and value.attr == "CASES":
                    group = case_values
                else:
                    group = ast.literal_eval(value)
                groups.append(group)
        identities = [
            node.name + ("[" + "-".join(map(str, items)) + "]" if groups else "")
            for items in itertools.product(*groups)
        ]
        categories[node.name] = len(identities)
        node_ids.extend(identities)
    assert len(node_ids) == len(set(node_ids)) == 133
    return node_ids, categories


def main():
    path = WORK / "check_joint_water_profile_barriers.py"
    spec = importlib.util.spec_from_file_location("joint_water_host_checker", path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    base = json.loads((checker.BASE / "source-manifest.json").read_text())["source_sha256"]
    handoff_path = checker.WATER_BARRIERS / "HANDOFF.json"
    assert sha(handoff_path) == checker.WATER_HANDOFF_SHA256
    handoff = json.loads(handoff_path.read_text())
    inputs = checker.WATER_BARRIERS / "history-07/inputs.json"
    assert sha(inputs) == handoff["phases"]["history-07"]["source_manifest_sha256"]
    root_inventory = json.loads(inputs.read_text())["source_hashes"]
    allowed = {*checker.SHARED, "src/cells/ensemble/plan.py"}
    assert not [
        name
        for name in base.keys() & root_inventory.keys()
        if name.startswith("src/") and name not in allowed and base[name] != root_inventory[name]
    ]
    for name in checker.SUPPLEMENT:
        assert sha(checker.WATER_BARRIERS / "history-07/source" / name) == root_inventory[name]
    with tempfile.TemporaryDirectory(prefix="joint-water-profile-barrier-routes-") as temporary:
        target = Path(temporary)
        for name in checker.SHARED:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((checker.BASE / "workspace" / name).read_bytes())
        patch, metadata = checker.routes(target)
        assert len(metadata) == 4 and patch
        for name in checker.SHARED:
            ast.parse((target / name).read_text())
        for _, cls, mid in checker.OWNERS:
            assert mid in (target / "src/cells/core/specs.py").read_text()
            assert cls in (target / "src/cells/models/registry.py").read_text()
    counts = {"tests": 2, "errors": 0, "failures": 0, "skipped": 0}
    assert checker.completed_successfully(None, [], counts, 2)
    for key in ("errors", "failures", "skipped"):
        assert not checker.completed_successfully(None, [], counts | {key: 1}, 2)
    assert not checker.completed_successfully(None, [], counts, 3)
    assert not checker.completed_successfully("failed", [], counts, 2)
    assert not checker.completed_successfully(None, ["changed"], counts, 2)
    node_ids, categories = declared_cases()
    launcher = WORK / "run_joint_water_profile_barrier_group.sh"
    groups = []
    prefix = "tests/unit/test_joint_water_profile_barriers.py::"
    full_nodes = [prefix + identity for identity in node_ids]
    legacy_first = ast.parse("complete_parent or (full_stage and joint and False)", mode="eval")
    legacy_baseline = ast.parse("full_stage and water_owner and False and not joint", mode="eval")
    legacy_counts = {
        "first": sum(keyword_match(legacy_first, node) for node in full_nodes),
        "water_baseline": sum(keyword_match(legacy_baseline, node) for node in full_nodes),
    }
    assert legacy_counts == {"first": 20, "water_baseline": 0}
    for name, selection, count, number in GROUPS:
        selected = [
            prefix + identity
            for identity in node_ids
            if keyword_match(ast.parse(selection, mode="eval"), identity)
        ]
        selected = checker.exact_nodes(selected, count)
        assert name + ") count=" + str(count) + "; run=" + number in launcher.read_text()
        node_file = WORK / "node_plans" / ("joint_water_profile_barrier_" + name + ".json")
        write(node_file, selected)
        groups.append(
            {
                "group": name,
                "planning_filter": selection,
                "execution_selection": "exact node IDs; no pytest keyword filter",
                "expected_tests": count,
                "output": "/mnt/workspaces/Cells/joint-water-profile-barriers-development-20261029-"
                + number,
                "command": ["bash", str(launcher), name],
                "status": "not_launched",
                "declared_test_ids": selected,
                "nodes_file": str(node_file),
                "nodes_file_sha256": sha(node_file),
            }
        )
    assert '"-k"' not in (WORK / "check_joint_water_profile_barriers.py").read_text()
    good = [full_nodes[0]]
    assert checker.exact_nodes(good, 1) == good
    for values, expected in (
        (good, 2),
        (good * 2, 2),
        (["other.py::test_wrong"], 1),
        ([True], 1),
        (["tests/unit/test_joint_water_profile_barriers.py"], 1),
    ):
        try:
            checker.exact_nodes(values, expected)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid exact-node plan accepted")
    selected = [identity for group in groups for identity in group["declared_test_ids"]]
    assert len(selected) == len(set(selected)) == 133
    for relative in checker.NEW_FILES:
        ast.parse((ROOT / relative).read_text())
    assert not any(
        name == "cells" or name.startswith(("cells.", "numpy", "jax", "scipy"))
        for name in sys.modules
    )
    record = {
        "utc": datetime.now(UTC).isoformat(),
        "status": "passed_host_only_static_checks",
        "qualified_physical_dependencies_match": True,
        "qualified_four_water_barrier_files_verified": True,
        "private_dispatch_four_files_parse": True,
        "declared_unique_test_cases": 133,
        "test_categories": categories,
        "group_counts_exact_and_disjoint": [group["expected_tests"] for group in groups],
        "legacy_k_with_actual_filename_counts": legacy_counts,
        "exact_node_execution_and_bad_plan_refusals": True,
        "completion_guard_refusals_passed": True,
        "new_python_files_parse": len(checker.NEW_FILES),
        "no_numerical_imports_or_execution": True,
        "no_qualification_claim": True,
        "source_sha256": {relative: sha(ROOT / relative) for relative in checker.NEW_FILES},
        "launcher_sha256": sha(launcher),
        "host_checker_sha256": sha(Path(__file__).resolve()),
        "preceding_host_receipt": str(WORK / "joint_water_profile_barrier_host_check.json"),
    }
    identity = (
        sha(Path(__file__).resolve())
        + record["launcher_sha256"]
        + json.dumps(record["source_sha256"], sort_keys=True)
    )
    key = hashlib.sha256(identity.encode()).hexdigest()[:16]
    host_path = WORK / "host_checks" / ("joint_water_profile_barriers_" + key + ".json")
    if host_path.exists():
        previous = json.loads(host_path.read_text())
        assert {k: v for k, v in previous.items() if k != "utc"} == {
            k: v for k, v in record.items() if k != "utc"
        }
    else:
        write(host_path, record)
    queue = {
        "status": "implementation_draft_component_acceptance_pending",
        "utc": datetime.now(UTC).isoformat(),
        "preparation": {
            "module": "cells.core.joint_water_profile_barrier_preparation",
            "request_kind": "cells.joint_water_profile_barrier_preparation_request@1",
            "kind": "cells.joint_water_profile_barrier_preparation@1",
            "order": "static_membrane_profiles_then_extracellular_barriers@1",
            "functions": ["prepare(request)", "replay(provenance)"],
        },
        "scheduled_artifact_kind": "cells.scheduled_joint_water_profile_barriers@1",
        "owners": [
            {
                "family": family,
                "model_id": mid,
                "parent_model_id": parent,
                "schema": "cells.core." + module + "_spec",
                "runtime": "cells.models." + module,
                "class": cls,
                "physical_fields": fields,
                "scheduled_fields": fields + 1,
            }
            for family, (module, cls, mid), parent, fields in zip(
                ("water", "repair"),
                checker.OWNERS,
                ("resolved_calcium_energy_water@2", "resolved_calcium_energy_water_repair@2"),
                (43, 48),
                strict=True,
            )
        ],
        "model_fields": [
            "coupled_preparation",
            "membrane_interventions",
            "barrier_intervention",
            "phase",
            "timing_policy",
            "reset_policy",
        ],
        "execution_fields": [
            "intervention_capacity",
            "intervention_target_capacity",
            "barrier_target_capacity",
        ],
        "timing_policy": "phase_clock_rk_stage_native_logistic@1",
        "reset_policy": "fresh_phase_zero_scheduled_sim_only@1",
        "all_parent_controls_preserved": True,
        "current_volume_and_fuel_stage_layout": True,
        "original_accounting_anchors_and_histories_preserved": True,
        "minimum_volume_summed_guards_and_both_ramps_kept": True,
        "product_sha256": {relative: sha(ROOT / relative) for relative in checker.RUNTIME},
        "qualification_source_sha256": record["source_sha256"],
        "host_check": {"path": str(host_path), "sha256": sha(host_path)},
        "passed_numerical_checks": 0,
        "shared_routes_and_PROGRESS_owned_by_Chief": True,
        "root_epochs_and_existing_calcium_fuel_six_files_untouched": True,
        "no_long_or_gpu_job_launched": True,
        "automatic_approval_retry": False,
        "validation_groups": groups,
        "execution_selection": "strict exact node IDs; no pytest -k",
        "legacy_selector_limitation": (
            "Earlier host checks matched bare function/parameter labels and omitted pytest "
            "module/filename keywords. They did not validate CLI selection. Old evidence "
            "and Root failed attempts remain preserved."
        ),
    }
    queue_path = WORK / "joint_water_profile_barrier_workqueue.json"
    if queue_path.exists():
        queue = merge_execution(json.loads(queue_path.read_text()), queue)
    write(queue_path, queue)
    print(
        json.dumps(
            {
                "host_check": str(host_path),
                "api_and_queue": str(queue_path),
                "declared_tests": 133,
                "numerical_checks_passed": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
