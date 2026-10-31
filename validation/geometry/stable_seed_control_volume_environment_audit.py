"""Source-only finite-ECM prerequisite correspondence and ownership audit."""

import ast
import hashlib
import json
import sys
from pathlib import Path

CORE = "src/cells/processes/stable_seed_control_volume_environment.py"
REFERENCE = "validation/geometry/stable_seed_control_volume_environment_reference.py"
FIXTURE = "validation/geometry/stable_seed_control_volume_environment_fixtures.py"
TEST = "tests/unit/test_stable_seed_control_volume_environment.py"
PARENT = Path(
    "/mnt/workspaces/Cells/stable-seed-control-volume-physical-bridge-prepared-20261031-02"
)
PARENT_SHA256 = "93431682e3dcae1ca06a311582227f8c0d58c31ac3a64a7b811efd5c0ad25938"
REPAIR_REVIEW = Path(
    "/mnt/workspaces/Cells/stable-seed-control-volume-physical-bridge-preflight-20261031-01/"
    "repair-review-01/REVIEW.json"
)
REPAIR_REVIEW_SHA256 = "46e8976ca62fde81dfab720672bcfdfe38cf67694e3574559c889fcaf7b51fda"
PROMOTION_SHA256 = "5039bcc2026d2b915df0d17d137be6d04ea11ebb39bddefa9336da7d722b061e"
FINITE = Path("/mnt/workspaces/Cells/finite-ecm-polygon-prepared-20261031-01")
FINITE_SHA256 = "232f5762460fd03d8990a65648e7f264dccb4b8f6ee5e2514f431d127041bc9f"
ACTIVE = Path("/mnt/workspaces/Cells/active-ecm-polygon-prepared-20261031-02")
ACTIVE_SHA256 = "929db847219d12c636fade8ee6f43ff0e8fd5bfdf8ea46fc8b8c747bc4ac0400"
DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal(tree, name):
    return ast.literal_eval(
        next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        )
    )


def function(tree, name):
    return next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def calls(node):
    return {ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)}


def site(source, node):
    return dict(
        source=source,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def dict_fields(function_node, name):
    value = next(
        node.value
        for node in ast.walk(function_node)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )
    assert isinstance(value, ast.Call) and ast.unparse(value.func) == "dict"
    return {item.arg for item in value.keywords}


def inventory(project):
    project = Path(project)
    fixtures, tests = (ast.parse((project / rel).read_bytes()) for rel in (FIXTURE, TEST))
    positive, ids = literal(fixtures, "POSITIVE_CASES"), literal(fixtures, "POSITIVE_IDS")
    assert len(positive) == len(ids) == 3
    entry = "test_complete_accepted_bridge_correspondence_and_exact_obstruction"
    functions = [
        node
        for node in tests.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    checks = [TEST + "::" + entry + "[" + name + "]" for name in ids]
    checks += [TEST + "::" + node.name for node in functions if node.name != entry]
    assert len(checks) == len(set(checks)) == 8
    assert all({"build", "independent"} <= calls(node) for node in functions)
    assert {"upstream.prepare", "upstream.independent"} <= calls(function(tests, "build"))
    panels = {
        name: list(literal(tests, name))
        for name in ("REFUSALS", "EVIDENCE_REFUSALS", "CORRUPTIONS")
    }
    assert [len(value) for value in panels.values()] == [14, 8, 14]
    return dict(
        check_ids=checks,
        positive_cases=[
            dict(id=name, case=case, physical_profile=profile)
            for name, (case, profile) in zip(ids, positive, strict=True)
        ],
        panels=panels,
        positive_scope="ownership_and_obstruction_correspondence_only_not_finite_ECM_adaptation",
        top_level_pytest_trees=8,
        potential_actual_constructor_children=8,
        potential_actual_bridge_children=8,
        potential_actual_environment_children=8,
        potential_actual_nested_children=24,
        Root_finalizer=1,
        scheduled_units=9,
        total_process_units=33,
        duplicate_child_replays=0,
        completed_tests=0,
        numerical_execution=False,
        collection=False,
    )


def reference_closure(project):
    project = Path(project)
    pending, seen, rows = [REFERENCE], set(), []
    while pending:
        rel = pending.pop()
        if rel in seen:
            continue
        seen.add(rel)
        imported, local = [], []
        for node in ast.walk(ast.parse((project / rel).read_bytes())):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                names = [node.module + "." + item.name for item in node.names]
            else:
                continue
            for name in names:
                parts = name.split(".")
                assert parts[0] not in DENIED, (rel, name)
                imported.append(name)
                matched = None
                for end in range(len(parts), 0, -1):
                    path = "/".join(parts[:end]) + ".py"
                    if (project / path).is_file():
                        matched = path
                        break
                if matched:
                    pending.append(matched)
                    local.append(matched)
                else:
                    assert parts[0] in sys.stdlib_module_names, (rel, name)
        rows.append(
            dict(
                source=rel,
                sha256=sha(project / rel),
                imports=sorted(imported),
                local_dependencies=sorted(set(local)),
            )
        )
    assert seen == {
        REFERENCE,
        "validation/geometry/stable_seed_control_volume_physical_bridge_reference.py",
        "validation/geometry/stable_seed_control_volumes_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    }
    return dict(
        modules=rows,
        production_and_scientific_imports=[],
        executed=False,
        upstream_geometry_derivations_replayed=0,
    )


def audit(project):
    project = Path(project)
    for root, pin in ((PARENT, PARENT_SHA256), (FINITE, FINITE_SHA256), (ACTIVE, ACTIVE_SHA256)):
        assert sha(root / "manifest.json") == pin
    assert sha(REPAIR_REVIEW) == REPAIR_REVIEW_SHA256
    assert sha(REPAIR_REVIEW.with_name("promotion.json")) == PROMOTION_SHA256
    review = json.loads(REPAIR_REVIEW.read_text())
    assert review["blocking_findings"] == [] and review["numerical_launch_authorized"] is False
    assert review["complete_inverse_reference_AST"] and review["complete_inverse_test_AST"]
    core, reference = (ast.parse((project / rel).read_bytes()) for rel in (CORE, REFERENCE))
    assert literal(core, "SOURCE_PINS") == literal(reference, "SOURCE_PINS")
    assert list(literal(core, "INVALIDATED")) == literal(reference, "INVALIDATED")
    assert literal(core, "LAW_ID") == literal(reference, "LAW")
    pins = literal(core, "SOURCE_PINS")
    origins = {}
    for name, expected in pins.items():
        root = (
            PARENT
            if "stable_seed_control_volume_physical_bridge" in name
            else ACTIVE
            if "active_ecm" in name
            else FINITE
        )
        files = json.loads((root / "manifest.json").read_text())["file_sha256"]
        rel = "src/cells/" + name
        assert sha(project / rel) == expected == files["source/" + rel]
        origins[rel] = dict(bundle=str(root), sha256=expected)
    assert (
        literal(core, "BRIDGE_REFERENCE_SHA256")
        == literal(reference, "BRIDGE_REFERENCE_SHA256")
        == sha(
            PARENT
            / "source/validation/geometry/stable_seed_control_volume_physical_bridge_reference.py"
        )
    )
    upstream_source = ast.parse(
        (
            PARENT
            / "source/validation/geometry/stable_seed_control_volume_physical_bridge_reference.py"
        ).read_bytes()
    )
    assert "complete_vector_axes" in calls(function(upstream_source, "geometry_fields"))
    assert "complete_permeability_species" in calls(function(upstream_source, "physical_fields"))
    geometry_rel = "src/cells/processes/finite_ecm_polygon_geometry.py"
    finite = ast.parse((project / geometry_rel).read_bytes())
    construction = function(finite, "_construct")
    messages = {
        node.args[0].value: node
        for node in ast.walk(construction)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "ValueError"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    required = (
        "Region area must exactly exhaust the declared domain",
        "A physical cell cannot meet the sealed domain boundary",
        "Direct cell-cell interfaces have no declared finite cleft geometry",
        "Require membrane ownership for every cell and at least one bath-bath face",
        "Bath centroid link is not exactly orthogonal to its shared face",
    )
    assert set(required) <= set(messages)
    passive_rel = "src/cells/core/finite_ecm_polygon_preparation.py"
    active_rel = "src/cells/core/active_ecm_polygon_preparation.py"
    passive, active = (ast.parse((project / rel).read_bytes()) for rel in (passive_rel, active_rel))
    assert "geometry.validate_binding" in calls(function(passive, "prepare"))
    assert "partition.validate_binding" in calls(function(active, "prepare"))
    assert "bridge.validate_physical" in calls(function(core, "bind"))
    assert not {
        "geometry.from_partition",
        "geometry.prepare",
        "partition.prepare",
        "physical.prepare",
    } & calls(core)
    assert isinstance(function(core, "require_finite_ecm").body[0], ast.Raise)
    assert isinstance(function(core, "require_cached_operators").body[0], ast.Raise)
    assert {"_area", "Fraction.from_float"} <= calls(function(core, "_construct"))
    assert {"polygon._complex", "polygon._polygon"} <= calls(function(reference, "derive"))
    assert not {"upstream.derive", "upstream.evaluate", "upstream.constructor.derive"} & calls(
        reference
    )
    assert {"upstream.verify", "upstream.evidence", "complete_upstream_axes"} <= calls(
        function(reference, "accepted_source")
    )
    for field in ("indices", "witnesses", "provenance"):
        assert dict_fields(function(core, "_construct"), field) == dict_fields(
            function(reference, "derive"), field
        ), field
    return dict(
        kind="cells.fixed_seed_environment_prerequisite_static_correspondence@1",
        source_only=True,
        physical_bridge02_manifest_sha256=PARENT_SHA256,
        upstream_schema_repair_review_sha256=REPAIR_REVIEW_SHA256,
        upstream_schema_promotion_sha256=PROMOTION_SHA256,
        repaired_upstream_reference_sha256=literal(core, "BRIDGE_REFERENCE_SHA256"),
        finite_ECM_manifest_sha256=FINITE_SHA256,
        active_ECM_manifest_sha256=ACTIVE_SHA256,
        source_origins=origins,
        existing_contract_blockers={text: site(geometry_rel, messages[text]) for text in required},
        passive_partition_dependency=site(passive_rel, function(passive, "prepare")),
        active_partition_dependency=site(active_rel, function(active, "prepare")),
        production_witness=site(CORE, function(core, "_construct")),
        independent_integer_grid_witness=site(REFERENCE, function(reference, "derive")),
        upstream_schema_completeness_guard=site(
            REFERENCE, function(reference, "complete_upstream_axes")
        ),
        upstream_schema_repair_status="source_review_clear_pending_fresh_qualification",
        fallback_scope=(
            "source ownership correspondence and exact obstruction only; "
            "finite-ECM adaptation unavailable"
        ),
        finite_ECM_adapted=False,
        existing_core_files_changed=False,
        source_and_output_dictionary_inventories_match=True,
        inventory=inventory(project),
        reference_closure=reference_closure(project),
        preparation=dict(
            scientific_imports=0,
            geometry_evaluations=0,
            reference_evaluations=0,
            fixture_executions=0,
            test_runs=0,
            collection=0,
            numerical_jobs=0,
            GPU_jobs=0,
            polls=0,
            shared_status_edited=False,
        ),
    )
