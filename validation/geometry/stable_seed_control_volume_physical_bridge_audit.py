"""Static source, field inventory and provenance audit; no model imports."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/stable_seed_control_volume_physical_bridge.py"
REFERENCE = "validation/geometry/stable_seed_control_volume_physical_bridge_reference.py"
FIXTURES = "validation/geometry/stable_seed_control_volume_physical_bridge_fixtures.py"
TEST = "tests/unit/test_stable_seed_control_volume_physical_bridge.py"
DOMAINS = "validation/geometry/stable_seed_control_volume_physical_bridge_domains.json"
CONSTRUCTOR_BUNDLE = Path("/mnt/workspaces/Cells/stable-seed-control-volumes-prepared-20261031-01")
CONSTRUCTOR_MANIFEST_SHA256 = "e882288ebec80abf4096cb87f7769f73400a5b713bb61c51f580af1aa71648cc"
POLYGON_BUNDLE = Path("/mnt/workspaces/Cells/conservative-polygon-geometry-prepared-20261030-02")
POLYGON_MANIFEST_SHA256 = "2a1182f4091761f20c8048e0bd8cf8281ff67b808410be2820dddb4531f1d95b"
REVIEW = Path("/mnt/workspaces/Cells/stable-seed-control-volumes-preflight-20261031-01/REVIEW.json")
REPAIR_REVIEW = Path(
    "/mnt/workspaces/Cells/stable-seed-control-volume-physical-bridge-preflight-20261031-01/"
    "repair-review-01/REVIEW.json"
)
REPAIR_REVIEW_SHA256 = "46e8976ca62fde81dfab720672bcfdfe38cf67694e3574559c889fcaf7b51fda"
PROMOTION = REPAIR_REVIEW.with_name("promotion.json")
PROMOTION_SHA256 = "5039bcc2026d2b915df0d17d137be6d04ea11ebb39bddefa9336da7d722b061e"
REPAIRED_REFERENCE_SHA256 = "817cec999961c7403e99addead76a720caad8ef16011a1a4e2f6319d0d72ee8c"
REPAIRED_TEST_SHA256 = "306657230727f680dc85db5b426d0e642b0f7ccd19be3c13ac12bb6d00077be2"
DENIED = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "PIL", "torch"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expression_literal(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        assert not node.args and all(item.arg is not None for item in node.keywords)
        return {item.arg: expression_literal(item.value) for item in node.keywords}
    return ast.literal_eval(node)


def literal(tree, name):
    return expression_literal(
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
    return [ast.unparse(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)]


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def returned_dict_keys(node):
    returned = next(child.value for child in node.body if isinstance(child, ast.Return))
    assert isinstance(returned, ast.Call) and ast.unparse(returned.func) == "dict"
    return {item.arg for item in returned.keywords}


def assigned_dict_keys(node, name):
    value = next(
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in child.targets)
    )
    assert isinstance(value, ast.Call) and ast.unparse(value.func) == "dict"
    return {item.arg for item in value.keywords}


def required_keys(tree, function_name, variable):
    return expression_literal(
        next(
            child.args[1]
            for child in ast.walk(function(tree, function_name))
            if isinstance(child, ast.Call)
            and ast.unparse(child.func) == "keys"
            and ast.unparse(child.args[0]) == variable
        )
    )


def dataclass_fields(tree, name):
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    return {node.target.id for node in cls.body if isinstance(node, ast.AnnAssign)}


def inventory(project):
    project = Path(project)
    tests, fixtures = (ast.parse((project / path).read_bytes()) for path in (TEST, FIXTURES))
    positive = literal(fixtures, "POSITIVE_CASES")
    ids = literal(fixtures, "POSITIVE_IDS")
    assert len(positive) == len(ids) == 3 and len(set(ids)) == 3
    entry = "test_complete_manufactured_geometry_and_physical_owners"
    functions = [
        node.name
        for node in tests.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    checks = [TEST + "::" + entry + "[" + name + "]" for name in ids]
    checks += [TEST + "::" + name for name in functions if name != entry]
    assert len(checks) == len(set(checks)) == 10
    assert all("independent" in calls(function(tests, name)) for name in functions)
    assert "constructor" in calls(function(tests, "prepare"))
    groups = {
        name: list(literal(tests, name))
        for name in (
            "DECLARATION_REFUSALS",
            "EVIDENCE_REFUSALS",
            "GEOMETRY_CORRUPTIONS",
            "PHYSICAL_CORRUPTIONS",
            "PHYSICAL_REFUSALS",
        )
    }
    assert [len(rows) for rows in groups.values()] == [14, 9, 19, 14, 12]
    assert all(len(rows) == len(set(rows)) for rows in groups.values())
    return dict(
        check_ids=checks,
        positive_cases=[
            dict(id=name, case=case, physical=physical)
            for name, (case, physical) in zip(ids, positive, strict=True)
        ],
        assertion_panels=groups,
        completed_checks=0,
        collection_performed=False,
        top_level_pytest_trees=10,
        potential_actual_nested_constructor_children=10,
        potential_actual_nested_bridge_children=10,
        actual_nested_reference_children_executed=0,
        potential_actual_nested_reference_children=20,
        Root_finalizer=1,
        scheduled_units=11,
        total_process_units=31,
        duplicate_child_replays=0,
    )


def reference_closure(project):
    project = Path(project)
    pending, seen, rows = [REFERENCE], set(), []
    while pending:
        source = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        imported, local = [], []
        for node in ast.walk(ast.parse((project / source).read_bytes())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0
                names = [node.module + "." + alias.name for alias in node.names]
            else:
                continue
            for name in names:
                parts = name.split(".")
                assert parts[0] not in DENIED, (source, name)
                imported.append(name)
                match = None
                for end in range(len(parts), 0, -1):
                    path = "/".join(parts[:end]) + ".py"
                    if (project / path).is_file():
                        match = path
                        break
                if match:
                    pending.append(match)
                    local.append(match)
                else:
                    assert parts[0] in __import__("sys").stdlib_module_names, (source, name)
        rows.append(
            dict(
                source=source,
                sha256=sha(project / source),
                imports=sorted(imported),
                local_dependencies=sorted(set(local)),
            )
        )
    assert seen == {
        REFERENCE,
        "validation/geometry/stable_seed_control_volumes_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    }
    return dict(
        kind="cells.fixed_seed_physical_bridge_independent_reference_AST_closure@1",
        modules=rows,
        production_and_scientific_imports=[],
        executed=False,
        constructor_derivation_replayed=False,
    )


def audit(project):
    project = Path(project)
    core, reference = (ast.parse((project / path).read_bytes()) for path in (CORE, REFERENCE))
    assert sha(REPAIR_REVIEW) == REPAIR_REVIEW_SHA256
    assert sha(PROMOTION) == PROMOTION_SHA256
    reviewed = json.loads(REPAIR_REVIEW.read_text())
    assert reviewed["status"] == "source_schema_repair_clear_pending_fresh_qualification"
    assert reviewed["blocking_findings"] == []
    assert reviewed["numerical_launch_authorized"] is False
    assert reviewed["complete_inverse_reference_AST"] and reviewed["complete_inverse_test_AST"]
    promoted = json.loads(PROMOTION.read_text())
    assert promoted["scientific_credit"] == 0 and promoted["tests_executed"] == 0
    for source, expected in ((REFERENCE, REPAIRED_REFERENCE_SHA256), (TEST, REPAIRED_TEST_SHA256)):
        assert sha(project / source) == expected == reviewed["source"][source]["sha256"]
        assert any(
            row["sha256"] == expected and row["path"].endswith("/" + source)
            for row in promoted["promoted"]
        )
    assert "complete_vector_axes" in calls(function(reference, "geometry_fields"))
    assert "complete_permeability_species" in calls(function(reference, "physical_fields"))
    assert sha(CONSTRUCTOR_BUNDLE / "manifest.json") == CONSTRUCTOR_MANIFEST_SHA256
    assert sha(POLYGON_BUNDLE / "manifest.json") == POLYGON_MANIFEST_SHA256
    assert sha(REVIEW) == literal(core, "CONSTRUCTOR_SOURCE_REVIEW_SHA256")
    constructor_manifest = json.loads((CONSTRUCTOR_BUNDLE / "manifest.json").read_text())[
        "file_sha256"
    ]
    polygon_manifest = json.loads((POLYGON_BUNDLE / "manifest.json").read_text())["file_sha256"]
    for path, expected in literal(core, "SOURCE_PINS").items():
        parent = (
            constructor_manifest
            if path.endswith("stable_seed_control_volumes.py")
            else polygon_manifest
        )
        assert (
            sha(project / "src/cells" / path) == expected == parent["source/src/cells/" + path]
        ), path
    assert literal(core, "SOURCE_PINS") == literal(reference, "SOURCE_PINS")
    assert list(literal(core, "INVALIDATED")) == literal(reference, "INVALIDATED")
    scope = literal(core, "SCOPE_CORRECTION")
    scope["missing_envelope_cases"] = list(scope["missing_envelope_cases"])
    assert scope == literal(reference, "SCOPE_CORRECTION")
    assert literal(core, "LAW_ID") == literal(reference, "LAW")
    assert literal(core, "INPUT_KIND") == literal(reference, "INPUT_KIND")
    assert literal(core, "CONSTRUCTOR_REFERENCE_SHA256") == literal(
        reference, "CONSTRUCTOR_REFERENCE_SHA256"
    )
    assert literal(core, "CONSTRUCTOR_SOURCE_REVIEW_SHA256") == literal(
        reference, "CONSTRUCTOR_SOURCE_REVIEW_SHA256"
    )
    physical_source = ast.parse(
        (project / "src/cells/core/conservative_polygon_tissue_preparation.py").read_bytes()
    )
    assert literal(physical_source, "ADMISSION_SOURCE_SHA256") == literal(
        reference, "PHYSICAL_PINS"
    )
    assert literal(reference, "POLYGON_REFERENCE_SHA256") == sha(
        project / "validation/geometry/conservative_polygon_geometry_reference.py"
    )
    assert literal(reference, "CONSTRUCTOR_REFERENCE_SHA256") == sha(
        project / "validation/geometry/stable_seed_control_volumes_reference.py"
    )
    assert {"geometry.from_polygons", "geometry.prepare", "_owner_maps", "_conservation"} <= set(
        calls(function(core, "prepare"))
    )
    assert "physical.prepare" in calls(function(core, "prepare_physical"))
    assert "volumes.prepare" in calls(function(core, "bind"))
    assert "_positive_constructor_evidence" in calls(function(core, "bind"))
    assert "geometry.from_generated" not in calls(core)
    assert isinstance(function(core, "require_cached_operators").body[0], ast.Raise)
    polygon_source = function(core, "polygon_input")
    cached_keys = [
        ast.literal_eval(node.slice)
        for node in ast.walk(polygon_source)
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "cv.stored_geometry"
    ]
    assert set(cached_keys) == {"vertices_m", "cells"}
    assert not {
        "constructor.derive",
        "constructor.evaluate",
        "constructor.independent_partition",
    } & set(calls(reference))
    assert {
        "constructor.authenticate",
        "constructor.verify",
        "polygons.evaluate",
        "polygons.compare",
        "polygons.compare_physical",
    } <= set(calls(reference))
    assert not any(
        isinstance(node, (ast.Assert, ast.Import, ast.ImportFrom))
        and (
            (
                isinstance(node, ast.Import)
                and any(item.name.startswith("cells") for item in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("cells"))
        )
        for node in ast.walk(reference)
    )
    assert dataclass_fields(core, "Request") == required_keys(reference, "evidence", "request")
    assert dataclass_fields(core, "GeometryPreparation") == required_keys(
        reference, "verify", "prepared"
    )
    assert dataclass_fields(core, "PhysicalPreparation") == required_keys(
        reference, "physical_fields", "admitted"
    )
    assert returned_dict_keys(function(core, "_conservation")) == returned_dict_keys(
        function(reference, "conservation")
    )
    assert assigned_dict_keys(function(core, "prepare"), "provenance") == returned_dict_keys(
        function(reference, "geometry_provenance")
    )
    assert assigned_dict_keys(
        function(core, "prepare_physical"), "provenance"
    ) == returned_dict_keys(function(reference, "physical_provenance"))
    domains = json.loads((project / DOMAINS).read_text())
    assert (
        len(domains["cases"]) == 2 and domains["missing_lattice_caller_envelopes_resolved"] is False
    )
    assert domains["constructor_proposal_domains_automatically_selected"] is False
    assert set(row["retained_source_case"] for row in domains["cases"]) == {
        "irregular-centroid-aux",
        "native-single-preset-seed17",
    }
    assert "stable_seed_control_volumes_fixtures" not in (project / FIXTURES).read_text()
    assert "proposed_domain" not in (project / FIXTURES).read_text()
    return dict(
        kind="cells.fixed_seed_control_volume_physical_bridge_static_correspondence@1",
        constructor_manifest_sha256=CONSTRUCTOR_MANIFEST_SHA256,
        polygon_manifest_sha256=POLYGON_MANIFEST_SHA256,
        constructor_source_review_sha256=sha(REVIEW),
        bridge_schema_repair_review_sha256=REPAIR_REVIEW_SHA256,
        bridge_schema_promotion_sha256=PROMOTION_SHA256,
        effective_repaired_source_sha256={
            REFERENCE: REPAIRED_REFERENCE_SHA256,
            TEST: REPAIRED_TEST_SHA256,
        },
        schema_repair_qualification_inherited=False,
        schema_guards={
            name: site(REFERENCE, function(reference, name))
            for name in ("complete_vector_axes", "complete_permeability_species")
        },
        source_scope_correction=scope,
        reused_physical_source_pins=literal(core, "SOURCE_PINS"),
        complete_source_only_inventory=inventory(project),
        coordinate_authority=(
            "validated constructor shared binary64 coordinates and directed rings; "
            "no cached metric input"
        ),
        production_sites={
            name: site(CORE, function(core, name))
            for name in (
                "_constructor_evidence_fields",
                "_declaration",
                "bind",
                "polygon_input",
                "_owner_maps",
                "_conservation",
                "prepare",
                "prepare_physical",
                "require_cached_operators",
            )
        },
        independent_sites={
            name: site(REFERENCE, function(reference, name))
            for name in (
                "evidence",
                "declaration",
                "topology",
                "conservation",
                "geometry_fields",
                "physical_fields",
                "verify",
                "evaluate",
            )
        },
        complete_preparation_and_provenance_field_inventories_match=True,
        conservation=(
            "exact declared-domain extrusion and incidence; rounded normal-area defects "
            "retained with independently derived bounds"
        ),
        boundary_translation=(
            "previous/current to current/next, numeric to lexical edge axes, "
            "caller-declared None-to-self boundary partners"
        ),
        reference_closure=reference_closure(project),
        preparation=dict(
            source_AST_only=True,
            production_imports=0,
            scientific_imports=0,
            geometry_evaluations=0,
            reference_evaluations=0,
            fixture_executions=0,
            collection=0,
            test_runs=0,
            numerical_jobs=0,
            GPU_jobs=0,
            shared_status_edited=False,
            existing_metric_operator_and_core_files_edited=False,
            source_review_does_not_authorize_launch=True,
        ),
    )
